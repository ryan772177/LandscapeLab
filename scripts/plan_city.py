"""plan_city.py -- turn recipes/city.json plus the terrain into placed volumes.

    python scripts/plan_city.py --recipe recipes/city.json

OFFLINE and SEEDED, so it produces the same plan every run and can be replayed
without an editor -- the same contract as `foliage/*.json`: absolute-cm
transforms in a plain JSON file that the placer reads and does not re-derive.

WHAT IT PRODUCES: a MASSING BLOCKOUT. Volumes on terraced pads along a street
network: plan.layout "lattice" (ring-and-spoke, below) or "organic" (least-cost
roads + street-fronted lots, scripts/city_organic.py, 2026-10-10). Not
architecture; see the recipe's own _what_this_is.

THE THINGS IT REFUSES, each because the alternative is a silent defect:

  A PAD THAT NEEDS TOO MUCH CUT OR FILL is dropped, not floated and not buried.
  A building levelled to the mean height under its footprint sits half-buried on
  a slope, and burying is exactly the failure that cost this project a rock
  species (a box-centred pivot buries 50% by construction).

  A FOOTPRINT THAT OVERLAPS ANOTHER is dropped. Checked against every accepted
  building, not against the plot it was drawn from, because plots are drawn in
  polar space and adjacent plots converge toward the centre.

  A PLAN BELOW `gates.min_buildings` EXITS NON-ZERO. A hamlet reported as a city
  is the kind of claim this project logs at two altitudes.

TERRAIN IS READ FROM THE HEIGHTMAP, and that is a stated limitation rather than
a hidden one. The heightmap is what the landscape was BUILT from; the collidable
surface is a different representation and has disagreed with it before, by
p90 30.98 m in the worst case this project has recorded. So the pad heights here
are a PLAN, and the placer re-grounds every volume by engine trace before it is
committed. Non-negotiable 0: two checks that share a source do not corroborate.
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

# ONE DEFINITION OF "CONNECTED", used by the planner that prunes the network and
# by the gate that checks it. Two implementations would be two lists that must
# agree, which is non-negotiable 24 and fails the same way every time.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_city_connectivity import components as street_components  # noqa: E402
import plan_stamp  # noqa: E402
import roof_servability  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def terrain_source_rel(biome_recipe):
    """heightmap.street_flatten.pre_source when declared, else heightmap.source."""
    sf = (biome_recipe.get("heightmap") or {}).get("street_flatten")
    return sf["pre_source"] if sf else biome_recipe["heightmap"]["source"]


class Terrain:
    """Heightmap sampler in world centimetres."""

    def __init__(self, biome_recipe, town=False):
        ls = biome_recipe["landscape"]
        # 2026-10-10 street flattening (FLATTEN_DESIGN.md, review change 2): the TOWN tools (town=True: plan_city,
        # town_kit_manifest, check_organic_plan) plan and trace on the PRE-streets ground, or a re-plan would gate
        # streets on ground already flattened for them. Every other caller (walkable extent, encounters, navmesh
        # tiles, design_pass ...) wants the LIVE map and keeps the default. `source_rel` = the file actually read,
        # which the town tools record and compare (one declaration).
        self.source_rel = terrain_source_rel(biome_recipe) if town else biome_recipe["heightmap"]["source"]
        src = os.path.join(REPO, self.source_rel)
        if not os.path.isfile(src):
            sys.exit("REFUSE: no heightmap at %s" % src)
        self.H = np.asarray(Image.open(src)).astype(np.float64)
        if self.H.ndim != 2:
            sys.exit("REFUSE: heightmap is not single channel")
        self.ox, self.oy, self.oz = [float(v) for v in ls["location_cm"]]
        self.px = float(ls["scale_xy_cm"])
        self.zs = float(ls["z_scale_cm"])
        self.h, self.w = self.H.shape

    def z_cm(self, x_cm, y_cm):
        """Bilinear height in world cm. Clamped at the edges, and CLAMPING IS
        REPORTED by the caller's bounds check rather than hidden here."""
        fx = (np.asarray(x_cm, dtype=np.float64) - self.ox) / self.px
        fy = (np.asarray(y_cm, dtype=np.float64) - self.oy) / self.px
        fx = np.clip(fx, 0, self.w - 1.001)
        fy = np.clip(fy, 0, self.h - 1.001)
        x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int)
        tx = fx - x0; ty = fy - y0
        h00 = self.H[y0, x0]; h10 = self.H[y0, x0 + 1]
        h01 = self.H[y0 + 1, x0]; h11 = self.H[y0 + 1, x0 + 1]
        h = (h00 * (1 - tx) * (1 - ty) + h10 * tx * (1 - ty)
             + h01 * (1 - tx) * ty + h11 * tx * ty)
        return self.oz + (h / 65535.0 - 0.5) * self.zs


def footprint_samples(cx, cy, sx, sy, yaw_deg, n=5):
    """A grid of sample points over a rectangular footprint, in world cm."""
    a = math.radians(yaw_deg)
    ca, sa = math.cos(a), math.sin(a)
    u = np.linspace(-0.5, 0.5, n)
    gu, gv = np.meshgrid(u, u)
    lx = gu * sx; ly = gv * sy
    return cx + lx * ca - ly * sa, cy + lx * sa + ly * ca


def rects_overlap(a, b, gap_cm):
    """Axis-aligned separation test on the two rects' bounding boxes.

    A BOUNDING-BOX TEST IS CONSERVATIVE AND THAT IS DELIBERATE: it can reject a
    pair of rotated buildings that would actually fit, and it can never accept a
    pair that intersects. For a blockout, refusing a legal placement costs one
    building; accepting an illegal one puts two volumes through each other in
    every render.
    """
    return not (a[2] + gap_cm < b[0] or b[2] + gap_cm < a[0]
                or a[3] + gap_cm < b[1] or b[3] + gap_cm < a[1])


