"""place_player_start.py — put a spawn point on ground that actually exists.

PHASE2_PLAN.md unit 5: "a spawn point traced onto the collidable surface".

THIS MUTATES THE WORLD AND SAVES IT. Tag a restore point named for the
operation first (THE RISKY-OP CHECKPOINT). The tool refuses to run without
--go and prints its plan first.

=====================================================================
WHY A PlayerStart ACTOR RATHER THAN A SPAWN TRANSFORM IN CONFIG
=====================================================================
Measured 2026-08-15: with no PlayerStart, PIE spawned the pawn at the world
origin and it fell to Z = -91,373 cm. Not a terrain defect -- the pawn
appears before World Partition has streamed any ground under it, and gravity
does the rest.

A config transform has the same problem: the location is known but nothing
has asked WP to load a cell there. A PlayerStart ACTOR is what the streaming
system understands as a place the player begins, so the cell is resident
before the pawn exists. That is why this writes an actor rather than a
number.

=====================================================================
THE GROUND COMES FROM COLLISION, WITH THE REGIONS LOADED FIRST
=====================================================================
The trace runs AFTER load_all_world_partition_regions, because a trace into
an unstreamed cell returns no hit and "not streamed" is indistinguishable
from "no terrain here" -- the same trap unit 1 hit at three stations.

The XY comes from a NAMED CAMERA in the world recipe, not from typed
coordinates, so the spawn point and the station the frame-cost series was
measured at cannot drift apart.

Exit codes:
  0  placed and saved
  1  could not look
  2  bad arguments or a malformed recipe
  3  rule 7: no verified editor node
  4  no ground under the requested XY -- nothing placed
  5  placed but the read-back disagrees -- treat the world as UNKNOWN
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_START__"


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "loaded": None, "proxies": 0, "ground_z_cm": None,
        "why": None, "existing": [], "placed": None, "readback": None,
        "saved": None}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _w = _ues.get_editor_world()

    # Regions FIRST. A trace into an unstreamed cell returns no hit, and that
    # reads exactly like "there is no terrain here".
    _ok, _mn, _mx, _err = _unreal.LandscapeLabTools.load_all_world_partition_regions()
    _out["loaded"] = bool(_ok)
    if _err:
        _out["why"] = "region load: " + str(_err)
    for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_a, _unreal.LandscapeStreamingProxy):
            _out["proxies"] += 1

    _x = __X__
    _y = __Y__
    _agl = __AGL__

    _hit = _unreal.SystemLibrary.line_trace_single(
        _w, _unreal.Vector(_x, _y, 500000.0), _unreal.Vector(_x, _y, -100000.0),
        _unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
        _unreal.DrawDebugTrace.NONE, True)
    if _hit is None:
        _out["why"] = "no collision hit between +5000 m and -1000 m"
    else:
        # FHitResult fields are PROTECTED in 5.8; to_dict is the accessor.
        _dd = _hit.to_dict()
        for _k in _dd:
            if _k.lower() in ("location", "impact_point"):
                _out["ground_z_cm"] = float(_dd[_k].z)
                break
        if _out["ground_z_cm"] is None:
            _out["why"] = "hit result carries no location key"

    # Census BEFORE placing, so a second run is visibly idempotent rather than
    # quietly additive.
    for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_a, _unreal.PlayerStart):
            _l = _a.get_actor_location()
            _out["existing"].append({
                "label": str(_a.get_actor_label()),
                "loc": [float(_l.x), float(_l.y), float(_l.z)]})

    if _out["ground_z_cm"] is not None and __GO__:
        _z = _out["ground_z_cm"] + _agl
        _target = None
        for _a in _unreal.EditorLevelLibrary.get_all_level_actors():
            if isinstance(_a, _unreal.PlayerStart) and \
               str(_a.get_actor_label()) == "__LABEL__":
                _target = _a
                break
        if _target is None:
            _target = _eas.spawn_actor_from_class(
                _unreal.PlayerStart, _unreal.Vector(_x, _y, _z),
                _unreal.Rotator(0.0, __PITCH__, __YAW__))
            _target.set_actor_label("__LABEL__")
        else:
            _target.set_actor_location(_unreal.Vector(_x, _y, _z), False, True)
            _target.set_actor_rotation(_unreal.Rotator(0.0, __PITCH__, __YAW__), False)
        _out["placed"] = [_x, _y, _z]

        # Read back off the ACTOR, then save, then count again.
        _rl = _target.get_actor_location()
        _out["readback"] = [float(_rl.x), float(_rl.y), float(_rl.z)]
        # ROTATION READ-BACK. This tool checked LOCATION drift and not
        # rotation, and that gap let Rotator(0, YAW, 0) -- which sets PITCH,
        # because the signature is (ROLL, PITCH, YAW) -- ship a spawn whose
        # pitch was 135, normalised by the engine to (180, 45, 180). The
        # camera then aimed into the ground for as long as nobody looked.
        # A value that is never read back is a value nothing defends.
        _rr = _target.get_actor_rotation()
        _out["readback_rot"] = [float(_rr.roll), float(_rr.pitch),
                                float(_rr.yaw)]
        _out["rot_ok"] = bool(abs(float(_rr.pitch) - __PITCH__) < 0.01
                              and abs(float(_rr.roll)) < 0.01)
        # SAVE THE ACTOR'S OWN PACKAGE, EXPLICITLY.
        # save_dirty_packages(True, True) returned True here on 2026-08-16 and
        # WROTE NOTHING: a Python actor edit does not reliably flag the
        # external actor package dirty, so "save every dirty package" saves an
        # empty set and reports success. The move survived only in editor
        # memory, and every read-back agreed with it because every read-back
        # was reading that memory. Naming the package and saving it directly
        # removes the dependency on the dirty flag entirely.
        _pkg = None
        try:
            _pkg = _target.get_package()
        except Exception as _e:
            _out["why"] = "could not reach the actor's package: " + str(_e)
        if _pkg is None:
            _out["saved"] = False
        else:
            _out["package"] = str(_pkg.get_name())
            _out["saved"] = bool(
                _unreal.EditorLoadingAndSavingUtils.save_packages([_pkg], False))
    del _w
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_START__" + _json.dumps(_out))
'''


def _free_ram_gb():
    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) / 1048576.0 if out else None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="recipes/character.json")
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--label", default="PlayerStart_LandscapeLab")
    ap.add_argument("--yaw", type=float, default=135.0)
    # The PlayerController takes its INITIAL CONTROL ROTATION from the
    # PlayerStart, and the third-person boom follows that rotation. A positive
    # pitch therefore aims the arm into the ground BEHIND the player. Measured
    # 2026-08-16: the camera sat 88 cm below the pawn, 125 cm back on a 400 cm
    # arm, looking up at him. A small NEGATIVE pitch looks slightly down, which
    # is what a third-person camera wants.
    ap.add_argument("--pitch", type=float, default=-10.0)
    ap.add_argument("--go", action="store_true",
                    help="actually place and SAVE. Without it, plans only.")
    args = ap.parse_args(argv)

    try:
        with open(os.path.join(bootstrap.REPO_ROOT, args.character),
                  "r", encoding="utf-8") as fh:
            ch = json.load(fh)
        with open(os.path.join(bootstrap.REPO_ROOT, args.world),
                  "r", encoding="utf-8") as fh:
            world = json.load(fh)
    except Exception as e:
        print("COULD NOT READ A RECIPE: %s: %s" % (type(e).__name__, e))
        return 1

    spawn = ch.get("spawn") or {}
    cam_name = spawn.get("from_camera")
    agl = float(spawn.get("height_above_ground_cm", 0.0))
    if not cam_name or agl <= 0.0:
        print("REFUSE: recipe needs spawn.from_camera and a positive "
              "spawn.height_above_ground_cm; got %r / %r"
              % (cam_name, spawn.get("height_above_ground_cm")))
        return 2

    cam = None
    for c in world.get("capture", {}).get("cameras", []):
        if c.get("name") == cam_name:
            cam = c
            break
    if cam is None:
        print("REFUSE: no camera named %r in %s" % (cam_name, args.world))
        return 2

    half = float(ch["capsule"]["half_height_cm"])
    if agl < half:
        print("REFUSE: spawn.height_above_ground_cm %.1f is below the capsule "
              "half height %.1f, so the capsule would start inside the ground."
              % (agl, half))
        return 2

    x, y = float(cam["location_cm"][0]), float(cam["location_cm"][1])
    ram = _free_ram_gb()
    print("free RAM before: %s"
          % ("COULD NOT READ" if ram is None else "%.2f GB" % ram))
    print("plan: PlayerStart %r at XY from camera %r = (%.1f, %.1f)"
          % (args.label, cam_name, x, y))
    print("      Z = traced ground + %.1f cm  (capsule half height %.1f)"
          % (agl, half))
    print("      loads ALL World Partition regions first, then traces")
    if not args.go:
        print("")
        print("DRY RUN — nothing placed, nothing saved. Re-run with --go.")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        payload = (PAYLOAD.replace("__X__", repr(x)).replace("__Y__", repr(y))
                          .replace("__AGL__", repr(agl))
                          .replace("__GO__", repr(bool(args.go)))
                          .replace("__LABEL__", args.label)
                          .replace("__YAW__", repr(float(args.yaw)))
                          .replace("__PITCH__", repr(float(args.pitch))))
        r = remote.run_command(payload, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            print("NO MARKER — could not look.")
            print(text[:2000])
            return 1
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1

    print("")
    print("regions loaded   %s, %d landscape proxies resident"
          % (d.get("loaded"), d.get("proxies", 0)))
    print("existing PlayerStarts: %d" % len(d.get("existing") or []))
    for e in (d.get("existing") or []):
        print("    %-28s %s" % (e["label"], e["loc"]))

    if d.get("ground_z_cm") is None:
        print("NO GROUND at (%.1f, %.1f): %s" % (x, y, d.get("why")))
        print("Nothing placed.")
        return 4
    print("ground (traced vs COLLISION)  %.1f cm" % d["ground_z_cm"])

    if not args.go:
        print("would place at Z = %.1f cm" % (d["ground_z_cm"] + agl))
        return 0

    placed, rb = d.get("placed"), d.get("readback")
    print("placed at        %s" % placed)
    print("read back        %s" % rb)
    if not placed or not rb:
        print("REFUSE: no read-back — treat the world as UNKNOWN.")
        return 5
    drift = max(abs(placed[i] - rb[i]) for i in range(3))
    print("drift            %.3f cm" % drift)
    if drift > 1.0:
        print("REFUSE: the actor is not where it was put.")
        return 5
    rot = d.get("readback_rot")
    if rot is not None:
        print("rotation r/p/y   %.2f / %.2f / %.2f" % tuple(rot))
        if not d.get("rot_ok"):
            print("REFUSE: the spawn rotation is not what was asked for.")
            print("        The controller inherits this rotation and the")
            print("        third-person boom follows it, so a wrong pitch")
            print("        aims the camera into the ground.")
            return 5
    print("saved            %s" % d.get("saved"))
    if d.get("package"):
        print("package          %s" % d["package"])
        print("  CHECK THE ARTEFACT: this package's file mtime and git status")
        print("  are the evidence the save happened. The tool's own word is")
        print("  not -- it said True once while writing nothing.")
    if not d.get("saved"):
        print("REFUSE: the actor's package did not save.")
        return 5
    ram2 = _free_ram_gb()
    print("free RAM after   %s"
          % ("COULD NOT READ" if ram2 is None else "%.2f GB" % ram2))
    print("")
    print("VERIFY IN PIE, not here: this proves an ACTOR is at a location.")
    print("Whether the character STAYS on the ground is a different claim and")
    print("needs probe_pie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
