"""town_kit_plan.py -- offline assembly planner: one town building row -> kit module placements.

    python scripts/town_kit_plan.py --selftest
    python scripts/town_kit_plan.py --demo W D COURSES        (prints one house's pieces)

research/town_kit/DESIGN.md (design review 2026-10-06: instance the full-resolution Nanite modules, one actor
per house). Pure, no editor. A house is built in its own frame: footprint W (local X) x D (local Y), centred on
the origin, base at z = 0; the placer applies the plan row's yaw/loc.

MODULE GEOMETRY (Free/_measured/kit_medievalvillage.json, measured live 2026-08-28):
  walls/doors  pivot at the LEFT end of the face plane; extend +X by their width; every module's bbox min y is
               ~ -15 cm (the shared face plane), thickness grows toward +Y (MB: -15 .. +34). EXTERIOR_SIGN says
               which local Y the exterior faces; -1 = the -Y face (flush plane) is outside. UNCONFIRMED until
               the orientation probe (two instruments); a recipe value, not a guess baked in.
  corner       L, pivot at the corner, arms 100 cm along +X and -Y (bbox x -2.6..100, y -100..2.6).
  course       200 cm (storey_m 2.0, RECIPES 13842).

Each side of length L (snapped to SNAP_CM) is: corner arm (CORNER_ARM_CM) + tiled modules + next corner's arm.
Tiling is EXACT over {300, 200, 150, 100} cm by dynamic programming (no gaps, no overlaps), shuffled by a
seeded RNG for variety. One door per house on the ground course of DOOR_SIDE, replacing a tiled module of the
same width.
"""
import argparse
import math
import random
import sys

import io as _io
import json as _json
import os as _os

# THE single source: recipes/town_kit.json (payload audit F5, roof audit 2026-10-06). Nothing restated here.
RECIPE_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'recipes', 'town_kit.json')
_R = _json.load(_io.open(RECIPE_PATH, encoding='utf-8'))
SNAP_CM = int(_R['snap_cm'])
CORNER_ARM_CM = int(_R['corner_arm_cm'])
COURSE_CM = int(_R['course_cm'])
EXTERIOR_SIGN = int(_R['exterior_sign'])          # confirmed by render, see the recipe's _what
CORNER_YAW_OFFSET = float(_R['corner_yaw_offset_deg'])
EAVE_CM = float(_R['eave_cm'])
ROOF_TOL = float(_R['roof_tol'])
ROOF_DROP_CM = float(_R['roof_drop_cm'])
ROOFS = dict((r['name'], (r['path'], tuple(r['size_cm']))) for r in _R['roofs'] if r.get('usable', True))
GABLE_AXIS = dict((r['name'], r.get('gable_axis')) for r in _R['roofs'])
# each roof mesh's slot-0 material as RECORDED (probe 2026-10-11, _verify/roof_variety/material_probe.json);
# scripts/make_roof_grades.py refuses unless the live mesh agrees
ROOF_MATERIAL = dict((r['name'], r.get('material')) for r in _R['roofs'])
for _r in _R['roofs']:
    # a gable height is gallery-tuned per roof; a default would be an untuned value that looks tuned (rule 12)
    if _r.get('gable_axis') not in (None, 'x', 'y') or (_r.get('gable_axis') and 'gable_z' not in _r):
        raise ValueError('recipes/town_kit.json roof %s: gable_axis must be x/y/absent, and needs gable_z' % _r['name'])
GABLE_Z = dict((r['name'], float(r['gable_z'])) for r in _R['roofs'] if r.get('gable_axis'))
GABLE = _R['gable']
if EXTERIOR_SIGN not in (-1, 1) or ROOF_TOL <= 0 or not ROOFS:
    raise ValueError('recipes/town_kit.json: exterior_sign must be +/-1, roof_tol > 0, roofs non-empty')

WALLS = {300: ["SM_MedievalModularWall3x2M"],
         200: ["SM_MedievalModularWall2x2MD", "SM_MedievalModularWall2x2MG", "SM_MedievalModularWall2x2MH"],
         150: ["SM_MedievalModularWall15x2M"],
         100: ["SM_MedievalModularWall1x2MA"]}
GROUND_100 = "SM_MedievalModularWall1x2MB"   # thick ground-course variant
DOORS = {300: "SM_MedievalModularDoor3x2M", 200: "SM_MedievalModularDoor2x2MA",
         150: "SM_MedievalModularDoor15x2M", 100: "SM_MedievalModularDoor1x2M"}