def street_seat(T, cx, cy, yaw_deg, len_cm, width_cm):
    """Pitch and roll that seat a flat slab on the local ground plane.

    A street slab is a flat box. Laid on sloping ground with only a yaw it
    touches at its centre and lifts at its ends, which is why
    `city_verify_payload`'s centre trace reports 0.0 cm while the eye sees
    daylight under the edges. Measured over all 838 streets:

        worst corner gap, flat      p50 67.2   p90 140.1   max 441.7 cm
        pitched to the local plane  p50  9.2   p90  26.4   max  56.7 cm
        over 50 cm                  556  ->  4

    The residual after pitching is the terrain's CURVATURE across the slab,
    which a flat box cannot follow at all; removing that needs conforming
    geometry or shorter segments, and is not what this does.

    ONE helper, called by both the ring and the spoke branch. Computing this
    inline twice is the shape non-negotiable 24 forbids: the two would drift
    and nothing would notice, because each branch is internally consistent.
    """
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    hl, hw = len_cm * 0.5, width_cm * 0.5
    local = [(-hl, -hw), (-hl, hw), (hl, -hw), (hl, hw)]
    zs = []
    for dx, dy in local:
        zs.append(float(T.z_cm(cx + dx * c - dy * s, cy + dx * s + dy * c)))
    A = np.array([[dx, dy, 1.0] for dx, dy in local])
    coef, _r, _rk, _sv = np.linalg.lstsq(A, np.array(zs), rcond=None)
    # coef[0] is dz per cm along the slab's own LENGTH, coef[1] across its
    # WIDTH. The mapping to UE's pitch/roll signs is NOT derived here from a
    # convention -- `unreal.Rotator(ROLL, PITCH, YAW)` has been got wrong three
    # times in this project. It is written one way, PLACED, and the corner gaps
    # re-measured in the engine; a wrong sign makes them worse, not better, and
    # the disproof is built into the same operation (non-negotiable 13).
    pitch = math.degrees(math.atan(coef[0]))
    roll = math.degrees(math.atan(coef[1]))
    return round(pitch, 3), round(roll, 3)


