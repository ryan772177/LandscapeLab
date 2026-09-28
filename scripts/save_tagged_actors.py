"""save_tagged_actors.py — write actors the editor has corrected but not flagged.

THE CLASS THIS EXISTS FOR
-------------------------
An edit lands on an actor or a component, every read-back agrees, and
`get_dirty_content_packages()` returns **0**. A normal save then writes nothing
and reports success. The editor is right, the disk is stale, and no check that
reads the editor can see the difference — World Partition streams from the
packages, so PIE and a cold boot get the old value.

Measured instances in this project, all identical in shape:

    2026-08-16  foliage collision fixup   1,093 actors corrected, 0 dirty
    2026-08-17  navmesh SetConfig         corrected in memory, 0 dirty
    2026-08-27  DirectionalLight.affects_world  3 components set, 0 dirty
    2026-08-27  317 spawned EncounterMarkers    counted in world, 0 dirty,
                                                NOTHING on disk

**NON-NEGOTIABLE 4a: the fourth instance is the promotion, not another patch.**
`save_foliage_actors.py` is the earlier single-purpose copy of this and is
narrowed to `InstancedFoliageActor`; it should be folded into this tool, and
until it is, it is a declared duplicate rather than an accepted one.

HOW IT WORKS, AND WHY EACH PART IS LOAD-BEARING
-----------------------------------------------
- Select actors by TAG or by CLASS. Never by label — labels collide, and this
  project has two landscapes whose proxies carried identical ones.
- `EditorAssetSubsystem.set_dirty_flag(actor, True)` on each. `actor.modify()`
  alone is not enough when the change is on a COMPONENT, which is how the
  DirectionalLight case slipped through.
- `save_loaded_assets(actors, only_if_is_dirty=False)`. Passing True would
  reproduce, inside the fix, the exact defect the fix exists for.
- **THE VERDICT COMES FROM THE FILESYSTEM, NOT FROM THE EDITOR'S REPLY.** This
  project has had `save_level` report failure on a save that succeeded, because
  a large reply exceeded the remote-exec deserialization limit. So the reply is
  kept small and the tool prints, and can check, `git status`.

    python scripts/save_tagged_actors.py --tag LandscapeLab.Encounter
    python scripts/save_tagged_actors.py --class InstancedFoliageActor --go
    python scripts/save_tagged_actors.py --tag X --go --expect 317

`--expect N` REFUSES unless exactly N actors are selected. A save that silently
touches more packages than intended is how the city save swept the hero rig into
the world on 2026-08-24.

Exit codes:
    0  saved (or dry run completed)
    1  could not look
    2  bad arguments
    3  rule 7: no verified editor node
    4  the selection did not match --expect; nothing was written
    5  the editor reported the save failed
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT

PAYLOAD = r'''
import json as _json
import unreal as _unreal

TAG = __TAG__
CLS = __CLS__
GO = __GO__
EXPECT = __EXPECT__

_out = {"error": None, "selected": 0, "packages": [], "saved": None,
        "marked": 0, "refused": None, "go": GO}
try:
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _ass = _unreal.get_editor_subsystem(_unreal.EditorAssetSubsystem)
    _all = _eas.get_all_level_actors()

    _sel = []
    for _a in _all:
        if CLS is not None and type(_a).__name__ != CLS:
            continue
        if TAG is not None:
            try:
                _tags = [str(_t) for _t in _a.tags]
            except Exception:
                _tags = []
            if TAG not in _tags:
                continue
        _sel.append(_a)

    _out["selected"] = len(_sel)
    _pk = []
    for _a in _sel:
        try:
            _n = str(_a.get_outermost().get_name())
        except Exception:
            _n = "UNREADABLE"
        if _n not in _pk:
            _pk.append(_n)
    # Only a sample of package names comes back. The full list on a 317-actor
    # save is large enough to matter, and an oversized reply is how a
    # successful save has reported as a failure here before.
    _out["packages"] = _pk[:5]
    _out["package_count"] = len(_pk)

    if EXPECT is not None and len(_sel) != EXPECT:
        _out["refused"] = (
            "selected %d actors, --expect said %d. Nothing was written."
            % (len(_sel), EXPECT))
    elif not _sel:
        _out["refused"] = ("nothing matched the selector. That is NOT 'saved "
                           "everything' -- it is a selection that found no "
                           "actors, and it writes nothing.")
    elif GO:
        for _a in _sel:
            try:
                _a.modify()
            except Exception:
                pass
            if _ass.set_dirty_flag(_a, True):
                _out["marked"] += 1
        _out["saved"] = bool(_ass.save_loaded_assets(_sel, False))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_SAVETAG__" + _json.dumps(_out))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default=None,
                    help="actor tag to select on, e.g. LandscapeLab.Encounter")
    ap.add_argument("--class", dest="cls", default=None,
                    help="actor class NAME to select on, e.g. "
                         "InstancedFoliageActor")
    ap.add_argument("--expect", type=int, default=None,
                    help="REFUSE unless exactly this many actors are selected. "
                         "A save that touches more than intended is how the "
                         "hero rig was swept into the world on 2026-08-24.")
    ap.add_argument("--go", action="store_true",
                    help="actually save. Without it this is a dry run that "
                         "writes nothing.")
    args = ap.parse_args(argv)

    if not args.tag and not args.cls:
        print("REFUSE: give --tag or --class. Selecting EVERYTHING and saving "
              "it is not a scoped operation.")
        return 2

    payload = (PAYLOAD
               .replace("__TAG__", repr(args.tag))
               .replace("__CLS__", repr(args.cls))
               .replace("__GO__", repr(bool(args.go)))
               .replace("__EXPECT__", repr(args.expect)))
    before = _git_touched()

    # USE ue_exec.run RATHER THAN RE-DERIVING THE TRANSPORT. The first version
    # of this staged the payload as a .txt and got an EMPTY reply with no
    # error: MODE_EXEC_FILE hands the path to the engine's ExecuteFile, which
    # wants a real .py. ue_exec.py has staged payloads as .py since it was
    # written, and re-deriving that cost a debugging round for nothing.
    code, d, raw = ue_exec.run(payload, marker="__LL_SAVETAG__",
                               timeout=25.0, stage_name="ll_save_tagged",
                               quiet=True)
    if code == 3:
        return 3
    if d is None:
        print("NO MARKER. The editor did not report. That is 'could not look',")
        print("not 'nothing was saved' -- check git status before assuming.")
        print(raw[:1500])
        return 1

    print("selector      %s"
          % (("tag %s" % args.tag) if args.tag else ("class %s" % args.cls)))
    print("selected      %d actors in %d packages"
          % (d["selected"], d.get("package_count", 0)))
    for p in d.get("packages", []):
        print("                %s" % p)
    if d.get("package_count", 0) > 5:
        print("                ... and %d more"
              % (d["package_count"] - 5))
    if d.get("error"):
        print("ERROR         %s" % d["error"])
        return 1
    if d.get("refused"):
        print("")
        print("REFUSED: %s" % d["refused"])
        return 4
    if not args.go:
        print("")
        print("DRY RUN — nothing written. Pass --go.")
        return 0

    print("marked dirty  %d" % d["marked"])
    print("editor says   saved=%s" % d["saved"])

    # THE VERDICT. The editor's reply is one instrument; the filesystem is a
    # different representation and it is the one that decides.
    after = _git_touched()
    if before is None or after is None:
        print("")
        print("COULD NOT READ THE FILESYSTEM (git status failed), so whether")
        print("anything reached disk is UNKNOWN. The editor's own reply is not")
        print("sufficient here — that is the whole premise of this tool.")
        return 5
    delta = after - before
    print("")
    print("FILESYSTEM    %d package files changed or added under Content/"
          % len(delta))
    for p in sorted(delta)[:5]:
        print("                %s" % p)
    if len(delta) > 5:
        print("                ... and %d more" % (len(delta) - 5))
    if not delta:
        print("")
        print("!! THE EDITOR REPORTED A SAVE AND THE FILESYSTEM DID NOT MOVE.")
        print("That is the exact defect this tool exists for, occurring inside")
        print("the tool. Do not record this as saved.")
        return 5
    if d.get("saved") is False:
        print("")
        print("The editor reported failure but files DID change. Treat as")
        print("UNKNOWN and inspect; a large reply has misreported a good save")
        print("in this project before.")
        return 5
    return 0


def _git_touched():
    """Paths git sees as changed or untracked under the project Content dir."""
    try:
        out = subprocess.run(
            ["git", "status", "--short", "-uall", "--", "LandscapeLab/Content"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        return {ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:
        # An unreadable git is COULD NOT LOOK. Returning an empty set would
        # make the delta look like "nothing changed", which is the wrong
        # direction to fail in for a tool whose job is to catch silent
        # non-writes.
        return None


if __name__ == "__main__":
    sys.exit(main())
