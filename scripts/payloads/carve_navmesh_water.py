"""carve_navmesh_water.py -- Brief-4 T6: mark the submerged lake footprints
NON-WALKABLE with NavArea_Null modifier volumes, so the post-rebuild navmesh
does not spread across the drowned lakebed.

WHY VOLUMES, NOT A PLANE PROPERTY (R-WATER-CARVE REJECTED). The water planes
are FLAT at the surface; setting can_ever_affect_navigation on them leaves the
lakebed walkable (the plane is thin, above the nav surface). Water
NON-walkability is NavArea_Null modifiers OVER the footprints (RULING §4.5).

HOW THE FOOTPRINT IS REUSED (NN24). The water plane actors already tile each
connected water component (277 surface planes, water/alpine_8k_water_plan.json,
spawn_water_set). This reads each SURFACE plane actor's LIVE world bounds +
location (no sx/sy unit assumption) and drops a NavModifierVolume over the same
XY, extended DOWN in Z to cover the submerged lakebed. Falls (vertical, on the
steep cascade) are NOT carved -- they are not part of the water-body union the
reachable re-measure subtracts (build_water_exclusion_mask unions the 12
SURFACE bodies, not the falls).

Z SPAN: box top AT the water level (no above-water shore carved), 200 m below
(covers Lake A's ~115 m lakebed and every shallower body). The box marks any
nav SURFACE inside it NavArea_Null; empty space below the lakebed is harmless.

IDEMPOTENT: deletes any prior NavNull_* volumes first, so re-running rebuilds
the same set. Refuses off /Game/Alpine8K (rule 11). Reads back area_class and
bounds per volume (rule 12); reports per-body counts (rule 13).

Run:  python scripts/ue_exec.py scripts/payloads/carve_navmesh_water.py \
          --marker __T6_NAVCARVE__ --set GO=1 --timeout 120
Dry-run (GO unset): reports what it WOULD spawn, spawns nothing.
"""
import json
import os
import unreal

_out = {"ok": False, "stage": "start", "spawned": 0, "per_body": {},
        "deleted_prior": 0}
