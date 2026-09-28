"""read_grass_type.py — what a LandscapeGrassType actually holds, from disk.

WHY
---
`make_landscape_material.py` builds grass types and reports what it set.
B-BUILD-UNKNOWN is open on that builder: it can report catastrophe over a
graph that is fine, and a truncated transport reply is indistinguishable
from a mid-build death. So its report is not the artefact.

More specifically, D3 rests on a claim the connectivity and sampler audits
cannot see: that each blueberry variety carries a WIND-OFF material
override. `GrassVariety.override_materials` (PythonStub :121628) is the only
place that can be true, and nothing else reads it.

This asks the SAVED asset. It shares no code with the builder.

Exit codes:
  0  read, and every declared expectation met
  2  bad arguments
  3  editor gate refused (conduct rule 7)
  4  an expectation failed
  5  could not look
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MARKER = "__LANDSCAPELAB_GRASSTYPE__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"path": {path!r}, "ok": False, "error": None, "varieties": []}}
try:
    _p = {path!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["error"] = "asset does not exist"
    else:
        _gt = _unreal.EditorAssetLibrary.load_asset(_p)
        if _gt is None:
            _out["error"] = "load_asset returned None"
        else:
            _out["asset_class"] = type(_gt).__name__
            for _v in (_gt.get_editor_property("grass_varieties") or []):
                _m = _v.get_editor_property("grass_mesh")
                _d = _v.get_editor_property("grass_density")
                _d = float(_d.get_editor_property("default")
                           if hasattr(_d, "get_editor_property") else _d)
                _e = _v.get_editor_property("end_cull_distance")
                _e = int(_e.get_editor_property("default")
                         if hasattr(_e, "get_editor_property") else _e)
                _ov = _v.get_editor_property("override_materials") or []
                _out["varieties"].append({{
                    "mesh": _m.get_path_name().split(".")[0] if _m else None,
                    "density": round(_d, 5),
                    "end_cull_cm": _e,
                    "override_materials": [
                        _x.get_path_name().split(".")[0] if _x else None
                        for _x in _ov],
                }})
            _out["ok"] = True
except Exception as _exc:
    _out["error"] = str(_exc)[:300]

print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asset", required=True,
                    help="/Game path to a LandscapeGrassType.")
    ap.add_argument("--expect-varieties", type=int, default=0)
    ap.add_argument("--expect-all-overridden", action="store_true",
                    help="REFUSE unless every variety carries at least one "
                         "override material.")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args(argv)

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(PAYLOAD.format(path=args.asset, marker=MARKER),
                               unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r) if r else ""
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    i = (text or "").find(MARKER)
    if i < 0:
        print("REFUSE: no marker — I could not look.")
        return 5
    try:
        got, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    except ValueError:
        print("REFUSE: unparseable result.")
        return 5
    if not got.get("ok"):
        print("REFUSE: {0}".format(got.get("error")))
        return 5

    print("{0}  [{1}]".format(got["path"], got.get("asset_class")))
    print("")
    rc = 0
    total = 0.0
    for v in got["varieties"]:
        total += v["density"]
        mesh = (v["mesh"] or "?").rsplit("/", 1)[-1]
        ovr = v["override_materials"]
        print("  {0:<26} {1:>7.3f} /10m2   cull {2:>7} cm   overrides: {3}"
              .format(mesh, v["density"], v["end_cull_cm"],
                      ", ".join(o.rsplit("/", 1)[-1] for o in ovr)
                      if ovr else "NONE"))
        if args.expect_all_overridden and not ovr:
            rc = 4
    print("")
    print("  {0} variety(ies), densities sum to {1}".format(
        len(got["varieties"]), round(total, 5)))

    if args.expect_varieties and len(got["varieties"]) != args.expect_varieties:
        print("REFUSE: expected {0} varieties, read {1}".format(
            args.expect_varieties, len(got["varieties"])))
        rc = 4
    if args.expect_all_overridden and rc == 4:
        print("REFUSE: at least one variety carries NO override material. "
              "That variety renders with the VENDOR material — for the "
              "blueberry understory that means wind ON, which is the thing "
              "the overrides exist to prevent.")
    elif args.expect_all_overridden:
        print("Every variety carries an override material, read from the "
              "SAVED asset by an instrument that shares no code with the "
              "builder.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
