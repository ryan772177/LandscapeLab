"""heightmap_orientation_check.py — does the heightmap's row/col map to
world X/Y the way the ENGINE imported it?

    python scripts/heightmap_orientation_check.py --station vista \
        --frames _verify/bench/<date>/<tag> [--out J]
    python scripts/heightmap_orientation_check.py --selftest

WHY THIS EXISTS.  Every offline derivation over the heightmap --
`derive_layer_weights`, `hillshade_snow_check`, the acceptance measures
-- assumes `row -> +Y, col -> +X`.  If the engine imported it mirrored,
ALL of them flip TOGETHER and keep agreeing with each other: they share
the premise, so they are ONE measurement, not several (NN0).  The snow
would sit on the sunlit flanks in game while every offline check read
PASS.

The only instrument that does not share the premise is the RENDER.  So:
ray-march the heightmap from a bench station and compare the resulting
SKYLINE against the engine's, taken from the scene-depth pass's sky
ceiling.  A silhouette needs no depth PRECISION -- only which pixels are
sky -- which is what makes this usable where reconstruction is not.

  WHY NOT RECONSTRUCT GEOMETRY FROM THE DEPTH PASS.  Measured
  2026-09-11: the pass is 8-bit LOG depth, 2^(20/255) per step = 5.6% of
  distance per LSB -- 5.6 m at 100 m, 56 m at 1 km.  Correct for
  R-DEPTHBIN's distance bins, useless for positions or normals.  The
  tell: reading the same pass as view-Z vs radial moved a shaded-octant
  population from 41 px to 517,913 px.  This module uses the pass ONLY
  as a sky/not-sky bit.

THE FOUR-MAPPING TABLE IS THE POWER ANALYSIS, and it runs on every
invocation, not only under --selftest.  Scoring one hypothesis alone
would report a number with no scale: is IoU 0.77 good?  Only the three
WRONG mappings can say.  A run where a control scores as well as ours is
reported as NO POWER -- not as a pass.

THE MARGIN IS DERIVED FROM THE RUN'S OWN SYSTEMATIC, not chosen.  The
march and the engine disagree for a known reason: the engine streams and
HLODs distant terrain, so its sky fraction and the march's differ by
`d = |sky_engine - sky_marched|`.  Spread over the union that is worth
at most `d / union` of IoU, so the true mapping must beat the best
control by MORE than that or the verdict is unearned.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from bench_station_derive import (camera_basis, load_terrain,  # noqa: E402
                                  ray_grid, raymarch)
from haze_metrics import CEILING_M, decode_depth_m  # noqa: E402

SKY_FRAC_OF_CEILING = 0.97
T_MAX_M = 6000.0
GRID = (480, 270)

# row -> +Y, col -> +X is OURS; the rest are the wrong hypotheses.
MAPPINGS = [("ours (row->+Y, col->+X)", lambda Z: Z),
            ("row flipped", lambda Z: np.ascontiguousarray(Z[::-1, :])),
            ("col flipped", lambda Z: np.ascontiguousarray(Z[:, ::-1])),
            ("transposed", lambda Z: np.ascontiguousarray(Z.T))]


def engine_sky(depth_png, grid):
    """Sky mask from the scene-depth pass, block-averaged to `grid`."""
    dm = decode_depth_m(depth_png)
    sky = dm > CEILING_M * SKY_FRAC_OF_CEILING
    H, W = sky.shape
    gw, gh = grid
    if H % gh or W % gw:
        raise ValueError("frame %dx%d does not divide by grid %dx%d"
                         % (W, H, gw, gh))
    return sky.reshape(gh, H // gh, gw, W // gw).mean(axis=(1, 3)) > 0.5


def marched_sky(Z, ox, oy, px_m, cam, pitch, yaw, grid, t_max=T_MAX_M):
    gw, gh = grid
    F, R, U = camera_basis(pitch, yaw)
    dirs = ray_grid(F, R, U, 90.0, gw, gh)
    hit = raymarch(Z, ox, oy, px_m, cam, dirs, t_max,
                   math.radians(90.0) / gw).reshape(gh, gw)
    return ~np.isfinite(hit)


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum()) / float(u) if u else 0.0


def evaluate(Z, ox, oy, px_m, cam, pitch, yaw, eng, grid):
    """Score all four mappings against the engine's sky mask."""
    rows = []
    for name, fn in MAPPINGS:
        sky = marched_sky(fn(Z), ox, oy, px_m, cam, pitch, yaw, grid)
        rows.append({"mapping": name, "sky_fraction": round(float(sky.mean()), 4),
                     "iou": round(iou(sky, eng), 4),
                     "pixel_agreement": round(float((sky == eng).mean()), 4)})
    ours = rows[0]
    best_ctrl = max(r["iou"] for r in rows[1:])
    # the run's own systematic, converted to the IoU it could move
    union = float(((marched_sky(Z, ox, oy, px_m, cam, pitch, yaw, grid))
                   | eng).mean())
    d = abs(float(eng.mean()) - ours["sky_fraction"])
    required = d / union if union > 0 else 1.0
    margin = ours["iou"] - best_ctrl
    ok = (ours["iou"] == max(r["iou"] for r in rows)) and (margin > required)
    return {"rows": rows,
            "engine_sky_fraction": round(float(eng.mean()), 4),
            "margin": round(margin, 4),
            "required_margin": round(required, 4),
            "_required_margin_is": ("the streaming/HLOD systematic "
                                    "|sky_engine - sky_ours| spread over the "
                                    "union -- derived per run, not chosen"),
            "verdict": "PASS" if ok else
                       ("NO POWER" if margin <= required else "FAIL")}


