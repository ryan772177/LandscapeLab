"""verify_tree_collision.py — fire real traces at real trunks, in PIE.

THE POINT: A READ-BACK IS NOT EVIDENCE THAT ANYTHING COLLIDES
    `apply_foliage_collision` reads back the field it wrote, which proves
    the value landed and nothing more (non-negotiable 8). This asks a
    DIFFERENT representation: a world line trace against instances that are
    actually in a running game world.

WHAT PYTHON CAN ACTUALLY READ FROM A TRACE, MEASURED
    Nothing but hit-or-miss. Every field of `FHitResult` is either
    protected or absent from the 5.8 reflected surface -- `component`,
    `distance`, `location`, `time`, `normal` and `item` all report
    "protected and cannot be read", and `hit_component`, `hit_actor`,
    `impact_point`, `face_index` are not found at all. Enumerated, not
    assumed, after `component` raised.

    So this test is built as a DIFFERENTIAL. It never asks what was hit;
    it asks the same question twice with one variable changed, which is a
    stronger instrument anyway.

THREE WAYS THIS TEST COULD LIE, AND WHAT STOPS EACH
    1. A trace could hit the LANDSCAPE instead of a trunk and read as
       success. Horizontal traces on alpine ground do this readily -- a 16
       degree slope rises 86 cm over the 3 m approach. So every trunk trace
       is run TWICE: once normally, and once with every InstancedFoliage
       actor in `actors_to_ignore`. A trunk hit is counted only when the
       first HITS and the second MISSES. Terrain is hit by both and
       therefore counts as nothing.
    2. The instrument could be incapable of returning a miss, in which case
       every hit is meaningless. Each trunk trace is paired with a NEGATIVE
       CONTROL at the same XY, above the top of the tree, which must MISS.
       The foliage-ignored trace is a second, independent miss-capability
       check on the exact line being tested.
    3. Collision could be "on" while the profile's responses still ignore
       the channel being traced. The trunk traces run on VISIBILITY, which
       the NoCollision profile explicitly sets to Ignore
       (BaseEngine.ini:3103). A Visibility hit therefore proves the
       responses were loaded, not merely that a flag was set.

AND IT STILL MEASURES THE CAPSULE, WITHOUT READING A DISTANCE
    The declared radius is checked GEOMETRICALLY, by offsetting the trace
    line sideways in steps and finding the largest offset that still
    registers a foliage hit. That cutoff IS the capsule radius in world
    units, and it is compared against `radius_cm x instance scale`. It uses
    only hit-or-miss, so the opacity of FHitResult costs nothing.

Exit codes:
    0  every species hit its own trunks and every negative control missed
    1  could not look (no result, PIE never came up, or the trace payload raised)
    2  bad arguments / recipe
    3  rule 7: no verified editor node
    5  a species did NOT collide, or a negative control HIT
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap   # noqa: E402
import ue_exec     # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT

BEGIN_PLAY = r'''
import json as _json
import unreal as _u
_out = {"error": None, "requested": False, "already": None}
try:
    _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
    _out["already"] = bool(_les.is_in_play_in_editor())
    if not _out["already"]:
        # A REQUEST: the session starts on a later tick, so nothing may be
        # read in this payload. Reading here would read the EDITOR world and
        # look like a failure.
        _les.editor_request_begin_play()
    _out["requested"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out))
'''

END_PLAY = r'''
import json as _json
import unreal as _u
_out = {"error": None, "ended": False}
try:
    _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
    if _les.is_in_play_in_editor():
        _les.editor_request_end_play()
    _out["ended"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL__" + _json.dumps(_out))
'''

TRACE = r'''
import json as _json
import unreal as _u

SPEC = _json.loads(r"""__SPEC__""")
PER_SPECIES = __PER_SPECIES__
REACH_CM = 300.0
TRACE_Z_CM = 100.0
# Sideways offsets for the geometric radius probe, in cm. Spans the
# declared 38 cm well on both sides so the cutoff is bracketed rather than
# assumed, and stays under the ~2 m gap to a neighbouring trunk.
OFFSETS = [0.0, 10.0, 20.0, 25.0, 30.0, 33.0, 36.0, 38.0, 40.0, 42.0,
           45.0, 50.0, 60.0, 80.0]

_out = {"ok": False, "error": None, "in_play": None, "world": None,
        "species": [], "components_seen": [], "ifa_count": 0}

IFAS = []


def _norm(p):
    return p.split(".")[0] if p else p


def _trace(w, x, y, z, y_offset, ignore):
    """One VISIBILITY line trace across the trunk. Returns the HitResult or
    None.

    Only the hit/miss distinction is usable: every FHitResult field is
    protected or absent in the 5.8 Python surface, enumerated 2026-08-16.
    That is why discrimination here is done by RUNNING THE TRACE TWICE with
    the foliage actors ignored, never by inspecting what came back.
    """
    return _u.SystemLibrary.line_trace_single(
        w, _u.Vector(x - REACH_CM, y + y_offset, z),
        _u.Vector(x + REACH_CM, y + y_offset, z),
        _u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, ignore,
        _u.DrawDebugTrace.NONE, True)


try:
    _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _out["in_play"] = bool(_les.is_in_play_in_editor())
    if not _out["in_play"]:
        raise RuntimeError("NOT IN PLAY -- refusing to trace the editor "
                           "world and call it a PIE result")
    w = _ues.get_game_world()
    _out["world"] = w.get_path_name()

    # Group the LOADED foliage components by the mesh they instance. World
    # Partition means only streamed-in cells are here, which is the honest
    # population to test -- it is what the running game actually has.
    by_mesh = {}
    skipped = {}
    _ifas = _u.GameplayStatics.get_all_actors_of_class(
        w, _u.InstancedFoliageActor)
    _out["ifa_count"] = len(_ifas)
    IFAS.extend(_ifas)
    for a in _ifas:
        for comp in a.get_components_by_class(
                _u.InstancedStaticMeshComponent):
            try:
                # get_editor_property("static_mesh"), NOT get_static_mesh().
                # The latter is not reflected on this component in 5.8; it
                # raises, and an `except: continue` around it turns 4,068
                # live components into an empty result that reads like "the
                # world has no foliage" (non-negotiable 23, and 6).
                sm = comp.get_editor_property("static_mesh")
            except Exception as _e:
                skipped["static_mesh: " + str(_e)] = \
                    skipped.get("static_mesh: " + str(_e), 0) + 1
                continue
            if sm is None:
                skipped["static_mesh is None"] = \
                    skipped.get("static_mesh is None", 0) + 1
                continue
            try:
                n = int(comp.get_instance_count())
            except Exception as _e:
                skipped["instance_count: " + str(_e)] = \
                    skipped.get("instance_count: " + str(_e), 0) + 1
                continue
            key = _norm(sm.get_path_name())
            by_mesh.setdefault(key, []).append((comp, n))
    _out["skipped_components"] = skipped

    for key, lst in sorted(by_mesh.items()):
        _out["components_seen"].append(
            {"mesh": key, "components": len(lst),
             "instances": sum(n for _c, n in lst)})

    for sp in SPEC:
        rec = {"species": sp["name"], "mesh": sp["mesh"],
               "want_radius_cm": sp.get("radius_cm"),
               "instances_available": 0, "tested": 0,
               "trunk_hits": 0, "terrain_or_other": 0, "misses": 0,
               "control_hits": 0, "control_misses": 0, "samples": [],
               "radius_probe": []}
        lst = by_mesh.get(_norm(sp["mesh"]), [])
        rec["instances_available"] = sum(n for _c, n in lst)
        if not lst:
            rec["why"] = ("no loaded foliage component instances this mesh; "
                          "COULD NOT LOOK, not a pass")
            _out["species"].append(rec)
            continue

        # Spread the sample across components rather than taking the first
        # N of one, so a single bad component cannot pass for the species.
        picks = []
        for comp, n in lst:
            if n <= 0:
                continue
            step = max(1, n // max(1, PER_SPECIES // max(1, len(lst)) + 1))
            for i in range(0, n, step):
                picks.append((comp, i))
                if len(picks) >= PER_SPECIES:
                    break
            if len(picks) >= PER_SPECIES:
                break

        for comp, i in picks:
            try:
                # POSITIONAL. The proven call in read_instance_transforms
                # is get_instance_transform(i, True).
                t = comp.get_instance_transform(i, True)
            except Exception as _e:
                rec["samples"].append({"i": i, "error": str(_e)})
                continue
            loc = t.translation
            scale = float(t.scale3d.x)
            z = loc.z + TRACE_Z_CM

            s = {"i": i, "scale": round(scale, 3),
                 "loc": [round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)]}

            hit_all = _trace(w, loc.x, loc.y, z, 0.0, [])
            hit_nof = _trace(w, loc.x, loc.y, z, 0.0, IFAS)
            s["hit"] = bool(hit_all)
            s["hit_without_foliage"] = bool(hit_nof)

            if hit_all and not hit_nof:
                rec["trunk_hits"] += 1
                s["verdict"] = "FOLIAGE"
            elif hit_all and hit_nof:
                # Something non-foliage is on this line -- almost certainly
                # the landscape on a slope. It tells us nothing about the
                # trunk either way, so it is counted separately and never
                # as a pass.
                rec["terrain_or_other"] += 1
                s["verdict"] = "OCCLUDED (non-foliage on the line)"
            else:
                rec["misses"] += 1
                s["verdict"] = "MISS"

            # NEGATIVE CONTROL: same XY, above the top of the tree. The
            # instrument must be able to return a miss, or every hit above
            # is meaningless.
            cz = loc.z + 4000.0
            if _trace(w, loc.x, loc.y, cz, 0.0, []) is None:
                rec["control_misses"] += 1
                s["control"] = "miss"
            else:
                rec["control_hits"] += 1
                s["control"] = "HIT"

            # GEOMETRIC RADIUS, from hit/miss alone: step the line sideways
            # until foliage stops being hit. Only run where the axial trace
            # cleanly isolated foliage, so a terrain-occluded line cannot
            # contribute a bogus cutoff.
            if s["verdict"] == "FOLIAGE" and len(rec["radius_probe"]) < 4:
                last_hit = None
                first_miss = None
                for off in OFFSETS:
                    a = _trace(w, loc.x, loc.y, z, off, [])
                    b = _trace(w, loc.x, loc.y, z, off, IFAS)
                    if a is not None and b is None:
                        last_hit = off
                    else:
                        first_miss = off
                        break
                rec["radius_probe"].append({
                    "i": i, "scale": round(scale, 3),
                    "last_hit_offset_cm": last_hit,
                    "first_miss_offset_cm": first_miss,
                })

            rec["tested"] += 1
            rec["samples"].append(s)

        _out["species"].append(rec)

    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out))
'''


def species_spec(recipe):
    out = []
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(sp, dict):
            continue
        system = "instanced" if "role" in sp else sp.get("system", "instanced")
        if system != "instanced":
            continue
        c = sp.get("collision") or {}
        if c.get("enabled") == "none":
            continue
        cap = c.get("capsule") or {}
        out.append({"name": sp.get("name"), "mesh": sp["mesh"],
                    "radius_cm": cap.get("radius_cm")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--per-species", type=int, default=8)
    ap.add_argument("--settle", type=float, default=25.0,
                    help="seconds to let PIE come up and stream before "
                         "tracing")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--keep-playing", action="store_true")
    args = ap.parse_args(argv)

    rp = args.recipe if os.path.isabs(args.recipe) else os.path.join(
        REPO_ROOT, args.recipe)
    with open(rp, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)
    spec = species_spec(recipe)
    if not spec:
        print("REFUSE: the recipe declares no instanced species with "
              "collision enabled; there is nothing to prove.")
        return 2
    print("Species to prove:",
          ", ".join("%s%s" % (s["name"],
                              "" if s["radius_cm"] is None
                              else " (r=%.1f cm)" % s["radius_cm"])
                    for s in spec))

    rc, d, _ = ue_exec.run(BEGIN_PLAY, timeout=args.timeout,
                           stage_name="verify_tree_collision_begin")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("COULD NOT LOOK: begin play failed:",
              (d or {}).get("error"))
        return 1
    if d.get("already"):
        print("NOTE: PIE was ALREADY running before this tool asked. Using "
              "it, but it is not a session this tool controls.")
    print("PIE requested; settling %.0f s ..." % args.settle)
    time.sleep(args.settle)

    payload = (TRACE.replace("__SPEC__", json.dumps(spec))
                    .replace("__PER_SPECIES__", str(int(args.per_species))))
    rc, t, _ = ue_exec.run(payload, timeout=args.timeout,
                           stage_name="verify_tree_collision_trace")

    if not args.keep_playing:
        ue_exec.run(END_PLAY, timeout=args.timeout,
                    stage_name="verify_tree_collision_end", quiet=True)

    if rc == 3:
        # Honour rule 7 from the TRACE stage too (BEGIN_PLAY's rc is guarded
        # earlier; this one was dropped, falling through to exit 1).
        print("REFUSE (rule 7): the trace stage found no verified editor node.")
        return 3
    if t is None:
        print("COULD NOT LOOK: no trace result.")
        return 1
    if t.get("error"):
        print("PAYLOAD ERROR:\n" + t["error"])
        return 1

    print()
    print("PIE world:", t.get("world"))
    print("InstancedFoliageActors loaded:", t.get("ifa_count"))
    print("loaded foliage components by mesh:")
    for c in t["components_seen"]:
        print("   %-70s %2d comp %7d inst"
              % (c["mesh"], c["components"], c["instances"]))
    if t.get("skipped_components"):
        print("components SKIPPED (why, so an empty result is never read as "
              "'the world has no foliage'):")
        for why, n in t["skipped_components"].items():
            print("   %5d  %s" % (n, why))

    print()
    bad = 0
    for r in t["species"]:
        print("%s  (%d instances loaded)" % (r["species"],
                                             r["instances_available"]))
        if r.get("why"):
            print("    %s" % r["why"])
            bad += 1
            continue
        print("    foliage hits %d / %d tested   non-foliage on the line %d"
              "   clean misses %d"
              % (r["trunk_hits"], r["tested"], r["terrain_or_other"],
                 r["misses"]))
        print("    negative control (above the tree): %d missed, %d HIT"
              % (r["control_misses"], r["control_hits"]))
        for p in r["radius_probe"]:
            want = (r["want_radius_cm"] * p["scale"]
                    if r["want_radius_cm"] else None)
            lo = p["last_hit_offset_cm"]
            hi = p["first_miss_offset_cm"]
            if want is None:
                print("    radius bracket: hits to %s cm, misses at %s cm "
                      "(scale %.2f; vendor-authored, no declared value)"
                      % (lo, hi, p["scale"]))
            else:
                ok = (lo is not None and hi is not None
                      and lo <= want <= hi)
                print("    radius bracket: hits to %s cm, misses at %s cm  "
                      "declared x scale = %.1f cm  %s"
                      % (lo, hi, want,
                         "BRACKETS IT" if ok else "does NOT bracket it"))

        if r["trunk_hits"] == 0:
            if r["misses"] == 0 and r["terrain_or_other"] > 0:
                # trunk_hits==0 with NO clean misses and every trace occluded
                # by terrain/other is "could not look", not proven non-collision
                # (this alpine slope occludes readily -- see the docstring).
                print("    *** COULD NOT LOOK: every trace was occluded before "
                      "reaching a trunk -- collision UNVERIFIED, not disproven "
                      "***")
            else:
                print("    *** THIS SPECIES DOES NOT COLLIDE ***")
            bad += 1
        if r["control_hits"]:
            print("    *** NEGATIVE CONTROL HIT — the instrument cannot "
                  "return a miss here, so its hits prove nothing ***")
            bad += 1

    print()
    if bad:
        print("FAILED: %d problem(s)." % bad)
        return 5
    print("PASS — every species registered FOLIAGE collision on the traced "
          "line (foliage vs non-foliage; the hit's mesh IDENTITY is not "
          "readable in 5.8), on the VISIBILITY channel, and every negative "
          "control missed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
