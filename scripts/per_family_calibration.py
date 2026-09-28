"""per_family_calibration.py — coherence instrument conditioned on material.

⛔ SUPERSEDED AS A GATE — RECIPES.md R16 (RULED 2026-08-05). Photoreal-lane
membership is ruled by PROVENANCE, not by these appearance statistics: R16 §2
measured GRASS conditioned on family at n=4 with ALL THREE features
OVERLAPPING, so conditioning did NOT rescue the separation the paragraph below
hoped for. This tool (with surface_coherence.py) is RETAINED DESCRIPTIVE ONLY
and "issues no verdicts" (R16 §4). The TRUSTED / VERDICT / ACCEPTED language
and the 0/4 exit codes below are HISTORICAL — read the numbers as a
description of how a surface compares to the set, never as a lane ruling.

The unconditioned check REFUSES: material identity dominates authoring
method, and the photoreal class spans snow to gravel with the stylized
class inside that spread. Conditioning was HOPED to rescue this but R16 §2
measured it insufficient (n=4, all overlap).

**A FAMILY IS ONLY A CONTROL IF BOTH SIDES ACTUALLY MATCH.** Pairing
natural gravel against a man-made tile produced an apparent direction
inversion that was a mis-pairing, not a counterexample. Families with no
stylized counterpart are reported UNPAIRED rather than forced.

**WILD GRASS IS THE HOLDOUT** — no part in calibration. A CLASSIFICATION
IS NOT A MARGIN: landing on the right side by a hair cannot distinguish
separation from noise.
"""
from __future__ import annotations
import math, os, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import surface_coherence as sc      # noqa: E402

F = os.path.join(REPO, "Free")
CAL = os.path.join(F, "_intake", "calib", "Game", "Fab", "Megascans", "Surfaces")
MG = os.path.join(F, "_intake", "megascans_grass", "Game", "Fab", "Megascans", "Surfaces")
PB = os.path.join(F, "_intake", "packbonus", "Game", "Pack_Bonus", "Textures")
WILD = os.path.join(F, "_intake", "megascans_grass", "unpacked")
FEATS = ("spec_slope", "norm_hf", "palette")
MIN_SD = 1.0
THIN = 0.25


def ms(folder, aid, base=CAL):
    d = os.path.join(base, folder, "High", aid + "_tier_1", "Textures")
    return (os.path.join(d, "T_%s_4K_B.PNG" % aid),
            os.path.join(d, "T_%s_4K_N.PNG" % aid))


def acg(s):
    d = os.path.join(F, s + "_4K-PNG")
    return (os.path.join(d, s + "_4K-PNG_Color.png"),
            os.path.join(d, s + "_4K-PNG_NormalDX.png"))


def pb(n):
    d = os.path.join(PB, n)
    return (os.path.join(d, "T_Pack_Bonus_%s_basecolor.PNG" % n),
            os.path.join(d, "T_Pack_Bonus_%s_normal.PNG" % n))


FAMILIES = {
    "GRASS": (
        [("Cut_Grass",) + ms("Cut_Grass_sfenffsa", "sfenffsa"),
         ("Lush_Grass",) + ms("Lush_Grass_xbrffjd", "xbrffjd"),
         ("Clover",) + ms("Clover_vlzlbjon", "vlzlbjon"),
         ("Uncut_Grass",) + ms("Uncut_Grass_oilpt20", "oilpt20", MG)],
        [("PB/" + n,) + pb(n) for n in ("Grass_1", "Grass_2", "Grass_3")]),
    "ROCK/STONE": (
        [("acg/" + s,) + acg(s) for s in ("Rock026", "Rock051", "Rock063")],
        [("PB/" + n,) + pb(n) for n in ("Stone_1", "Stone_2")]),
    "GROUND/SOIL": (
        [("acg/Ground037",) + acg("Ground037"),
         ("Dirt_Ground",) + ms("Dirt_Ground_xdhhdgq", "xdhhdgq"),
         ("Soil_Mud",) + ms("Soil_Mud_pjuph20", "pjuph20")], []),
    "LEAVES/FOREST FLOOR": (
        [("Dry_Fallen_Leaves",) + ms("Dry_Fallen_Leaves_vetladiaw", "vetladiaw"),
         ("Forest_Floor",) + ms("Forest_Floor_sfjmafua", "sfjmafua")], []),
}
HOLDOUT = ("HOLDOUT Wild_Grass", os.path.join(WILD, "WildGrass_C.png"),
           os.path.join(WILD, "WildGrass_N.png"))


def feats(row):
    name, alb, nrm = row
    if not os.path.isfile(alb):
        print("  SKIP %s (missing)" % name)
        return None
    f = sc.features(alb, nrm if os.path.isfile(nrm) else None)
    f["name"] = name
    return f


