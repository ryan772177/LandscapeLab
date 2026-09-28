#!/usr/bin/env python3
"""Brief 5 D0 -- per-zone tree-density multiplier map.

Offline, read-only inputs; writes research/brief5/derived/zone_map.json and
zone_map.png. No editor, no network.

ZONE RULE (Ryan, 2026-09-22, Daylight Density session):
  Each budget station (forest_floor, plaza, treeline) owns a 512 m disc (its
  cull_max) around its world XY. A bin inside a disc takes that station's CAP;
  inside several discs, the MINIMUM cap. Outside every disc a bin takes the global
  target m = 5.48 (canopy_cover m_for.p90_bin -- no station measures there; vista
  sees it only as HLOD, item 8 ~1%). A 128 m linear blend runs across each disc
  edge (m ramps from the disc cap at the inner edge to the target at the outer
  edge). Each station's cap is min(budget-derived cap, target): the target is a
  CEILING, not a floor (the recipe's own elevation thinning stays in force above it).

CAPS are computed from DENSITY_PLAN's own cost model (density_project.py:128-144),
NOT hardcoded:
  proj(m) = current_hold + live_now*(m-1) + (hlod_frac*current_hold*(m-1) if all_HLOD)
  cap_raw = largest m with proj(m) <= (budget - margin)  ->  m = 1 + (budget-margin-hold)/slope
  cap     = min(cap_raw, target)
Budgets: forest_floor 13.0 (R5-1 desk revision, 2026-09-22), treeline tol 7.7,
plaza 10.5. forest_floor cap is from CURRENT headroom -- no T4 rung PASSED the
visual gate (D1a: the gate never ran; SpruceSub build stalled), so per the brief
the cap uses current headroom, stated. DESK MARGIN (2026-09-22 part 2): a 0.1 ms
safety margin is held below the forest_floor budget, so its cap solves 12.90 (not
13.0), giving m_ff = 2.38. plaza/treeline are target-capped so their margin is inert.

zone_map.json records per bin {bin, center_m, zone, m_cap, m_final, discs_containing,
dist_to_each_m} + a summary (caps, overlap bins, unconstrained bins).
"""
import json
import math
import os

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from matplotlib.patches import Rectangle, Circle

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BR = os.path.join(REPO, "research", "brief5")

DISC_R_CM = 51200.0      # 512 m cull_max
BLEND_CM = 12800.0       # 128 m blend band, straddling the disc edge
INNER_CM = DISC_R_CM - BLEND_CM / 2.0   # 448 m: full cap inside
OUTER_CM = DISC_R_CM + BLEND_CM / 2.0   # 576 m: target beyond
EPS = 1e-6


def load(rel):
    return json.load(open(os.path.join(BR, rel), encoding="utf-8"))


