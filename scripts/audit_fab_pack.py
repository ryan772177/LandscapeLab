"""audit_fab_pack.py — CHUNKED intake audit for a native Fab pack.

Native packs ship materials ALREADY WIRED, so R-ASSET's FAB-PLUGIN branch
says VERIFY, do not rebuild. This is that verification.

WHY CHUNKED (R8 amendment, 2026-08-03). The single-shot version was
fired at KiteDemo — 270 uassets across 6,527 MB — on a host with 1.8 GB
free RAM. It never returned: the client died with a 0-byte output, the
editor's working set had been paged down to 0.15 GB, and NOTHING was
recoverable. An over-memory workload on this hardware does not fail
loudly; it dissolves.

So the unit of work is a CHUNK of ~30 assets, and every chunk APPENDS to
a results file before the next begins. A saturated editor now costs one
chunk, not the whole audit. Re-running resumes automatically from what is
already recorded.

WHAT IT CHECKS
  meshes      bounds in CM, triangles, LODs, Nanite enabled, collision
  materials   THE SAMPLER AUDIT — every TextureSample's sampler_type must
              agree with its texture's compression_settings. A mismatch
              is SILENT: it compiles, binds, renders, and is wrong.

CONTROL GROUP. KiteDemo is native Epic content and SHOULD pass clean.
If the audit flags KiteDemo, suspect the audit before suspecting Epic.

READ-ONLY. Spawns nothing, mutates nothing, saves nothing.

Usage:
    python scripts/audit_fab_pack.py KiteDemo --list      # enumerate only
    python scripts/audit_fab_pack.py KiteDemo             # next chunk
    python scripts/audit_fab_pack.py KiteDemo --all       # chunk to done
    python scripts/audit_fab_pack.py KiteDemo --report    # summarise
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(REPO, "Free", "_measured")

MARK_LIST = "__LL_FABLIST__"
MARK_CHUNK = "__LL_FABCHUNK__"

# Enumerate only. Deliberately does NOT load assets -- listing is cheap,
# loading is what saturates.
LIST_PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {{}}
_ral = _unreal.EditorAssetLibrary
try:
    _all = list(_ral.list_assets("{root}", recursive=True))
except Exception as _e:
    _all = []
    _out["error"] = str(_e)[:160]
_rows = []
for _a in _all:
    _p = _a.split(".")[0]
    try:
        _c = str(_ral.find_asset_data(_p).asset_class_path.asset_name)
    except Exception:
        _c = "?"
    _rows.append([_p, _c])
_out["assets"] = _rows
print("{marker}" + _json.dumps(_out))
'''

CHUNK_PAYLOAD = r'''
import json as _json
import unreal as _unreal

_TARGETS = _json.loads({targets!r})
_out = {{"meshes": [], "sampler_findings": [], "checked": 0, "skipped": 0}}
_ral = _unreal.EditorAssetLibrary
_mel = _unreal.MaterialEditingLibrary

_EXPECT = {{
    "TC_NORMALMAP": ["SAMPLERTYPE_NORMAL"],
    "TC_MASKS": ["SAMPLERTYPE_MASKS", "SAMPLERTYPE_LINEAR_COLOR",
                 "SAMPLERTYPE_LINEAR_GREYSCALE"],
    "TC_ALPHA": ["SAMPLERTYPE_ALPHA", "SAMPLERTYPE_LINEAR_GREYSCALE"],
    "TC_GRAYSCALE": ["SAMPLERTYPE_GREYSCALE", "SAMPLERTYPE_LINEAR_GREYSCALE"],
    "TC_DEFAULT": ["SAMPLERTYPE_COLOR", "SAMPLERTYPE_LINEAR_COLOR"],
    "TC_BC7": ["SAMPLERTYPE_COLOR", "SAMPLERTYPE_LINEAR_COLOR"],
}}

def _err(_e):
    return "{{0}}: {{1}}".format(type(_e).__name__, str(_e)[:120])

for _p, _cls in _TARGETS:
    if _cls == "StaticMesh":
        _m = _ral.load_asset(_p)
        if _m is None:
            _out["meshes"].append({{"asset": _p, "error": "load failed"}})
            continue
        _r = {{"asset": _p}}
        try:
            _b = _m.get_bounds().box_extent
            _r["extent_cm"] = [round(float(_b.x) * 2, 1),
                               round(float(_b.y) * 2, 1),
                               round(float(_b.z) * 2, 1)]
        except Exception as _e:
            _r["extent_cm"] = _err(_e)
        for _k, _fn in (("lods", lambda: int(_m.get_num_lods())),
                        ("tris", lambda: int(_m.get_num_triangles(0))),
                        ("sections", lambda: int(_m.get_num_sections(0)))):
            try:
                _r[_k] = _fn()
            except Exception as _e:
                _r[_k] = _err(_e)
        try:
            _ns = _m.get_editor_property("nanite_settings")
            _r["nanite"] = bool(_ns.get_editor_property("enabled"))
        except Exception as _e:
            _r["nanite"] = _err(_e)
        try:
            _bs = _m.get_editor_property("body_setup")
            _n = 0
            if _bs is not None:
                _ag = _bs.get_editor_property("agg_geom")
                for _f in ("convex_elems", "box_elems", "sphere_elems",
                           "sphyl_elems"):
                    try:
                        _n += len(_ag.get_editor_property(_f))
                    except Exception:
                        pass
            _r["collision"] = _n
        except Exception as _e:
            _r["collision"] = _err(_e)
        _out["meshes"].append(_r)

    elif _cls in ("Material", "MaterialInstanceConstant"):
        _m = _ral.load_asset(_p)
        if _m is None:
            _out["skipped"] += 1
            continue
        try:
            _exprs = list(_mel.get_material_expressions(_m))
        except Exception:
            _out["skipped"] += 1
            continue
        for _e in _exprs:
            if type(_e).__name__ != "MaterialExpressionTextureSample":
                continue
            try:
                _t = _e.get_editor_property("texture")
                if _t is None:
                    continue
                _cs = str(_t.get_editor_property("compression_settings"))
                _st = str(_e.get_editor_property("sampler_type"))
                _csn = _cs.split(".")[-1].split(":")[0].strip()
                _stn = _st.split(".")[-1].split(":")[0].strip()
                _out["checked"] += 1
                _ok = _EXPECT.get(_csn)
                if _ok is not None and _stn not in _ok:
                    _out["sampler_findings"].append({{
                        "material": _p, "texture": _t.get_path_name(),
                        "compression": _csn, "sampler": _stn,
                        "expected_one_of": _ok}})
            except Exception:
                _out["skipped"] += 1

print("{marker}" + _json.dumps(_out))
'''


def _state_path(pack):
    return os.path.join(OUTDIR, "fab_audit_{0}.json".format(pack))


def _load_state(pack):
    p = _state_path(pack)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return {"pack": pack, "assets": [], "done": [], "meshes": [],
            "sampler_findings": [], "checked": 0, "skipped": 0,
            "chunk_runtimes_s": []}


def _save_state(pack, st):
    os.makedirs(OUTDIR, exist_ok=True)
    with open(_state_path(pack), "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, sort_keys=True)


def _run(src, timeout, marker):
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, why = verify_landscape._select_verified_node(
            remote_exec, remote,
            bootstrap._norm(bootstrap.UE_PROJECT_ROOT), timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(why))
            return None
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(src, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("command failed: {0}".format((r or {}).get("result")))
            return None
        for line in bootstrap._collect_output(r).splitlines():
            if line.startswith(marker):
                return json.loads(line[len(marker):])
        print("no marker in output")
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack")
    ap.add_argument("--chunk", type=int, default=30)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    pack = args.pack.strip("/")
    st = _load_state(pack)

    if args.report:
        return _report(st)

    if args.list or not st["assets"]:
        src = LIST_PAYLOAD.format(root="/Game/" + pack, marker=MARK_LIST)
        d = _run(src, args.timeout, MARK_LIST)
        if d is None:
            return 4
        st["assets"] = d.get("assets", [])
        _save_state(pack, st)
        kinds = {}
        for _p, c in st["assets"]:
            kinds[c] = kinds.get(c, 0) + 1
        print("{0}: {1} assets".format(pack, len(st["assets"])))
        for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:10]:
            print("   {0:<28} {1}".format(k, v))
        if args.list:
            return 0

    auditable = [a for a in st["assets"]
                 if a[1] in ("StaticMesh", "Material",
                             "MaterialInstanceConstant")]
    done = set(st["done"])
    todo = [a for a in auditable if a[0] not in done]
    print("auditable {0}, done {1}, remaining {2}".format(
        len(auditable), len(done), len(todo)))

    rounds = 0
    while todo:
        batch = todo[:args.chunk]
        t0 = time.time()
        src = CHUNK_PAYLOAD.format(targets=json.dumps(batch),
                                   marker=MARK_CHUNK)
        d = _run(src, args.timeout, MARK_CHUNK)
        dt = time.time() - t0
        if d is None:
            print("CHUNK FAILED after {0:.0f}s — {1} asset(s) already "
                  "recorded survive. Re-run to resume.".format(dt, len(done)))
            _save_state(pack, st)
            return 5
        st["meshes"].extend(d.get("meshes", []))
        st["sampler_findings"].extend(d.get("sampler_findings", []))
        st["checked"] += d.get("checked", 0)
        st["skipped"] += d.get("skipped", 0)
        st["done"].extend([b[0] for b in batch])
        st["chunk_runtimes_s"].append(round(dt, 1))
        _save_state(pack, st)
        done = set(st["done"])
        todo = [a for a in auditable if a[0] not in done]
        rounds += 1
        print("  chunk {0}: {1} assets in {2:.0f}s   ({3} left)".format(
            rounds, len(batch), dt, len(todo)))
        if not args.all:
            break

    return _report(st)


def _report(st):
    print("")
    print("=" * 66)
    print("PACK {0}".format(st["pack"]))
    print("  audited {0} / {1} auditable".format(
        len(st["done"]),
        len([a for a in st["assets"] if a[1] in
             ("StaticMesh", "Material", "MaterialInstanceConstant")])))
    rt = st.get("chunk_runtimes_s") or []
    if rt:
        print("  chunk runtimes: {0}  (total {1:.0f}s, mean {2:.0f}s)".format(
            ", ".join("{0:.0f}".format(x) for x in rt[:10]),
            sum(rt), sum(rt) / len(rt)))
    ms = [m for m in st["meshes"] if "error" not in m]
    print("")
    print("MESHES: {0}".format(len(ms)))
    non = [m for m in ms if m.get("nanite") is False]
    on = [m for m in ms if m.get("nanite") is True]
    print("  Nanite ON {0} / OFF {1}".format(len(on), len(non)))
    if non:
        print("  Nanite OFF (tier ruling wants it ON):")
        for m in non[:12]:
            print("     {0}".format(m["asset"].split("/")[-1]))
    tri = [m["tris"] for m in ms if isinstance(m.get("tris"), int)]
    if tri:
        print("  triangles: min {0:,} max {1:,} total {2:,}".format(
            min(tri), max(tri), sum(tri)))
    ext = [m for m in ms if isinstance(m.get("extent_cm"), list)]
    if ext:
        big = max(ext, key=lambda m: max(m["extent_cm"]))
        small = min(ext, key=lambda m: max(m["extent_cm"]))
        print("  largest  {0}  {1} cm".format(
            big["asset"].split("/")[-1], big["extent_cm"]))
        print("  smallest {0}  {1} cm".format(
            small["asset"].split("/")[-1], small["extent_cm"]))
    print("")
    f = st["sampler_findings"]
    print("SAMPLER AUDIT — {0} checked, {1} skipped".format(
        st["checked"], st["skipped"]))
    if not f:
        print("  CLEAN — every sampler_type agrees with its texture's "
              "compression_settings.")
    else:
        print("  {0} MISMATCH(ES):".format(len(f)))
        seen = {}
        for x in f:
            k = (x["compression"], x["sampler"])
            seen[k] = seen.get(k, 0) + 1
        for (c, s), n in sorted(seen.items(), key=lambda i: -i[1]):
            print("     {0:<16} sampled as {1:<28} x{2}".format(c, s, n))
        print("")
        print("  IF THIS IS THE CONTROL PACK (KiteDemo, native Epic "
              "content),")
        print("  SUSPECT THE AUDIT FIRST — a false positive here means the")
        print("  expectation table is wrong, not Epic.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
