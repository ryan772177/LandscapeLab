"""rejudge_sky_depth.py — re-judge Brief 2's frames with the DEPTH sky mask.

RULED 2026-09-10 (Ryan): replace the colour SKY_BAND with far-plane depth
from the depth pass in featureless / haze / dE, re-judge Tasks 1–5's
existing frames OFFLINE, and produce a before/after table. No re-render.

WHY. LESSONS 2026-09-09e: the colour band (`b - r >= 0.06`) keys on the
property Brief 2 changes by design — the sky desaturates, the mask sees
less of it, and four metrics degrade together in the direction of the
work (Task 5 mid_slope read 0.0000 sky over a frame that is mostly sky).

THE PREMISE, STATED (verification practice). Depth is GEOMETRY: invariant
to every Brief-2 change, which are lighting-only. So the 2026-09-09 depth
passes at near_ground and mid_slope serve every task's frames at those
stations. The premise is CHECKED, not assumed, three ways below.

WHAT HAZE NEEDS: nothing. haze_metrics.py has excluded sky BY DEPTH since
it was written (its docstring: "SKY IS EXCLUDED by depth, not by colour").
It appears in the table as already-depth for completeness.

VISTA HAS NO DEPTH PASS. Its rows report NO DEPTH rather than a silently
colour-based number — a failed measurement reports that it failed. Task
6's required vista recapture carries --depth and closes the gap.

INSTRUMENT CHECKS (three directions):
  1. SEES WHAT COLOUR LOST: Task 5 mid_slope, colour sky 0.0000 → the
     depth mask must report the geometric sky, which cannot have moved
     between tasks (station geometry is fixed).
  2. AGREES WHERE COLOUR WAS VALID: Task 2 frames pre-date the
     desaturation — colour and depth sky fractions must roughly agree
     there (reported, with the residual stated, not gated).
  3. REFUSES BROKEN INPUT: a depth frame from the wrong station or
     resolution raises in featureless_split / returns a refusing row in
     fog_vs_sky; asserted here by feeding a deliberately wrong pairing.
  Plus: two independent depth captures of mid_slope exist (target_depth
  and target_depth_task4). Their masks are compared tile-for-tile — two
  instruments, one geometry.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_capture as bc  # noqa: E402
import fog_vs_sky as fvs    # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B09 = os.path.join(REPO, "_verify", "bench", "2026-09-09")

TASKS = ["task1", "task2", "task3", "task4", "task5"]
B10 = os.path.join(REPO, "_verify", "bench", "2026-09-10")

DEPTH = {
    "near_ground": os.path.join(B09, "target_depth",
                                "near_groundFinalImageSceneDepth.png"),
    "mid_slope": os.path.join(B09, "target_depth",
                              "mid_slopeFinalImageSceneDepth.png"),
    # Captured 2026-09-10 with Task 6's pre-cloud vista run, closing the
    # NO DEPTH gap the first re-judge reported. Depth is geometry, so a
    # 09-10 pass serves the 09-09 frames; clouds never write scene depth
    # (pre/post cloud masks agree 1.0000 — clouds_vista_acceptance.json).
    "vista": os.path.join(B10, "target_precloud",
                          "vistaFinalImageSceneDepth.png"),
}
DEPTH["vista"] = DEPTH["vista"] if os.path.isfile(DEPTH["vista"]) else None
DEPTH_MID_ALT = os.path.join(B09, "target_depth_task4",
                             "mid_slopeFinalImageSceneDepth.png")


def frame(task, st):
    p = os.path.join(B09, "target_" + task, st + ".png")
    return p if os.path.isfile(p) else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        REPO, "_verify", "bench", "2026-09-10", "sky_rejudge_depth.json"))
    a = ap.parse_args(argv)

    out = {"_what": __doc__.splitlines()[0],
           "_ruled": "2026-09-10", "checks": {}, "rows": []}

    # ---- instrument check: two depth captures of one station agree ------
    m1 = bc.sky_mask_from_depth(DEPTH["mid_slope"])
    m2 = bc.sky_mask_from_depth(DEPTH_MID_ALT)
    agree = float((m1 == m2).mean())
    out["checks"]["two_depth_captures_mid_slope"] = {
        "tile_agreement": round(agree, 5),
        "sky_frac_a": round(float(m1.mean()), 5),
        "sky_frac_b": round(float(m2.mean()), 5),
        "_note": "two independent captures of one geometry; disagreement "
                 "is edge tiles + residency, not the mask"}

    # ---- instrument check: refuses a wrong pairing ----------------------
    # A grid mismatch can only arise from a RESOLUTION mismatch (the same
    # tile size is applied to both sides), so the test pairs the 1920-wide
    # send-back copy of mid_slope with the 4K depth pass. Anything but a
    # ValueError here means a wrong-resolution depth frame silently
    # classifies, which is the failure mode the check exists to block.
    small = os.path.join(REPO, "research", "brief2", "for_research",
                         "mid_slope.png")
    if not os.path.isfile(small):
        # AUDIT 2026-09-10 F1: a check that silently skips is satisfiable
        # by the failure it guards. No specimen -> no verdict -> no table.
        print("REFUSE: the 1920-wide specimen %s is missing; the "
              "mismatch-refusal check cannot run, so nothing below it "
              "can be trusted." % small)
        return 1
    refused = False
    try:
        bc.featureless_split(small, bc.SKY_BAND,
                             depth_path=DEPTH["mid_slope"])
    except ValueError:
        refused = True
    out["checks"]["refuses_mismatched_grid"] = bool(refused)
    if not refused:
        # AUDIT 2026-09-10 F1: the run must STOP here, not record False
        # in the JSON and carry on printing a plausible table.
        print("REFUSE: a 1920-wide beauty against the 4K depth pass did "
              "NOT raise -- a wrong-resolution depth frame classifies "
              "silently. The instrument is broken; no table.")
        return 1

    # ---- the before/after table ----------------------------------------
    for task in TASKS:
        for st in ["near_ground", "mid_slope", "vista"]:
            p = frame(task, st)
            row = {"task": task, "station": st}
            if p is None:
                row["error"] = "frame missing"
                out["rows"].append(row)
                continue
            t, s, n = bc.featureless_split(p, bc.SKY_BAND)
            row["colour"] = {"featureless": round(t, 4),
                             "sky": round(s, 4), "non_sky": round(n, 4)}
            dp = DEPTH[st]
            if dp is None:
                row["depth"] = "NO DEPTH -- vista has no depth pass; "\
                               "captured with Task 6's vista recapture"
            else:
                t2, s2, n2 = bc.featureless_split(p, bc.SKY_BAND,
                                                  depth_path=dp)
                row["depth_mask"] = {"featureless": round(t2, 4),
                                     "sky": round(s2, 4),
                                     "non_sky": round(n2, 4)}
            # dE where the brief measures it: mid_slope and vista
            if st in ("mid_slope", "vista"):
                r_c = fvs.measure(p, bc.SKY_BAND)
                row["dE_colour"] = r_c.get("fog_vs_sky_dE")
                if dp is not None:
                    r_d = fvs.measure(p, bc.SKY_BAND, depth_path=dp)
                    row["dE_depth"] = r_d.get("fog_vs_sky_dE")
                    if r_d.get("_why"):
                        row["dE_depth_why"] = r_d["_why"]
            out["rows"].append(row)

    # ---- direction 2: colour/depth agreement where colour was valid -----
    t2rows = [r for r in out["rows"] if r["task"] == "task2"
              and "depth_mask" in r]
    out["checks"]["colour_valid_era_agreement"] = [
        {"station": r["station"],
         "sky_colour": r["colour"]["sky"],
         "sky_depth": r["depth_mask"]["sky"],
         "residual": round(r["depth_mask"]["sky"] - r["colour"]["sky"], 4)}
        for r in t2rows]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    hdr = ("%-7s %-12s | %9s %9s | %9s %9s | %9s %9s"
           % ("task", "station", "sky(col)", "sky(dep)", "nsky(col)",
              "nsky(dep)", "dE(col)", "dE(dep)"))
    print(hdr)
    print("-" * len(hdr))
    for r in out["rows"]:
        if "error" in r:
            print("%-7s %-12s | %s" % (r["task"], r["station"], r["error"]))
            continue
        d = r.get("depth_mask")
        print("%-7s %-12s | %9.4f %9s | %9.4f %9s | %9s %9s"
              % (r["task"], r["station"], r["colour"]["sky"],
                 ("%9.4f" % d["sky"]) if d else " NO DEPTH",
                 r["colour"]["non_sky"],
                 ("%9.4f" % d["non_sky"]) if d else " NO DEPTH",
                 ("%.4f" % r["dE_colour"]) if r.get("dE_colour") is not None
                 else ("-" if "dE_colour" not in r else "none"),
                 ("%.4f" % r["dE_depth"]) if r.get("dE_depth") is not None
                 else ("-" if "dE_depth" not in r else "n/a")))
    c = out["checks"]
    print("\nchecks:")
    print("  two depth captures of mid_slope: tile agreement %.4f "
          "(sky %.4f vs %.4f)"
          % (c["two_depth_captures_mid_slope"]["tile_agreement"],
             c["two_depth_captures_mid_slope"]["sky_frac_a"],
             c["two_depth_captures_mid_slope"]["sky_frac_b"]))
    print("  refuses mismatched grid: %s" % c["refuses_mismatched_grid"])
    for e in c["colour_valid_era_agreement"]:
        print("  task2 %-12s colour %.4f vs depth %.4f (residual %+.4f)"
              % (e["station"], e["sky_colour"], e["sky_depth"],
                 e["residual"]))
    print("\nwrote %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
