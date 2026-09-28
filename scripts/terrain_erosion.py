"""terrain_erosion.py — hydraulic erosion, de-spiking and hillshade.

LOCAL ONLY. Pure numpy/scipy. Contacts no editor, writes no file; every
function takes an array and returns arrays. `make_alpine_terrain.py` owns
the pipeline and the file writing, this owns the maths.

Split out rather than pasted into the generator for two reasons: the
generator is already 500 lines of noise synthesis, and the flow and
deposition maps produced here are consumed by a SECOND script
(`make_layer_weightmap` / the material builder, Priority 2 of the
2026-08-01 aesthetic brief). Two callers means one home (lesson 1.9).

WHY PARTICLE EROSION AT ALL
The generator already had thermal erosion, which caps slopes at the angle
of repose and gives straight scree faces. What it could not do is carve:
thermal erosion moves material downhill uniformly, so it produces smooth
lobes with no channels. The 2026-08-01 read of the captures put it
plainly — "no gullies, couloirs, spurs, talus fans, or flow-carved
ridges — the single biggest tell that this is procedural."

Water is what makes those. Droplets concentrate along paths, and the
concentration is the point: a channel exists because many droplets chose
the same route, which is a thing only a particle model reproduces.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def despike(h, k=4.0):
    """Remove single-cell outliers. Returns (field, cells replaced).

    THE DEFECT THIS FIXES, named in the 2026-08-01 capture read: "dark
    spike artifacts on ridgelines (small black triangles along the crest
    and mid-slope)". A lone cell far from its neighbours makes a
    near-vertical micro-face whose shaded normal points away from the
    light, so at kilometre distance it reads as a dark speck, not terrain.

    Median-filter, then replace ONLY cells whose deviation from that
    median exceeds k standard deviations of the deviation itself. A
    blanket median filter would also round off every genuine ridge crest —
    the exact shape the generator exists to produce — so the selectivity
    is the whole point, not a refinement.
    """
    med = ndimage.median_filter(h, size=3, mode="nearest")
    dev = h - med
    sigma = float(dev.std())
    if sigma <= 0.0:
        return h, 0
    spikes = np.abs(dev) > (k * sigma)
    return np.where(spikes, med, h), int(spikes.sum())


def hydraulic_droplets(h, rng, count=120000, lifetime=48, inertia=0.05,
                       capacity_factor=8.0, erode_rate=0.30,
                       deposit_rate=0.30, evaporate=0.02, gravity=4.0,
                       min_slope=0.0005, smooth=0.6):
    """Particle hydraulic erosion. Returns (height, flow, deposition).

    VECTORISED OVER DROPLETS, NOT OVER TIME. Every droplet takes step 1
    together, then step 2, and so on. A per-droplet Python loop at 2017^2
    with 10^5 droplets runs for minutes; this runs in seconds, and the
    physics is unchanged because droplets interact only through the shared
    heightmap — never with each other.

    The two byproducts are as valuable as the heights, which is why they
    are returned rather than thrown away:

      FLOW        accumulated water through each cell. Channels — for the
                  material to darken and desaturate rock (water staining).
      DEPOSITION  sediment dropped. Scree aprons and valley fill — for the
                  material to lighten and warm.

    Scatter-add uses `np.bincount` on flattened indices rather than
    `np.add.at`. Same result; `add.at` is roughly an order of magnitude
    slower and this runs four times per step, so it is the whole runtime.

    Erosion and deposition are applied BILINEARLY across the four corner
    cells, not dumped into the nearest one. Dumping into one cell is how a
    droplet simulation creates the very single-cell spikes `despike` then
    has to remove.
    """
    n = h.shape[0]
    field = h.astype(np.float64, copy=True)
    flow = np.zeros((n, n), dtype=np.float64)
    depo = np.zeros((n, n), dtype=np.float64)
    cells = n * n

    # Start in the interior so a droplet always has a full 2x2 patch.
    px = rng.uniform(1.0, n - 3.0, size=count)
    py = rng.uniform(1.0, n - 3.0, size=count)
    dx = np.zeros(count)
    dy = np.zeros(count)
    speed = np.ones(count)
    water = np.ones(count)
    sediment = np.zeros(count)
    alive = np.ones(count, dtype=bool)

    for _ in range(lifetime):
        if not alive.any():
            break
        ix = np.clip(px.astype(np.int64), 0, n - 2)
        iy = np.clip(py.astype(np.int64), 0, n - 2)
        fx = px - ix
        fy = py - iy

        h00 = field[iy, ix]
        h10 = field[iy, ix + 1]
        h01 = field[iy + 1, ix]
        h11 = field[iy + 1, ix + 1]
        height = (h00 * (1 - fx) * (1 - fy) + h10 * fx * (1 - fy)
                  + h01 * (1 - fx) * fy + h11 * fx * fy)
        gx = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
        gy = (h01 - h00) * (1 - fx) + (h11 - h10) * fx

        # Inertia blends the previous direction with the downhill
        # gradient. At 0 the droplet follows steepest descent exactly and
        # channels come out grid-aligned; a little inertia lets it cut
        # across contours the way real water does.
        dx = dx * inertia - gx * (1.0 - inertia)
        dy = dy * inertia - gy * (1.0 - inertia)
        mag = np.sqrt(dx * dx + dy * dy)
        moving = mag > 1e-9
        dx = np.where(moving, dx / np.maximum(mag, 1e-9), 0.0)
        dy = np.where(moving, dy / np.maximum(mag, 1e-9), 0.0)

        nx = px + dx
        ny = py + dy
        # Retired at the border, never wrapped: wrapping would carve a
        # channel straight across the seam and the landscape is not
        # tileable.
        inside = (nx >= 1.0) & (nx < n - 3.0) & (ny >= 1.0) & (ny < n - 3.0)
        alive = alive & moving & inside

        jx = np.clip(nx.astype(np.int64), 0, n - 2)
        jy = np.clip(ny.astype(np.int64), 0, n - 2)
        gxf = nx - jx
        gyf = ny - jy
        m00 = field[jy, jx]
        m10 = field[jy, jx + 1]
        m01 = field[jy + 1, jx]
        m11 = field[jy + 1, jx + 1]
        new_h = (m00 * (1 - gxf) * (1 - gyf) + m10 * gxf * (1 - gyf)
                 + m01 * (1 - gxf) * gyf + m11 * gxf * gyf)
        dh = new_h - height

        # Capacity goes to zero on flat ground and uphill, so a droplet
        # sheds its load exactly where the slope eases — which is where
        # scree aprons and valley fill belong.
        capacity = (np.maximum(-dh, min_slope) * speed * water
                    * capacity_factor)
        drop = np.where(
            dh > 0.0,
            np.minimum(dh, sediment),
            np.where(sediment > capacity,
                     (sediment - capacity) * deposit_rate, 0.0))
        drop = np.clip(drop, 0.0, sediment)
        take = np.maximum(
            np.where(sediment < capacity,
                     np.minimum((capacity - sediment) * erode_rate, -dh),
                     0.0), 0.0)

        for (ox, oy, wt) in ((0, 0, (1 - fx) * (1 - fy)),
                             (1, 0, fx * (1 - fy)),
                             (0, 1, (1 - fx) * fy),
                             (1, 1, fx * fy)):
            idx = ((iy + oy) * n + (ix + ox))[alive]
            if idx.size == 0:
                continue
            field += np.bincount(idx, weights=((drop - take) * wt)[alive],
                                 minlength=cells).reshape(n, n)
            depo += np.bincount(idx, weights=(drop * wt)[alive],
                                minlength=cells).reshape(n, n)

        idxf = (iy * n + ix)[alive]
        if idxf.size:
            flow += np.bincount(idxf, weights=water[alive],
                                minlength=cells).reshape(n, n)

        sediment = sediment + take - drop
        speed = np.sqrt(np.maximum(speed * speed + dh * gravity, 0.0))
        water = water * (1.0 - evaporate)
        px, py = nx, ny

    if smooth > 0:
        # The scatter is per-texel, so channels come out one cell wide —
        # narrower than the 4 m landscape grid can represent. A light blur
        # turns them into geometry that survives the import.
        field = ndimage.gaussian_filter(field, smooth)
    return field, flow, depo


def hillshade(h, azimuth_deg=315.0, altitude_deg=45.0, scale=400.0):
    """Shaded relief, 0..1. Judge terrain without touching the editor.

    Hard-won lesson 14 says inspect the artefact before it goes
    downstream, and viewing the heightmap has already caught two bad
    terrains in seconds each — each of which would otherwise have cost a
    full import and capture cycle to discover. A raw 16-bit heightmap
    viewed directly is a featureless grey wash; a hillshade shows
    ridgelines, channels and spikes at a glance, which is what makes the
    check actually happen.
    """
    # NORMALISE FIRST. `scale` is meaningful only against a 0..1 field.
    # The first version took whatever it was handed, and the generator
    # handed it the raw 0..65535 heightmap: gradients came out four
    # orders of magnitude too large and the preview saturated to pure
    # black and pure white, showing nothing. An instrument that silently
    # depends on the units of its input is not an instrument — and this
    # one exists precisely so terrain gets LOOKED at before it ships.
    h = h.astype(np.float64)
    span = float(h.max() - h.min())
    h = (h - h.min()) / max(span, 1e-9)

    gy, gx = np.gradient(h)
    az, alt = np.radians(azimuth_deg), np.radians(altitude_deg)
    lx = np.cos(alt) * np.cos(az)
    ly = np.cos(alt) * np.sin(az)
    lz = np.sin(alt)
    nx, ny, nz = -gx * scale, -gy * scale, 1.0
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.clip((nx * lx + ny * ly + nz * lz) / np.maximum(norm, 1e-9),
                   0.0, 1.0)


# UE 5.8 UCharacterMovementComponent defaults, read from the LIVE class
# default object (2026-08-01), not from memory or documentation:
#     WalkableFloorAngle = 44.765083   WalkableFloorZ = 0.71
#     MaxStepHeight      = 45.0 cm
# A surface steeper than the angle cannot be walked on at all. For a world
# built to be explored on foot this is not a stylistic preference, it is
# the boundary between world and wall — which is why it lives here as a
# measured constant rather than as a number somebody picked.
UE_WALKABLE_FLOOR_DEG = 44.765083


# Movement profiles. DATA, not hardcoded policy — the pipeline is being
# built for a world that will be crossed on foot, by climb, by mount, by
# airship and by whatever a later dimension needs. Baking "walkable" in
# as though it were physics would quietly make every future world a
# walking world.
#
# Only `walk` carries an engine-derived number. The rest are starting
# points to be moved per world, which is exactly why they are a table.
MOVEMENT_PROFILES = {
    # UE 5.8 CharacterMovementComponent CDO, read live 2026-08-01.
    "walk": {"max_slope_deg": UE_WALKABLE_FLOOR_DEG,
             "note": "engine default; steeper is not terrain but wall"},
    "climb": {"max_slope_deg": 70.0,
              "note": "scalable faces; a design choice, not an engine one"},
    "mount": {"max_slope_deg": 35.0,
              "note": "horses/vehicles want gentler ground than a walker"},
    "air": {"max_slope_deg": 90.0,
            "note": "everything is crossable; legibility is what matters"},
}


def traversability(slope_deg, profiles=None):
    """How much of this world can be crossed, per movement mode.

    Returns {profile: {frac, largest_frac, regions, reachable_frac}}.

    WHY CONNECTIVITY AND NOT JUST PERCENTAGE. A map can be 70% crossable
    and still broken if that 70% is a thousand isolated shelves separated
    by cliffs — the player arrives on one and can reach none of the
    others. Percentage cannot tell those apart; connected-component
    labelling can, and it is the difference between a world and a
    diorama. 8-connectivity, since movement is not axis-aligned.

    WHY PER PROFILE. The same heightmap is a wall to a walker, a route to
    a climber and open sky to an airship. A single number cannot describe
    a world that supports all three, and the interesting design question
    is usually the RELATIONSHIP between them: terrain where the walkable
    region is fragmented but the climbable region is whole is terrain
    that rewards the player for gaining a traversal ability, which is
    exactly what an exploration game is made of.
    """
    if profiles is None:
        profiles = MOVEMENT_PROFILES
    out = {}
    structure = np.ones((3, 3), dtype=bool)
    total = float(slope_deg.size)
    for name, spec in profiles.items():
        mask = slope_deg <= float(spec["max_slope_deg"])
        frac = float(mask.sum()) / total
        if frac <= 0.0:
            out[name] = {"frac": 0.0, "largest_frac": 0.0, "regions": 0,
                         "reachable_frac": 0.0}
            continue
        labels, count = ndimage.label(mask, structure=structure)
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        largest = float(sizes.max()) / total if count else 0.0
        out[name] = {"frac": frac, "largest_frac": largest,
                     "regions": int(count),
                     "reachable_frac": largest / max(frac, 1e-9)}
    return out


def landmarks(h_units, spacing_cm, z_scale_cm, min_prominence_m=120.0,
              neighbourhood=64):
    """Peaks that can be navigated BY, not just looked at.

    For travel above the ground — airship, flight, any long-range view —
    the question stops being "can I stand here" and becomes "can I tell
    where I am". That is what landmarks are: summits with enough
    PROMINENCE over their surroundings to be recognisable from a
    distance and from an unfamiliar angle.

    Prominence, not height, is the measure. A high point on a high plateau
    is invisible as a landmark; a modest peak standing alone is not. This
    approximates it as height above the local maximum-filtered
    neighbourhood floor, which is cheap and good enough to compare worlds
    against each other — which is the job.
    """
    z_m = h_units.astype(np.float64) / 65535.0 * (z_scale_cm / 100.0)
    peaks = (z_m == ndimage.maximum_filter(z_m, size=neighbourhood,
                                           mode="nearest"))
    floor = ndimage.minimum_filter(z_m, size=neighbourhood, mode="nearest")
    prominence = z_m - floor
    good = peaks & (prominence >= min_prominence_m)
    labels, count = ndimage.label(good, structure=np.ones((3, 3), bool))
    span_km = (h_units.shape[0] - 1) * spacing_cm / 100000.0
    area = max(span_km * span_km, 1e-9)

    # WHERE the peaks are, not just how many. The first version computed
    # every position it needed and then returned only a count, so the one
    # thing a camera needs in order to point AT a landmark was thrown
    # away — and camera framing stayed hand-tuned world coordinates,
    # which is the defect that put a camera above the whole world on
    # 2026-08-02. Sorted by prominence, because that is the ranking that
    # decides which summit reads as a landmark from a distance.
    peaks_out = []
    if count:
        centres = ndimage.center_of_mass(good, labels,
                                         range(1, count + 1))
        maxima = ndimage.maximum(prominence, labels, range(1, count + 1))
        maxima = np.atleast_1d(maxima)
        for (row, col), prom in zip(np.atleast_2d(centres), maxima):
            r, c = int(round(row)), int(round(col))
            peaks_out.append({
                # Metres from the heightmap's own origin, so the caller
                # adds landscape.location_cm / 100.0 — these are METRES,
                # location_cm is CENTIMETRES (Pass 3 2026-09-16 F2: the
                # old comment said "adds location_cm", inviting a 100x
                # world-position error of the 2026-08-02 camera class).
                "x_m": c * spacing_cm / 100.0,
                "y_m": r * spacing_cm / 100.0,
                "z_m": float(z_m[r, c]),
                "prominence_m": float(prom),
                "row": r, "col": c,
            })
        peaks_out.sort(key=lambda p: -p["prominence_m"])

    return {"count": int(count),
            "per_100km2": 100.0 * count / area,
            "max_prominence_m": float(prominence.max()),
            "span_km": span_km,
            "peaks": peaks_out}


def composition(h_units, spacing_cm, z_scale_cm, window_m=250.0,
                flat_relief_m=20.0, edge_band_m=800.0):
    """Is the whole map WORLD, or is it an island in a dead plain?

    Traversability answers "can this be crossed". It cannot answer "is
    there anything out there", because a billiard-table plain is 100%
    walkable and 100% one piece — it scores perfectly and is nothing to
    explore. This is the companion measure: how much of the map carries
    RELIEF, and whether that relief reaches the borders.

    LOCAL RELIEF, not height. Absolute elevation says nothing — a high
    flat shelf is as empty as a low one. What a player reads as terrain
    is variation within eyeshot, so relief is measured as (max - min)
    over a `window_m` neighbourhood, which at 250 m is roughly what fills
    a view.

    FLATNESS IS THE DEFECT; THE EDGE RATIO IS CONTEXT. Both are
    reported, and it is worth being precise about which one detects
    what, because the first run with a replacement mask separated them
    immediately. `*_flat_frac` counts DEAD ground — below `flat_relief_m`
    of relief, which is a plain whatever its elevation. `edge_ratio`
    compares the outer `edge_band_m` against the interior, and a low
    ratio only says the outskirts are GENTLER, which is what foothills
    are. The island was both: 82.9% of its border cells dead, ratio
    0.166. A world can score 0.0% flat at a ratio of 0.3 and be exactly
    right. Read the flat fractions first.

    Neither number is visible to any other gate in the pipeline, which is
    how the island survived five sessions of inspection: traversability
    scores a billiard table 100% crossable in one piece.

    Returns metres and fractions, never raw units, so the numbers can be
    argued about in terms a person can picture (lesson 18.5).
    """
    h_units = np.asarray(h_units)
    n = h_units.shape[0]
    win = int(max(3, round(window_m * 100.0 / float(spacing_cm))))
    band = int(max(1, round(edge_band_m * 100.0 / float(spacing_cm))))
    if band * 2 >= n:
        raise ValueError(
            "edge band {0} m is at least half the {1} cell map — there is "
            "no interior left to compare it against".format(edge_band_m, n))

    z_m = h_units.astype(np.float64) / 65535.0 * (float(z_scale_cm) / 100.0)
    relief = (ndimage.maximum_filter(z_m, size=win, mode="nearest")
              - ndimage.minimum_filter(z_m, size=win, mode="nearest"))

    idx = np.arange(n)
    dist_to_border = np.minimum(idx, n - 1 - idx)
    border_dist = np.minimum(dist_to_border[:, None], dist_to_border[None, :])
    edge = border_dist < band
    core = ~edge

    flat = relief < float(flat_relief_m)
    edge_med = float(np.median(relief[edge]))
    core_med = float(np.median(relief[core]))

    ring = np.zeros((n, n), dtype=bool)
    ring[0, :] = ring[-1, :] = True
    ring[:, 0] = ring[:, -1] = True

    return {
        "window_m": float(window_m),
        "flat_relief_m": float(flat_relief_m),
        "edge_band_m": float(edge_band_m),
        "flat_frac": float(flat.mean()),
        "edge_flat_frac": float(flat[edge].mean()),
        "core_flat_frac": float(flat[core].mean()),
        "border_flat_frac": float(flat[ring].mean()),
        "edge_relief_m": edge_med,
        "core_relief_m": core_med,
        # 1.0 = the border is as alive as the middle; 0 = an island.
        "edge_ratio": edge_med / max(core_med, 1e-9),
        "median_relief_m": float(np.median(relief)),
        "p90_relief_m": float(np.percentile(relief, 90)),
    }


def spacing_for(resolution, recipe_resolution, recipe_scale_xy_cm):
    """Cell spacing in cm for a map generated at `resolution`.

    THE TRAP THIS EXISTS FOR. `scale_xy_cm` in the recipe is the spacing
    at the RECIPE's resolution. Generate a preview at 1009 instead of
    2017 and the same world span is covered by half as many samples, so
    the real spacing doubles — and a slope computed with the recipe value
    comes out about twice too steep. That is exactly the shape of the
    2026-08-01 all-snow defect: a number that arrives, is finite and
    plausible, and means something other than what the caller assumed.
    Sweeps compared across resolutions would have been nonsense.
    """
    span = (float(recipe_resolution) - 1.0) * float(recipe_scale_xy_cm)
    return span / max(float(resolution) - 1.0, 1.0)


def slope_degrees(h_units, scale_xy_cm, z_scale_cm):
    """Slope in degrees, on the same datum the weightmap bake uses.

    scale_xy_cm IS THE PER-SAMPLE SPACING, already resolution-corrected
    by the caller via spacing_for — this function does NO correction. A
    `resolution` parameter used to sit in the signature and was NEVER
    read (Pass 3 2026-09-16 F1): it looked like the resolution-vs-spacing
    guard this module exists for, and a caller passing the recipe's
    scale_xy_cm plus a preview resolution would have got slopes wrong by
    the resolution ratio (the 2026-08-01 all-snow shape) with no error.
    Removed so the signature cannot lie; correct the spacing BEFORE the
    call (spacing_for), never inside it.

    Kept here so the generator can REPORT the slope distribution it just
    produced. The recipe's layer thresholds are chosen against that
    distribution, and the 2026-08-01 all-snow render happened because a
    threshold was tuned against a measurement nothing downstream made.
    A generator that prints its own slope percentiles makes that class of
    mistake visible at generation time instead of three steps later.
    """
    z_cm = h_units.astype(np.float64) / 65535.0 * z_scale_cm
    gy, gx = np.gradient(z_cm, float(scale_xy_cm))
    return np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))
