#!/usr/bin/env python
"""Brief 5 v3 Task 4a/4b -- LOD/billboard/imposter switch distances and the
recipe-vs-asset LOD comparison.

READ-ONLY, offline. Consumes a FRESH tree LOD probe (bounds sphere radius +
per-LOD screen sizes + triangles, captured this session by the editor pass) and
the recipe, and computes for each species and each LOD the distance in metres at
which it engages at the judgement camera, plus the tree's pixel height there.

Formula (header-verified, research/brief5/input/levers_verified.md):
  ComputeBoundsDrawDistance (SceneManagement.cpp:980): Dist = ScreenMultiple*R /
  (ScreenSize*0.5). ScreenMultiple = max(0.5*P00, 0.5*P11); at 4K 90 deg hFOV
  16:9, P11 dominates -> ScreenMultiple = 0.5/tan(vFOV/2), so
      D_switch_cm = ScreenMultiple * R_cm / (ScreenSize * 0.5)
                  = R_cm / (tan(vFOV/2) * ScreenSize)
  All three LOD/view distance scales are 1.0 in this project, so no correction.

Pixel height of a tree of world height H at distance D (angular_budget.pixels_tall):
  px = (H / (2*D*tan(vFOV/2))) * res_v.

Detail threshold 40 px (recipes/alpine_8k.json perception.thresholds_px.detail):
switches that happen while the tree is still >40 px tall are flagged (a visible
representation change above the detail floor).
"""
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
IN = os.path.join(REPO, "research", "brief5", "input")
sys.path.insert(0, os.path.join(REPO, "scripts"))
import angular_budget as ab  # pixels_tall

JUDGE_RES = [3840, 2160]
JUDGE_FOV_H = 90.0


def vfov_deg(fov_h, res):
    w, h = res
    half_h = math.radians(fov_h) / 2.0
    return math.degrees(2.0 * math.atan(math.tan(half_h) * (h / float(w))))


def main(probe_path):
    probe = json.load(open(probe_path, encoding="utf-8"))
    recipe = json.load(open(os.path.join(REPO, "recipes", "alpine_8k.json"),
                            encoding="utf-8-sig"))
    perc = recipe["perception"]
    detail_px = float(perc["thresholds_px"]["detail"])
    vfov = vfov_deg(JUDGE_FOV_H, JUDGE_RES)
    res_v = JUDGE_RES[1]
    tan_half_v = math.tan(math.radians(vfov) / 2.0)

    # recipe LOD screen sizes per species (only ConiferPine declares them)
    recipe_lods = {}
    for sp in recipe.get("foliage", {}).get("species", []):
        if sp.get("system") == "grass" or "role" in sp:
            continue
        recipe_lods[sp["name"]] = {
            "cull_distance_m": sp.get("cull_distance_m"),
            "lod_screen_sizes": [l["screen_size"] for l in sp.get("lods", [])]
                                 if sp.get("lods") else None,
        }

    out = {
        "_what": "Brief 5 v3 Task 4a/4b: LOD/billboard/imposter switch distances "
                 "(header-verified formula) and recipe-vs-asset LOD comparison.",
        "_probe": os.path.relpath(probe_path, REPO),
        "_formula": "D_switch_cm = R_cm / (tan(vFOV/2) * ScreenSize); "
                    "ScreenMultiple = 0.5/tan(vFOV/2) (P11 dominates at 16:9); "
                    "all LOD/view distance scales = 1.0. "
                    "SceneManagement.cpp:980 (ComputeBoundsDrawDistance).",
        "judge_camera": {"res": JUDGE_RES, "fov_h_deg": JUDGE_FOV_H,
                         "vfov_deg": round(vfov, 4)},
        "detail_threshold_px": detail_px,
        "species": [],
    }

    for m in probe.get("meshes", []):
        sp = m["species"]
        R = m.get("bounding_sphere_radius_cm")
        H_cm = m.get("height_cm")  # bounds box_extent.z * 2
        ss = m.get("screen_sizes") or []
        tris = m.get("triangles_per_lod") or []
        nanite = m.get("nanite_enabled")
        rows = []
        for i, s in enumerate(ss):
            if not s or s <= 0 or R is None:
                continue
            d_cm = R / (tan_half_v * s)
            d_m = d_cm / 100.0
            # pixel height of the whole tree at this distance
            px = ab.pixels_tall(H_cm / 100.0, d_m, vfov, res_v) if H_cm else None
            rows.append({
                "lod_index": i,
                "screen_size": round(s, 5),
                "engage_distance_m": round(d_m, 1),
                "tree_px_height_at_engage": round(px, 1) if px else None,
                "triangles": tris[i] if i < len(tris) else None,
                "above_detail_threshold": (px is not None and px > detail_px),
            })
        rl = recipe_lods.get(sp, {})
        # recipe vs asset LOD screen-size comparison
        recipe_ss = rl.get("lod_screen_sizes")
        disagreement = None
        if recipe_ss is not None:
            disagreement = {
                "recipe_lod_screen_sizes": recipe_ss,
                "asset_lod_screen_sizes": [round(x, 5) for x in ss],
                "recipe_lod_count": len(recipe_ss),
                "asset_lod_count": len(ss),
                "differ": (len(recipe_ss) != len(ss)
                           or any(abs(a - b) > 1e-3
                                  for a, b in zip(sorted(recipe_ss, reverse=True),
                                                  sorted(ss, reverse=True)))),
            }
        out["species"].append({
            "species": sp,
            "nanite": nanite,
            "bounding_sphere_radius_cm": R,
            "height_m": round(H_cm / 100.0, 2) if H_cm else None,
            "cull_distance_m_recipe": rl.get("cull_distance_m"),
            "lod_switches": rows,
            "lowest_lod_engage_m": rows[-1]["engage_distance_m"] if rows else None,
            "recipe_vs_asset_lod": disagreement,
        })

    p = os.path.join(IN, "switch_distances.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1)
    for s in out["species"]:
        print("%-14s R=%scm H=%sm nanite=%s"
              % (s["species"], s["bounding_sphere_radius_cm"], s["height_m"],
                 s["nanite"]))
        for r in s["lod_switches"]:
            flag = "  <<< ABOVE 40px" if r["above_detail_threshold"] else ""
            print("    LOD%d ss=%.4f  engage %.1f m  px=%s tris=%s%s"
                  % (r["lod_index"], r["screen_size"], r["engage_distance_m"],
                     r["tree_px_height_at_engage"], r["triangles"], flag))
        if s["recipe_vs_asset_lod"] and s["recipe_vs_asset_lod"]["differ"]:
            print("    RECIPE vs ASSET LOD DISAGREE: recipe %s asset %s"
                  % (s["recipe_vs_asset_lod"]["recipe_lod_screen_sizes"],
                     s["recipe_vs_asset_lod"]["asset_lod_screen_sizes"]))
    print("wrote", os.path.relpath(p, REPO))


if __name__ == "__main__":
    probe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        REPO, "_verify", "bench", "2026-09-20", "tree_lod_probe_v3.json")
    main(probe)
