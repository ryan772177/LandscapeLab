"""measure_palette_live.py — measure the palette from LOADED meshes.

READ-ONLY on assets: it loads meshes and reads their reflected
properties. It writes ONE new measurement file under `Free/_measured/`
and never edits `recipes/alpine.json`.

WHY THIS EXISTS
---------------
Pass 0 is "Verification + alpine palette" and the audit graded it
OPTIMISTIC because the verification half has zero instances: 38 entries,
all `verified: false`, and the `measured` block comes from a REGISTRY TAG
SCAN taken with **zero assets loaded**. Two of its fields are known to be
wrong or empty:

  * `measured.material_slots` — contradicted on 8 of the 13 meshes an
    independent instrument covered (palette says 4/3/2/2/4/5/12/4 where
    the loaded mesh says 1). The vendor packages serialize a STALE TAG;
    `StaticMesh.cpp:6319` defines the real value as
    `GetStaticMaterials().Num()`. The audit's ruling was blunt: **do not
    consume that field.**
  * `measured.nanite` — "UNKNOWN — registry tag absent" on all 38.
    **Absent is not OFF** (non-negotiable 17 in its purest form: the tag
    records what was written, not what is in effect).

This asks the LOADED MESH instead. Different representation, different
answer, and the disagreement is the finding.

THE SPLIT CONTRACT IS PRESERVED (schema v1.13): judgements live in
`recipes/alpine_palette_curation.json`, measurements live under
`Free/_measured/`. This writes only a measurement file. Folding it into
the palette is `make_alpine_palette.py`'s job and a separate, deliberate
step — precedent: `Free/_measured/rock_pivots.json`, also loaded-mesh.

MEMORY IS A FIRST-CLASS FAILURE MODE HERE. Loading 38 vendor meshes on a
machine with ~2 GB free is exactly the "heavy operations run one at a
time" case (pipeline rule 5). One mesh per remote call, free RAM read
BEFORE each, and the run ABORTS at the floor and reports how many it
measured. **A partial measurement is declared, never silently short**
(non-negotiable 14).

Exit codes:
  0  every palette entry measured
  2  editor gate refused (rule 7), or bad arguments
  3  measured; DISAGREEMENTS with the recorded palette
  4  COULD NOT MEASURE anything
  5  PARTIAL — stopped at the memory floor; what was measured is written
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import resource_guard     # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_PALETTELIVE__"

# One mesh per call. Every accessor below is already proven on this
# editor by `measure_rock_meshes.py` — reused, not re-derived.
PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "exists": False, "ok": False, "error": None}}
try:
    _p = {path!r}
    if _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["exists"] = True
        _m = _unreal.EditorAssetLibrary.load_asset(_p)
        _out["class"] = type(_m).__name__
        if isinstance(_m, _unreal.StaticMesh):
            try:
                _ns = _m.get_editor_property("nanite_settings")
                _out["nanite_enabled"] = bool(
                    _ns.get_editor_property("enabled"))
            except Exception as _ex:
                _out["nanite_enabled"] = None
                _out["nanite_error"] = str(_ex)[:120]
            try:
                _out["material_slots"] = len(_m.static_materials)
            except Exception as _ex:
                _out["material_slots"] = None
                _out["slots_error"] = str(_ex)[:120]
            try:
                _ss = _unreal.get_editor_subsystem(
                    _unreal.StaticMeshEditorSubsystem)
                _out["lod_count"] = int(_ss.get_lod_count(_m))
            except Exception as _ex:
                _out["lod_count"] = None
            try:
                _n = _out.get("lod_count") or 0
                _out["lod_triangles"] = [
                    int(_m.get_num_triangles(_i)) for _i in range(_n)]
                _out["triangles"] = (_out["lod_triangles"][0]
                                     if _out["lod_triangles"] else None)
            except Exception as _ex:
                _out["lod_triangles"] = None
                _out["triangles"] = None
            try:
                _b = _m.get_bounds()
                _e = _b.box_extent
                _out["dims_m"] = [round(float(_e.x) * 2.0 / 100.0, 2),
                                  round(float(_e.y) * 2.0 / 100.0, 2),
                                  round(float(_e.z) * 2.0 / 100.0, 2)]
            except Exception:
                _out["dims_m"] = None
            _out["ok"] = True
        else:
            _out["error"] = "not a StaticMesh"
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def _free_gb():
    """Free GB, or None if it could not be read.

    `resource_guard.available_gb()` returns a (avail, total) TUPLE and
    returns (None, None) on failure — deliberately, because "0 GB free"
    from a broken read would fire every run. So None here means I COULD
    NOT LOOK, and the caller must not treat it as either comfortable or
    exhausted (non-negotiable 6).
    """
    try:
        avail, _total = resource_guard.available_gb()
    except Exception:
        return None
    return None if avail is None else float(avail)


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default="recipes/alpine.json")
    ap.add_argument("--out", default=None,
                    help="measurement file to write under Free/_measured")
    ap.add_argument("--floor-gb", type=float, default=0.9,
                    help="abort before a load if free RAM is below this")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    rp = args.recipe if os.path.isabs(args.recipe) else os.path.join(
        bootstrap.REPO_ROOT, args.recipe)
    with open(rp, encoding="utf-8") as fh:
        recipe = json.load(fh)
    entries = ((recipe.get("palette") or {}).get("entries")) or []
    if not entries:
        print("REFUSE: recipe has no palette.entries")
        return 2
    if args.limit:
        entries = entries[:args.limit]

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("palette entries: {0}".format(len(entries)))
    _f0 = _free_gb()
    print("free RAM: {0}, floor {1:.2f} GB. One mesh per call; a partial "
          "run is DECLARED.".format(
              "{0:.2f} GB".format(_f0) if _f0 is not None
              else "COULD NOT READ", args.floor_gb))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    rows, stopped = [], None
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            for i, e in enumerate(entries):
                free = _free_gb()
                if free is None:
                    # Could not look. Loading vendor meshes blind on a
                    # 15.4 GB machine that is already paged out is the
                    # case the floor exists for, so this stops too — and
                    # it stops with a DIFFERENT reason than exhaustion.
                    stopped = "could not read free memory"
                    print("STOP at entry {0}/{1}: {2}".format(
                        i, len(entries), stopped))
                    break
                if free < args.floor_gb:
                    stopped = ("memory floor: {0:.2f} GB free < {1:.2f}"
                               .format(free, args.floor_gb))
                    print("STOP at entry {0}/{1}: {2}".format(
                        i, len(entries), stopped))
                    break
                r = remote.run_command(
                    PAYLOAD.format(path=e["path"], marker=MARKER),
                    unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                got = _parse(bootstrap._collect_output(r)) if r else None
                if got is None:
                    got = {"path": e["path"], "ok": False,
                           "error": "no parseable result"}
                got["id"] = e["id"]
                got["free_gb_before"] = round(free, 2)
                rows.append(got)
                print("  {0:<26s} {1:<5s} nanite {2!s:<6s} slots {3!s:<4s} "
                      "tris {4!s:<9s} free {5:.2f}GB".format(
                          e["id"][:26], "ok" if got.get("ok") else "FAIL",
                          got.get("nanite_enabled"),
                          got.get("material_slots"),
                          got.get("triangles"), free))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    ok = [r for r in rows if r.get("ok")]
    if not ok:
        print("")
        print("COULD NOT MEASURE: no mesh returned a reading.")
        return 4

    # ---- write the measurement file (measurements only, no judgement)
    out = args.out or os.path.join(
        bootstrap.REPO_ROOT, "Free", "_measured", "palette_live.json")
    if not os.path.isabs(out):
        out = os.path.join(bootstrap.REPO_ROOT, out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({
            "instrument": "scripts/measure_palette_live.py",
            "source": "LOADED StaticMesh reflected properties",
            "note": ("measurements only; contains no judgement. The "
                     "palette's own `measured` block comes from a "
                     "registry TAG scan with zero assets loaded, which "
                     "is a different representation and disagrees."),
            "measured": len(ok), "of_entries": len(entries),
            "partial_reason": stopped,
            "rows": rows,
        }, fh, indent=1)
    print("")
    print("wrote {0} ({1} of {2} entries)".format(out, len(ok), len(entries)))

    # ---- diff against the recorded palette ------------------------
    by_id = {e["id"]: e for e in entries}
    dis_slots, dis_tris, nanite_on, nanite_off, nanite_unread = \
        [], [], [], [], []
    for r in ok:
        rec = (by_id.get(r["id"], {}).get("measured") or {})
        rs, ls = rec.get("material_slots"), r.get("material_slots")
        if rs is not None and ls is not None and int(rs) != int(ls):
            dis_slots.append((r["id"], rs, ls))
        rt, lt = rec.get("triangles"), r.get("triangles")
        if rt is not None and lt is not None and int(rt) != int(lt):
            dis_tris.append((r["id"], rt, lt))
        ne = r.get("nanite_enabled")
        (nanite_on if ne is True else
         nanite_off if ne is False else nanite_unread).append(r["id"])

    print("")
    print("NANITE, from the reflected settings (the palette says "
          "'UNKNOWN — registry tag absent' for every entry):")
    print("  enabled  {0}".format(len(nanite_on)))
    print("  disabled {0}".format(len(nanite_off)))
    print("  COULD NOT READ {0}".format(len(nanite_unread)))
    if nanite_on:
        print("  ENABLED on: {0}".format(", ".join(sorted(nanite_on))))

    print("")
    print("material_slots: registry TAG vs LOADED mesh — {0} "
          "disagreement(s) of {1} compared".format(len(dis_slots), len(ok)))
    for pid, rs, ls in dis_slots:
        print("  {0:<28s} palette {1:<4} loaded {2}".format(pid, rs, ls))
    print("")
    print("triangles: registry TAG vs LOADED LOD0 — {0} disagreement(s)"
          .format(len(dis_tris)))
    for pid, rt, lt in dis_tris[:15]:
        print("  {0:<28s} palette {1:<9} loaded {2}".format(pid, rt, lt))

    print("")
    print("SOURCE: loaded StaticMesh properties. The palette's `measured`")
    print("block is a registry TAG scan taken with zero assets loaded —")
    print("a different representation, which is why this is evidence and")
    print("not a re-read of the same number.")
    print("This measures the ASSET. It does NOT spawn or render anything,")
    print("so it does not make any entry `verified` under the palette's")
    print("own policy — that still needs a spawn and a frame.")

    if stopped:
        print("")
        print("VERDICT: PARTIAL — {0}".format(stopped))
        return 5
    if dis_slots or dis_tris:
        print("")
        print("VERDICT: DISAGREEMENTS PRESENT ({0} slots, {1} triangles)."
              .format(len(dis_slots), len(dis_tris)))
        return 3
    print("")
    print("VERDICT: the loaded meshes agree with the recorded palette.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
