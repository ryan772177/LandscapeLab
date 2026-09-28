#!/usr/bin/env python3
"""Brief 5 Part C -- P4 density-plan arithmetic.

Offline. Reads measured JSON only; writes research/brief5/input/density_projection.json.
No editor, no network. Every output number traces to a source field named in `_sources`.

Model
-----
The density upgrade is ONE global multiplier `m` on the recipe's existing tree
density field (BRIEF.md:132), set to `m_for.p90_bin` (canopy_cover.json summary,
crown_factor 0.85) = 5.48. Applied globally, every location's LOCAL tree density
scales by m, so the count of live trees VISIBLE at a fixed station scales by m
(culling geometry unchanged). Sensitivity: crown 0.70 -> 8.03, crown 1.00 -> 3.96.

Live-tree GPU cost scales linearly at the measured upper-bound rate
0.1003 ms / 1000 in-frustum-in-cull trees (forest_cost.json; an UPPER bound --
that delta also removed grass + off-frustum trees).

HLOD proxy cost is the GATING UNKNOWN. item8 measured the HLOD *share* at MRQ 4K
quality: treeline 0.576 ms = 1.2% of the 49 ms MRQ frame; the instanced tree
proxies (the part that scales with tree count) were 61,427 instances = 4.37% of
GPUScene. Per the item8 rule-10 caveat, transfer the SHARE FRACTION (~1.2%), not
the MRQ ms, to the game frame. So HLOD instanced-proxy share at a game station =
(item8 share fraction) x current game-frame ms, and it scales ~linearly with m on
the instanced portion. A true in-game HLOD-share ms needs PIE profiling not taken.
Both a fraction-transfer estimate and the naive ms x m upper bound are emitted and
labelled.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
BR = os.path.dirname(HERE)  # research/brief5


def load(rel):
    with open(os.path.join(BR, rel)) as f:
        return json.load(f)


forest = load("input/forest_cost.json")
dens = load("input/density_baseline.json")
canopy = load("derived/canopy_cover.json")
share = load("input/item8_share.json")

# --- multipliers (canopy_cover summary = crown_factor 0.85 default) ---
m_default = canopy["summary"]["m_for"]["p90_bin"]            # 5.48
m_low = canopy["sensitivity"]["crown_factor_1.00"]["m_for"]["p90_bin"]   # 3.96
m_high = canopy["sensitivity"]["crown_factor_0.70"]["m_for"]["p90_bin"]  # 8.03

# --- live-tree cost rate ---
ms_per_1000 = forest["ms_per_1000_in_frustum_in_cull_trees"]  # 0.1003

# --- per-station baseline visible live trees (density_baseline item1) ---
vis = dens["item1_instance_census"]["per_station_visible"]

# forest_floor visible live = the 1844 in-frustum-in-cull trees measured for cost
ff_visible = forest["in_frustum_in_cull_trees"]  # 1844

# BUDGET RULING (Ryan, 2026-09-22, Daylight Density session): R5-1 = 13.0 ms is the
# forest_floor budget (the desk revision), SUPERSEDING an earlier same-day 12.5. 13.0 is
# both the pass/fail budget and the fence abort ceiling (STATE.md:17-24, DENSITY_PLAN.md:34).
# Consequence at 13.0: the current hold 12.645 is 0.355 ms UNDER budget before any density.
BUDGET_CONFLICT = {
    "resolved_by": "Ryan ruling 2026-09-22 (Daylight Density session)",
    "forest_floor_budget_ms": 13.0,      # R5-1 desk revision, supersedes same-day 12.5
    "superseded_12_5": "the earlier same-day 12.5 ruling was reinstated to 13.0",
    "_note": "current hold 12.645 is 0.355 ms under 13.0 before any density increase.",
}
stations = {
    "forest_floor": {
        "visible_live_now": ff_visible,
        "current_hold_ms": 12.645,   # r3_perf.json (POST-hold, 2026-09-21 repair)
        "current_hold_src": "r3_perf.json / STATE.md:91 (post-hold)",
        "budget_ms": 13.0,           # Ryan ruling 2026-09-22 (Daylight Density): R5-1 = 13.0 (desk revision, supersedes same-day 12.5)
        "budget_ratified_ms": 13.0,  # R5-1 desk revision
        "tol_ms": 13.0,              # hard budget = fence abort ceiling (STATE.md:17-24)
        "live_cost_now_ms": forest["gpu_p90_ms"]["as_is"]["mean"]
        - forest["gpu_p90_ms"]["hidden"]["mean"],  # 0.185 measured directly (PRE-hold rate)
        "live_rate_epoch": "PRE-hold (forest_cost.json v3). LOWER BOUND on growth: the T3 "
                           "hold added +1.597 ms of card->geometry cost on in-cull trees "
                           "which ALSO scales with m and is NOT in the 0.1003 card-era rate. "
                           "Post-hold per-tree rate re-measure owed.",
        "hlod_all_forest": False,
    },
    "treeline": {
        "visible_live_now": vis["treeline"]["visible_total"],  # 0
        "current_hold_ms": 7.139,    # T11_VERIFY.md:20 (2026-09-19, pre-hold-repair; 0 live in frustum so hold-insensitive)
        "current_hold_src": "T11_VERIFY.md:20",
        "budget_ms": 7.0,            # queue header (v3 zone budget)
        "budget_ratified_ms": 7.0,
        "tol_ms": 7.7,               # +10%, density_baseline item2_density_sweep
        "live_cost_now_ms": vis["treeline"]["visible_total"] * ms_per_1000 / 1000.0,
        "live_rate_epoch": "n/a (0 live trees in frustum)",
        "hlod_all_forest": True,     # 0 live; forest 300 m-3 km is all HLOD proxy
    },
    "plaza": {
        "visible_live_now": vis["plaza"]["visible_total"],     # 903
        "current_hold_ms": 9.476,    # density_baseline item1_gpu_passes.plaza (2026-09-20, pre-hold-repair)
        "current_hold_src": "density_baseline item1_gpu_passes.plaza (pre-hold-repair; 903 detail-band trees exposed to the hold)",
        "budget_ms": 10.5,           # queue header
        "budget_ratified_ms": 10.5,
        "tol_ms": 11.55,             # density_baseline line 728 budget_tol_ms
        "live_cost_now_ms": vis["plaza"]["visible_total"] * ms_per_1000 / 1000.0,
        "live_rate_epoch": "PRE-hold rate on a pre-hold-repair baseline",
        "hlod_all_forest": False,
    },
}

# --- item8 HLOD share fractions (MRQ) -- sourced from item8_share.json ---
_tl = share["stations"]["treeline"]
hlod_frac_treeline = _tl["hlod_share_pct_of_A"] / 100.0   # 1.17% -> 0.0117
hlod_ms_treeline_mrq = _tl["hlod_share_ms"]               # 0.5764

out = {"_what": "Brief 5 Part C P4 density-plan projection (offline arithmetic).",
       "_sources": {
           "ms_per_1000_visible_trees": "input/forest_cost.json ms_per_1000_in_frustum_in_cull_trees = %s (UPPER bound)" % ms_per_1000,
           "m_multiplier": "derived/canopy_cover.json summary.m_for.p90_bin = %s (crown 0.85); sens 3.96/8.03" % m_default,
           "forest_floor_live_cost_now": "forest_cost.json as_is-hidden = 0.185 ms (measured, x11.4 min_detectable)",
           "visible_counts": "density_baseline.json item1_instance_census.per_station_visible",
           "hlod_share": "item8_share.json stations.treeline.hlod_share_ms=%.4f pct_of_A=%.2f%%; instanced proxies 61,427 = 4.37%% GPUScene (STATE 2026-09-21)" % (hlod_ms_treeline_mrq, _tl["hlod_share_pct_of_A"]),
           "budgets": "queue header (law): forest_floor 13.0, treeline 7.0/tol7.7, plaza 10.5",
       },
       "_budget_conflict": BUDGET_CONFLICT,
       "multipliers": {"default_m": m_default, "sens_low_m": m_low, "sens_high_m": m_high},
       "ms_per_1000_visible_trees": ms_per_1000,
       "stations": {}}

for name, s in stations.items():
    vis_now = s["visible_live_now"]
    live_now = s["live_cost_now_ms"]
    rows = {}
    for label, m in [("m_5.48", m_default), ("m_3.96_sens", m_low), ("m_8.03_sens", m_high)]:
        vis_up = vis_now * m
        # live cost at m: scale the measured live-now by m (linear in visible count)
        live_up = live_now * m
        live_delta = live_up - live_now
        # HLOD growth: only the instanced-proxy share scales with m.
        # fraction-transfer estimate at treeline; other stations get treeline's
        # fraction as a proxy (only station with a measured all-HLOD forest).
        hlod_now_frac = hlod_frac_treeline * s["current_hold_ms"]  # ms-equiv of the 1.2% share
        hlod_up_frac = hlod_now_frac * m
        hlod_delta_frac = hlod_up_frac - hlod_now_frac
        hlod_delta_naive_mrq = hlod_ms_treeline_mrq * (m - 1)  # flagged MRQ-scale upper bound
        proj_frac = s["current_hold_ms"] + live_delta + (hlod_delta_frac if s["hlod_all_forest"] else 0.0)
        hlod_is_proxy = not s["hlod_all_forest"]  # forest_floor/plaza use treeline's fraction as a DISPLAY proxy only
        rows[label] = {
            "m": round(m, 3),
            "visible_live_trees": int(round(vis_up)),
            "live_tree_cost_ms": round(live_up, 4),
            "live_tree_delta_ms": round(live_delta, 4),
            "hlod_share_frac_ms_now": round(hlod_now_frac, 4),
            "hlod_share_frac_delta_ms": round(hlod_delta_frac, 4),
            "hlod_is_display_proxy_from_treeline": hlod_is_proxy,
            "hlod_naive_mrq_delta_ms_FLAG": round(hlod_delta_naive_mrq, 4),
            "projected_ms_ex_clutter_fraction_transfer": round(proj_frac, 4),
            "budget_ms": s["budget_ms"],
            "budget_ratified_ms": s["budget_ratified_ms"],
            "tol_ms": s["tol_ms"],
            "over_budget_ex_clutter": round(proj_frac - s["budget_ms"], 4),
            "over_budget_ratified_ex_clutter": round(proj_frac - s["budget_ratified_ms"], 4),
            "over_tol_ex_clutter": round(proj_frac - s["tol_ms"], 4),
        }
    out["stations"][name] = {
        "visible_live_now": vis_now,
        "live_cost_now_ms": round(live_now, 4),
        "live_rate_epoch": s["live_rate_epoch"],
        "current_hold_ms": s["current_hold_ms"],
        "current_hold_src": s["current_hold_src"],
        "budget_ms": s["budget_ms"],
        "budget_ratified_ms": s["budget_ratified_ms"],
        "tol_ms": s["tol_ms"],
        "hlod_all_forest": s["hlod_all_forest"],
        "at_multiplier": rows,
    }

out["_clutter_note"] = ("Clutter cost column is filled from P3 measured ms/1000 by "
                        "class at the chosen densities; NOT included in "
                        "projected_ms_ex_clutter_* above. Add it per station once "
                        "pcg_cost.json lands.")
out["_hlod_caveat"] = ("HLOD growth is the gating unknown. fraction_transfer scales the "
                       "WHOLE 1.17% treeline share (merged+instanced) by m -- an "
                       "OVER-estimate, since only the instanced-proxy portion (61,427 = "
                       "4.37% GPUScene) truly scales with tree count; taken as a "
                       "conservative upper bound. naive_mrq is 0.5764 ms x (m-1) at MRQ 4K "
                       "quality and MUST NOT be read as game ms. Applied only to treeline "
                       "(0 live, all-HLOD forest); forest_floor/plaza carry it as a "
                       "display proxy, EXCLUDED from their projection. A true in-game HLOD "
                       "share needs PIE profiling not taken (item8 OPEN item).")

with open(os.path.join(BR, "input/density_projection.json"), "w") as f:
    json.dump(out, f, indent=1)
print("wrote input/density_projection.json")
for name, st in out["stations"].items():
    r = st["at_multiplier"]["m_5.48"]
    print("%-13s now=%.3f budget=%.1f(ratified %.1f)  ->m5.48 live+%.3f  proj(ex-clutter)=%.3f  over_hdr=%+.3f over_ratified=%+.3f over_tol=%+.3f"
          % (name, st["current_hold_ms"], st["budget_ms"], st["budget_ratified_ms"],
             r["live_tree_delta_ms"], r["projected_ms_ex_clutter_fraction_transfer"],
             r["over_budget_ex_clutter"], r["over_budget_ratified_ex_clutter"], r["over_tol_ex_clutter"]))