CORNER = "SM_MedievalModularCornerWall1x2M"


def tile(length_cm, rng):
    """Exact composition of length_cm from {300,200,150,100}; fewest pieces, then shuffled. None if impossible."""
    sizes = (300, 200, 150, 100)
    if length_cm < 0 or length_cm % SNAP_CM:
        return None
    n = length_cm // SNAP_CM
    best = [None] * (n + 1)
    best[0] = []
    for i in range(1, n + 1):
        for s in sizes:
            k = s // SNAP_CM
            if k <= i and best[i - k] is not None:
                cand = best[i - k] + [s]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    out = best[n]
    if out is None:
        return None
    out = list(out)
    rng.shuffle(out)
    return out


def _side_frames(W, D):
    """Four sides, counter-clockwise from above, as (start_xy, unit_dir, outward_normal, length)."""
    hw, hd = W / 2.0, D / 2.0
    return [((-hw, -hd), (1, 0), (0, -1), W),    # south, runs +X
            ((hw, -hd), (0, 1), (1, 0), D),      # east,  runs +Y
            ((hw, hd), (-1, 0), (0, 1), W),      # north, runs -X
            ((-hw, hd), (0, -1), (-1, 0), D)]    # west,  runs -Y


def _yaw_for(u, n):
    """Yaw (deg) that maps module local +X to u and local (EXTERIOR_SIGN * Y) to the outward normal n."""
    yaw = math.degrees(math.atan2(u[1], u[0]))
    # local +Y after rotation by yaw is (-sin, cos); exterior is EXTERIOR_SIGN * that.
    ly = (-math.sin(math.radians(yaw)), math.cos(math.radians(yaw)))
    ext = (EXTERIOR_SIGN * ly[0], EXTERIOR_SIGN * ly[1])
    if round(ext[0] - n[0], 6) or round(ext[1] - n[1], 6):
        raise ValueError("convention cannot map +X->u with exterior->n (u=%s n=%s)" % (u, n))
    return yaw


def _pick(choices, rng, weights):
    """rng.choice when no weights (the shipped RNG stream, byte-identical), else a weighted draw."""
    if not weights:
        return rng.choice(choices)
    w = [float(weights.get(m, 1.0)) for m in choices]
    return rng.choices(choices, weights=w, k=1)[0]


def _symmetric(run):
    """Re-order a tiled run into a palindrome-like rhythm about its centre (largest modules outermost-in pairs),
    so a door placed at the middle candidate is flanked symmetrically. Same multiset, same total length."""
    left, right, mid = [], [], []
    for s in sorted(run, reverse=True):
        if len(left) <= len(right):
            left.append(s)
        else:
            right.append(s)
    if len(left) > len(right):
        mid = [left.pop()]
    return left + mid + list(reversed(right))


def jetty_footprint(W_cm, D_cm, door_side, jetty_cm):
    """(W, D, dx, dy) of an UPPER storey that overhangs the door side by jetty_cm (centre shifted outward)."""
    nx, ny = _side_frames(W_cm, D_cm)[door_side][2]
    return (W_cm + abs(nx) * jetty_cm, D_cm + abs(ny) * jetty_cm, nx * jetty_cm / 2.0, ny * jetty_cm / 2.0)


