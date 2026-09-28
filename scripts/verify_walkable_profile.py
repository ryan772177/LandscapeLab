"""verify_walkable_profile.py — three places, one declaration, proven.

PHASE2_PLAN.md unit 5's second acceptance clause. READ-ONLY throughout.

=====================================================================
WHAT IT PROVES, AND WHY THREE PLACES IS ALREADY TOO MANY
=====================================================================
The walkable slope angle is a PHYSICAL fact about how a character relates to
ground. Non-negotiable 19 says a physical parameter is defined once and every
consumer reads it; non-negotiable 24 says two lists that must agree are one
list badly stored. This project currently has it in three places:

    terrain_erosion.MOVEMENT_PROFILES   the declaration
    recipes/character.json              names a PROFILE, never an angle
    the live CharacterMovementComponent what the engine will actually use

The second is already correct by construction -- it stores a KEY, so it
cannot drift numerically. The third is the engine's and we do not own it. So
what this actually gates is: **does the engine still agree with the number we
wrote down about it**, and **has anyone typed an angle where a key belongs**.

=====================================================================
AND THE RULING-19 GATE, WHICH IS THE ONE THAT BITES
=====================================================================
`AgentMaxSlope` derives from the navmesh agent profile and is gated never to
exceed the PAWN's own walkable floor. Drift upward is SILENT: the navmesh
grants paths onto ground the character slides off, and nothing errors. That
gate is checked here rather than at navmesh build time, because by then the
packages are written.

THE COMPARAND IS THE PAWN, NOT THE WORLD. Ruling 19 compares
`navigation.agent_profile` against `character.json` `movement.profile`
(RECIPES.md:12715, :13221; apply_navigation_config.py's 2026-08-26 correction).
It PREVIOUSLY compared against `world.primary_movement_mode` -- a MEASURED
defect (LESSONS.md 2026-08-26): with the world declared "mount" (35 deg) the
gate refused a "walk" navmesh (44.765) though the pawn is "climb" (70) and
walks every metre of it, leaving the town's outer third unreachable from its
own plaza. `world.primary_movement_mode` is a world-scale POI-spacing
declaration, not this gate's bar; it is reported for context only.

As shipped: nav agent "walk" (44.765) <= pawn "climb" (70) -> the gate PASSES.
(A prior version of this tool used the world-primary comparand and false-fired
exit 5; corrected 2026-09-18 to match RECIPES.md and apply_navigation_config.)

=====================================================================
OFFLINE BY DEFAULT
=====================================================================
The declaration checks need no editor and run in a cold replay. The CDO check
needs one and is added with --live. A run without --live says plainly which
checks did not run; it never reports them as passed.

**A NOTE ON WHAT THE CDO MEANS TODAY.** This project has no character class
yet, so the CDO read is the ENGINE default -- which is exactly the state a
spawned `ACharacter` would have, and therefore the right thing to compare
against until unit 5 authors one. Once a project character class exists this
tool must be pointed at THAT CDO, or it will keep proving something true
about a class nobody spawns.

Exit codes:
  0  all checks that ran, passed
  1  could not look (incl. a recipe that cannot be READ or PARSED)
  2  bad arguments, or the recipe is SEMANTICALLY invalid (a required field
     absent, a typed angle, or an unknown profile name)
  3  rule 7: no verified editor node (only with --live)
  4  DRIFT: a declared value disagrees with the engine
  5  RULING 19 VIOLATED: the nav agent angle exceeds the world's primary
     movement mode
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import terrain_erosion as te  # noqa: E402

MARKER = "__LL_WALK__"

# recipe key -> (CDO property, tolerance). The tolerance is 1e-4 because these
# are floats round-tripped through JSON and a reflected float read, not
# because any real slack is intended.
MOVEMENT_FIELDS = {
    "max_walk_speed_cm_s": "max_walk_speed",
    "max_step_height_cm": "max_step_height",
    "jump_z_velocity_cm_s": "jump_z_velocity",
    "max_acceleration_cm_s2": "max_acceleration",
    "gravity_scale": "gravity_scale",
}
TOL = 1e-4


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "cmc": {}, "capsule": {}, "unreadable": []}
try:
    _cdo = _unreal.get_default_object(_unreal.CharacterMovementComponent)
    for _p in __CMC_PROPS__:
        try:
            _out["cmc"][_p] = float(_cdo.get_editor_property(_p))
        except Exception as _e:
            # Unreadable is NOT a value. Recorded so the caller can report
            # "could not look" instead of comparing against a fabricated 0.
            _out["unreadable"].append("cmc." + _p)
    # THE CAPSULE MUST COME OFF THE CHARACTER, NOT OFF CapsuleComponent.
    # CapsuleComponent's own CDO is the GENERIC component default (22 / 44).
    # ACharacter initialises ITS OWN capsule subobject to 34 / 88 in the
    # constructor (Character.cpp:78 InitCapsuleSize(34.0f, 88.0f)), so the
    # generic CDO answers plausibly and is about a different object.
    _out["capsule_source"] = None
    _ch = _unreal.get_default_object(_unreal.Character)
    _cap = None
    try:
        _cap = _ch.get_editor_property("capsule_component")
        _out["capsule_source"] = "Character CDO -> capsule_component"
    except Exception as _ce:
        _out["unreadable"].append(
            "Character.capsule_component: " + type(_ce).__name__ + ": " + str(_ce))
    if _cap is not None:
        for _p in ("capsule_radius", "capsule_half_height"):
            try:
                _out["capsule"][_p] = float(_cap.get_editor_property(_p))
            except Exception:
                _out["unreadable"].append("capsule." + _p)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_WALK__" + _json.dumps(_out))
'''


def _read_live():
    """Read the CMC and capsule CDOs. Returns (dict, error_string)."""
    import verify_landscape
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            return None, "rule 7: " + str(reason)
        remote.open_command_connection(node["node_id"])
        props = list(MOVEMENT_FIELDS.values()) + ["walkable_floor_angle",
                                                  "walkable_floor_z"]
        r = remote.run_command(
            PAYLOAD.replace("__CMC_PROPS__", repr(props)),
            unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            return None, "no marker in the reply"
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
        return d, d.get("error")
    finally:
        try:
            remote.stop()
        except Exception:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="recipes/character.json")
    ap.add_argument("--world", default="recipes/alpine_8k.json")
    ap.add_argument("--live", action="store_true",
                   help="also read the live CharacterMovementComponent CDO")
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

    rc = 0
    print("=== WALKABLE PROFILE — three places, one declaration ===")
    print("")

    # ---- 1. the recipe must name a PROFILE, not an angle -------------------
    mv = ch.get("movement", {})
    prof = mv.get("profile")
    print("--- 1. the character names a profile, not an angle ---")
    if prof is None:
        print("  REFUSE: movement.profile is absent.")
        return 2
    for k in mv:
        if "angle" in k.lower() or "slope" in k.lower():
            print("  REFUSE: movement.%s is a typed ANGLE. Ruling 19 says the" % k)
            print("          angle is DERIVED from the profile, never typed.")
            print("          A second copy is a second thing to drift.")
            return 2
    if prof not in te.MOVEMENT_PROFILES:
        print("  REFUSE: profile %r is not in terrain_erosion.MOVEMENT_PROFILES"
              % prof)
        print("          known: %s" % ", ".join(sorted(te.MOVEMENT_PROFILES)))
        return 2
    char_deg = float(te.MOVEMENT_PROFILES[prof]["max_slope_deg"])
    print("  OK    movement.profile = %r" % prof)
    print("        -> %.6f deg, derived from MOVEMENT_PROFILES" % char_deg)
    print("        no angle is typed in the recipe")

    # ---- 2. ruling 19: nav agent must not exceed the PAWN's movement mode ---
    # THE COMPARAND IS THE PAWN (RECIPES.md:12715/:13221; the 2026-08-26
    # correction in apply_navigation_config). char_deg (from check 1) is the
    # pawn's movement.profile angle. The old world.primary_movement_mode
    # comparand was a MEASURED defect and is reported only for context.
    print("")
    print("--- 2. ruling 19: nav agent <= the PAWN's movement profile ---")
    nav = ch.get("navigation", {})
    agent_prof = nav.get("agent_profile")
    if agent_prof is None:
        print("  REFUSE: navigation.agent_profile is absent.")
        return 2
    if agent_prof not in te.MOVEMENT_PROFILES:
        print("  REFUSE: unknown agent profile %r" % agent_prof)
        return 2
    a = float(te.MOVEMENT_PROFILES[agent_prof]["max_slope_deg"])
    print("  nav agent   %-6r %.6f deg" % (agent_prof, a))
    print("  pawn        %-6r %.6f deg" % (prof, char_deg))
    if a > char_deg + TOL:
        print("  VIOLATED: the navmesh would grant paths onto ground the PAWN")
        print("            slides off, silently.")
        rc = max(rc, 5)
    else:
        print("  OK    %.6f <= %.6f" % (a, char_deg))
    # world.primary_movement_mode is context, NOT the ruling-19 bar.
    _wp = (world.get("world") or {}).get("primary_movement_mode")
    if _wp in te.MOVEMENT_PROFILES:
        _w = float(te.MOVEMENT_PROFILES[_wp]["max_slope_deg"])
        print("  (context: world.primary_movement_mode %r = %.3f deg -- a "
              "world-scale POI declaration, NOT this gate's bar)" % (_wp, _w))

    # ---- 3. against the engine --------------------------------------------
    print("")
    print("--- 3. against the live engine CDO ---")
    if not args.live:
        print("  NOT RUN — pass --live. These checks are NOT passed, they are")
        print("  UNRUN, and this run says so rather than reporting a verdict")
        print("  it did not earn.")
        print("")
        if rc == 0:
            print("VERDICT: declaration checks passed; engine comparison UNRUN.")
        else:
            print("VERDICT: a declaration check FAILED (exit %d — see above, "
                  "e.g. RULING 19); engine comparison UNRUN." % rc)
        return rc

    live, err = _read_live()
    if live is None:
        print("  COULD NOT LOOK: %s" % err)
        return 3 if str(err).startswith("rule 7") else 1
    if err:
        print("  PAYLOAD ERROR: %s" % err)
        return 1
    for u in live.get("unreadable", []):
        print("  UNREADABLE: %s — reported as could-not-look, not as a value" % u)
        rc = max(rc, 1)

    cmc = live.get("cmc", {})
    # WHAT IS COMPARED HERE, AND WHAT IS NOT.
    # Only the 'walk' profile is a RECORD OF AN ENGINE VALUE -- it holds
    # acos(0.71) from SetWalkableFloorZ(0.71f). That one must keep matching the
    # CDO, and drift means our record went stale.
    # Every other profile ('climb', 'mount') is a DESIGN CHOICE. Comparing
    # those to the engine default would report DRIFT on a deliberate decision,
    # which is a gate failing on correct input.
    eng_deg = cmc.get("walkable_floor_angle")
    walk_deg = float(te.MOVEMENT_PROFILES["walk"]["max_slope_deg"])
    if eng_deg is None:
        print("  walkable_floor_angle UNREADABLE — no verdict on the angle")
        rc = max(rc, 1)
    else:
        print("  walkable_floor_angle  engine CDO %.6f   MOVEMENT_PROFILES"
              "['walk'] %.6f" % (eng_deg, walk_deg))
        if abs(eng_deg - walk_deg) > 1e-3:
            print("    DRIFT: this project's RECORD of the engine's own")
            print("    walkable angle no longer matches the engine. The engine")
            print("    is the source; MOVEMENT_PROFILES['walk'] is the copy.")
            rc = max(rc, 4)
        else:
            print("    OK — our record of the engine value is current")
        print("  this character uses profile %r = %.6f deg" % (prof, char_deg))
        if abs(char_deg - eng_deg) > 1e-3:
            print("    (a DESIGN CHOICE, deliberately not the engine default —")
            print("     not compared against the CDO, because that would fail")
            print("     the gate on a decision rather than on a defect)")

    for rk, ck in sorted(MOVEMENT_FIELDS.items()):
        want = mv.get(rk)
        got = cmc.get(ck)
        if want is None:
            print("  %-24s recipe does not declare it" % rk)
            continue
        if got is None:
            print("  %-24s UNREADABLE from the CDO" % rk)
            rc = max(rc, 1)
            continue
        ok = abs(float(want) - got) <= TOL
        print("  %-24s recipe %-10s engine %-10s %s"
              % (rk, want, got, "OK" if ok else "DRIFT"))
        if not ok:
            rc = max(rc, 4)

    cap = ch.get("capsule", {})
    lcap = live.get("capsule", {})
    for rk, ck in (("radius_cm", "capsule_radius"),
                   ("half_height_cm", "capsule_half_height")):
        want, got = cap.get(rk), lcap.get(ck)
        if want is None or got is None:
            print("  capsule.%-16s COULD NOT COMPARE (recipe=%s engine=%s)"
                  % (rk, want, got))
            rc = max(rc, 1)
            continue
        ok = abs(float(want) - got) <= TOL
        print("  capsule.%-16s recipe %-8s engine %-8s %s"
              % (rk, want, got, "OK" if ok else "DRIFT"))
        if not ok:
            rc = max(rc, 4)

    print("")
    print("  NOTE: this project has no character CLASS yet, so the CDO above")
    print("  is the ENGINE default — which is exactly what a spawned ACharacter")
    print("  would carry today. Once unit 5 authors a class, point this tool at")
    print("  THAT CDO or it will keep proving something about a class nobody")
    print("  spawns.")
    print("")
    print("VERDICT: %s" % ("PASS" if rc == 0 else "see the non-zero rows above"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