def bbox(cx, cy, sx, sy, yaw_deg):
    a = math.radians(yaw_deg)
    hx = (abs(sx * math.cos(a)) + abs(sy * math.sin(a))) * 0.5
    hy = (abs(sx * math.sin(a)) + abs(sy * math.cos(a))) * 0.5
    return (cx - hx, cy - hy, cx + hx, cy + hy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="recipes/city.json")
    ap.add_argument("--biome", default="recipes/alpine_8k.json")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rec = json.load(open(os.path.join(REPO, a.recipe), encoding="utf-8"))
    biome = json.load(open(os.path.join(REPO, a.biome), encoding="utf-8"))
    T = Terrain(biome, town=True)

    site = rec["site"]
    pl = rec["plan"]
    bd = rec["buildings"]
    g = rec["gates"]
    cx0, cy0 = [float(v) for v in site["centre_world_cm"]]
    # The flat core, and how far the town may REACH. Beyond the core the pad
    # gates decide, so the boundary follows the terrain instead of a circle.
    R_core_cm = float(site["usable_radius_m"]) * 100.0
    R_cm = float(pl.get("extent_radius_m", site["usable_radius_m"])) * 100.0
    rng = np.random.default_rng(int(bd["seed"]))

    # ---- street network: rings and spokes --------------------------------
    #
    # STREETS ARE GATED ON THEIR OWN RUN, and separately from the buildings.
    # The first version gated only buildings, and the plan came back with a full
    # circular lattice over ground the buildings had refused -- streets climbing
    # terrain no cart could use, drawn because the ring geometry said so. A
    # building bar cannot speak for a street.
    #
    # A STREET IS GATED THE WAY A BUILDING PAD IS: a grade limit AND an
    # earthmoving limit. Both are needed and neither is sufficient.
    street_max = float(pl.get("max_street_slope_deg", 8.0))
    street_cf_cm = float(pl.get("max_street_cut_fill_m", 1.8)) * 100.0
    gate_ds_cm = (float(pl["street_gate_sample_m"]) * 100.0
                  if "street_gate_sample_m" in pl else None)
    if gate_ds_cm is not None and not gate_ds_cm > 0:
        # 0 was falsy (silent legacy 15 points) and negative silently sampled
        # 15 too (delta re-audit 2026-10-10 F-1)
        raise ValueError("plan.street_gate_sample_m must be > 0, got %r"
                         % pl["street_gate_sample_m"])
    streets = []
    st_rej_grade = 0
    st_rej_cutfill = 0

    def street_gates(mx, my, yaw_deg, seg_len):
        """(grade_deg, cutfill_cm) for one segment.

        GRADE is rise over run END TO END. That is the quantity the 8 deg bar
        was ruled about -- "roughly a 15% grade, about the limit for a cart".

        ⛔ THE PREVIOUS IMPLEMENTATION MEASURED SOMETHING ELSE. It took the MAX
        of six consecutive sample differences along the run, which is a
        ROUGHNESS statistic: one rough 2.5 m sub-interval anywhere condemned the
        whole segment. Over the ungated lattice it read p50 10.54 deg against
        this metric's p50 3.84, on a basin surveyed at MEAN SLOPE 6.25 deg -- so
        it rejected the median segment of ground already certified flat enough
        to hold a town, 883 of 1342, and shredded the network into 155
        disconnected pieces with the town centre stranded in a 22-segment
        fragment. The bar was right; the measurand was not.
        Narrative: LESSONS.md 2026-08-25. Specification: RECIPES.md R-CITY.

        CUT/FILL is the largest deviation of the natural ground from the
        straight run joining the two ends -- the earth moved to build the strip.
        GRADE ALONE IS INSUFFICIENT BY CONSTRUCTION: a segment that dives into a
        gully and climbs out level at the far side has a grade of zero. This is
        the same gate a building pad already carries, because a street is the
        same kind of object -- a levelled surface cut into a slope.
        """
        a2 = math.radians(yaw_deg)
        hl = seg_len * 0.5
        ax, ay = mx - hl * math.cos(a2), my - hl * math.sin(a2)
        bx2, by2 = mx + hl * math.cos(a2), my + hl * math.sin(a2)
        # SAMPLE SPACING, not a fixed count (LESSONS 2026-10-10e: 15 points
        # over 17.9 m read cut/fill 1.58 m where 21/41/81 read 1.96 m).
        # Absent key = the legacy 15 points, so lattice payloads reproduce.
        t = (np.linspace(0.0, 1.0, max(15, int(math.ceil(seg_len / gate_ds_cm)) + 1))
             if gate_ds_cm is not None else np.linspace(0.0, 1.0, 15))
        zz = np.asarray(T.z_cm(ax + (bx2 - ax) * t, ay + (by2 - ay) * t),
                        dtype=np.float64)
        grade = math.degrees(math.atan(abs(float(zz[-1] - zz[0]))
                                       / max(seg_len, 1.0)))
        chord = zz[0] + (zz[-1] - zz[0]) * t
        return grade, float(np.abs(zz - chord).max())

    def street_ok(mx, my, yaw_deg, seg_len):
        """True if the segment passes both gates; counts WHICH gate refused."""
        nonlocal st_rej_grade, st_rej_cutfill
        grade, cf = street_gates(mx, my, yaw_deg, seg_len)
        if grade > street_max:
            st_rej_grade += 1
            return False
        if cf > street_cf_cm:
            st_rej_cutfill += 1
            return False
        return True

    core = float(pl["core_radius_m"]) * 100.0
    spacing = float(pl["ring_spacing_m"]) * 100.0
    # ---- the landmark -----------------------------------------------------
    # COMPUTED BEFORE THE LAYOUT (2026-10-10): it depends only on the plaza and
    # draws no RNG, so the lattice payload is unchanged, and the organic layout
    # can route streets and plots around it. It used to be placed AFTER every
    # street and building and tested against none: the shipped lattice
    # landmark overlaps 2 streets (#707, #718) and the organic plans put 1-2
    # houses inside it (LESSONS 2026-10-10f).
    landmark = None
    lm = rec.get("landmark", {})
    if lm.get("enabled"):
        lx = cx0 + (float(pl["plaza_radius_m"]) * 100.0 + 900.0) * math.cos(math.radians(35.0))
        ly = cy0 + (float(pl["plaza_radius_m"]) * 100.0 + 900.0) * math.sin(math.radians(35.0))
        s = float(lm["footprint_m"]) * 100.0
        px, py = footprint_samples(lx, ly, s, s, 0.0, 5)
        z = T.z_cm(px, py)
        pad = float(z.mean())
        h = float(lm["height_m"]) * 100.0
        lm_cut_fill = round(float(np.abs(z - pad).max()) / 100.0, 3)
        # THE LANDMARK GETS THE SAME CUT/FILL GATE AS EVERY BUILDING
        # (Pass 3 2026-09-16 F5): its cut_fill was recorded and compared
        # against NOTHING, so on a different site it could ship
        # half-buried or floating — the exact refusal the module
        # docstring promises. The shipped site passes (0.797 m vs 1.8),
        # so the committed payload is unchanged by this gate.
        if lm_cut_fill > float(bd["max_pad_cut_fill_m"]):
            sys.exit(
                "REFUSE: the landmark pad needs %.3f m of cut/fill, above "
                "buildings.max_pad_cut_fill_m = %.1f. A landmark that is "
                "half-buried or floating is the docstring's own named "
                "failure. Nothing was written."
                % (lm_cut_fill, float(bd["max_pad_cut_fill_m"])))
        landmark = {
            "kind": "landmark",
            "loc_cm": [round(lx, 1), round(ly, 1), round(pad + h * 0.5, 1)],
            "pad_z_cm": round(pad, 1), "yaw_deg": 0.0,
            "size_cm": [round(s, 1), round(s, 1), round(h, 1)],
            "pad_cut_fill_m": lm_cut_fill}


    # LAYOUT (2026-10-10, Ryan option a): "lattice" (default, the ring-and-spoke network below, payload unchanged)
    # or "organic" (scripts/city_organic.py: least-cost roads + street-fronted plots).
    layout = pl.get("layout", "lattice")
    if layout not in ("lattice", "organic", "image"):
        raise ValueError("plan.layout must be lattice, organic or image")
    o_junctions, o_stats = [], {}
    # "image" (2026-10-10): streets and lots from a town-from-image plan (scripts/city_image.py), same
    # call signatures as city_organic, so every organic branch below applies to it unchanged.
    if layout in ("organic", "image"):
        import city_organic
        if layout == "image":
            import city_image as city_organic  # noqa: F811 -- same interface, different source
        def street_pass(mx, my, yaw_deg, seg_len):
            # the SAME street gate as street_ok, uncounted -- the organic generator calls it once per segment per
            # reroute attempt, and a counter summed over attempts would report refusals no final segment had
            grade, cf = street_gates(mx, my, yaw_deg, seg_len)
            return grade <= street_max and cf <= street_cf_cm
        # the landmark footprint is an obstacle to streets and plots (LESSONS 2026-10-10f)
        o_obstacles = ([(landmark["loc_cm"][0], landmark["loc_cm"][1], landmark["size_cm"][0],
                         landmark["size_cm"][1], landmark["yaw_deg"])] if landmark else [])
        streets, o_junctions, o_stats = city_organic.streets(
            T, pl, cx0, cy0, R_cm, rng, street_pass, street_seat, o_obstacles)
        print("organic    %s" % o_stats)
    for i in (range(int(pl["ring_count"])) if layout == "lattice" else []):
        r = core + i * spacing
        if r > R_cm:
            break
        n_seg = max(24, int(2 * math.pi * r / 1500.0))
        for s in range(n_seg):
            t0 = 2 * math.pi * s / n_seg
            t1 = 2 * math.pi * (s + 1) / n_seg
            mx = cx0 + r * math.cos(0.5 * (t0 + t1))
            my = cy0 + r * math.sin(0.5 * (t0 + t1))
            seg_len = r * (t1 - t0)
            yaw_r = math.degrees(0.5 * (t0 + t1)) + 90.0
            if not street_ok(mx, my, yaw_r, seg_len):
                continue
            _w_cm = float(pl["street_width_m"]) * 100.0
            _pitch, _roll = street_seat(T, mx, my, yaw_r, seg_len, _w_cm)
            streets.append({
                "kind": "ring", "ring": i,
                "loc_cm": [round(mx, 1), round(my, 1),
                           round(float(T.z_cm(mx, my)), 1)],
                "yaw_deg": round(math.degrees(0.5 * (t0 + t1)) + 90.0, 2),
                "pitch_deg": _pitch,
                "roll_deg": _roll,
                "len_cm": round(seg_len, 1),
                "width_cm": _w_cm})
    for s in (range(int(pl["spoke_count"])) if layout == "lattice" else []):
        th = 2 * math.pi * s / int(pl["spoke_count"])
        r0 = float(pl["plaza_radius_m"]) * 100.0
        n_seg = 14
        for k in range(n_seg):
            ra = r0 + (R_cm - r0) * k / n_seg
            rb = r0 + (R_cm - r0) * (k + 1) / n_seg
            rm = 0.5 * (ra + rb)
            mx = cx0 + rm * math.cos(th); my = cy0 + rm * math.sin(th)
            if not street_ok(mx, my, math.degrees(th), rb - ra):
                continue
            _w_cm = float(pl["street_width_m"]) * 100.0
            _pitch, _roll = street_seat(T, mx, my, math.degrees(th),
                                        rb - ra, _w_cm)
            streets.append({
                "kind": "spoke", "spoke": s,
                "loc_cm": [round(mx, 1), round(my, 1),
                           round(float(T.z_cm(mx, my)), 1)],
                "yaw_deg": round(math.degrees(th), 2),
                "pitch_deg": _pitch,
                "roll_deg": _roll,
                "len_cm": round(rb - ra, 1),
                "width_cm": _w_cm})

    # ---- keep only the network that reaches the plaza ---------------------
    #
    # Gating segments one at a time punches holes in a lattice, and a lattice
    # with holes is not a network. Whatever survives in a piece that cannot be
    # walked to from the town centre is a road to nowhere -- it would be placed,
    # rendered, and lie to anyone reading the town from a ridge.
    #
    # KEEP THE CENTRE-ANCHORED COMPONENT, NOT THE LARGEST ONE. Precisely:
    # the component containing the segment whose MIDPOINT is radially
    # nearest the site centre — a PROXY for the plaza; plaza adjacency
    # itself is never checked (Pass 3 2026-09-16 F8: the old "plaza's
    # component" wording overclaimed). The 2026-08-24 note proposed
    # "keep the largest connected component"; measured on the shipped
    # plan the largest held 9.2% of segments and DID NOT CONTAIN THE
    # CENTRE, so that rule would have deleted the town and kept an
    # outlying scrap. The centre is the thing a town is organised
    # around, so the centre defines the network. (The emitted plan text
    # still says "containing the PLAZA" — that string is in the
    # reproducible payload and moves to this wording at the next ruled
    # regeneration.)
    #
    # THE DEFINITION OF "CONNECTED" IS IMPORTED, NOT RE-IMPLEMENTED. The gate
    # `measure_city_connectivity.py` owns it; two copies would be two lists that
    # must agree (non-negotiable 24). Note what that does and does not buy:
    # the gate re-reading this plan proves only that the pruner ran. The
    # INDEPENDENT check is the one taken in the world, from placed actor
    # transforms, which is a different SOURCE for the same definition.
    join_tol_cm = float(pl.get("street_join_tol_m",
                               pl["street_width_m"])) * 100.0
    # organic: join per pair at the mean of the two widths (audit 2026-10-10 F9; measure_city_connectivity owns it)
    wjoin = layout in ("organic", "image")
    if wjoin and streets:
        join_tol_cm = max(float(s["width_cm"]) for s in streets)
    st_pruned = 0
    if streets:
        comps = street_components(streets, join_tol_cm, width_join=wjoin)

        def _r(seg):
            return math.hypot(seg["loc_cm"][0] - cx0, seg["loc_cm"][1] - cy0)

        inner = min(range(len(streets)), key=lambda i: _r(streets[i]))
        home = next(c for c in comps if inner in c)
        keep = set(home)
        st_pruned = len(streets) - len(keep)
        streets = [s for i, s in enumerate(streets) if i in keep]

    # ---- buildings on plots ----------------------------------------------
    accepted, boxes = [], []
    # LATTICE: `on_street` is NEVER INCREMENTED (Pass 3 2026-09-16 F1): street
    # clearance is by PLOT CONSTRUCTION only (r_in/r_out padded by
    # half_street; pad_t), and no building-vs-street overlap check
    # exists — a 0 here is the absence of a measurement, not a verdict.
    # The key stays until the next RULED regeneration (removing it now
    # would change the plan payload roofbias reproduces against).
    # ORGANIC (2026-10-10): city_organic's oriented clearance test DOES
    # increment on_street, so there it is a measurement.
    rej = {"outside_radius": 0, "in_plaza": 0, "pad_cut_fill": 0,
           "pad_slope": 0, "overlap": 0, "on_street": 0}
    # ONE distance for both uses: the whole-town orphan gate below, and the
    # optional per-plot gate (buildings.place_only_near_streets, 2026-10-06 kit
    # town -- small kit footprints fill rim plots the street network never
    # reaches, 21 of 405 = 5.2%, and the whole-town gate refused the plan).
    # The street network is final (pruned) at this point, so the per-plot gate
    # measures the same network the whole-town gate does.
    orphan_cm = float(g.get("max_building_to_street_m", 40.0)) * 100.0
    _sxy = [(s["loc_cm"][0], s["loc_cm"][1]) for s in streets]

    def nearest_street_cm(bx, by):
        return min(math.hypot(bx - px, by - py) for px, py in _sxy)

    # organic plots are fronted ON a street piece by construction, so the per-plot gate never runs there and a
    # far_from_street 0 would be the absence of a measurement (audit 2026-10-10 F3): the key is lattice-only
    near_only = bool(bd.get("place_only_near_streets", False)) and layout == "lattice"
    if layout in ("organic", "image"):
        # organic clashes are counted by what they hit (F4); the lattice dict stays as its payload has it
        rej["in_square"] = 0
        rej["on_landmark"] = 0
    if near_only:
        if not _sxy:
            sys.exit("REFUSE: place_only_near_streets with zero street segments")
        rej["far_from_street"] = 0
    plaza = float(pl["plaza_radius_m"]) * 100.0
    gap = float(bd["gap_min_m"]) * 100.0
    half_street = float(pl["street_width_m"]) * 50.0
    hc = float(bd["height_m"]["centre"]); he = float(bd["height_m"]["edge"])
    fmin = float(bd["footprint_m"]["min"]) * 100.0
    fmax = float(bd["footprint_m"]["max"]) * 100.0

    # Roof servability, from the ONE module that owns the fit test so the
    # planner and the audit cannot drift apart about what "+-20%, roofs may
    # rotate" means.
    _rsc = bd.get("roof_servability") or {}
    rs_on = bool(_rsc.get("enabled"))
    rs_tol = float(_rsc.get("tolerance", 0.20))
    rs_bias = float(_rsc.get("bias", 0.0)) if rs_on else 0.0
    rs_jitter = float(_rsc.get("jitter", 0.5))
    # source "town_kit": the builder's own fit (roof_servability.kit_*), sizes
    # snapped to the kit snap. Absent = the original kit_v2 span test, so a
    # recipe without the key reproduces its old payload unchanged.
    rs_kit = rs_on and _rsc.get("source", "kit_v2") == "town_kit"
    if rs_on and _rsc.get("source", "kit_v2") not in ("kit_v2", "town_kit"):
        raise ValueError("buildings.roof_servability.source must be kit_v2 or town_kit")
    rs_spans = roof_servability.roof_spans() if rs_on and not rs_kit else []
    if rs_kit:
        import town_kit_plan as _tkp
        # every size the snap can record must be one the builder can wall
        # (audit 2026-10-06 F5): bounds on the snap, every snapped side tiles
        if fmin % _tkp.SNAP_CM or fmax % _tkp.SNAP_CM or not all(
                roof_servability.kit_side_tiles(L) for L in
                range(int(fmin), int(fmax) + 1, _tkp.SNAP_CM)):
            raise ValueError("town_kit: footprint_m %.2f-%.2f must be multiples of "
                             "the kit snap and every side between must tile"
                             % (fmin / 100.0, fmax / 100.0))
        # the fit tolerance is the BUILDER's roof_tol; jitter scales it, so
        # city.json `tolerance` is not read under town_kit (F6)
        rs_tol = float(_tkp.ROOF_TOL)
        rs_targets = roof_servability.kit_targets(fmin / 100.0, fmax / 100.0)
        if not rs_targets:
            raise ValueError("town_kit: no usable roof target inside footprint_m")
    else:
        rs_targets = (roof_servability.targets(
            rs_spans, fmin / 100.0, fmax / 100.0, rs_tol) if rs_on else [])

    # ---- the size draw and the building gate, ONE implementation for both layouts (2026-10-10) ----
    # Extracted verbatim from the lattice loop; the lattice calls them in the same order with the same RNG draws,
    # so a "lattice" recipe reproduces its old payload byte for byte (positive control).
    def draw_size():
        # ---- ROOF SERVABILITY BIAS (ruled 2026-08-30, 4b) --------
        # A roof piece is a WHOLE object with a fixed span, unlike the
        # modular walls, so a footprint either takes one at +-tol or it
        # does not. Sampling UNIFORMLY over 7-15 m left only 43.6%
        # servable. `bias` of the draws now come from the servable
        # targets, jittered INSIDE their tolerance band; the rest stay
        # free so the town keeps size variety.
        if rs_targets and rng.random() < rs_bias:
            _name, _tx, _ty = rs_targets[
                rng.integers(0, len(rs_targets))]
            _j = rs_tol * rs_jitter
            sx = _tx * (1.0 + rng.uniform(-_j, _j)) * 100.0
            sy = _ty * (1.0 + rng.uniform(-_j, _j)) * 100.0
            sx = min(max(sx, fmin), fmax)
            sy = min(max(sy, fmin), fmax)
        else:
            sx = rng.uniform(fmin, fmax)
            sy = sx * rng.uniform(1.0 / float(bd["aspect_max"]),
                                  float(bd["aspect_max"]))
            sy = min(max(sy, fmin), fmax)
        if rs_kit:
            # the plan records the footprint the builder will BUILD
            sx = roof_servability.kit_snap_m(sx / 100.0) * 100.0
            sy = roof_servability.kit_snap_m(sy / 100.0) * 100.0
        return sx, sy

    def try_building(bx, by, sx, sy, yaw, d, extra=None, fields=None):
        """The building gate: pad cut/fill, pad slope, overlap (AABB, conservative), optional extra test (organic:
        oriented square/street/house clearance, returning None or the rejection key), height falloff, roof
        candidate. `fields` are merged into the record (organic: door_side). Appends and returns True if accepted."""
        px, py = footprint_samples(bx, by, sx, sy, yaw, 5)
        z = T.z_cm(px, py)
        pad = float(z.mean())
        cut_fill = float(np.abs(z - pad).max()) / 100.0
        if cut_fill > float(bd["max_pad_cut_fill_m"]):
            rej["pad_cut_fill"] += 1
            return False
        span = max(sx, sy)
        slope = math.degrees(math.atan(
            (float(z.max()) - float(z.min())) / max(span, 1.0)))
        if slope > float(bd["max_pad_slope_deg"]):
            rej["pad_slope"] += 1
            return False

        bb = bbox(bx, by, sx, sy, yaw)
        if extra is None:
            if any(rects_overlap(bb, o, gap) for o in boxes):
                rej["overlap"] += 1
                return False
        else:
            why = extra(bx, by, sx, sy, yaw)
            if why is not None:
                rej[why] += 1
                return False

        f = d / R_cm
        h = (hc + (he - hc) * f) * 100.0
        storeys = max(1, int(round(h / (float(bd["storey_m"]) * 100.0))))
        h = storeys * float(bd["storey_m"]) * 100.0

        boxes.append(bb)
        # Record what covers it PER BUILDING, so the audit reads the
        # plan instead of re-deriving the fit and possibly disagreeing
        # with the planner about the same footprint.
        if rs_kit:
            _roof = roof_servability.kit_servable_by(sx / 100.0, sy / 100.0)
        else:
            _roof = (roof_servability.servable_by(
                sx / 100.0, sy / 100.0, rs_spans, rs_tol)
                if rs_spans else None)
        accepted.append({
            "kind": "building",
            # null when NOT MEASURED (servability disabled) —
            # bool(None) read as "measured not-servable" was
            # rule 13's silence-as-verdict, persisted (Pass 3
            # F7; latent — the shipped recipe enables it, so
            # the shipped payload is unchanged)
            "roof_servable": (bool(_roof) if (rs_spans or rs_kit) else None),
            "roof_candidate": _roof,
            "loc_cm": [round(bx, 1), round(by, 1),
                       round(pad + h * 0.5, 1)],
            "pad_z_cm": round(pad, 1),
            "yaw_deg": round(yaw, 2),
            "size_cm": [round(sx, 1), round(sy, 1), round(h, 1)],
            "storeys": storeys,
            "radial_frac": round(f, 3),
            "pad_cut_fill_m": round(cut_fill, 3),
            "pad_slope_deg": round(slope, 2)})
        if fields:
            accepted[-1].update(fields)
        return True

    o_squares, o_plot_stats = [], {}
    if layout in ("organic", "image"):
        def _try(bx, by, sx, sy, yaw, d, extra, fields):
            if d > R_cm:
                rej["outside_radius"] += 1
                return False
            if d < plaza:
                rej["in_plaza"] += 1
                return False
            return try_building(bx, by, sx, sy, yaw, d, extra, fields)
        # fronted along the PRUNED network only (audit F7): a dropped or stranded piece fronts no house
        o_squares, o_plot_stats = city_organic.plots(pl, bd, streets, o_junctions, o_obstacles, cx0, cy0, plaza, rng,
                                                     draw_size, _try)

    n_rings = int(pl["ring_count"]) if layout == "lattice" else 0
    n_spokes = int(pl["spoke_count"])
    per_plot = int(pl.get("candidates_per_plot", 3))
    for i in range(n_rings):
        r_in = core + i * spacing + half_street
        r_out = core + (i + 1) * spacing - half_street
        if r_in >= R_cm:
            break
        r_out = min(r_out, R_cm)
        for s in range(n_spokes):
            t_in = 2 * math.pi * s / n_spokes
            t_out = 2 * math.pi * (s + 1) / n_spokes
            for _ in range(per_plot):
                rr = rng.uniform(r_in, r_out)
                # keep clear of the spoke centrelines
                pad_t = half_street / max(rr, 1.0)
                tt = rng.uniform(t_in + pad_t, t_out - pad_t) if \
                    (t_out - t_in) > 2 * pad_t else 0.5 * (t_in + t_out)
                bx = cx0 + rr * math.cos(tt)
                by = cy0 + rr * math.sin(tt)
                d = math.hypot(bx - cx0, by - cy0)
                if d > R_cm:
                    rej["outside_radius"] += 1
                    continue
                if d < plaza:
                    rej["in_plaza"] += 1
                    continue
                # tested AFTER the plot draws and BEFORE the size draws, so a
                # recipe without the flag consumes the RNG exactly as before
                if near_only and nearest_street_cm(bx, by) > orphan_cm:
                    rej["far_from_street"] += 1
                    continue
                sx, sy = draw_size()
                # sx axis tangential to the ring; the LONG axis may be
                # either — sy = sx * uniform(1/aspect, aspect) exceeds sx
                # ~65% of the time, so most long axes are RADIAL (Pass 3
                # 2026-09-16 F4: the old "long axis tangential" claim had
                # the majority case backwards; swapping axes now would
                # change the reproducible payload, so the comment moves
                # to the truth and the geometry stays).
                yaw = math.degrees(tt) + 90.0 + rng.uniform(-8.0, 8.0)
                try_building(bx, by, sx, sy, yaw, d)

    # ---- roofs -----------------------------------------------------------
    #
    # A GABLE PER BUILDING, ridge along the LONG axis. The gable is one Cube
    # rolled 45 degrees about that axis, so its square cross-section stands on a
    # corner: the upper two faces are the roof at 45 degrees, the lower half is
    # inside the building and never seen.
    #
    # THE GEOMETRY, because the placer must not re-derive it:
    #   W_o = width + 2*eaves           the oversailing width
    #   the rolled cube's local Y and Z are BOTH W_o/sqrt(2), so after the roll
    #   its half-height is exactly W_o/2 -- that is the ridge height above the
    #   eaves line, and it is why a 45 degree roof needs no trigonometry here.
    #   centre sits at the TOP OF THE WALL, so half the diamond is buried.
    #
    # The ridge runs along whichever footprint axis is longer. A building whose
    # long axis is Y gets ridge_yaw = yaw + 90, with the two extents swapped,
    # rather than a second code path.
    rf = rec.get("roofs", {})
    roofs = []
    if rf.get("enabled", False) and accepted:
        eaves = float(rf.get("eaves_overhang_m", 0.7)) * 100.0
        gable = float(rf.get("gable_overhang_m", 0.4)) * 100.0
        for b in accepted:
            bsx, bsy, bsz = b["size_cm"]
            if bsx >= bsy:
                ridge_len, width, ridge_yaw = bsx, bsy, b["yaw_deg"]
            else:
                ridge_len, width, ridge_yaw = bsy, bsx, b["yaw_deg"] + 90.0
            w_o = width + 2.0 * eaves
            side = w_o / math.sqrt(2.0)
            roofs.append({
                "kind": "roof",
                # loc_cm z is a COPY of the building CENTRE (wall
                # mid-height) — only x,y are meaningful; eaves_z_cm is
                # the placement height and the placer rebuilds Z from it
                # (city_place_payload.txt). At the next ruled regen this
                # field should record eaves_z_cm (Pass 3 2026-09-16 F3;
                # changing it now would change the reproducible payload).
                "loc_cm": [b["loc_cm"][0], b["loc_cm"][1], b["loc_cm"][2]],
                "pad_z_cm": b["pad_z_cm"],
                "eaves_z_cm": round(b["pad_z_cm"] + bsz, 1),
                "yaw_deg": round(ridge_yaw % 360.0, 2),
                "roll_deg": 45.0,
                "size_cm": [round(ridge_len + 2.0 * gable, 1),
                            round(side, 1), round(side, 1)],
                "ridge_height_cm": round(w_o * 0.5, 1)})

    # ---- the spire -------------------------------------------------------
    # A cone on the tower, so the landmark reads as a CHURCH and not a silo.
    spire = None
    lmk = rec.get("landmark", {})
    if landmark and lmk.get("enabled", False) and lmk.get("spire_height_m"):
        _lsx, _lsy, _lsz = landmark["size_cm"]
        spire = {
            "kind": "spire",
            "loc_cm": list(landmark["loc_cm"]),
            "pad_z_cm": landmark["pad_z_cm"],
            "base_z_cm": round(landmark["pad_z_cm"] + _lsz, 1),
            "yaw_deg": 0.0,
            "size_cm": [round(_lsx * 0.98, 1), round(_lsy * 0.98, 1),
                        round(float(lmk["spire_height_m"]) * 100.0, 1)]}

    zs = [b["pad_z_cm"] for b in accepted]
    # which fit test filled roof_candidate (audit 2026-10-06 F2); only under
    # town_kit, so a kit_v2 recipe's payload is unchanged
    _roof_src = ({"roof_fit_source": "town_kit",
                  "_roof_recipe": "recipes/town_kit.json",
                  "_roof_fit": "scripts/town_kit_plan.py",
                  # decides every snapped size and tileable side (re-audit F1)
                  "_roof_snap": "scripts/roof_servability.py"} if rs_kit else {})
    # organic layout record (2026-10-10): only under "organic", so a lattice payload is unchanged
    _org = ({"layout": layout, "_layout_code": "scripts/city_organic.py" if layout == "organic" else "scripts/city_image.py",
             "_water_mask": getattr(city_organic, "WATER_REL", None),
             **({"_image_plan": (pl.get("image") or {}).get("plan_json")} if layout == "image" else {}),
             "squares": [list(sq) for sq in o_squares],
             "organic_stats": dict(o_stats, plots=o_plot_stats)} if layout in ("organic", "image") else {})
    plan = {
        **_roof_src,
        **_org,
        "_produced_by": "scripts/plan_city.py",
        "_recipe": a.recipe, "_biome": a.biome,
        "_terrain_source": T.source_rel,      # the file Terrain read (pre_source when street_flatten is declared)
        "_heights_are_a_PLAN": (
            "pad heights come from the HEIGHTMAP. The collidable surface is a "
            "different representation and has disagreed with it before; the "
            "placer re-grounds every volume by engine trace."),
        "city_id": rec["city_id"], "level_path": rec["level_path"],
        "seed": int(bd["seed"]),
        "site_centre_cm": [cx0, cy0],
        "usable_radius_cm": R_core_cm,
        "extent_radius_cm": R_cm,
        # The plaza is a DECLARED CIRCLE and consumers need its size. The
        # planner already rejects buildings inside it; the foliage clear needs
        # the same disc to reach the one part of the town a per-structure clear
        # never can. Recording it HERE rather than having each consumer re-read
        # `recipes/city.json` keeps the plan self-describing: everything else
        # the clear uses comes from the plan, and a radius fetched from a recipe
        # that may have moved since would be a second source for one fact.
        "plaza_radius_cm": float(pl["plaza_radius_m"]) * 100.0,
        # organic: the street gate is called uncounted (street_pass), so the two
        # refusal counters would be unincremented zeros printed as measurements
        # (re-audit 2026-10-10 F5); its refusals are organic_stats.why instead
        "counts": {k: v for k, v in (
                   ("buildings", len(accepted)),
                   ("roofs", len(roofs)),
                   ("spire", 1 if spire else 0),
                   ("streets", len(streets)),
                   ("streets_rejected_grade", st_rej_grade),
                   ("streets_rejected_cutfill", st_rej_cutfill),
                   ("streets_pruned_disconnected", st_pruned),
                   ("landmark", 1 if landmark else 0))
                   if layout == "lattice" or k not in (
                       "streets_rejected_grade", "streets_rejected_cutfill")},
        "_street_counts_are_separate": (
            "grade and cut/fill are counted apart because they refuse for "
            "different physical reasons, and a single total cannot say which "
            "bar is binding. The shipped metric before 2026-08-25 reported one "
            "number, 883, and it read as difficult terrain when it was a "
            "roughness statistic standing in for a grade."),
        "_street_network_is_one_piece": (
            "streets are pruned to the connected component containing the "
            "PLAZA. Segments in any other piece cannot be walked to from the "
            "town centre and are dropped rather than placed."),
        "rejected": rej,
        "_rejected_is_reported": (
            "a planner that silently drops candidates cannot be told apart "
            "from one that never generated them"),
        "pad_z_cm": {"min": round(min(zs), 1), "max": round(max(zs), 1),
                     "spread": round(max(zs) - min(zs), 1)} if zs else None,
        "buildings": accepted,
        "landmark": landmark,
        "spire": spire,
        "roofs": roofs,
        "streets": streets,
    }

    # ---- EVERY GATE RUNS BEFORE THE WRITE ---------------------------------
    #
    # ⛔ THEY USED TO RUN AFTER IT, and that is strictly worse than having no
    # gate at all. A refused run wrote the plan and THEN exited 1, so
    # `city/<id>_plan.json` -- the exact file `city_place_payload.txt` reads --
    # was left holding the REFUSED plan. Measured 2026-08-25: a run refused at
    # 10 street segments had already written all 10 to disk. The exit code is
    # transient and lives in one shell; the bad file is durable and is what the
    # next step consumes.
    #
    # This is LESSONS Division 3's "a refusal that MUTATED AND SAVED before
    # printing REFUSE", found in our own planner. Refusing before touching
    # anything leaves the previous good plan in place, which is a state a
    # caller can actually recover from.
    if len(accepted) < int(g["min_buildings"]):
        sys.exit("REFUSE: %d buildings is below gates.min_buildings=%d -- that "
                 "is a hamlet, not a city. Nothing was written."
                 % (len(accepted), g["min_buildings"]))

    # THE PRUNER'S CLAIM IS ASSERTED, NOT PRINTED. Non-negotiable 25: a message
    # saying "the network is one piece" is a belief compiled into text, and
    # nothing re-checks it when the code changes underneath. This re-derives it.
    if streets:
        n_comp = len(street_components(streets, join_tol_cm, width_join=wjoin))
        if n_comp != 1:
            sys.exit("REFUSE: the pruned street network is %d components, not "
                     "1. The prune did not do what it claims and the plan would "
                     "ship roads to nowhere. Nothing was written." % n_comp)

    # ---- WHOLE-NETWORK GATE: is every building ON the network? -----------
    #
    # ⛔ THE DEFECT THIS EXISTS FOR. The town's extent was drawn by PER-STRUCTURE
    # gates -- cut/fill and pad slope, each building judged alone. Every building
    # passed its own bar and the town reached onto ground that cannot be walked
    # to: measured against the built navmesh, 185 of 838 streets and 50 of 303
    # buildings are unreachable from the town's own plaza.
    #
    # Per-element gates say NOTHING about the whole. This is the same lesson the
    # street network already taught one level down, and it is why the streets are
    # pruned to one component above.
    #
    # THIS IS AN OFFLINE PROXY, AND IT IS LABELLED ONE. A building adjacent to
    # the pruned (connected) street network is reachable BY CONSTRUCTION of the
    # street graph. It cannot see a navmesh step, so it is necessary and not
    # sufficient -- scripts/reachability.py against the BUILT navmesh remains the
    # authority. It catches the class that produced this town: structures placed
    # beyond where the network reaches.
    orphans = []
    # ZERO STREETS REFUSES HERE (Pass 3 2026-09-16 F2): with streets ==
    # [], this loop, the prune, and the one-component re-derivation all
    # silently skip, frac_orphan evaluates 0.0, and the network print
    # would claim a PASSING whole-network verdict over ZERO street
    # samples (rule 13). The min_street_segments backstop defaults to 0
    # when the recipe omits it, so it cannot be relied on alone.
    if accepted and not streets:
        sys.exit("REFUSE: zero street segments survived, so the network "
                 "verdict has NOTHING to measure — a passing verdict over "
                 "zero samples is silence wearing agreement's clothes. "
                 "Nothing was written.")
    if streets and accepted:
        for bi, b in enumerate(accepted):
            bx, by = b["loc_cm"][0], b["loc_cm"][1]
            best = nearest_street_cm(bx, by)
            if best > orphan_cm:
                orphans.append({"building": bi,
                                "nearest_street_m": round(best / 100.0, 1)})
    frac_orphan = (len(orphans) / float(len(accepted))) if accepted else 0.0
    max_frac = float(g.get("max_orphan_building_fraction", 1.0))
    # distance is building centre to street segment MIDPOINTS (~32 m
    # segments, so it can overstate by up to ~16 m — conservative: it
    # over-orphans, never under; Pass 3 2026-09-16 F6). The print names
    # the measurand and the street sample count (rule 13).
    print("network    %d of %d buildings within %.0f m of the connected "
          "street network (midpoint metric, %d street segments sampled; "
          "%d orphaned, %.1f%%)"
          % (len(accepted) - len(orphans), len(accepted), orphan_cm / 100.0,
             len(streets), len(orphans), 100.0 * frac_orphan))
    if near_only:
        # audit 2026-10-06 F7: with the per-plot gate on, this re-check uses the
        # SAME function, threshold and centre point -- it is not independent
        # (non-negotiable 0); reachability.py on the built navmesh is.
        print("network    NOTE: enforced per plot by the same nearest_street_cm "
              "(%d plots rejected far_from_street); the line above is a re-check "
              "of that filter, NOT an independent measurement"
              % rej["far_from_street"])
    if layout == "organic":
        # audit 2026-10-10 F2: every organic house is fronted on a pruned piece, so this gate is near-vacuous by
        # construction; reachability.py on the built navmesh is the measurement
        print("network    NOTE: organic houses are street-fronted by construction -- the line above re-checks the "
              "construction, it is NOT an independent measurement")
    if frac_orphan > max_frac:
        sys.exit(
            "REFUSE: %.1f%% of buildings are further than %.0f m from the "
            "connected street network, above gates.max_orphan_building_fraction"
            " = %.1f%%. Per-structure pad gates passed them; the WHOLE did not. "
            "Nothing was written."
            % (100.0 * frac_orphan, orphan_cm / 100.0, 100.0 * max_frac))

    min_seg = int(g.get("min_street_segments", 0))
    if len(streets) < min_seg:
        sys.exit("REFUSE: %d street segments is below "
                 "gates.min_street_segments=%d. A connected network that small "
                 "is a lane, not a town -- and a prune that collapses to it "
                 "means the gates upstream shredded the lattice. Nothing was "
                 "written." % (len(streets), min_seg))

    # STAMP THE INPUTS, AFTER every gate and immediately before the write.
    # Non-negotiable 20: an adopted artefact is hash-proven against its source
    # at adoption time. Without this a plan carries its inputs' PATHS and not
    # their HASHES, and "is this plan current" is answerable only by re-running
    # the producer -- which is how encounters/alpine_8k_all.json came to sit in
    # the repo carrying five encounters its producer had stopped generating.
    # plan_stamp REFUSES rather than stamping around an input it cannot read.
    plan[plan_stamp.STAMP_KEY] = plan_stamp.stamp(plan, REPO)
    # R5 (E-4): the CONSUMED-FIELD stamp — reviewed against the reads,
    # cited (granularity floor: at or above what the code touches):
    #   city.json: site :170, plan :171, buildings :172, gates :173,
    #     landmark :266/:691, roofs :658, city_id :726/:904,
    #     level_path :726  (re-cited 2026-10-10 after the landmark move)
    #   biome recipe: landscape + heightmap (Terrain.__init__ :61-:62,
    #     _terrain_source :721)
    # A recipe edit outside these fields no longer stales this plan.
    plan[plan_stamp.CONSUMED_KEY] = plan_stamp.consumed_stamp(plan, REPO, {
        "_recipe": ["site", "plan", "buildings", "gates", "landmark",
                    "roofs", "city_id", "level_path"],
        "_biome": ["landscape", "heightmap"],
    })

    out = a.out or os.path.join("city", "%s_plan.json" % rec["city_id"])
    op = os.path.join(REPO, out)
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2)

    print("city   %s" % rec["city_id"])
    print("site   centre (%.0f, %.0f) cm   usable radius %.0f m"
          % (cx0, cy0, R_cm / 100.0))
    print("built  %d buildings, %d street segments, %d landmark"
          % (len(accepted), len(streets), 1 if landmark else 0))
    # 45.0 is the CONSTRUCTED angle (the rolled-cube geometry is only
    # valid at 45; roll_deg is the literal) — printing the recipe's
    # pitch_deg reported a value the construction never reads (Pass 3
    # 2026-09-16 F9, rule 12's shape).
    print("roofs  %d gables at %.0f deg, ridge %.1f..%.1f m above the eaves; "
          "spire %s"
          % (len(roofs), 45.0,
             min([r["ridge_height_cm"] for r in roofs]) / 100.0 if roofs else 0,
             max([r["ridge_height_cm"] for r in roofs]) / 100.0 if roofs else 0,
             "yes" if spire else "no"))
    if layout == "lattice":
        print("street %d refused on grade, %d on cut/fill, %d pruned as "
              "unreachable from the plaza"
              % (st_rej_grade, st_rej_cutfill, st_pruned))
    elif layout == "image":
        print("street image pieces dropped by gate %d of %d, outside radius %d; %d pruned as unreachable from the plaza"
              % (o_stats.get("dropped_by_gate", 0), o_stats.get("source_streets", 0), o_stats.get("outside_radius", 0), st_pruned))
    else:
        print("street organic pieces failed %d %s (detoured or truncated, "
              "never placed); %d pruned as unreachable from the plaza"
              % (o_stats["pieces_failed"], o_stats["why"], st_pruned))
    # a real if/else: the old conditional EXPRESSION evaluated the bare
    # string 'pads   none' and discarded it — the else branch never
    # printed (Pass 3 2026-09-16 F10).
    if zs:
        print("pads   z %.1f .. %.1f cm  (spread %.1f cm over the site)"
              % (plan["pad_z_cm"]["min"], plan["pad_z_cm"]["max"],
                 plan["pad_z_cm"]["spread"]))
    else:
        print("pads   none")
    print("reject %s" % rej)
    print("wrote  %s" % out)

    # (every gate now runs BEFORE the write, above -- see the note there)


if __name__ == "__main__":
    # GUARDED so this module can be IMPORTED for its Terrain sampler without
    # rewriting the plan as a side effect. Added 2026-08-25: measuring the
    # street network needed the same heightmap sampler, and the alternative was
    # a SECOND COPY of it -- non-negotiable 19, one physical fact defined once
    # and read by every consumer. An unguarded main() makes reuse impossible and
    # makes `import plan_city` a destructive act.
    main()