def plan_house(W_cm, D_cm, courses, door_side=0, seed=0, sub_courses=0, style=None):
    """Return [{'mesh', 'x','y','z' (cm, house frame), 'yaw'}] for walls, doors and corners, plus sub_courses
    foundation courses below z=0 (_plan_foundation).

    style (2026-10-10, Shape Grammar trial ARM C, research/town_kit/SHAPE_GRAMMAR_TRIAL.md) -- None reproduces
    the shipped output byte for byte: VERIFIED ONCE by regenerating all 349 shipped manifest houses equal (commit
    c06fa65c); the selftest does NOT assert it (audit 2026-10-10 F1):
      weights_ground / weights_upper  {mesh: weight} for the 2 m (and other) wall variants per storey band
      symmetric_front                 the door side's run is re-ordered to a symmetric rhythm about the door
      jetty_cm                        upper storeys (course >= 1) overhang the door side by this much"""
    if sub_courses < 0:
        raise ValueError("sub_courses must be >= 0")
    if W_cm % SNAP_CM or D_cm % SNAP_CM:
        raise ValueError("footprint must be snapped to %d cm" % SNAP_CM)
    st = style or {}
    jetty = int(st.get("jetty_cm", 0))
    if jetty < 0 or jetty % SNAP_CM:
        raise ValueError("style.jetty_cm must be a non-negative multiple of %d" % SNAP_CM)
    rng = random.Random(seed)
    pieces = []
    for c in range(courses):
        z = c * COURSE_CM
        Wc, Dc, dx, dy = (jetty_footprint(W_cm, D_cm, door_side, jetty) if jetty and c >= 1
                          else (W_cm, D_cm, 0.0, 0.0))
        wts = st.get("weights_ground") if c == 0 else st.get("weights_upper")
        for si, (p0, u, n, L) in enumerate(_side_frames(Wc, Dc)):
            p0 = (p0[0] + dx, p0[1] + dy)
            # EXTERIOR_SIGN -1: module +X runs along u, pivot at the start of each module.
            # EXTERIOR_SIGN +1: the side is laid BACKWARDS -- module +X along -u, pivot at the far end of each
            # module -- so the module's +Y face points outward (audit 2026-10-06 F4; +1 used to always raise).
            fwd = EXTERIOR_SIGN == -1
            yaw = _yaw_for(u if fwd else (-u[0], -u[1]), n)
            # corner at p0: arms along +u (this side) and back along the previous side.
            pieces.append({"mesh": CORNER, "x": p0[0], "y": p0[1], "z": z, "yaw": yaw + CORNER_YAW_OFFSET,
                           "role": "corner"})
            run = tile(L - 2 * CORNER_ARM_CM, rng)
            if run is None:
                raise ValueError("side %d of %d cm cannot be tiled" % (si, L))
            if st.get("symmetric_front") and si == door_side:
                run = _symmetric(run)
            door_at = None
            if c == 0 and si == door_side:
                cands = [i for i, s in enumerate(run) if s in DOORS]
                door_at = cands[len(cands) // 2] if cands else None
            off = CORNER_ARM_CM
            for i, s in enumerate(run):
                if i == door_at:
                    mesh, role = DOORS[s], "door"
                elif c == 0 and s == 100:
                    mesh, role = GROUND_100, "wall"
                else:
                    mesh, role = _pick(WALLS[s], rng, wts), "wall"
                at = off if fwd else off + s
                pieces.append({"mesh": mesh, "x": p0[0] + u[0] * at, "y": p0[1] + u[1] * at, "z": z,
                               "yaw": yaw, "role": role, "w": s})
                off += s
            if off != L - CORNER_ARM_CM:
                raise AssertionError("side %d does not close: %d vs %d" % (si, off, L - CORNER_ARM_CM))
    pieces.extend(_plan_foundation(W_cm, D_cm, sub_courses))
    if jetty and courses > 1 and st.get("soffit"):
        pieces.extend(_plan_soffit(W_cm, D_cm, door_side, jetty, st["soffit"], seed))
    return pieces


def _plan_soffit(W_cm, D_cm, door_side, jetty, cfg, seed):
    """2026-10-11 jetty soffit: horizontal timber beams side by side closing the underside of the overhang (the upper
    walls' single-sided modules leave it open -- a dark band in townkit_armc01). Beams run along the door side, under
    the FIRST upper course (top of the beam at z = COURSE_CM), spanning the side plus both perpendicular walls'
    exterior thickness. Depths are measured outward from the UPPER storey's perimeter line. Placed with fit='bounds'
    (x, y = bounds centre, z = bounds bottom), so no pivot assumption. A SEPARATE rng: the wall stream is untouched,
    so a house's walls stay byte-identical when soffit is switched on."""
    rng = random.Random(seed * 7919 + 17)
    Wu, Du, dx, dy = jetty_footprint(W_cm, D_cm, door_side, jetty)
    p0, u, n, L = _side_frames(Wu, Du)[door_side]
    p0 = (p0[0] + dx, p0[1] + dy)
    ext = float(cfg["exterior_cm"])                       # how far the walls' exterior sits outside the line
    span0, span1 = -ext, L + ext
    nb = max(1, int(math.ceil((span1 - span0) / float(cfg["beam_length_cm"]))))
    seg = (span1 - span0) / nb
    yaw = math.degrees(math.atan2(u[1], u[0]))
    out = []
    for d in cfg["depths_cm"]:
        for k in range(nb):
            t = span0 + seg * (k + 0.5)
            mp = rng.choice(cfg["meshes"])                    # full package path (outside the Megascans root)
            out.append({"mesh": mp.rsplit("/", 1)[-1], "path": mp, "fit": "bounds",
                        "x": p0[0] + u[0] * t + n[0] * float(d), "y": p0[1] + u[1] * t + n[1] * float(d),
                        "z": COURSE_CM - float(cfg["beam_height_cm"]), "yaw": yaw, "role": "soffit",
                        "scale": [seg / float(cfg["beam_length_cm"]), 1.0, 1.0]})
    return out


def _plan_foundation(W_cm, D_cm, sub_courses):
    """Courses BELOW the floor (z < 0) on sloping ground: the plain brick-based ground module (GROUND_100,
    townkit_lineup02: brick base + ledge, no window) tiled in 100s between corner modules, so the downhill side
    stands on a plinth instead of floating. Buried where the ground is higher; that costs instances, not looks."""
    out = []
    for k in range(1, sub_courses + 1):
        z = -k * COURSE_CM
        for p0, u, n, L in _side_frames(W_cm, D_cm):
            fwd = EXTERIOR_SIGN == -1
            yaw = _yaw_for(u if fwd else (-u[0], -u[1]), n)
            out.append({"mesh": CORNER, "x": p0[0], "y": p0[1], "z": z, "yaw": yaw + CORNER_YAW_OFFSET,
                        "role": "corner"})
            run = L - 2 * CORNER_ARM_CM
            if run <= 0:
                continue
            # count pieces stretched uniformly along X to close the run exactly (a 50 cm remainder would otherwise
            # need the 150 module, which carries a window). round() is half-to-even, so scale = run/(100*count):
            # 50 -> 0.5, 150 -> 0.75, 250 -> 1.25, 350 -> 0.875; within +/-6.25% for runs >= 800 (audit F5)
            count = max(1, int(round(run / 100.0)))
            w = run / float(count)
            for i in range(count):
                off = CORNER_ARM_CM + i * w
                at = off if fwd else off + w
                out.append({"mesh": GROUND_100, "x": p0[0] + u[0] * at, "y": p0[1] + u[1] * at, "z": z,
                            "yaw": yaw, "role": "foundation", "w": w, "scale": [w / 100.0, 1.0, 1.0]})
    return out


# Whole-roof meshes (Free/_measured/kit_medievalvillage_v2.json size_cm, measured live 2026-08-30). Excluded:
# SM_House04 (a whole-house piece, design review item 8), SM_House07_RoofSmall / SM_Roof_05small (porch-scale).
# Roof table, EAVE_CM and ROOF_TOL come from the recipe (loaded at the top of this module).


def plan_roof(W_cm, D_cm, courses, only=None):
    """Best-fitting whole roof: minimise the worst per-axis log scale, both orientations. Returns a piece with
    fit='bounds' (x, y = bounds centre, z = bounds BOTTOM, in the house frame; the payload reads the mesh bounds
    live), or None when no roof is within ROOF_TOL on both axes."""
    if only is not None and only not in ROOFS:
        raise ValueError("unknown roof %r (recipe roofs: %s)" % (only, sorted(ROOFS)))
    tw, td = W_cm + 2 * EAVE_CM, D_cm + 2 * EAVE_CM
    best = None
    for name, (path, (sx, sy)) in ROOFS.items():
        if only is not None and name != only:
            continue
        for yaw, (ax, ay) in ((0.0, (sx, sy)), (90.0, (sy, sx))):
            kx, ky = tw / ax, td / ay
            worst = max(abs(math.log(kx)), abs(math.log(ky)))
            if best is None or worst < best[0]:
                best = (worst, name, path, yaw, kx, ky)
    worst, name, path, yaw, kx, ky = best
    if max(abs(kx - 1), abs(ky - 1)) > ROOF_TOL:
        return None
    # scale is in the MESH frame: with yaw 90 the mesh X runs along house Y
    sx, sy = (kx, ky) if yaw == 0.0 else (ky, kx)
    sz = min(sx, sy)
    return {"mesh": name, "path": path, "x": 0.0, "y": 0.0, "z": courses * COURSE_CM - ROOF_DROP_CM, "yaw": yaw,
            "scale": [sx, sy, sz], "fit": "bounds", "role": "roof"}


def roof_stretch(roof):
    """Worst per-axis plan-scale deviation of a planned roof, |k - 1| over mesh X and Y (the ROOF_TOL measure)."""
    return max(abs(roof["scale"][0] - 1.0), abs(roof["scale"][1] - 1.0))


def _roof_at(W_cm, D_cm, courses, name, yaw):
    """plan_roof's piece for one (roof, yaw in {0, 90}), with no tolerance test -- the same arithmetic."""
    path, (sx, sy) = ROOFS[name]
    ax, ay = (sx, sy) if yaw == 0.0 else (sy, sx)
    kx, ky = (W_cm + 2 * EAVE_CM) / ax, (D_cm + 2 * EAVE_CM) / ay
    mx, my = (kx, ky) if yaw == 0.0 else (ky, kx)
    return {"mesh": name, "path": path, "x": 0.0, "y": 0.0, "z": courses * COURSE_CM - ROOF_DROP_CM, "yaw": yaw,
            "scale": [mx, my, min(mx, my)], "fit": "bounds", "role": "roof"}


def ridge_axis(roof):
    """'x' or 'y': the HOUSE-frame axis the ridge runs along (the gable ends lie on the mesh's gable_axis, so the
    ridge runs along it), through the roof's yaw. None for a roof with no recorded gable_axis."""
    ga = GABLE_AXIS.get(roof["mesh"])
    if not ga:
        return None
    return "x" if (ga == "x") == (roof["yaw"] == 0.0) else "y"


def roof_candidates(W_cm, D_cm, courses, max_stretch):
    """Every usable (roof, yaw 0/90) that fits this footprint with stretch <= max_stretch, sorted by (mesh, yaw),
    PLUS plan_roof's best fit whatever its stretch -- so the list is empty only when plan_roof is None. Both yaws,
    so a footprint near square can take its ridge either way. 2026-10-11 roof variety
    (research/town_kit/ROOF_VARIETY.md)."""
    best = plan_roof(W_cm, D_cm, courses)
    if best is None:
        return []
    out = [r for r in (_roof_at(W_cm, D_cm, courses, n, y) for n in sorted(ROOFS) for y in (0.0, 90.0))
           if roof_stretch(r) <= max_stretch]
    if all((r["mesh"], r["yaw"]) != (best["mesh"], best["yaw"]) for r in out):
        out.append(best)
        out.sort(key=lambda r: (r["mesh"], r["yaw"]))
    return out


def grade_mic_path(grade_dir, roof_mi_path, grade):
    """THE one naming rule for a roof weathering-grade MIC: <grade_dir>/<roof MI asset name>_<grade>. The manifest
    writes it into roof pieces; scripts/make_roof_grades.py creates exactly these assets."""
    return "%s/%s_%s" % (grade_dir, roof_mi_path.rsplit("/", 1)[1], grade)


def _axial_close(a_deg, b_deg, tol_deg):
    d = abs((a_deg - b_deg) % 180.0)
    return min(d, 180.0 - d) <= tol_deg


def pick_roof(cands, house_yaw_deg, neighbours, rng, ridge_tol_deg=45.0):
    """The candidate least like its neighbours: score = neighbours with the same mesh + neighbours whose WORLD ridge
    runs within ridge_tol_deg of this candidate's (house yaw + ridge axis; a roof with no ridge record matches
    nothing). neighbours = [(mesh, world_ridge_deg or None)]. Lowest score wins; a tie is broken by rng over the
    (mesh, yaw)-sorted tied set, so the result depends only on the inputs and the rng state."""
    if not cands:
        raise ValueError("pick_roof: no candidates")

    def score(r):
        w = world_ridge_deg(r, house_yaw_deg)
        return sum((m == r["mesh"]) + (w is not None and d is not None and _axial_close(w, d, ridge_tol_deg))
                   for m, d in neighbours)
    lo = min(score(r) for r in cands)
    tied = sorted((r for r in cands if score(r) == lo), key=lambda r: (r["mesh"], r["yaw"]))
    return tied[rng.randrange(len(tied))]


def world_ridge_deg(roof, house_yaw_deg):
    a = ridge_axis(roof)
    return None if a is None else (house_yaw_deg + (0.0 if a == "x" else 90.0)) % 180.0


def plan_gables(W_cm, D_cm, courses, roof):
    """Gable infills under a roof whose ends are arched (recipe 'gable_axis'). One per end, bounds-seated on the
    wall top at the end-wall plane, scaled along its width to the end wall, visible face outward. [] if the roof
    has no gable_axis."""
    if roof is None or not GABLE_AXIS.get(roof["mesh"]):
        return []
    # mesh-local gable axis -> house axis, through the roof's yaw (0 or 90)
    if roof["yaw"] not in (0.0, 90.0):
        raise ValueError("plan_gables: roof yaw must be 0 or 90, got %r" % roof["yaw"])
    along_x = (GABLE_AXIS[roof["mesh"]] == "x") == (roof["yaw"] == 0.0)
    out = []
    for sgn in (1, -1):
        if along_x:
            n, pos, width = (sgn, 0), (sgn * W_cm / 2.0, 0.0), D_cm
        else:
            n, pos, width = (0, sgn), (0.0, sgn * D_cm / 2.0), W_cm
        # visible face is EXTERIOR_SIGN * local +Y; choose yaw so it points along n
        yaw = math.degrees(math.atan2(-n[0] * EXTERIOR_SIGN, n[1] * EXTERIOR_SIGN))
        k = width / float(GABLE["width_cm"])
        out.append({"mesh": GABLE["name"], "path": GABLE["path"], "x": pos[0], "y": pos[1],
                    "z": courses * COURSE_CM, "yaw": yaw, "scale": [k, 1.0, GABLE_Z[roof["mesh"]]], "fit": "bounds", "role": "gable"})
        if GABLE.get("double_sided"):
            # the Gable4 module is SINGLE-SIDED; where a roof's end frame stands above its thatch you can see
            # past it to the BACK of the far gable, which renders as nothing (2026-10-08, Alpine8K TownKit_008,
            # _verify/lookdev/townkit_alpine03/h008.png). A second copy turned 180 deg on the same bounds-centred
            # pivot faces inward, so the end reads closed from both sides.
            out.append(dict(out[-1], yaw=yaw + 180.0, role="gable_back"))
    return out


def selftest():
    fails = []
    rng = random.Random(1)
    for L in range(0, 1601, 50):
        t = tile(L, rng)
        if L >= 100 or L == 0:
            if t is None or sum(t) != L:
                fails.append("tile(%d) -> %s" % (L, t))
    if tile(50, rng) is not None:
        fails.append("tile(50) must be impossible")
    global EXTERIOR_SIGN
    _saved = EXTERIOR_SIGN
    cases = [(W, D, c, sg) for sg in (-1, 1) for (W, D, c) in ((1500, 1200, 6), (700, 700, 3), (1050, 850, 4))]
    for W, D, c, sg in cases:
        EXTERIOR_SIGN = sg
        try:
            p = plan_house(W, D, c, door_side=2, seed=7)
        except Exception as e:
            fails.append("sign %d %dx%d raised %s" % (sg, W, D, e))
            continue
        # every wall piece's footprint [pivot, pivot + w along +X(yaw)] must lie on its side segment
        for q in p:
            if q["role"] == "corner":
                continue
            ex = q["x"] + math.cos(math.radians(q["yaw"])) * q["w"]
            ey = q["y"] + math.sin(math.radians(q["yaw"])) * q["w"]
            for (px, py) in ((q["x"], q["y"]), (ex, ey)):
                if abs(abs(px) - W / 2.0) > 1e-6 and abs(abs(py) - D / 2.0) > 1e-6:
                    fails.append("sign %d piece off the perimeter at (%.1f, %.1f)" % (sg, px, py))
                    break
        if sum(1 for q in p if q["role"] == "corner") != 4 * c:
            fails.append("corner count")
        if sum(1 for q in p if q["role"] == "door") != 1:
            fails.append("door count %dx%d" % (W, D))
        per_course = {}
        for q in p:
            if q["role"] != "corner":
                per_course[q["z"]] = per_course.get(q["z"], 0) + q["w"]
        want = 2 * (W - 2 * CORNER_ARM_CM) + 2 * (D - 2 * CORNER_ARM_CM)
        if any(v != want for v in per_course.values()) or len(per_course) != c:
            fails.append("perimeter %dx%d: %s want %d" % (W, D, per_course, want))
    EXTERIOR_SIGN = _saved
    # foundation: each sub-course closes the perimeter with GROUND_100 between 4 corners, on the perimeter,
    # visible face outward (same _yaw_for as the walls), and nothing below z=0 without sub_courses
    for W, D, sub in ((1050, 850, 2), (400, 500, 1), (700, 550, 0)):
        p = plan_house(W, D, 2, door_side=1, seed=3, sub_courses=sub)
        below = [q for q in p if q["z"] < 0]
        want = 2 * (W - 2 * CORNER_ARM_CM) + 2 * (D - 2 * CORNER_ARM_CM)
        for k in range(1, sub + 1):
            ring = [q for q in below if q["z"] == -k * COURSE_CM]
            if sum(q.get("w", 0) for q in ring if q["role"] == "foundation") != want \
                    or sum(1 for q in ring if q["role"] == "corner") != 4 \
                    or any(q["role"] == "foundation" and q["mesh"] != GROUND_100 for q in ring):
                fails.append("foundation %dx%d course -%d does not close" % (W, D, k))
        if len(set(q["z"] for q in below)) != sub:
            fails.append("foundation %dx%d: %d sub-course levels, want %d" % (W, D, len(set(q["z"] for q in below)), sub))
        for q in below:
            if q["role"] != "foundation":
                continue
            ex = q["x"] + math.cos(math.radians(q["yaw"])) * q["w"]
            ey = q["y"] + math.sin(math.radians(q["yaw"])) * q["w"]
            if any(abs(abs(px) - W / 2.0) > 1e-6 and abs(abs(py) - D / 2.0) > 1e-6
                   for px, py in ((q["x"], q["y"]), (ex, ey))):
                fails.append("foundation piece off the perimeter %dx%d" % (W, D))
                break
    r = plan_roof(700, 550, 2)
    if r is None or r["mesh"] != "SM_House08_Roof":
        fails.append("roof for 700x550 expected SM_House08_Roof (826x668 vs target 820x670), got %s" % (r and r["mesh"]))
    if plan_roof(1500, 400, 3) is not None:
        fails.append("an unservable 1500x400 footprint must return None")
    # gables: both recipe axes x both roof yaws -- on the end walls the axis names, full end-wall width,
    # the roof's gable_z, visible face (EXTERIOR_SIGN * local +Y) pointing outward
    W, D = 700, 550
    for name in [n for n in ROOFS if GABLE_AXIS.get(n)]:
        for yaw in (0.0, 90.0):
            g = plan_gables(W, D, 2, {"mesh": name, "yaw": yaw})
            along_x = (GABLE_AXIS[name] == "x") == (yaw == 0.0)
            want_n = 4 if GABLE.get("double_sided") else 2
            if len(g) != want_n:
                fails.append("gables %s yaw %g: %d, want %d" % (name, yaw, len(g), want_n))
                continue
            if GABLE.get("double_sided"):
                # each end: one outward + one inward copy at the same point, 180 deg apart
                fronts = [q for q in g if q["role"] == "gable"]
                backs = [q for q in g if q["role"] == "gable_back"]
                if len(fronts) != 2 or len(backs) != 2 or any(
                        (b["x"], b["y"]) != (f["x"], f["y"]) or abs((b["yaw"] - f["yaw"]) % 360 - 180) > 1e-6
                        for f, b in zip(fronts, backs)):
                    fails.append("double-sided gables %s yaw %g are not front/back pairs" % (name, yaw))
            for q in g:
                on = abs(abs(q["x"]) - W / 2.0) < 1e-6 and q["y"] == 0 if along_x else \
                    abs(abs(q["y"]) - D / 2.0) < 1e-6 and q["x"] == 0
                width = q["scale"][0] * float(GABLE["width_cm"])
                ly = (-math.sin(math.radians(q["yaw"])), math.cos(math.radians(q["yaw"])))
                face = (EXTERIOR_SIGN * ly[0], EXTERIOR_SIGN * ly[1])
                outward = (face[0] * q["x"] + face[1] * q["y"] > 0) == (q["role"] == "gable")
                if not on or abs(width - (D if along_x else W)) > 1e-6 or q["scale"][2] != GABLE_Z[name] \
                        or not outward:
                    fails.append("gable %s yaw %g at (%g, %g) on %s width %.1f z %s outward %s"
                                 % (name, yaw, q["x"], q["y"], on, width, q["scale"][2], outward))
    if not any(GABLE_AXIS.get(n) == "y" for n in ROOFS) or not any(GABLE_AXIS.get(n) == "x" for n in ROOFS):
        fails.append("selftest needs a usable roof of each gable axis")
    # independent anchors from the renders (not from GABLE_AXIS): House08 at yaw 0 is gabled on the +/-X end
    # walls (probe06/07), House02 at yaw 0 on the +/-Y walls (gallery01: open triangle facing the -Y door side)
    for name, key, want in (("SM_House08_Roof", "x", W / 2.0), ("SM_House02_Roof", "y", D / 2.0)):
        if name in ROOFS:
            got = sorted(q[key] for q in plan_gables(W, D, 2, {"mesh": name, "yaw": 0.0}) if q["role"] == "gable")
            if got != [-want, want]:
                fails.append("anchor %s yaw 0: gable %s = %s, want +/-%g" % (name, key, got, want))
    # roof variety (2026-10-11): candidates respect the cap, always hold the best fit, empty only when nothing fits;
    # pick_roof prefers the roof the neighbours use least and is a pure function of its inputs
    for W, D in ((700, 550), (800, 800), (500, 450), (750, 850)):
        best = plan_roof(W, D, 2)
        # _roof_at is plan_roof's arithmetic: the best fit must be reproduced exactly
        if _roof_at(W, D, 2, best["mesh"], best["yaw"]) != best:
            fails.append("_roof_at %dx%d does not reproduce plan_roof's piece" % (W, D))
        for cap in (0.0, 0.1, ROOF_TOL):
            cs = roof_candidates(W, D, 2, cap)
            key = [(r["mesh"], r["yaw"]) for r in cs]
            if best not in cs:
                fails.append("roof_candidates %dx%d cap %g lost the best fit" % (W, D, cap))
            if any(roof_stretch(r) > cap and r != best for r in cs):
                fails.append("roof_candidates %dx%d cap %g admitted a roof over the cap" % (W, D, cap))
            if len(set(key)) != len(key) or key != sorted(key):
                fails.append("roof_candidates %dx%d cap %g repeats or is unsorted" % (W, D, cap))
    if roof_candidates(1500, 400, 3, ROOF_TOL) != []:
        fails.append("roof_candidates of an unservable footprint must be []")
    # ridge: House08 at yaw 0 is gabled on the +/-X ends (anchor above) -> ridge along house X; yaw 90 -> Y
    if ridge_axis({"mesh": "SM_House08_Roof", "yaw": 0.0}) != "x" or \
            ridge_axis({"mesh": "SM_House08_Roof", "yaw": 90.0}) != "y" or \
            world_ridge_deg({"mesh": "SM_House08_Roof", "yaw": 90.0}, 30.0) != 120.0:
        fails.append("ridge_axis / world_ridge_deg disagree with the House08 gable anchor")
    multi = roof_candidates(800, 800, 2, ROOF_TOL)
    if len(multi) >= 2:
        a = multi[0]
        wa = world_ridge_deg(a, 0.0)
        # neighbours all share a's mesh AND a's ridge direction: a must lose to any candidate differing in either
        got = pick_roof(multi, 0.0, [(a["mesh"], wa)] * 3, random.Random(5))
        if (got["mesh"], got["yaw"]) == (a["mesh"], a["yaw"]):
            fails.append("pick_roof chose the candidate every neighbour matches")
        if pick_roof(multi, 0.0, [], random.Random(9)) != pick_roof(multi, 0.0, [], random.Random(9)):
            fails.append("pick_roof is not deterministic for a fixed rng seed")
        if not _axial_close(10.0, 175.0, 20.0) or _axial_close(0.0, 90.0, 45.0 - 1e-9):
            fails.append("_axial_close is not axial (mod 180)")
    else:
        fails.append("selftest expects >= 2 roof candidates at 800x800 (got %d)" % len(multi))
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--demo", nargs=3, type=int, metavar=("W_CM", "D_CM", "COURSES"))
    a = ap.parse_args(argv)
    if a.selftest or not a.demo:
        f = selftest()
        print("SELFTEST " + ("PASS" if not f else "FAIL:\n  " + "\n  ".join(f)))
        if f:
            return 1
    if a.demo:
        p = plan_house(*a.demo, door_side=0, seed=1)
        for q in p:
            print(q)
        print("pieces:", len(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