# --------------------------------------------------------------------------

def selftest():
    """Synthetic: march a known field to stand in for the engine, then
    confirm ours wins and all three controls lose.  Direction 3 covers
    malformed input."""
    fails = []

    def check(name, cond):
        print("  %-58s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    n, sp = 500, 8.0
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    # deliberately ASYMMETRIC under flip and transpose, or the controls
    # would be indistinguishable and the test would have no power
    Z = (240.0 * np.exp(-(((xx - 140) ** 2 + (yy - 300) ** 2) / 5200.0))
         + 150.0 * np.exp(-(((xx - 380) ** 2 + (yy - 120) ** 2) / 14000.0))
         + 0.06 * xx + 0.015 * yy).astype(np.float32)
    ox = oy = 0.0
    cam = np.array([n * sp * 0.5, 20.0, float(Z[3, n // 2]) + 120.0])
    grid = (160, 90)
    eng = marched_sky(Z, ox, oy, sp, cam, -6.0, 90.0, grid, t_max=4000.0)
    print("direction 1 -- the true mapping wins, with power")
    r = evaluate(Z, ox, oy, sp, cam, -6.0, 90.0, eng, grid)
    for row in r["rows"]:
        print("    %-26s iou %.4f" % (row["mapping"], row["iou"]))
    check("true mapping scores IoU 1.0 against its own march",
          r["rows"][0]["iou"] > 0.999)
    check("verdict PASS", r["verdict"] == "PASS")

    print("direction 2 -- a wrong mapping is BLOCKED")
    # feed the engine mask from a MIRRORED world: ours must now lose
    eng_bad = marched_sky(np.ascontiguousarray(Z[:, ::-1]), ox, oy, sp, cam,
                          -6.0, 90.0, grid, t_max=4000.0)
    r2 = evaluate(Z, ox, oy, sp, cam, -6.0, 90.0, eng_bad, grid)
    check("engine mirrored -> ours does NOT pass",
          r2["verdict"] != "PASS")
    check("every control is distinguishable from ours (has power)",
          all(abs(r["rows"][0]["iou"] - row["iou"]) > 0.02
              for row in r["rows"][1:]))

    print("direction 3 -- malformed input REFUSES")
    try:
        engine_sky(os.path.join(REPO, "does_not_exist.png"), GRID)
        check("missing depth frame refuses", False)
    except Exception:
        check("missing depth frame refuses", True)
    try:
        bad = np.zeros((2160, 3840), dtype=bool)
        H, W = bad.shape
        bad.reshape(7, H // 7, 3840, W // 3840)
        check("indivisible grid refuses", False)
    except Exception:
        check("indivisible grid refuses", True)

    print("\n%s" % ("selftest PASSED" if not fails
                    else "selftest FAILED: %s" % fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=os.path.join(REPO, "recipes",
                                                     "alpine_8k.json"))
    ap.add_argument("--station", default="vista")
    ap.add_argument("--frames", help="directory holding "
                                     "<station>FinalImageSceneDepth.png")
    ap.add_argument("--stations-json", default=os.path.join(
        REPO, "_verify", "bench", "2026-09-05", "bench_stations_derived.json"))
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.frames:
        sys.exit("REFUSE: --frames is required (or run --selftest)")

    dpath = os.path.join(a.frames, "%sFinalImageSceneDepth.png" % a.station)
    if not os.path.isfile(dpath):
        sys.exit("REFUSE: no depth pass at %s" % dpath)
    Z, ox, oy, px_m = load_terrain(a.recipe)
    st = json.load(open(a.stations_json, encoding="utf-8"))
    cs = [float(v) for v in
          st["derived_stations"][a.station]["camera_string"].split(",")]
    cam = np.array(cs[:3]) / 100.0
    eng = engine_sky(dpath, GRID)
    r = evaluate(Z, ox, oy, px_m, cam, cs[3], cs[4], eng, GRID)
    r["station"] = a.station
    r["depth_pass"] = dpath
    print("station %s  camera %s  engine sky %.4f"
          % (a.station, cs[:5], r["engine_sky_fraction"]))
    for row in r["rows"]:
        print("  %-26s sky %.4f  IoU %.4f  agreement %.4f"
              % (row["mapping"], row["sky_fraction"], row["iou"],
                 row["pixel_agreement"]))
    print("margin %.4f vs required %.4f -> %s"
          % (r["margin"], r["required_margin"], r["verdict"]))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "heightmap_orientation_check", "result": r},
                      fh, indent=1)
        print("wrote %s" % a.out)
    return 0 if r["verdict"] == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