def main():
    print("PER-FAMILY COHERENCE CALIBRATION  (Wild Grass held out)\n")
    report = {}
    for fam, (php, pst) in FAMILIES.items():
        ph = [x for x in map(feats, php) if x]
        st = [x for x in map(feats, pst) if x]
        print("=== %s ===  photoreal n=%d  stylized n=%d" % (fam, len(ph), len(st)))
        for r in ph + st:
            tag = "photoreal" if r in ph else "stylized "
            print("    %s %-20s %8.4f %8.4f %8.3f" % (
                tag, r["name"], r["spec_slope"], r["norm_hf"], r["palette"]))
        if not st:
            print("    UNPAIRED — no stylized counterpart; no verdict can be")
            print("    calibrated here. Reported, not forced onto a mismatch.\n")
            report[fam] = {"ph": ph, "st": st, "trusted": {}}
            continue
        trusted = {}
        for f in FEATS:
            a = np.array([r[f] for r in ph], float)
            b = np.array([r[f] for r in st], float)
            a, b = a[~np.isnan(a)], b[~np.isnan(b)]
            if len(a) == 0 or len(b) == 0:
                # After dropping NaN (e.g. a family with no normal map) a side
                # can empty; a.min()/b.max() below would ValueError. Skip the
                # feature (mirrors surface_coherence's all-NaN guard).
                print("  %-11s no non-NaN data on one side (pho %d / sty %d) "
                      "-- skipped" % (f, len(a), len(b)))
                continue
            sep = a.min() > b.max() or b.min() > a.max()
            gap = (a.min() - b.max()) if a.min() > b.max() else (
                (b.min() - a.max()) if b.min() > a.max() else 0.0)
            sd = math.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2) \
                if len(a) > 1 and len(b) > 1 else 0.0
            n_sd = gap / sd if sd > 0 else 0.0
            ok = sep and n_sd >= MIN_SD
            if ok:
                trusted[f] = (float(a.mean()), float(b.mean()))
            print("  %-11s n(pho %d/sty %d) pho[%7.4f..%7.4f] sty[%7.4f..%7.4f]"
                  " gap %+.4f  %s"
                  % (f, len(a), len(b), a.min(), a.max(), b.min(), b.max(), gap,
                     ("%.2f SD TRUSTED" % n_sd) if ok else
                     (("%.2f SD below %s" % (n_sd, MIN_SD)) if sep else "OVERLAPS")))
        report[fam] = {"ph": ph, "st": st, "trusted": trusted}
        print("")

    print("--- norm_hf DIRECTION, paired families only ---")
    for fam, d in report.items():
        if not d["st"]:
            continue
        pm = float(np.nanmean([r["norm_hf"] for r in d["ph"]]))
        sm = float(np.nanmean([r["norm_hf"] for r in d["st"]]))
        print("  %-20s photoreal %.4f  stylized %.4f  -> photoreal %s"
              % (fam, pm, sm, "LOWER" if pm < sm else "HIGHER"))

    print("\n--- HOLDOUT TEST ---")
    h = feats(HOLDOUT)
    trusted = report.get("GRASS", {}).get("trusted", {})
    if not trusted:
        print("  REFUSE: GRASS has no trusted feature; holdout unscoreable.")
        return 4
    votes, thin = [], []
    for f, (pm, sm) in trusted.items():
        v = h[f]
        dp, ds = abs(v - pm), abs(v - sm)
        side = "photoreal" if dp < ds else "stylized"
        margin = abs(dp - ds) / max(abs(pm - sm), 1e-9)
        votes.append(side)
        if margin < THIN:
            thin.append(f)
        print("  %-11s %8.4f -> %-9s margin %.2f of class separation"
              % (f, v, side, margin))
    ph_votes = votes.count("photoreal")
    # DESCRIPTIVE classification (R16: not a ruling). Labelled provisional so
    # the "not trusted" lines below do not contradict a printed verdict.
    print("\n  DESCRIPTIVE classification: %s (%d/%d trusted features)" % (
        "photoreal-side" if ph_votes > len(votes) / 2 else "stylized-side",
        ph_votes, len(votes)))
    if thin:
        print("  MARGIN THIN on %s. A CLASSIFICATION IS NOT A MARGIN."
              % ", ".join(thin))
        return 4
    if ph_votes <= len(votes) / 2:
        print("  HOLDOUT did not land photoreal by majority — instrument not "
              "trusted here (historical exit 4; R16 makes this descriptive).")
        return 4
    print("  Instrument would be ACCEPTED for GRASS (historical; R16 retired "
          "the gate — this is descriptive, not a lane ruling).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
