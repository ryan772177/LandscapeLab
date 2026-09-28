#!/usr/bin/env python
"""Brief 5 Task 0, item 1 -- per-species instance census by Brief-1 band, and
the visible count at each of the four ratified perf stations.

READ-ONLY. Reads the committed placement plans (foliage/alpine_8k_*.json), the
station cameras (recipes/perf_budgets.json spline), and the Brief-1 pixel
thresholds (recipes/alpine_8k.json foliage.cull_derived.thresholds_px). No
world mutation, no editor.

Bands (Brief 1 sec 2, thresholds_px): an instance's apparent height in pixels
at a station decides its band --
    detail : px >= 40.0            (internal structure resolvable)
    shape  : 6.0 <= px < 40.0      (silhouette carries it)
    blob   : 1.5 <= px < 6.0       (a flat blob of the right colour suffices)
    gone   : px < 1.5              (below the render's Nyquist limit)
Apparent height uses the PER-INSTANCE world height = mesh_height_m * scale, at
the DECLARED camera (fov_h 90, res 2160 vertical -> vfov 58.7155). The -game
process does not apply that FOV (rule 12); this census is at the DECLARED
frustum and says so.

"visible" at a station = inside the frustum AND inside the species cull. The
band tells you WHAT it looks like there; visible tells you whether it draws.
"""
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import angular_budget as ab  # dist_for_pixels / pixels_tall

TREE_SPECIES = ["Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"]
# Populated in main() from recipes/alpine_8k.json perception.* -- NOT hardcoded
# (audit F6/F7). Left empty here so a forgotten load fails loud, not silently
# on a stale literal.
THRESH = {}
RES_V = None
FOV_H = None


def vfov_deg(fov_h_deg, res):
    w, h = res
    half_h = math.radians(fov_h_deg) / 2.0
    half_v = math.atan(math.tan(half_h) * (h / float(w)))
    return math.degrees(2.0 * half_v)


def load_recipe(name):
    return json.load(open(os.path.join(REPO, "recipes", name), encoding="utf-8-sig"))


def forward(yaw_deg, pitch_deg):
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))


def frustum_geom(dx, dy, dz, fwd):
    """dx,dy,dz: camera->instance BASE, in cm. Return the raw geometry the two
    visibility tests need, so the caller decides point-vs-segment (audit C):
        (d_cm, ang_h_rad, horiz_cm, pitch_base_rad, cam_pitch_rad)
    ang_h  -- horizontal angular offset of the base from the camera forward.
    horiz  -- horizontal range (yaw plane) used to convert heights to angles.
    pitch_base -- elevation angle of the base point.
    cam_pitch  -- camera pitch.
    A cheap separable frustum -- correct for a symmetric FOV. ALWAYS a 5-tuple
    (the old d<1e-6 early return was a 2-tuple the 4-tuple caller crashed on)."""
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    cam_pitch = math.asin(max(-1.0, min(1.0, fwd[2])))
    if d < 1e-6:
        return 0.0, 0.0, 0.0, cam_pitch, cam_pitch  # instance at the camera
    fyaw = math.atan2(fwd[1], fwd[0])
    cos_y = math.cos(-fyaw)
    sin_y = math.sin(-fyaw)
    rx = dx * cos_y - dy * sin_y      # forward-ish horizontal
    ry = dx * sin_y + dy * cos_y      # lateral
    horiz = math.sqrt(rx * rx + ry * ry)
    ang_h = abs(math.atan2(ry, rx))
    pitch_base = math.atan2(dz, horiz) if horiz > 0 else cam_pitch
    return d, ang_h, horiz, pitch_base, cam_pitch


def point_in_frustum(ang_h, pitch_base, cam_pitch, half_h, half_v):
    """The BASE point is inside the frustum. What v1 called 'visible'."""
    return ang_h <= half_h and abs(pitch_base - cam_pitch) <= half_v


def segment_in_frustum(ang_h, horiz_cm, pitch_base, top_cm, cam_pitch,
                       half_h, half_v):
    """The tree's vertical extent (base->top) intersects the vertical frustum,
    with the base passing azimuth. Catches a tree whose base is below frame but
    whose crown is on screen -- the point test drops it, this keeps it.
    NO occlusion: a segment behind terrain or another tree still counts (occlusion
    is out of scope for this census -- see the output _occlusion_note)."""
    if not ang_h <= half_h:
        return False
    pitch_top = math.atan2(top_cm, horiz_cm) if horiz_cm > 0 else pitch_base
    lo = cam_pitch - half_v
    hi = cam_pitch + half_v
    # interval [pitch_base, pitch_top] intersects [lo, hi]
    return pitch_top >= lo and pitch_base <= hi


