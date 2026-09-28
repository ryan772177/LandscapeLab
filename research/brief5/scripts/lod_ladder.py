#!/usr/bin/env python3
"""lod_ladder.py - Brief 5 (desk): derive a tree representation ladder from measured assets.

Pure python, no UE. Reads CC's tree_lod_probe JSON (bounding radius, height, per-LOD
triangles + screen sizes) and derives, per species:

  1. the CURRENT ladder: where each LOD engages and how tall the tree is on screen there;
  2. the CARD RULE: the lowest LOD of a card/imposter species must not engage while the
     instance is live (it is the HLOD representation; World Partition Instancing HLOD
     uses the lowest LOD regardless of screen size);
  3. the MISSING RUNGS between the last geometric LOD and the cull, by holding on-screen
     triangle density constant at the value the asset author accepted for that LOD;
  4. the TEXEL GATE distance for a card/imposter when its atlas frame size is known;
  5. a triangle-load estimate at a station (uniform areal density inside the cull - an
     ESTIMATE, replaced by --plans when instance positions are available).

Engine relation (verified by CC at SceneManagement.cpp:966/980, UE 5.8):
    ScreenSize = 2 * ScreenMultiple * R / D,  ScreenMultiple = max(0.5*P00, 0.5*P11)
For 16:9 with horizontal FOV h:  P00 = 1/tan(h/2),  P11 = aspect/tan(h/2).
All LOD distance scales are assumed 1.0 (CC verified; pass --lod-scale otherwise).

Usage:
  python lod_ladder.py --probe tree_lod_probe_v3.json --station forest_station.json \
      --cull-cm Conifer=51200 ConiferPine=51200 SpruceSub=51200 SpruceSapling=23827 \
      --out derived_ladder.json
  python lod_ladder.py --selftest
"""
import argparse, json, math, sys

CARD_TRI_MAX = 64          # a LOD with <= this many triangles is a card/imposter, not geometry
RUNG_STEP = 2.0            # each new rung engages at RUNG_STEP x the previous distance
MIN_RUNG_TRIS = 100        # do not ask mesh reduction for a rung below this (it cannot make one)
CARD_LIVE_MARGIN = 1.10    # card engages at >= margin x cull_max, i.e. never while live


def screen_k(res, hfov_deg):
    """k such that ScreenSize = k * R / D."""
    aspect = res[0] / float(res[1])
    t = math.tan(math.radians(hfov_deg) / 2.0)
    p00, p11 = 1.0 / t, aspect / t
    return 2.0 * max(0.5 * p00, 0.5 * p11)