def main():
    forest = load("input/forest_cost.json")
    dens = load("input/density_baseline.json")
    canopy = load("derived/canopy_cover.json")
    share = load("input/item8_share.json")
    stcen = load("input/_census_stations.json")
    stations_cen = stcen["stations"] if "stations" in stcen else stcen

    TARGET = float(canopy["summary"]["m_for"]["p90_bin"])          # 5.48
    ms_per_1000 = float(forest["ms_per_1000_in_frustum_in_cull_trees"])  # 0.1003
    vis = dens["item1_instance_census"]["per_station_visible"]
    hlod_frac_treeline = share["stations"]["treeline"]["hlod_share_pct_of_A"] / 100.0

    # per-station cost model (reproduces density_project.py) -> slope, hold, budget
    ff_live_now = (forest["gpu_p90_ms"]["as_is"]["mean"]
                   - forest["gpu_p90_ms"]["hidden"]["mean"])       # 0.185 measured
    # DESK MARGIN (2026-09-22, Daylight Density part 2). The desk holds a 0.1 ms
    # safety margin below the forest_floor budget so the cap does not sit exactly
    # on the abort ceiling: forest_floor cap solves proj(m) = 13.0 - 0.1 = 12.90,
    # giving m_ff = 2.38 (was 2.919 at the bare budget). plaza/treeline are already
    # target-capped, so a margin there is inert; kept 0.0 for record.
    FF_MARGIN_MS = 0.1
    model = {
        "forest_floor": {"hold": 12.645, "slope": ff_live_now, "budget": 13.0,
                         "margin_ms": FF_MARGIN_MS,
                         "budget_src": "R5-1 desk revision 2026-09-22 (STATE.md:17)",
                         "cap_basis": "current headroom (no T4 rung PASSED the gate); "
                                      "0.1 ms desk margin below budget"},
        "plaza": {"hold": 9.476,
                  "slope": vis["plaza"]["visible_total"] * ms_per_1000 / 1000.0,
                  "budget": 10.5, "margin_ms": 0.0, "budget_src": "queue header",
                  "cap_basis": "live-tree growth"},
        "treeline": {"hold": 7.139,
                     "slope": hlod_frac_treeline * 7.139,   # HLOD-share growth (0 live trees)
                     "budget": 7.7, "margin_ms": 0.0, "budget_src": "tol +10% (7.0 nominal)",
                     "cap_basis": "HLOD-proxy growth (all-HLOD forest)"},
    }

    def proj(name, m):
        s = model[name]
        return s["hold"] + s["slope"] * (m - 1.0)

    def cap_target(name):
        # the ms the cap must solve = budget minus the desk margin
        return model[name]["budget"] - model[name].get("margin_ms", 0.0)

    def cap_raw(name):
        s = model[name]
        if s["slope"] <= 0:
            return float("inf")
        return 1.0 + (cap_target(name) - s["hold"]) / s["slope"]

    caps = {}
    for name in model:
        cr = cap_raw(name)
        caps[name] = {"cap_raw": round(cr, 4), "cap": round(min(cr, TARGET), 4),
                      "budget": model[name]["budget"],
                      "margin_ms": model[name].get("margin_ms", 0.0),
                      "cap_solves_ms": round(cap_target(name), 4),
                      "hold": model[name]["hold"],
                      "slope_ms_per_unit_m": round(model[name]["slope"], 6),
                      "proj_at_target": round(proj(name, TARGET), 4),
                      "proj_at_cap": round(proj(name, min(cr, TARGET)), 4),
                      "cap_basis": model[name]["cap_basis"],
                      "budget_src": model[name]["budget_src"]}

    # --- cross-check the model against density_project's published projection ---
    # (rule 13: prove the replication reproduces the known numbers before using it)
    XCHECK = {"forest_floor": 13.474, "treeline": 7.513, "plaza": 9.882}
    xcheck_ok = {}
    for name, want in XCHECK.items():
        got = proj(name, TARGET)
        xcheck_ok[name] = abs(got - want) < 0.01
        assert xcheck_ok[name], ("model xcheck FAILED %s: proj(%.2f)=%.4f != %.4f"
                                 % (name, TARGET, got, want))
    # forest_floor cap must solve (budget - margin) exactly = 12.90
    _ff_solve = cap_target("forest_floor")
    assert abs(proj("forest_floor", caps["forest_floor"]["cap"]) - _ff_solve) < 0.01, \
        "forest_floor cap does not solve budget-margin %.2f" % _ff_solve
    assert abs(_ff_solve - 12.90) < 0.01, "forest_floor cap target != 12.90"

    # disc centers (world cm) from the ratified station census
    DISC = {name: (float(stations_cen[name]["camera"]["x_cm"]),
                   float(stations_cen[name]["camera"]["y_cm"]))
            for name in model}

    def blended(name, d_cm):
        c = caps[name]["cap"]
        if d_cm <= INNER_CM:
            return c
        if d_cm >= OUTER_CM:
            return TARGET
        t = (d_cm - INNER_CM) / (OUTER_CM - INNER_CM)
        return c + (TARGET - c) * t

    bin_cm = float(canopy["params"]["bin_cm"])
    bins_out = []
    n_in = {name: 0 for name in model}
    n_overlap = 0
    overlap_pairs = {}
    n_unconstrained = 0
    n_below = 0
    for b in canopy["bins"]:
        ix, iy = b["bin"]
        cx = (ix + 0.5) * bin_cm
        cy = (iy + 0.5) * bin_cm
        dist = {name: math.hypot(cx - DISC[name][0], cy - DISC[name][1]) for name in model}
        containing = [name for name in model if dist[name] <= DISC_R_CM]
        for name in containing:
            n_in[name] += 1
        # m_cap is the BLEND-AWARE per-bin ceiling: the most this bin may be
        # multiplied under the zone rule, INCLUDING the 128 m edge blend. It is
        # the min over discs of the blended contribution, so m_final <= m_cap by
        # construction (the density ceiling, applied later at placement, can only
        # lower m_final further). The flat disc cap (2.38 at forest_floor) is
        # recorded separately as disc_flat_cap -- the blend intentionally exceeds
        # it between the inner (448 m) and outer (576 m) edges, so the flat cap is
        # NOT a per-bin ceiling and comparing m_final against it is a category
        # error (Ryan's ASK#1 invariant check, 2026-09-22).
        contrib = {name: blended(name, dist[name]) for name in model}
        m_final = min([TARGET] + list(contrib.values()))
        m_cap = m_final                       # blend-aware ceiling; m_final <= m_cap
        disc_flat_cap = (min([caps[name]["cap"] for name in containing])
                         if containing else TARGET)
        binding = min(contrib, key=contrib.get)
        if m_final >= TARGET - EPS:
            zone = "open"
            n_unconstrained += 1
        else:
            zone = binding
            n_below += 1
        if len(containing) >= 2:
            n_overlap += 1
            key = "+".join(sorted(containing))
            overlap_pairs[key] = overlap_pairs.get(key, 0) + 1
        bins_out.append({
            "bin": [ix, iy],
            "center_m": [round(cx / 100.0, 1), round(cy / 100.0, 1)],
            "zone": zone,
            "m_cap": round(m_cap, 4),
            "disc_flat_cap": round(disc_flat_cap, 4),
            "m_final": round(m_final, 4),
            "discs_containing": containing,
            "dist_to_each_m": {name: round(dist[name] / 100.0, 1) for name in model},
            "cover": b.get("cover"),
            "cover_class": b.get("class"),
        })

    # projected ms per station under the zone map (apply m_final at the station's
    # own location). vista included as informational (HLOD-only viewpoint).
    proj_stations = {}
    all_st = dict(DISC)
    all_st["vista"] = (float(stations_cen["vista"]["camera"]["x_cm"]),
                       float(stations_cen["vista"]["camera"]["y_cm"]))
    for name, (sx, sy) in all_st.items():
        dist = {dn: math.hypot(sx - DISC[dn][0], sy - DISC[dn][1]) for dn in model}
        contrib = {dn: blended(dn, dist[dn]) for dn in model}
        m_here = min([TARGET] + list(contrib.values()))
        row = {"m_applied": round(m_here, 4),
               "discs_containing": [dn for dn in model if dist[dn] <= DISC_R_CM]}
        if name in model:
            p = proj(name, m_here)
            row.update({"projected_ms": round(p, 4), "budget_ms": model[name]["budget"],
                        "over_budget_ms": round(p - model[name]["budget"], 4),
                        "hold_ms": model[name]["hold"]})
        else:
            row["_note"] = ("viewpoint, not a budget station; sees the forest only as "
                            "HLOD (item8 ~1%). m_applied is the zone value at its XY.")
        proj_stations[name] = row

    out = {
        "_what": "Brief 5 D0 -- per-zone tree-density multiplier map (256 m bins).",
        "_zone_rule": ("512 m station cull-discs (forest_floor, plaza, treeline); bin cap "
                       "= min over containing discs; outside all discs = target m; 128 m "
                       "linear blend across each disc edge; per-station cap = min(budget "
                       "cap, target). Ryan ruling 2026-09-22."),
        "_sources": {
            "target_m": "derived/canopy_cover.json summary.m_for.p90_bin = %.4f (crown 0.85)" % TARGET,
            "cost_model": "reproduces research/brief5/scripts/density_project.py:128-144",
            "ms_per_1000": "forest_cost.json = %.4f" % ms_per_1000,
            "hlod_frac_treeline": "item8_share.json stations.treeline.hlod_share_pct_of_A/100 = %.4f" % hlod_frac_treeline,
            "disc_centers": "input/_census_stations.json camera.x_cm/y_cm",
            "budgets": "forest_floor 13.0 (R5-1 desk revision 2026-09-22), 0.1 ms desk margin -> cap solves 12.90; treeline tol 7.7; plaza 10.5",
        },
        "params": {
            "target_m": round(TARGET, 4),
            "disc_radius_cm": DISC_R_CM, "disc_radius_m": DISC_R_CM / 100.0,
            "blend_cm": BLEND_CM, "blend_m": BLEND_CM / 100.0,
            "inner_edge_m": INNER_CM / 100.0, "outer_edge_m": OUTER_CM / 100.0,
            "bin_cm": bin_cm,
            "disc_centers_m": {n: [round(c[0] / 100.0, 1), round(c[1] / 100.0, 1)] for n, c in DISC.items()},
        },
        "caps": caps,
        "model_xcheck_vs_density_projection": {"expected": XCHECK, "ok": xcheck_ok},
        "summary": {
            "n_bins": len(bins_out),
            "n_in_disc": n_in,
            "n_overlap_bins": n_overlap,
            "overlap_membership_counts": overlap_pairs,
            "n_constrained_below_target": n_below,
            "n_unconstrained_at_target": n_unconstrained,
            "_note_treeline_plaza": ("plaza and treeline caps both == target %.2f (their "
                                     "budget caps 12.31 / 7.72 exceed the target ceiling), "
                                     "so ONLY the forest_floor disc (cap %.3f) constrains a "
                                     "bin below target. Their discs are recorded in "
                                     "discs_containing but do not lower m."
                                     % (TARGET, caps["forest_floor"]["cap"])),
        },
        "projected_ms_per_station": proj_stations,
        "bins": bins_out,
    }
    dest = os.path.join(BR, "derived", "zone_map.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("wrote", os.path.relpath(dest, REPO))
    print("caps:", {n: caps[n]["cap"] for n in caps})
    print("bins: total=%d below_target=%d unconstrained=%d overlap=%d %s"
          % (len(bins_out), n_below, n_unconstrained, n_overlap, overlap_pairs))
    for n, r in proj_stations.items():
        print("  %-13s m=%.3f %s" % (n, r["m_applied"],
              ("proj=%.3f budget=%.1f over=%+.3f" % (r["projected_ms"], r["budget_ms"], r["over_budget_ms"]))
              if "projected_ms" in r else r.get("_note", "")))

    _render_png(out, canopy, bins_out, DISC, caps, TARGET)
    return out


def _render_png(out, canopy, bins_out, DISC, caps, TARGET):
    r = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                       encoding="utf-8-sig"))
    loc = r.get("landscape", {}).get("location") or r.get("location") or [-406400, -406400, 128000]
    scale = (r.get("sampling", {}) or {}).get("scale_xy_cm") or 100.0
    ox, oy = float(loc[0]), float(loc[1])
    bin_cm = float(canopy["params"]["bin_cm"])
    binm = bin_cm / 100.0

    im = Image.open(os.path.join(REPO, "terrain", "alpine_8k.png"))
    W, H = im.size
    ds = max(1, W // 1200)
    z = np.asarray(im.resize((W // ds, H // ds), Image.BILINEAR), dtype=np.float64)
    if z.ndim == 3:
        z = z[..., 0]
    hs = LightSource(azdeg=315, altdeg=45).hillshade(z, vert_exag=0.02)

    fig, ax = plt.subplots(figsize=(11, 11), dpi=110)
    x0, x1 = ox / 100.0, (ox + W * scale) / 100.0
    y0, y1 = oy / 100.0, (oy + H * scale) / 100.0
    ax.imshow(hs, cmap="gray", extent=[x0, x1, y0, y1], origin="upper")

    cmap = plt.get_cmap("viridis")
    ff_cap = caps["forest_floor"]["cap"]
    lo, hi = ff_cap, TARGET   # m_final spans [ff_cap, target]
    for b in bins_out:
        ix, iy = b["bin"]
        wx = (ix * bin_cm) / 100.0
        wy = (iy * bin_cm) / 100.0
        frac = 0.0 if hi <= lo else (b["m_final"] - lo) / (hi - lo)
        ax.add_patch(Rectangle((wx, wy), binm, binm, facecolor=cmap(frac),
                               edgecolor="none", alpha=0.72))
    # disc edges + station markers
    dcol = {"forest_floor": "#ff3030", "plaza": "#30a0ff", "treeline": "#ffd000"}
    for name, (cx, cy) in DISC.items():
        ax.add_patch(Circle((cx / 100.0, cy / 100.0), 512.0, fill=False,
                            edgecolor=dcol[name], lw=1.6, ls="--"))
        ax.plot(cx / 100.0, cy / 100.0, "o", color=dcol[name], ms=7,
                markeredgecolor="k")
        ax.annotate("%s cap %.2f" % (name, caps[name]["cap"]),
                    (cx / 100.0, cy / 100.0), color=dcol[name], fontsize=8,
                    xytext=(6, 6), textcoords="offset points", weight="bold")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_title("Brief 5 D0 -- tree-density multiplier m per 256 m bin\n"
                 "512 m cull discs; forest_floor cap %.2f, plaza/treeline = target %.2f; "
                 "128 m blend" % (ff_cap, TARGET))
    ax.set_xlabel("world X (m)")
    ax.set_ylabel("world Y (m)")
    sm = plt.cm.ScalarMappable(cmap=cmap,
                               norm=plt.Normalize(vmin=lo, vmax=hi))
    sm.set_array([])
    fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04, label="m_final")
    dest = os.path.join(REPO, "research", "brief5", "derived", "zone_map.png")
    fig.savefig(dest, bbox_inches="tight")
    print("wrote", os.path.relpath(dest, REPO))


if __name__ == "__main__":
    main()