def band_of(px):
    if px >= THRESH["detail"]:
        return "detail"
    if px >= THRESH["silhouette"]:
        return "shape"
    if px >= THRESH["vanish"]:
        return "blob"
    return "gone"


def main():
    global THRESH, FOV_H, RES_V
    r8k = load_recipe("alpine_8k.json")
    # Bands, camera and resolution READ FROM THE RECIPE (audit F6/F7), not
    # hardcoded -- perception.thresholds_px / perception.declared_camera are the
    # same source the culls were derived from.
    perc = r8k["perception"]
    THRESH = {k: perc["thresholds_px"][k]
              for k in ("detail", "silhouette", "vanish")}
    FOV_H = float(perc["declared_camera"]["fov_h_deg"])
    cam_res = perc["declared_camera"]["res"]
    RES_V = int(cam_res[1])
    budgets = json.load(open(os.path.join(REPO, "recipes", "perf_budgets.json"),
                             encoding="utf-8-sig"))
    spline = budgets["spline"]
    eye_cm = float(spline.get("eye_height_cm", 175.0))
    vfov = vfov_deg(FOV_H, cam_res)
    half_h = math.radians(FOV_H) / 2.0
    half_v = math.radians(vfov) / 2.0

    # Load tree plans: instances [x,y,z,yaw,pitch,roll,scale] cm, and mesh height.
    species = {}
    for sp in TREE_SPECIES:
        d = json.load(open(os.path.join(REPO, "foliage", "alpine_8k_%s.json" % sp),
                           encoding="utf-8-sig"))
        species[sp] = {
            "instances": d["instances"],
            "count": len(d["instances"]),
            "mesh_height_m": d["cull_derivation"]["mesh_height_m"],
            "cull_cm": d["cull_cm"],
            "cull_m": d["cull_cm"] / 100.0,
        }

    # Station cameras. z from heightmap+eye is the perf tool's; here we read the
    # measured z from the committed perf run so the census sits at the SAME eye
    # the cost run measured.
    perf = json.load(open(os.path.join(
        REPO, "_verify", "perf", "standalone_2026-09-19", "perf_standalone.json"),
        encoding="utf-8-sig"))
    stations = {}
    for zone, zz in perf["zones"].items():
        c = zz["camera"]
        stations[zone] = (c["x_cm"], c["y_cm"], c["z_cm"], c["pitch_deg"], c["yaw_deg"])
    # Brief 5 v3 Task 3: the derived forest_floor station sits BESIDE the four
    # ratified stations (its counts are the denominator for the forest cost).
    fs_path = os.path.join(REPO, "research", "brief5", "input", "forest_station.json")
    if os.path.exists(fs_path):
        fc = json.load(open(fs_path, encoding="utf-8"))["camera"]
        stations["forest_floor"] = (fc["x_cm"], fc["y_cm"], fc["z_cm"],
                                    fc["pitch_deg"], fc["yaw_deg"])

    out = {
        "_what": "Brief 5 Task 0 item 1: per-species instance census by Brief-1 "
                 "band, and the visible count at each ratified perf station.",
        "_read_back_source": {
            "instances": "foliage/alpine_8k_<species>.json (committed placement "
                         "plans; the SAME rows every downstream consumer reads)",
            "mesh_height_m": "each plan's cull_derivation.mesh_height_m "
                             "(measured from mesh geometry, Brief 1)",
            "cull_cm": "each plan's cull_cm (place_foliage derived, clamped to "
                       "streaming.main_loading_range_cm = 512 m)",
            "station_cameras": "recipes/perf_budgets.json spline + the measured "
                               "camera in _verify/perf/standalone_2026-09-19",
            "thresholds_px": "recipes/alpine_8k.json perception.thresholds_px",
            "declared_camera": "recipes/alpine_8k.json "
                               "perception.declared_camera (fov_h_deg, res)",
        },
        "_frustum_caveat": "Bands and frustum are at the DECLARED camera "
                           "(fov_h %.1f, vfov %.4f, res %dv). The -game cost "
                           "process does NOT apply this FOV (rule 12), so these "
                           "are the DECLARED-frustum counts, not a read-back of "
                           "the -game frustum." % (FOV_H, vfov, RES_V),
        "_point_vs_segment_note": "in_frustum_in_cull tests the BASE point "
                           "(v1's 'visible'). in_frustum_in_cull_segment tests "
                           "the base->top vertical extent against the vertical "
                           "half-angle, so a tree whose base is below frame but "
                           "whose crown is on screen is counted (the treeline "
                           "'elevation' exclusions are mostly this). Azimuth is "
                           "still a base-point test in both.",
        "_occlusion_note": "NO occlusion in either count. A tree behind terrain "
                           "or behind a nearer tree still counts as in-frustum. "
                           "Occlusion is out of scope for this census; the counts "
                           "are an upper bound on what draws.",
        "thresholds_px": THRESH,
        "eye_height_cm": eye_cm,
        "vfov_deg": vfov,
        "species_totals": {sp: species[sp]["count"] for sp in TREE_SPECIES},
        "total_tree_instances": sum(species[sp]["count"] for sp in TREE_SPECIES),
        "band_ring_radii_m": {},
        "stations": {},
    }

    # Per-species band-ring radii: the distance at which a p50-scaled instance
    # crosses each pixel threshold. detail_ring = where it drops out of the
    # detail band; below cull it never reaches the far rings (culled first).
    for sp in TREE_SPECIES:
        d = json.load(open(os.path.join(REPO, "foliage", "alpine_8k_%s.json" % sp),
                           encoding="utf-8-sig"))
        h50 = d["cull_derivation"]["placed_height_p50_m"]
        rings = {}
        for name, px in (("detail", THRESH["detail"]),
                         ("silhouette", THRESH["silhouette"]),
                         ("vanish", THRESH["vanish"])):
            rings[name + "_m"] = round(ab.dist_for_pixels(h50, px, vfov, RES_V), 1)
        rings["cull_m"] = species[sp]["cull_m"]
        rings["_note"] = ("cull sits at the detail ring, clamped to the 512 m "
                          "streaming range; the silhouette/vanish rings lie "
                          "beyond the cull, so a live instance is removed before "
                          "it reaches them -- those bands are carried by HLOD.")
        out["band_ring_radii_m"][sp] = rings

    for zone, (cx, cy, cz, pitch, yaw) in stations.items():
        fwd = forward(yaw, pitch)
        zrec = {"camera": {"x_cm": cx, "y_cm": cy, "z_cm": cz,
                           "pitch_deg": pitch, "yaw_deg": yaw},
                "per_species": {}, "band_totals_visible": {},
                "band_totals_all_in_cull": {}}
        band_vis_tot = {"detail": 0, "shape": 0, "blob": 0, "gone": 0}
        band_cull_tot = {"detail": 0, "shape": 0, "blob": 0, "gone": 0}
        seg_vis_tot = 0
        for sp in TREE_SPECIES:
            s = species[sp]
            cull_cm = s["cull_cm"]
            h_m = s["mesh_height_m"]
            # gone included: an in-frustum in-cull instance whose apparent px is
            # below the vanish threshold is honestly counted, not silently
            # dropped (audit F10). Structurally near-zero (cull <= detail ring).
            bands_vis = {"detail": 0, "shape": 0, "blob": 0, "gone": 0}
            bands_cull = {"detail": 0, "shape": 0, "blob": 0, "gone": 0}
            n_in_cull = 0
            n_in_frustum = 0
            n_pt_in_cull = 0    # base-point test, in cull -- v1's 'visible'
            n_seg_in_cull = 0   # base->top segment test, in cull (audit C)
            # Limb decomposition of in-cull-but-point-outside (audit: make the
            # treeline zero carry its reason -- azimuth vs elevation).
            excl_azimuth = 0     # in cull, outside horizontal half-angle
            excl_elevation = 0   # in cull, inside azimuth, base outside vertical
            for inst in s["instances"]:
                ix, iy, iz, _, _, _, sc = inst
                dx, dy, dz = ix - cx, iy - cy, iz - cz
                d_cm, ang_h, horiz, pitch_base, cam_pitch = frustum_geom(
                    dx, dy, dz, fwd)
                d_m = d_cm / 100.0
                in_cull = d_cm <= cull_cm
                pt_in = point_in_frustum(ang_h, pitch_base, cam_pitch,
                                         half_h, half_v)
                top_cm = dz + h_m * sc * 100.0   # base + world tree height
                seg_in = segment_in_frustum(ang_h, horiz, pitch_base, top_cm,
                                            cam_pitch, half_h, half_v)
                if in_cull:
                    n_in_cull += 1
                    if d_m > 0:
                        px = ab.pixels_tall(h_m * sc, d_m, out["vfov_deg"], RES_V)
                        bc = band_of(px)
                        bands_cull[bc] += 1
                        band_cull_tot[bc] += 1
                if pt_in:
                    n_in_frustum += 1
                if pt_in and in_cull and d_m > 0:
                    b = band_of(px)
                    bands_vis[b] += 1
                    band_vis_tot[b] += 1
                    n_pt_in_cull += 1
                elif in_cull and not pt_in:
                    if ang_h > half_h:
                        excl_azimuth += 1
                    else:
                        excl_elevation += 1
                if seg_in and in_cull:
                    n_seg_in_cull += 1
                    seg_vis_tot += 1
            zrec["per_species"][sp] = {
                "count_total": s["count"],
                "cull_m": s["cull_m"],
                "in_cull_radius": n_in_cull,
                "in_frustum": n_in_frustum,
                "in_frustum_in_cull": n_pt_in_cull,          # renamed from 'visible'
                "in_frustum_in_cull_segment": n_seg_in_cull,  # base->top segment
                "in_frustum_in_cull_by_band": bands_vis,
                "in_cull_by_band": bands_cull,
                "in_cull_not_visible_excluded_by": {
                    "azimuth": excl_azimuth, "elevation": excl_elevation,
                },
            }
        zrec["band_totals_in_frustum_in_cull"] = band_vis_tot
        zrec["band_totals_all_in_cull"] = band_cull_tot
        zrec["in_frustum_in_cull_total"] = sum(
            band_vis_tot[b] for b in ("detail", "shape", "blob", "gone"))
        zrec["in_frustum_in_cull_segment_total"] = seg_vis_tot
        out["stations"][zone] = zrec

    outdir = os.path.join(REPO, "research", "brief5", "input")
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "_census_stations.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    # console summary
    print("total tree instances: %d" % out["total_tree_instances"])
    for sp in TREE_SPECIES:
        print("  %-14s %6d  cull %.0f m" % (sp, species[sp]["count"], species[sp]["cull_m"]))
    for zone, z in out["stations"].items():
        bt = z["band_totals_in_frustum_in_cull"]
        print("%-12s in_frustum_in_cull=%d (seg=%d)  detail=%d shape=%d blob=%d"
              % (zone, z["in_frustum_in_cull_total"],
                 z["in_frustum_in_cull_segment_total"],
                 bt["detail"], bt["shape"], bt["blob"]))
    print("wrote", os.path.relpath(p, REPO))


