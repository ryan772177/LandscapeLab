"""save_foliage_actors.py — write the corrected foliage COMPONENTS to disk.

WHY THIS IS A SEPARATE, DELIBERATE STEP
    Setting collision on a `UFoliageType` asset is not enough to make
    anything collide at runtime, and the gap is invisible to every
    asset-level check.

    `FFoliageStaticMesh::UpdateComponentSettings` copies the foliage type's
    BodyInstance onto the component (InstancedFoliage.cpp:1822) and runs at
    LOAD. So after an editor restart the in-memory components are correct
    -- and the load-time fixup does NOT mark their packages dirty.
    Measured 2026-08-16: `get_dirty_content_packages()` returns **0** with
    1,093 InstancedFoliageActors holding corrected components.

    The external actor packages on disk therefore still carry the OLD
    serialized BodyInstance. World Partition streams from those packages,
    so PIE gets the old value. Measured, same session:

        editor world components   QUERY_ONLY  FoliageBlockQueryOnly  BLOCK
        PIE world components      NO_COLLISION  NoCollision          IGNORE

    A normal save writes nothing here, because nothing is dirty. This tool
    therefore saves with **only_dirty=False**, which is the whole point of
    it existing rather than calling save_dirty_packages.

SCOPE IS DELIBERATELY NARROW
    Only packages owning an InstancedFoliageActor are touched. The
    landscape, the lighting and every other actor are left alone, so a
    failure here cannot damage anything outside foliage.

VERIFY FROM THE ARTEFACT, NOT FROM THIS TOOL
    `save_level` in this project has reported failure on a save that
    SUCCEEDED, because a large reply exceeded the remote-exec
    deserialization limit. This tool keeps its reply tiny for that reason,
    and still prints the instruction to check `git status`: the filesystem
    is the evidence, not the return value.

Exit codes:
    0  saved, and the editor reported success
    1  could not look
    2  bad arguments / nothing to save
    3  rule 7: no verified editor node
    5  the editor reported a save failure
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap        # noqa: E402
import resource_guard   # noqa: E402
import ue_exec          # noqa: E402

PAYLOAD = r'''
import json as _json
import unreal as _u

BATCH = __BATCH__
APPLY = __APPLY__

_out = {"ok": False, "error": None, "ifa_count": 0, "packages": 0,
        "batches": 0, "saved_ok": 0, "batch_failures": [],
        "dirty_before": None, "dirty_after": None}
try:
    _out["dirty_before"] = len(
        _u.EditorLoadingAndSavingUtils.get_dirty_content_packages())

    sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    seen = {}
    n = 0
    for a in sub.get_all_level_actors():
        if not isinstance(a, _u.InstancedFoliageActor):
            continue
        n += 1
        try:
            p = a.get_package()
        except Exception:
            p = None
        if p is not None:
            seen[p.get_path_name()] = p
    _out["ifa_count"] = n
    pkgs = list(seen.values())
    _out["packages"] = len(pkgs)

    if APPLY and pkgs:
        for i in range(0, len(pkgs), BATCH):
            chunk = pkgs[i:i + BATCH]
            _out["batches"] += 1
            # only_dirty=False. Nothing is dirty -- the load-time fixup
            # that corrected these components did not mark them -- so a
            # dirty-only save is a no-op that reports success.
            ok = _u.EditorLoadingAndSavingUtils.save_packages(chunk, False)
            if ok:
                _out["saved_ok"] += len(chunk)
            else:
                _out["batch_failures"].append(
                    {"first": i, "count": len(chunk)})

    _out["dirty_after"] = len(
        _u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true",
                    help="actually save; without it this only counts")
    ap.add_argument("--batch", type=int, default=250)
    ap.add_argument("--timeout", type=float, default=25.0,
                    help="node DISCOVERY window, not the execution budget")
    args = ap.parse_args(argv)

    # resource_guard has NO free_gb — the hasattr guard was ALWAYS False,
    # so this rule-5 RAM line never printed while the source read as
    # though it did (Pass 3 2026-09-16 F5). The real API is
    # available_gb() -> (avail, total); a None reads as could-not-look,
    # never as a number.
    _free, _total = resource_guard.available_gb()
    if _free is not None:
        print("free RAM: %.1f GB of %.1f GB (pipeline rule 5)"
              % (_free, _total))
    else:
        print("free RAM: COULD NOT BE READ (pipeline rule 5) -- not "
              "'memory is fine'")

    payload = (PAYLOAD.replace("__BATCH__", str(int(args.batch)))
                      .replace("__APPLY__", "True" if args.go else "False"))
    rc, d, _ = ue_exec.run(payload, timeout=args.timeout,
                           stage_name="save_foliage_actors")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: no result. The save may still have run — "
              "check `git status` before concluding anything.")
        return 1
    if d.get("error"):
        print("PAYLOAD ERROR:\n" + d["error"])
        return 1

    print("InstancedFoliageActors : %d" % d["ifa_count"])
    print("owning packages        : %d" % d["packages"])
    print("dirty before / after   : %s / %s"
          % (d["dirty_before"], d["dirty_after"]))
    if not args.go:
        print("\nCOUNT ONLY — nothing written. Re-run with --go.")
        return 0 if d["packages"] else 2
    print("batches                : %d" % d["batches"])
    print("packages reported saved: %d" % d["saved_ok"])
    if d["batch_failures"]:
        print("BATCH FAILURES        : %s" % d["batch_failures"])
    print()
    print("NOW CHECK THE ARTEFACT, not this output:")
    print("    git status --short LandscapeLab/Content/__ExternalActors__")
    print("A save in this project has reported failure on a save that "
          "succeeded, and success on one that wrote nothing.")
    return 5 if d["batch_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
