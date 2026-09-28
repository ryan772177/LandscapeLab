"""audit_fab_registry.py — intake audit via the ASSET REGISTRY, no loading.

WHY THIS EXISTS INSTEAD OF audit_fab_pack.py.

The load-based audit hung the editor for 20+ minutes and returned
nothing. The editor log gave the cause:

    LogTexture: Building texture ... (TFO_AutoDXT, 8192x8192)
      (Required Memory Estimate: 4608.999984 MB)

**`load_asset` is not a read.** Native Fab packs ship without DDC-cooked
data for the local cache, so the FIRST load COOKS the asset — and
KiteDemo carries 8192x8192 textures wanting ~4.6 GB to encode, against
1.8 GB free on this host. Chunking by item count could not save it: a
chunk of ONE would still have hung.

THE ASSET REGISTRY ANSWERS MOST OF IT WITHOUT LOADING ANYTHING.
`find_asset_data` returns an FAssetData whose TAGS are populated at scan
time and carry, for static meshes, things like triangle counts, LOD
counts, material slot counts, Nanite state and bounds; and for textures,
dimensions and compression settings. Reading tags touches no bulk data
and cooks nothing.

WHAT THIS CANNOT DO, stated plainly rather than glossed:
the sampler audit needs the material GRAPH, which the registry does not
expose. That check still requires loading, so it is a separate, opt-in
pass over MATERIALS ONLY (far cheaper than textures — a material asset
is small; it is the 8K TEXTURES that cook). Even then it is chunked and
resumable.

READ-ONLY, and this time that claim is about what it makes the ENGINE do.

Usage:
    python scripts/audit_fab_registry.py KiteDemo
    python scripts/audit_fab_registry.py KiteDemo --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(REPO, "Free", "_measured")
MARKER = "__LL_REG__"

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_ROOT = "{root}"
_out = {{"root": _ROOT, "assets": [], "tag_error": None}}

_ar = _unreal.AssetRegistryHelpers.get_asset_registry()

# Wait for the registry scan rather than racing it -- an incomplete scan
# would under-report and look like an empty pack.
try:
    _ar.wait_for_completion()
    _out["registry_ready"] = True
except Exception as _e:
    _out["registry_ready"] = "wait failed: " + str(_e)[:100]

try:
    _datas = _ar.get_assets_by_path(_ROOT, recursive=True)
except Exception as _e:
    _datas = []
    _out["tag_error"] = str(_e)[:160]

def _tag(_d, _n):
    """Read a registry TAG. Touches no bulk data, cooks nothing."""
    try:
        _v = _d.get_tag_value(_n)
        return None if _v is None else str(_v)
    except Exception:
        return None

for _d in _datas:
    try:
        _cls = str(_d.asset_class_path.asset_name)
    except Exception:
        _cls = "?"
    _row = {{
        "path": str(_d.package_name),
        "name": str(_d.asset_name),
        "class": _cls,
    }}
    # Names differ by class; collect broadly and let the host sort it out.
    for _k in ("Triangles", "Vertices", "LODs", "MinLOD", "Materials",
               "NaniteEnabled", "ApproxSize", "CollisionPrims",
               "PhysicsTriMeshData", "Dimensions", "Format",
               "CompressionSettings", "SizeX", "SizeY", "AddressX",
               "HasAlphaChannel", "SourceFileHash"):
        _v = _tag(_d, _k)
        if _v is not None:
            _row[_k] = _v
    _out["assets"].append(_row)

_out["count"] = len(_out["assets"])
print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    pack = args.pack.strip("/")
    src = PAYLOAD.format(root="/Game/" + pack, marker=MARKER)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, why = verify_landscape._select_verified_node(
            remote_exec, remote,
            bootstrap._norm(bootstrap.UE_PROJECT_ROOT), args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(why))
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(src, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("command failed: {0}".format((r or {}).get("result")))
            return 4
        for line in bootstrap._collect_output(r).splitlines():
            if line.startswith(MARKER):
                d = json.loads(line[len(MARKER):])
                os.makedirs(OUTDIR, exist_ok=True)
                out = os.path.join(OUTDIR,
                                   "fab_registry_{0}.json".format(pack))
                with open(out, "w", encoding="utf-8") as fh:
                    json.dump(d, fh, indent=1, sort_keys=True)
                _report(d, pack, out)
                return 0
        print("no marker in output")
        return 4
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()


def _report(d, pack, out):
    print("PACK {0}   registry_ready={1}   {2} assets".format(
        pack, d.get("registry_ready"), d.get("count")))
    if d.get("tag_error"):
        print("  TAG ERROR: {0}".format(d["tag_error"]))
    kinds = {}
    for a in d["assets"]:
        kinds[a["class"]] = kinds.get(a["class"], 0) + 1
    print("")
    print("by class:")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print("   {0:<32} {1}".format(k, v))

    meshes = [a for a in d["assets"] if a["class"] == "StaticMesh"]
    print("")
    print("STATIC MESHES: {0}".format(len(meshes)))
    # Which tags actually came back? Report that honestly -- a tag the
    # registry does not carry is "could not read", not "absent".
    tags = {}
    for m in meshes:
        for k in m:
            if k not in ("path", "name", "class"):
                tags[k] = tags.get(k, 0) + 1
    if tags:
        print("  tags available on meshes:")
        for k, v in sorted(tags.items(), key=lambda x: -x[1]):
            print("     {0:<24} present on {1}/{2}".format(k, v, len(meshes)))
    else:
        print("  NO TAGS RETURNED — the registry carries none of the "
              "requested keys for\n  StaticMesh in 5.8. This is 'could not "
              "read', not 'absent'. The load-based\n  audit is then the only "
              "instrument, and must be cost-budgeted.")

    nan = [m for m in meshes if m.get("NaniteEnabled")]
    if nan:
        on = sum(1 for m in nan if m["NaniteEnabled"].lower()
                 in ("true", "1"))
        print("  Nanite: ON {0} / OFF {1} (from registry tag)".format(
            on, len(nan) - on))

    tex = [a for a in d["assets"] if a["class"] == "Texture2D"]
    print("")
    print("TEXTURES: {0}".format(len(tex)))
    big = [t for t in tex if t.get("Dimensions")]
    if big:
        print("  sample dimensions: {0}".format(
            ", ".join(sorted({t["Dimensions"] for t in big})[:8])))
    print("")
    print("wrote {0}".format(os.path.relpath(out, REPO)))
    print("")
    print("NOTE: the sampler audit needs the material GRAPH, which the")
    print("registry does not expose. That remains a separate, chunked,")
    print("MATERIALS-ONLY pass — materials are small; it is the 8K")
    print("TEXTURES that cook and that hung the previous attempt.")


if __name__ == "__main__":
    raise SystemExit(main())
