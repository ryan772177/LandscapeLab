"""skyline_iou.py — is the far world PRESENT in the player frame?

Brief 2 Task 0's second acceptance: the player frame and the truth frame must
agree on where the land ends, IoU > 0.9. They differ ONLY in residency — the
truth instrument force-loads every cell, the player instrument gets whatever
World Partition streamed — so a skyline that disagrees is a skyline with
missing world in it. That is the measurement behind "the player near_ground
frame is missing the snow massif that the truth frame shows".

Both masks come from `measure_concept_look.sky_mask`, the SAME function the
rest of Brief 2 measures with, so this is not a second opinion about what sky
is; it is one opinion applied to two frames.

IoU is computed on the SKY mask and reported for the LAND mask too. They are
complements of each other, so they carry the same information, but a reader
chasing "missing mountain" is thinking about land and the land number is the
one that will mean something to them.

    python skyline_iou.py --player A.png --truth B.png [--out x.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_concept_look import sky_mask  # noqa: E402


def _mask(path):
    srgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    m, _step = sky_mask(srgb)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    P, T = _mask(a.player), _mask(a.truth)
    if P.shape != T.shape:
        print("REFUSE: mask shapes %s vs %s -- the two frames must be the "
              "same resolution, or the comparison is between grids, not "
              "worlds" % (P.shape, T.shape))
        return 2

    def iou(x, y):
        inter = np.logical_and(x, y).sum()
        union = np.logical_or(x, y).sum()
        return float(inter) / float(union) if union else 1.0

    sky_iou = iou(P, T)
    land_iou = iou(~P, ~T)

    # WHERE they disagree, and in which direction. "player says sky where
    # truth says land" is the missing-world signature; the opposite would be
    # the player showing MORE than the truth frame, which should not happen
    # and is worth seeing if it ever does.
    player_sky_truth_land = np.logical_and(P, ~T)
    player_land_truth_sky = np.logical_and(~P, T)

    rep = {
        "player": a.player, "truth": a.truth,
        "sky_iou": round(sky_iou, 5),
        "land_iou": round(land_iou, 5),
        "player_sky_fraction": round(float(P.mean()), 5),
        "truth_sky_fraction": round(float(T.mean()), 5),
        "player_sky_truth_land_fraction": round(float(player_sky_truth_land.mean()), 5),
        "player_land_truth_sky_fraction": round(float(player_land_truth_sky.mean()), 5),
        "acceptance": "sky_iou > 0.9",
        "verdict": "PASS" if sky_iou > 0.9 else "FAIL",
        "_read": ("player_sky_truth_land is the MISSING-WORLD signature: the "
                  "player frame shows sky where the fully-loaded world has "
                  "land. The reverse direction should be ~0."),
    }
    js = json.dumps(rep, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(js)
    print(js)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