try:
    # ue_exec --set does LITERAL __NAME__ substitution (R-UEEXEC; the
    # spawn_water_set pattern). `--set GO=1` rewrites the __GO__ token to 1;
    # unset, it stays literal and compares False -> DRY-RUN (standing rule 8).
    GO = ("__GO__" == "1")
    _out["go"] = GO

    _sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    _w = _sub.get_editor_world()
    _wn = _w.get_path_name()
    _out["level"] = _wn
    # LOW-5: exact level, not a substring (rule 11 -- the loaded level is the
    # authority, and a partial match could pass on a differently-named map).
    if _wn != "/Game/Alpine8K.Alpine8K":
        _out["error"] = "refuse: loaded level is %s, not /Game/Alpine8K.Alpine8K" % _wn
        print("__T6_NAVCARVE__" + json.dumps(_out)); raise SystemExit(0)

    # Plan lives at a fixed repo path; the payload reads it itself (R-UEEXEC:
    # transforms never travel the transport).
    _repo = r"C:/Users/Admin/UE5LandscapePipeline"
    _plan = json.load(open(os.path.join(_repo, "water",
                                        "alpine_8k_water_plan.json")))
    # SURFACE planes only (role lake or cascade_pool); map label -> level_m.
    _surf = {}
    for s in _plan["surfaces"]:
        lvl = float(s["level_m"])
        for p in s.get("planes", []):
            _surf[p["label"]] = {"level_m": lvl, "lake_id": s["lake_id"],
                                 "key": s["key"]}
    _out["surface_planes_in_plan"] = len(_surf)

    _eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _all = _eas.get_all_level_actors()

    # index the live water SURFACE plane actors + the prior NavNull_ volumes.
    # NO mutation here -- the destroy is gated behind GO (HIGH-1: a GO-unset run
    # must never delete the carve then respawn nothing while reporting ok).
    _out["stage"] = "index"
    _water_actors = {}
    _prior = []
    for _a in _all:
        try:
            _lbl = _a.get_actor_label()
        except Exception:
            continue
        if _lbl.startswith("NavNull_"):
            _prior.append(_a)
        elif _lbl in _surf:
            _water_actors[_lbl] = _a
    _out["water_actors_found"] = len(_water_actors)
    _missing = [l for l in _surf if l not in _water_actors]
    _out["labels_missing_in_world"] = len(_missing)
    _out["missing_sample"] = _missing[:5]

    if not GO:
        _out["stage"] = "dry_run"
        _out["would_spawn"] = len(_water_actors)
        _out["would_delete"] = len(_prior)
        # LOW-4: a dry-run that cannot find every planned footprint is NOT ok.
        _out["ok"] = (_out["labels_missing_in_world"] == 0
                      and len(_water_actors) > 0)
        print("__T6_NAVCARVE__" + json.dumps(_out)); raise SystemExit(0)

    # GO: delete any prior NavNull_* volumes (idempotency), then spawn.
    _out["stage"] = "delete_prior"
    for _a in _prior:
        _eas.destroy_actor(_a)
        _out["deleted_prior"] += 1

    _out["stage"] = "spawn"
    _Z_HALF_CM = 10000.0     # 100 m half-height
    _readback_fail = []
    for _lbl, _a in _water_actors.items():
        _info = _surf[_lbl]
        _level_cm = _info["level_m"] * 100.0
        _origin, _ext = _a.get_actor_bounds(False)   # world AABB, cm (half)
        _tx, _ty = max(_ext.x, 50.0), max(_ext.y, 50.0)
        _loc = unreal.Vector(_origin.x, _origin.y, _level_cm - _Z_HALF_CM)
        _v = _eas.spawn_actor_from_class(unreal.NavModifierVolume, _loc,
                                         unreal.Rotator(0, 0, 0))
        if _v is None:
            _readback_fail.append(_lbl + ":spawn_none")
            continue
        _v.set_actor_label("NavNull_" + _lbl)
        # brush half = 100 cm at scale 1; scale so half-extent == plane half
        _v.set_actor_scale3d(unreal.Vector(_tx / 100.0, _ty / 100.0,
                                           _Z_HALF_CM / 100.0))
        _v.set_editor_property("area_class", unreal.NavArea_Null)
        # READ BACK (rule 12): the applied geometry re-read from the engine,
        # not inferred from the setter. area_class + the box half-extents +
        # the box top at the water level. Any miss -> destroy the volume so no
        # unverified modifier is left in the level (MED-2, MED-3).
        _ac = _v.get_editor_property("area_class")
        _ro, _re = _v.get_actor_bounds(False)
        _geo_ok = (abs(_re.x - _tx) <= 2.0 and abs(_re.y - _ty) <= 2.0
                   and abs((_ro.z + _re.z) - _level_cm) <= 2.0)
        if _ac is None or "NavArea_Null" not in str(_ac):
            _readback_fail.append(_lbl + ":area_class")
            _eas.destroy_actor(_v)
            continue
        if not _geo_ok:
            _readback_fail.append(
                "%s:geo dx=%.1f dy=%.1f topz=%.1f want=%.1f"
                % (_lbl, _re.x, _re.y, _ro.z + _re.z, _level_cm))
            _eas.destroy_actor(_v)
            continue
        _out["spawned"] += 1
        _k = _info["key"]
        _out["per_body"][_k] = _out["per_body"].get(_k, 0) + 1
    _out["readback_failures"] = _readback_fail[:10]
    _out["readback_fail_count"] = len(_readback_fail)
    _out["ok"] = (_out["spawned"] == len(_water_actors)
                  and len(_readback_fail) == 0
                  and _out["labels_missing_in_world"] == 0)
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)

print("__T6_NAVCARVE__" + json.dumps(_out))