def focal_px(res, hfov_deg):
    return (res[0] / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def engage_cm(k, r_cm, ss, lod_scale=1.0):
    return k * r_cm / ss / lod_scale


def ss_for(k, r_cm, d_cm, lod_scale=1.0):
    return k * r_cm / (d_cm * lod_scale)


def px_tall(h_cm, d_cm, f_px):
    return h_cm / d_cm * f_px


def derive_species(m, k, f_px, cull_cm, px_floor, frame_px=None, lod_scale=1.0):
    r, h = m["bounding_sphere_radius_cm"], m["height_cm"]
    tris, ss = m["triangles_per_lod"], m["screen_sizes"]
    out = {"species": m["species"], "nanite": bool(m.get("nanite_enabled")),
           "R_cm": round(r, 1), "H_m": round(h / 100, 2), "cull_m": round(cull_cm / 100, 1),
           "px_tall_at_cull": round(px_tall(h, cull_cm, f_px), 1),
           "px_floor_distance_m": round(h * f_px / px_floor / 100, 1)}
    if out["nanite"] or len(tris) < 2:
        out["verdict"] = "SINGLE-REPRESENTATION (Nanite): no ladder to derive; no action."
        return out

    # current ladder. LOD0 is used from 0; LOD i>=1 engages at D(ss[i]).
    cur = []
    for i, (t, s) in enumerate(zip(tris, ss)):
        d = 0.0 if i == 0 else engage_cm(k, r, s, lod_scale)
        cur.append({"lod": i, "tris": t, "screen_size": round(s, 5),
                    "engage_m": round(d / 100, 1),
                    "px_tall_at_engage": None if i == 0 else round(px_tall(h, d, f_px), 1),
                    "live": d < cull_cm})
    out["current"] = cur

    last_is_card = tris[-1] <= CARD_TRI_MAX
    out["last_lod_is_card"] = last_is_card
    if not last_is_card:
        out["verdict"] = "no card LOD; ladder is geometric to the cull. No card-rule action."
        g = len(tris) - 1
    else:
        g = len(tris) - 2
        card_d = cur[-1]["engage_m"] * 100
        out["card_defect"] = {
            "engages_m": cur[-1]["engage_m"], "px_tall_there": cur[-1]["px_tall_at_engage"],
            "px_floor": px_floor, "x_over_floor": round(cur[-1]["px_tall_at_engage"] / px_floor, 1),
            "fraction_of_live_range_shown_as_card": round(1 - (card_d / cull_cm) ** 2, 3)
            if card_d < cull_cm else 0.0,
            "_fraction_note": "area fraction of the in-cull disc beyond the card engage distance = "
                              "share of live instances drawn as the card under uniform density."}

    # constant-density rungs anchored on the last geometric LOD's own engage distance
    d_g = cur[g]["engage_m"] * 100 if g > 0 else None
    rungs = []
    if d_g:
        t, d = float(tris[g]), d_g
        while True:
            d *= RUNG_STEP
            t /= RUNG_STEP ** 2
            if d >= cull_cm or t < MIN_RUNG_TRIS:
                break
            rungs.append({"engage_m": round(d / 100, 1), "target_tris": int(round(t)),
                          "percent_of_lod%d" % g: round(100.0 * t / tris[g], 2),
                          "screen_size": round(ss_for(k, r, d, lod_scale), 5),
                          "px_tall_at_engage": round(px_tall(h, d, f_px), 1)})
    out["anchor"] = {"lod": g, "tris": tris[g], "engage_m": cur[g]["engage_m"],
                     "_rule": "required_tris(D) = tris_G * (D_G / D)^2  (constant on-screen "
                              "triangle density, anchored where the asset author engaged LOD G)"}
    out["new_rungs"] = rungs

    # proposed ladder: keep geometric LODs where they are, insert rungs, push the card past the cull
    prop_ss = [round(s, 5) for s in ss[:g + 1]] + [x["screen_size"] for x in rungs]
    prop_tris = list(tris[:g + 1]) + [x["target_tris"] for x in rungs]
    if last_is_card:
        prop_ss.append(round(ss_for(k, r, cull_cm * CARD_LIVE_MARGIN, lod_scale), 5))
        prop_tris.append(tris[-1])
    out["proposed"] = {"screen_sizes": prop_ss, "tris": prop_tris,
                       "_card_note": "last entry is the card: screen size set so it engages at "
                                     "%.2f x cull_max -> never live; HLOD Instancing still uses it "
                                     "(lowest LOD) beyond the streaming range." % CARD_LIVE_MARGIN
                       if last_is_card else None}
    # the no-new-asset fallback: hold LOD G to the cull
    hold_ss = [round(s, 5) for s in ss[:g + 1]]
    if last_is_card:
        hold_ss.append(prop_ss[-1])
    out["fallback_hold"] = {"screen_sizes": hold_ss,
                            "_what": "no new LODs: last geometric LOD held to the cull, card pushed past it."}

    if last_is_card:
        tg = {"frame_px": frame_px}
        if frame_px:
            d_t = h * f_px / frame_px
            tg.update({"card_allowed_beyond_m": round(d_t / 100, 1),
                       "card_may_be_live": d_t < cull_cm,
                       "_rule": "a card is magnified (blurred) wherever tree_px > atlas frame px; "
                                "allowed only beyond D = H * f_px / frame_px"})
        else:
            tg["status"] = "NEEDS_READBACK: atlas texture size and frame grid (Task 2)"
        out["texel_gate"] = tg
    return out


def tri_load(sp, n_in_frustum, cull_cm, which):
    """triangles drawn for n instances uniformly spread over the in-cull sector."""
    if "current" not in sp:
        return None
    if which == "current":
        edges = [(c["engage_m"] * 100, c["tris"]) for c in sp["current"]]
    else:
        key = "proposed" if which == "proposed" else "fallback_hold"
        k_ss = sp[key]["screen_sizes"]
        tr = sp["proposed"]["tris"] if which == "proposed" else \
            [c["tris"] for c in sp["current"]][:len(k_ss) - (1 if sp["last_lod_is_card"] else 0)] + \
            ([sp["current"][-1]["tris"]] if sp["last_lod_is_card"] else [])
        kk = sp["_k"]
        edges = [(0.0 if i == 0 else kk * sp["R_cm"] / s, t) for i, (s, t) in enumerate(zip(k_ss, tr))]
    total = 0.0
    for i, (d0, t) in enumerate(edges):
        d1 = edges[i + 1][0] if i + 1 < len(edges) else cull_cm
        d0, d1 = min(d0, cull_cm), min(d1, cull_cm)
        total += n_in_frustum * (d1 ** 2 - d0 ** 2) / cull_cm ** 2 * t
    return int(round(total))


def run(probe, cam_res, hfov, culls, px_floor, frames, station, lod_scale):
    k, f = screen_k(cam_res, hfov), focal_px(cam_res, hfov)
    res = {"_what": "Brief 5 desk derivation: tree representation ladder",
           "judge_camera": {"res": cam_res, "fov_h_deg": hfov, "k_screen": round(k, 4),
                            "focal_px": round(f, 1)},
           "px_floor": px_floor, "lod_distance_scale": lod_scale, "species": []}
    for m in probe["meshes"]:
        cull = culls.get(m["species"])
        if cull is None:
            raise SystemExit("no --cull-cm for %s" % m["species"])
        sp = derive_species(m, k, f, cull, px_floor, frames.get(m["species"]), lod_scale)
        sp["_k"] = k
        if station:
            n = station["per_species"].get(m["species"], {}).get("in_frustum_in_cull", 0)
            if "current" in sp:
                sp["station_tri_load"] = {
                    "n_in_frustum_in_cull": n,
                    "current": tri_load(sp, n, cull, "current"),
                    "fallback_hold": tri_load(sp, n, cull, "hold"),
                    "proposed": tri_load(sp, n, cull, "proposed"),
                    "_assumption": "uniform areal density inside the cull sector (ESTIMATE)"}
        sp.pop("_k")
        res["species"].append(sp)
    if station:
        tot = {w: sum((s.get("station_tri_load") or {}).get(w) or 0 for s in res["species"])
               for w in ("current", "fallback_hold", "proposed")}
        res["station_tri_load_total_non_nanite"] = tot
    return res


def selftest():
    ok = True
    k = screen_k([3840, 2160], 90.0)
    ok &= abs(k - 16 / 9.0) < 1e-9                      # 1.7778 at 16:9 / 90 deg
    ok &= abs(focal_px([3840, 2160], 90.0) - 1920) < 1e-6
    # CC's measured pine: R 1209.66, ss 0.16821 -> 127.8 m, 332 px for H 2210.7
    d = engage_cm(k, 1209.6594, 0.16820885)
    ok &= abs(d / 100 - 127.8) < 0.15
    ok &= abs(px_tall(2210.72, d, 1920) - 332.0) < 0.6
    # round trip
    ok &= abs(ss_for(k, 1209.6594, d) - 0.16820885) < 1e-9
    # rung rule: 4000 tris engaging at 100 m, cull 512 -> rungs at 200 (1000), 400 (250)
    m = {"species": "T", "nanite_enabled": False, "bounding_sphere_radius_cm": 1000.0,
         "height_cm": 2000.0, "triangles_per_lod": [16000, 4000, 12],
         "screen_sizes": [1.0, k * 1000.0 / 10000.0, k * 1000.0 / 15000.0]}
    sp = derive_species(m, k, 1920.0, 51200.0, 40.0, frame_px=256)
    r = sp["new_rungs"]
    ok &= [x["target_tris"] for x in r] == [1000, 250] and [x["engage_m"] for x in r] == [200.0, 400.0]
    ok &= sp["last_lod_is_card"] and sp["proposed"]["tris"] == [16000, 4000, 1000, 250, 12]
    # card pushed past the cull
    ok &= engage_cm(k, 1000.0, sp["proposed"]["screen_sizes"][-1]) > 51200.0
    # texel gate: H 20 m, 256 px frame -> 150 m
    ok &= abs(sp["texel_gate"]["card_allowed_beyond_m"] - 150.0) < 0.05
    # tri load conservation: all instances inside one band
    sp["_k"] = k
    tl = tri_load(sp, 100, 51200.0, "current")
    exp = 100 * ((100 / 512.) ** 2 * 16000 + ((150 ** 2 - 100 ** 2) / 512. ** 2) * 4000
                 + (1 - (150 / 512.) ** 2) * 12)
    ok &= abs(tl - exp) < 2
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe"); ap.add_argument("--station"); ap.add_argument("--out")
    ap.add_argument("--res", nargs=2, type=int, default=[3840, 2160])
    ap.add_argument("--hfov", type=float, default=90.0)
    ap.add_argument("--px-floor", type=float, default=40.0)
    ap.add_argument("--lod-scale", type=float, default=1.0)
    ap.add_argument("--cull-cm", nargs="*", default=[], help="Species=cm ...")
    ap.add_argument("--frame-px", nargs="*", default=[], help="Species=px (atlas frame size) ...")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.probe:
        ap.error("--probe required")
    kv = lambda xs, c: {x.split("=")[0]: c(x.split("=")[1]) for x in xs}
    res = run(json.load(open(a.probe, encoding="utf-8")), a.res, a.hfov, kv(a.cull_cm, float),
              a.px_floor, kv(a.frame_px, float),
              json.load(open(a.station, encoding="utf-8")) if a.station else None, a.lod_scale)
    s = json.dumps(res, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(s + "\n")
    else:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
