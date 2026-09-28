"""READ-ONLY: which actors SHOULD be resident at a station, per the engine.

Ruled 2026-09-09: the player instrument's residency expectation is DERIVED, not
declared. `benchmark.json` used to carry `expect_landscape_components: 1024`
and later `16`, both typed by hand.

WHY CONTENT AND NOT CELLS. The ruling asked for the set of CELLS intersecting
the loading range. Cell size is unreachable from Python:
`URuntimePartitionLHGrid.cell_size` lives inside
`UWorldPartitionRuntimeHashSet.RuntimePartitions`, which is declared `private:`
without `AllowPrivateAccess` (WorldPartitionRuntimeHashSet.h:256, :262-263), and
`GetFixedGridInfo()` is `WITH_EDITOR` and not a UFUNCTION. Main-partition cells
are not actors, so they leave nothing to measure either. So the expectation is
expressed in the CONTENT the engine says is in range, which is the question the
gate exists for -- was the world there when the frame was taken.

THE ENGINE ANSWERS, not this file.
`UWorldPartitionBlueprintLibrary::GetIntersectingActorDescs`
(WorldPartitionBlueprintLibrary.h:150-151) is a reflected UFUNCTION and takes an
FBox. `FActorDesc` exposes Guid, Name, Label, Bounds, RuntimeGrid and
bIsSpatiallyLoaded, all BlueprintReadOnly (:32-61).

THREE FILTERS, each with a reason:
  bIsSpatiallyLoaded  a non-spatial actor is ALWAYS loaded and is not streamed,
                      so demanding it proves nothing about streaming
  RuntimeGrid empty   HLOD proxies sit on `MainPartition:HLODLayer_*` and
                      stream on their OWN loading range; mixing them in would
                      fail the main grid for a proxy grid's behaviour
  bounds vs SPHERE    GetIntersectingActorDescs takes a BOX, and the loading
                      range is a RADIUS. Without this the corners of the box
                      add actors up to R*sqrt(2) away that the engine never
                      intended to stream.

Run via ue_exec with --set LOC_X=.. LOC_Y=.. LOC_Z=.. RADIUS_CM=..
"""
import json as _json

import unreal as _u

LOC_X = float("__LOC_X__")
LOC_Y = float("__LOC_Y__")
LOC_Z = float("__LOC_Z__")
R = float("__RADIUS_CM__")

_out = {"error": None, "loc_cm": [LOC_X, LOC_Y, LOC_Z], "radius_cm": R}
try:
    _box = _u.Box()
    _box.min = _u.Vector(LOC_X - R, LOC_Y - R, LOC_Z - R)
    _box.max = _u.Vector(LOC_X + R, LOC_Y + R, LOC_Z + R)
    _box.is_valid = True

    # The Python return shape is NOT (bool, array): unpacking to two names
    # raised "too many values to unpack". Captured and inspected instead of
    # guessed a second time.
    _ret = _u.WorldPartitionBlueprintLibrary.get_intersecting_actor_descs(_box)
    _out["_ret_type"] = type(_ret).__name__
    if isinstance(_ret, tuple):
        _out["_ret_len"] = len(_ret)
        _descs = None
        for _part in _ret:
            if isinstance(_part, (list, tuple)) or hasattr(_part, "__len__"):
                if not isinstance(_part, (str, bytes)):
                    _descs = _part
        _out["query_ok"] = bool(_ret[0]) if _ret else None
    else:
        _descs = _ret
        _out["query_ok"] = _descs is not None
    _out["descs_in_box"] = len(_descs) if _descs is not None else 0

    def _sphere_hit(b):
        """EXPECTED only when the desc AABB's FARTHEST corner is inside R.

        TWICE corrected 2026-09-10, both at the 768 m rim, both measured:

        1. The old 2D-XY closest-point claimed "a Z term would drop valid
        cells on the slopes" -- FALSE: the ENGINE's query is a genuine 3D
        sphere (WorldPartitionRuntimeHashSet.cpp:608-611,
        FStaticSpatialIndex::FSphere against 3D cell bounds), so from the
        elevated vista camera 12 in-XY-range actors could never load at
        any warm-up. A 2D expectation against a 3D sphere demands content
        the engine never streams -- the pre-2026-09-09 defect, one
        dimension over.

        2. A 3D CLOSEST-point test still over-demands at the rim: the
        container-class IFAs (grid-level suffix _2) carry desc bounds
        that are FULL 256 m CELL-ALIGNED BOXES, not tight content bounds
        -- measured grazing the sphere by 9-30 m while the engine's
        TIGHT cell-content bounds sit outside. The desc cannot say where
        inside its box the content is, so the only demand the gate may
        make is the one the geometry GUARANTEES: farthest corner inside
        R => the whole box, hence the content and its cell's content
        bounds, is inside the sphere => the engine must load it. Rim
        actors (closest in, farthest out) are counted in skipped["rim"]
        -- NO VERDICT for them, never a demand (the populated-bins
        shape). The expected set is a strict lower bound, which is
        exactly what the subset verdict needs."""
        fx = max(abs(float(b.min.x) - LOC_X), abs(float(b.max.x) - LOC_X))
        fy = max(abs(float(b.min.y) - LOC_Y), abs(float(b.max.y) - LOC_Y))
        fz = max(abs(float(b.min.z) - LOC_Z), abs(float(b.max.z) - LOC_Z))
        return (fx * fx + fy * fy + fz * fz) <= (R * R)

    def _closest_in(b):
        cx = min(max(LOC_X, float(b.min.x)), float(b.max.x))
        cy = min(max(LOC_Y, float(b.min.y)), float(b.max.y))
        cz = min(max(LOC_Z, float(b.min.z)), float(b.max.z))
        dx, dy, dz = cx - LOC_X, cy - LOC_Y, cz - LOC_Z
        return (dx * dx + dy * dy + dz * dz) <= (R * R)

    _expected, _skipped = [], {"not_spatial": 0, "other_grid": 0,
                               "box_only": 0, "rim": 0}
    for _d in (_descs or []):
        # `bIsSpatiallyLoaded` -> `is_spatially_loaded`: UE's Python bindings
        # strip the Hungarian `b` from bool UPROPERTYs. Measured -- the
        # literal `b_is_spatially_loaded` raises "Failed to find property".
        if not _d.get_editor_property("is_spatially_loaded"):
            _skipped["not_spatial"] += 1
            continue
        _grid = str(_d.get_editor_property("runtime_grid"))
        if _grid and _grid not in ("None", ""):
            _skipped["other_grid"] += 1
            continue
        _b = _d.get_editor_property("bounds")
        if not _sphere_hit(_b):
            # rim = desc grazes the sphere but does not fit inside it:
            # NO VERDICT for these, per the docstring above.
            _skipped["rim" if _closest_in(_b) else "box_only"] += 1
            continue
        _expected.append(str(_d.get_editor_property("name")))

    _expected.sort()
    _out["expected_count"] = len(_expected)
    _out["expected_actors"] = _expected
    _out["skipped"] = _skipped
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = _tb.format_exc()[-800:]

print("__LL__" + _json.dumps(_out))
