"""apply_navigation_config.py — recipe -> navmesh build configuration.

TWO HALVES, AND THEY LAND IN DIFFERENT PLACES BECAUSE THE ENGINE PUTS THEM
IN DIFFERENT PLACES.

    --ini     ARecastNavMesh and UNavigationSystemV1 properties are
              `config`, so they belong in DefaultEngine.ini and reach the
              CDO at engine init. THIS REQUIRES AN EDITOR RESTART.
              READ-BACK SCOPE: only the RecastNavMesh CDO is re-read and
              compared. The NavigationSystemV1 config (DataGatheringMode,
              +SupportedAgents) is WRITTEN but not read back here -- verify it
              from the NavigationSystemV1 CDO if it ever needs a gate.
    --world   AWorldSettings.NavigationDataChunkGridSize and
              .NavigationDataBuilderLoadingCellSize are EditAnywhere and
              NOT config, and ANavMeshBoundsVolume is an actor. Both are
              world edits, done through the running editor.

WHY THE ini AND NOT THE ACTOR, for the RecastNavMesh half.
`ARecastNavMesh::PostLoad` (RecastNavMesh.cpp:963-1015) FORCES TileSizeUU
and AgentMaxSlope back to the class default when the voxel cache is on,
with a log warning and nothing else. Writing them onto an instance would
be silently reverted. Writing them into config moves the CDO too, so the
comparison it makes is 1600 against 1600 and cannot fire.

RULING 19 IS RE-CHECKED HERE, not trusted from R-CHARACTER. The navmesh
agent's max slope must not exceed the PAWN's movement profile
(character.json `movement.profile`): drift upward is SILENT, and grants the
AI paths onto ground the character slides off. The check is one-directional.
(The comparand is the PAWN, not `world.primary_movement_mode` -- the latter
was a MEASURED defect, corrected 2026-08-26; see the inline note at the gate
and RECIPES.md:12715, :13221.)

Exit codes:
    0  applied (or dry run completed)
    2  bad arguments, bad recipe, or ruling-19 refusal
    3  rule 7: no verified editor node
    4  applied but a read-back disagreed (a CDO/WorldSettings value, or a
       NavMeshBoundsVolume whose placement did not match the intended bounds)
    5  the editor payload reported an error, OR returned no result
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap        # noqa: E402
import import_heightmap as ih   # noqa: E402
import terrain_erosion  # noqa: E402
import ue_exec          # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
INI = os.path.join(bootstrap.UE_PROJECT_ROOT, "Config", "DefaultEngine.ini")
BEGIN = "; >>> LANDSCAPELAB NAVIGATION — GENERATED FROM recipes, DO NOT EDIT BY HAND"
END = "; <<< LANDSCAPELAB NAVIGATION"


def _filter_volumes(vols, only):
    """The subset named by --volumes, or all of them.

    REFUSES on a name the recipe does not declare. A typo would otherwise
    produce an empty batch, and "applied 0 volumes" reads exactly like a batch
    that had nothing to do.
    """
    if not only:
        return vols
    want = [n.strip() for n in only.split(",") if n.strip()]
    have = {v["name"]: v for v in vols}
    missing = [n for n in want if n not in have]
    if missing:
        # ValueError, NOT SystemExit: build_spec runs inside main()'s
        # `except ValueError -> return 2` guard. SystemExit would propagate
        # uncaught and exit 1, contradicting the documented exit-2 contract
        # for a bad --volumes argument.
        raise ValueError(
            "REFUSE: --volumes names %d volume(s) the recipe does not "
            "declare: %s. The recipe declares %d."
            % (len(missing), ", ".join(missing), len(have)))
    return [have[n] for n in want]


def build_spec(world_recipe, world_path, char_recipe, only=None):
    """Both recipes -> one spec, with ruling 19 enforced before anything."""
    errs = ih._validate_recipe(json.loads(json.dumps(world_recipe)), world_path)
    if errs:
        raise ValueError("world recipe does not validate:\n  "
                         + "\n  ".join(errs))
    nav = world_recipe.get("navigation")
    if not nav:
        raise ValueError("the world recipe declares no `navigation` block")

    profiles = terrain_erosion.MOVEMENT_PROFILES
    agent_profile = (char_recipe.get("navigation") or {}).get("agent_profile")
    if agent_profile not in profiles:
        raise ValueError(
            "character recipe navigation.agent_profile %r is not a key into "
            "MOVEMENT_PROFILES %r. It is a KEY, never an angle."
            % (agent_profile, sorted(profiles)))
    # ⛔ THE COMPARAND IS THE PAWN, NOT THE WORLD. Corrected 2026-08-26.
    #
    # This guard exists to stop a navmesh granting paths onto ground THE
    # CHARACTER SLIDES OFF. The thing that slides is the pawn, so the bar is the
    # pawn's own walkable floor -- character.json movement.profile, the same key
    # apply_character_recipe projects into CfgWalkableFloorAngleDeg.
    #
    # It previously compared against world.primary_movement_mode, which is a
    # WORLD-SCALE declaration about how the region is crossed (it sizes POI
    # spacing against mounted speed in WORLD_VISION). Using it here conflated
    # two different questions and produced a real defect: with the world
    # declared "mount" (35 deg), the guard refused a WALK navmesh (44.765) even
    # though the pawn is "climb" (70) and could walk every metre of it. The
    # measured consequence was a town whose outer third was unreachable from its
    # own plaza -- 19 of 60 street points in a different navmesh island -- while
    # every gate stayed green.
    #
    # The guard is not weakened by this: walk 44.765 <= climb 70 still leaves it
    # one-directional and still refuses an agent steeper than the pawn. It is
    # now comparing the two things whose disagreement actually causes the
    # failure it names.
    pawn_profile = (char_recipe.get("movement") or {}).get("profile")
    if pawn_profile not in profiles:
        raise ValueError(
            "character recipe movement.profile %r is not a key into "
            "MOVEMENT_PROFILES %r. It is a KEY, never an angle."
            % (pawn_profile, sorted(profiles)))

    agent_deg = float(profiles[agent_profile]["max_slope_deg"])
    pawn_deg = float(profiles[pawn_profile]["max_slope_deg"])
    # RULING 19, re-comparanded. One-directional, never equality.
    if agent_deg > pawn_deg:
        raise ValueError(
            "REFUSED (ruling 19): navmesh agent profile %r is %.3f deg, "
            "steeper than the PAWN's movement profile %r at %.3f deg. "
            "Drift upward is SILENT -- the navmesh would grant paths onto "
            "ground the character slides off, and nothing would error."
            % (agent_profile, agent_deg, pawn_profile, pawn_deg))

    agent = char_recipe.get("navigation") or {}
    return {
        "recast": {
            "TileSizeUU": float(nav["tile_size_uu"]),
            "AverageLayersPerTile": float(nav["average_layers_per_tile"]),
            "MaxSimultaneousTileGenerationJobsCount":
                int(nav["max_simultaneous_tile_generation_jobs"]),
            # The engine property is NAMED MinRegionArea and is a LINEAR
            # dimension: RecastNavMeshGenerator.cpp:5267 does
            # rcSqr(MinRegionArea / CellSize). The recipe key says so.
            "MinRegionArea": float(nav["min_region_dimension_uu"]),
            "AgentMaxSlope": agent_deg,
            "AgentRadius": float(agent["agent_radius_cm"]),
            "AgentHeight": float(agent["agent_height_cm"]),
        },
        "navsystem": {
            "DataGatheringMode": nav["data_gathering_mode"].capitalize(),
            # THE AGENT DIMENSIONS DO NOT COME FROM ARecastNavMesh.
            # NavigationSystem.cpp:2874-2875 and :4729 call
            # NavData->SetConfig(SupportedAgents[...]), which OVERWRITES the
            # navmesh's AgentRadius/AgentHeight with the supported agent's.
            # Measured 2026-08-17: with AgentRadius=34/AgentHeight=176 set on
            # ARecastNavMesh, the CDO read back 34/176 and the auto-created
            # RecastNavMesh-Default ACTOR read 35/144 -- the FNavDataConfig
            # fallbacks -- because SupportedAgents was empty. The CDO check
            # was green over a value the build would not have used.
            #
            # `+` appends: verified 2026-08-17 that no SupportedAgents entry
            # exists anywhere in the engine or project config, so this
            # produces exactly one agent and one navmesh.
            "+SupportedAgents": (
                '(Name="Default",AgentRadius=%.6f,AgentHeight=%.6f,'
                'AgentStepHeight=%.6f)'
                % (float(agent["agent_radius_cm"]),
                   float(agent["agent_height_cm"]),
                   float((char_recipe.get("movement") or {})
                         .get("max_step_height_cm", 45.0)))),
        },
        "world_settings": {
            "navigation_data_chunk_grid_size": int(nav["chunk_grid_size_cm"]),
            "navigation_data_builder_loading_cell_size":
                int(nav["builder_loading_cell_size_cm"]),
        },
        # Filtered by --volumes when the caller is applying a BATCH. The
        # recipe stays the single declaration of the whole grid; the filter
        # only decides which of its volumes reach the world on this run, so a
        # 72-tile grid can be spawned in bounded batches instead of one
        # unbounded pass. An unrecognised name REFUSES rather than silently
        # matching nothing -- a typo would otherwise read as "batch applied,
        # zero volumes", which is indistinguishable from success.
        "volumes": _filter_volumes(nav["bounds_volumes"], only),
        # The comparand is the PAWN, not the world -- see the guard above.
        "_ruling19": {"agent": agent_profile, "agent_deg": agent_deg,
                      "pawn": pawn_profile, "pawn_deg": pawn_deg},
    }


def render_ini_block(spec):
    L = [BEGIN,
         "; ARecastNavMesh and UNavigationSystemV1 properties are `config`,",
         "; so they load into the CDO at engine init. Writing them onto an",
         "; ACTOR instead would be reverted by ARecastNavMesh::PostLoad",
         "; (RecastNavMesh.cpp:963-1015) when the voxel cache is on.",
         "; AgentMaxSlope is DERIVED from the character recipe's",
         "; navigation.agent_profile via terrain_erosion.MOVEMENT_PROFILES.",
         "; It is never typed: ruling 19 refuses an agent steeper than the",
         "; PAWN's movement profile (character.json movement.profile; the",
         "; comparand is the pawn, not world.primary_movement_mode), and",
         "; drift upward is silent.",
         "[/Script/NavigationSystem.RecastNavMesh]"]
    for k, v in spec["recast"].items():
        L.append("%s=%s" % (k, v))
    L.append("")
    L.append("[/Script/NavigationSystem.NavigationSystemV1]")
    for k, v in spec["navsystem"].items():
        L.append("%s=%s" % (k, v))
    L.append(END)
    return "\n".join(L)


def write_ini(spec, dry):
    with open(INI, "r", encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    block = render_ini_block(spec).replace("\n", nl)

    i = text.find(BEGIN)
    if i >= 0:
        j = text.find(END, i)
        if j < 0:
            raise ValueError("found the generated block's BEGIN marker with "
                             "no END marker; refusing to guess where it ends")
        new = text[:i] + block + text[j + len(END):]
        action = "replaced"
    else:
        sep = nl + nl if not text.endswith(nl) else nl
        new = text + sep + block + nl
        action = "appended"

    if dry:
        return action, block, False
    if new == text:
        return action, block, False
    with open(INI, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    return action, block, True


PAYLOAD = r'''
import json as _json
import unreal as _u

SPEC = _json.loads(r"""__SPEC__""")
APPLY = __APPLY__

_out = {"ok": False, "error": None, "level": None, "world_settings": {},
        "volumes": [], "recast_cdo": {}, "existing_navmesh_actors": 0}


def _rd(o, p):
    try:
        v = o.get_editor_property(p)
        return v if isinstance(v, (int, float, bool, str)) else str(v)
    except Exception as _e:
        return "UNREADABLE(%s): %s" % (p, str(_e)[:70])


try:
    ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    w = ues.get_editor_world()
    _out["level"] = w.get_path_name()

    # The CDO is what the ini reached. Reported so a run before the restart
    # cannot be mistaken for a run after it.
    cdo = _u.get_default_object(_u.RecastNavMesh)
    for p in ("tile_size_uu", "agent_max_slope", "average_layers_per_tile",
              "max_simultaneous_tile_generation_jobs_count",
              "min_region_area", "agent_radius", "agent_height"):
        _out["recast_cdo"][p] = _rd(cdo, p)

    ws = w.get_world_settings()
    for k, v in SPEC["world_settings"].items():
        _out["world_settings"][k] = {"before": _rd(ws, k), "want": v}
        if APPLY:
            ws.set_editor_property(k, v)
            _out["world_settings"][k]["after"] = _rd(ws, k)

    existing = {}
    for a in eas.get_all_level_actors():
        if isinstance(a, _u.NavMeshBoundsVolume):
            existing[a.get_actor_label()] = a
        elif isinstance(a, _u.RecastNavMesh):
            _out["existing_navmesh_actors"] += 1
            # THE ACTOR, NOT THE CDO. The CDO is what the ini wrote; the
            # ACTOR is what builds, and NavigationSystem.cpp:2874 overwrites
            # its agent dimensions from SupportedAgents. Reading only the
            # CDO reports success over a value the build will not use
            # (non-negotiable 8).
            rec = {"label": a.get_actor_label()}
            for p in ("tile_size_uu", "agent_max_slope",
                      "average_layers_per_tile",
                      "max_simultaneous_tile_generation_jobs_count",
                      "min_region_area", "agent_radius", "agent_height"):
                rec[p] = _rd(a, p)
            _out.setdefault("recast_actors", []).append(rec)

    for v in SPEC["volumes"]:
        mn, mx = v["min_cm"], v["max_cm"]
        centre = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
        # A brush Volume is a 200-uu default cube scaled by the actor
        # scale, so the scale IS extent/100 -- half the size, not the size.
        scale = [(mx[i] - mn[i]) / 200.0 for i in range(3)]
        rec = {"name": v["name"], "centre": centre, "scale": scale,
               "min_cm": mn, "max_cm": mx,   # intended AABB, for the compare
               "existed": v["name"] in existing}
        if APPLY:
            a = existing.get(v["name"])
            if a is None:
                a = eas.spawn_actor_from_class(
                    _u.NavMeshBoundsVolume,
                    _u.Vector(centre[0], centre[1], centre[2]))
                a.set_actor_label(v["name"])
            else:
                a.set_actor_location(
                    _u.Vector(centre[0], centre[1], centre[2]), False, False)
            a.set_actor_scale3d(_u.Vector(scale[0], scale[1], scale[2]))
            try:
                o, e = a.get_actor_bounds(False)
                rec["read_back_min"] = [round(o.x - e.x, 1),
                                        round(o.y - e.y, 1),
                                        round(o.z - e.z, 1)]
                rec["read_back_max"] = [round(o.x + e.x, 1),
                                        round(o.y + e.y, 1),
                                        round(o.z + e.z, 1)]
            except Exception as _e:
                rec["read_back_min"] = "UNREADABLE: %s" % str(_e)[:70]
        _out["volumes"].append(rec)

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
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--character", default="recipes/character.json")
    ap.add_argument("--ini", action="store_true",
                    help="write the config block (needs an editor RESTART)")
    ap.add_argument("--volumes", default=None,
                    help="comma-separated volume names to apply on this run. "
                         "The recipe stays the single declaration of the "
                         "whole grid; this only decides which of its volumes "
                         "reach the world now, so a large grid can be "
                         "spawned in bounded batches. An unknown name "
                         "REFUSES.")
    ap.add_argument("--world", action="store_true",
                    help="apply world settings and bounds volumes")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)

    wp = os.path.join(REPO_ROOT, args.recipe)
    cp = os.path.join(REPO_ROOT, args.character)
    with open(wp, "r", encoding="utf-8") as fh:
        world = json.load(fh)
    with open(cp, "r", encoding="utf-8") as fh:
        char = json.load(fh)

    try:
        spec = build_spec(world, wp, char, only=args.volumes)
    except ValueError as exc:
        print("REFUSE:", exc)
        return 2

    r = spec["_ruling19"]
    print("ruling 19: agent %r %.3f deg <= PAWN %r %.3f deg  OK"
          % (r["agent"], r["agent_deg"], r["pawn"], r["pawn_deg"]))
    print("AgentMaxSlope DERIVED as %.3f — not typed anywhere"
          % spec["recast"]["AgentMaxSlope"])
    print()

    if args.ini:
        action, block, wrote = write_ini(spec, dry=not args.go)
        print("--- config block (%s%s) ---"
              % (action, "" if wrote else ", DRY RUN" if not args.go
                 else ", already current"))
        print(block)
        print()
        if wrote:
            print("WROTE %s" % os.path.relpath(INI, REPO_ROOT))
            print("*** RESTART THE EDITOR. These are `config` properties "
                  "read at engine init; a running editor will not see "
                  "them, and the CDO read-back below is the check. ***")

    if not args.world:
        return 0

    payload = (PAYLOAD.replace("__SPEC__", json.dumps(spec))
                      .replace("__APPLY__", "True" if args.go else "False"))
    rc, d, _ = ue_exec.run(payload, timeout=args.timeout,
                           stage_name="apply_navigation_config")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: no result from the editor.")
        return 5
    if d.get("error"):
        print("PAYLOAD ERROR:\n" + d["error"])
        return 5

    print("level:", d["level"])
    print()
    print("RecastNavMesh CDO — what the ini actually reached:")
    bad = 0
    want_cdo = {
        "tile_size_uu": spec["recast"]["TileSizeUU"],
        "agent_max_slope": spec["recast"]["AgentMaxSlope"],
        "average_layers_per_tile": spec["recast"]["AverageLayersPerTile"],
        "max_simultaneous_tile_generation_jobs_count":
            spec["recast"]["MaxSimultaneousTileGenerationJobsCount"],
        "min_region_area": spec["recast"]["MinRegionArea"],
        "agent_radius": spec["recast"]["AgentRadius"],
        "agent_height": spec["recast"]["AgentHeight"],
    }
    for k, want in want_cdo.items():
        got = d["recast_cdo"].get(k)
        ok = isinstance(got, (int, float)) and abs(float(got) - want) < 1e-3
        bad += 0 if ok else 1
        print("   %-46s %-12s want %-12s %s"
              % (k, got, want, "OK" if ok else "*** NOT IN EFFECT ***"))

    actors = d.get("recast_actors") or []
    print()
    if not actors:
        print("RecastNavMesh ACTORS: none yet (one is auto-created when a "
              "NavMeshBoundsVolume first appears)")
    else:
        print("RecastNavMesh ACTOR — what will actually BUILD:")
        for a in actors:
            print("   %s" % a["label"])
            for k, want in want_cdo.items():
                got = a.get(k)
                ok = (isinstance(got, (int, float))
                      and abs(float(got) - want) < 1e-3)
                bad += 0 if ok else 1
                note = ""
                if not ok and k in ("agent_radius", "agent_height"):
                    note = ("  <- comes from SupportedAgents "
                            "(NavigationSystem.cpp:2874), not from this "
                            "navmesh; needs an editor restart after the ini")
                print("      %-44s %-12s want %-12s %s%s"
                      % (k, got, want, "OK" if ok else "*** MISMATCH ***",
                         note))

    print()
    print("WorldSettings:")
    for k, v in d["world_settings"].items():
        line = "   %-46s before %-10s want %-10s" % (k, v["before"], v["want"])
        if "after" in v:
            ok = str(v["after"]) == str(v["want"])
            bad += 0 if ok else 1
            line += " after %-10s %s" % (v["after"], "OK" if ok else "***")
        print(line)

    print()
    print("NavMeshBoundsVolumes:")
    VOL_TOL_CM = 10.0
    for v in d["volumes"]:
        print("   %-24s existed=%s" % (v["name"], v["existed"]))
        print("       centre %s  scale %s"
              % ([round(c, 1) for c in v["centre"]],
                 [round(s, 3) for s in v["scale"]]))
        rbmn, rbmx = v.get("read_back_min"), v.get("read_back_max")
        if (isinstance(rbmn, list) and isinstance(rbmx, list)
                and "min_cm" in v and "max_cm" in v):
            # COMPARE the read-back AABB to the intended one (rule 12): the
            # placement was read back but never checked, so a mis-placed volume
            # still reported "APPLIED". Tolerance is generous (brush bounds vs
            # the declared extent); a real drift dwarfs it.
            dmin = max(abs(rbmn[i] - v["min_cm"][i]) for i in range(3))
            dmax = max(abs(rbmx[i] - v["max_cm"][i]) for i in range(3))
            vok = dmin <= VOL_TOL_CM and dmax <= VOL_TOL_CM
            bad += 0 if vok else 1
            print("       read back  %s .. %s   want %s .. %s   %s"
                  % (rbmn, rbmx, v["min_cm"], v["max_cm"],
                     "OK" if vok else "*** off by %.1f/%.1f cm" % (dmin, dmax)))
        elif "read_back_min" in v:
            # present but not a coordinate pair (e.g. "UNREADABLE: ...")
            bad += 1
            print("       read back  %r   *** could not read the placed bounds"
                  % (rbmn,))

    print()
    if not args.go:
        print("DRY RUN — nothing written to the world.")
        return 0
    if bad:
        print("%d value(s) NOT IN EFFECT. If the CDO rows are the ones "
              "failing, the editor has not been restarted since the ini "
              "was written." % bad)
        return 4
    print("APPLIED. The world is DIRTY — save it before building, or the "
          "builder reads the packages on disk and not what is in memory. "
          "That is exactly how unit 6's collision reached PIE as "
          "NoCollision.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