def selftest():
    """A tree whose BASE is 1 deg below the bottom frustum edge but whose CROWN
    is inside the frame must count under the SEGMENT test and NOT under the
    point test (audit C). Camera at origin, forward +X, pitch 0."""
    fov_h, res = 90.0, [3840, 2160]
    vfov = vfov_deg(fov_h, res)
    half_h = math.radians(fov_h) / 2.0
    half_v = math.radians(vfov) / 2.0
    fwd = forward(0.0, 0.0)               # +X, level
    horiz_cm = 10000.0                    # 100 m out
    # base 1 deg below the bottom edge (cam_pitch 0 -> bottom at -half_v)
    base_ang = -(half_v + math.radians(1.0))
    dz_base = horiz_cm * math.tan(base_ang)
    dx, dy, dz = horiz_cm, 0.0, dz_base
    d_cm, ang_h, horiz, pitch_base, cam_pitch = frustum_geom(dx, dy, dz, fwd)
    # crown angle inside the frame: -half_v + 1 deg (inside [-half_v, half_v]).
    # top_cm is the crown's world z relative to the camera; since its angle
    # exceeds the base angle, the implied tree height is positive.
    top_ang = -half_v + math.radians(1.0)
    top_cm = horiz_cm * math.tan(top_ang)
    pt = point_in_frustum(ang_h, pitch_base, cam_pitch, half_h, half_v)
    seg = segment_in_frustum(ang_h, horiz, pitch_base, top_cm, cam_pitch,
                             half_h, half_v)
    assert pt is False, "point test should DROP a base-below-frame tree, got %s" % pt
    assert seg is True, "segment test should KEEP a crown-in-frame tree, got %s" % seg
    # control: a tree fully below frame (base and crown both below) fails both
    low_top = horiz_cm * math.tan(-(half_v + math.radians(0.5)))
    seg_low = segment_in_frustum(ang_h, horiz, pitch_base, low_top, cam_pitch,
                                 half_h, half_v)
    assert seg_low is False, "segment test should DROP a fully-below tree, got %s" % seg_low
    print("selftest OK: point=%s seg=%s seg_fully_below=%s (vfov %.4f)"
          % (pt, seg, seg_low, vfov))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        main()
