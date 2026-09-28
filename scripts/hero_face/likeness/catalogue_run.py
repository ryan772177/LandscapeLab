"""catalogue_run.py — render one hair onto the placed hero, gate it, index it.

RESUMABLE BY CONSTRUCTION. Every hair writes its own row into
`_verify/<run>/index.json` the moment it completes, and a hair already in the
index is skipped. Killed at any point, the run loses at most the hair in
flight; restarted, it picks up where it stopped. That is the shape the
catalogue needs because it is documentation, not a blocking deliverable, and
morning may arrive mid-run.

EVERY HAIR COSTS THE SAME NOW
-----------------------------
Binds through `LandscapeLabTools.build_groom_binding_for_mesh`
(RECIPES R-GROOMBIND3), which does the MetaHuman pipeline's own four steps in
about 15 s: duplicate an already-built vendor binding, retarget it, RBF-bake
the deformation into a duplicated groom, and rebuild.

That replaced a two-tier cost model. Until 2026-08-20 a hair that had never
been on this character cost a ~12 minute wardrobe select + assemble + two
editor restarts, and only previously-assembled hairs could be swapped cheaply
-- so a 38-hair catalogue was an evening. It is now about an hour.

EVERY ROW IS GATED, INCLUDING THE CROWN CHECK. A hair that reads PRESENT with
1% of its pixels on the scalp is recorded SCALP-BALD, not PRESENT -- the
catalogue is only worth having if a wrong entry is visibly wrong.

Exit codes:
    0  all requested hairs rendered and indexed
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  a hair failed to assign; its row records the failure and the run goes on
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

UNPACKED = "/Game/Hero/Unpacked/MHC_AlpineHero/Grooms"
PY = sys.executable


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hairs", required=True,
                    help="comma-separated groom names as they appear unpacked, "
                         "e.g. Hair_M_BobMessy,Hair_S_Messy")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--bind-dir",
                    default="/Game/Characters/AlpineHero/Grooms/Bindings")
    ap.add_argument("--groom-dir",
                    default="/Game/Characters/AlpineHero/Grooms/Catalogue")
    ap.add_argument("--redo", action="store_true",
                    help="re-render hairs already in the index")
    # THE FRAMING IS A PARAMETER BECAUSE ONE FRAMING CANNOT SERVE ALL 38.
    # It was hardcoded at dist 110 / fov 26 until 2026-08-20, which is right
    # for long hair (it has to fit in frame) and useless for a buzz cut: at
    # 110 cm a 5 mm strand is sub-pixel against a dark forest, so twenty short
    # styles photographed as a bald head while passing the gate. At dist 45 /
    # fov 14 the same buzz cut resolves into individual strands with a correct
    # hairline. The hardcoding ALSO silently overwrote any framing set by a
    # separate place_hero_in_world call, because this respawns -- the tell was
    # a macro run returning 27,991 px against the wide run's 27,994.
    ap.add_argument("--dist", default="110")
    ap.add_argument("--fov", default="26")
    ap.add_argument("--cam-up", default="152")
    ap.add_argument("--look-up", default="158")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    index_path = os.path.join(args.out_dir, "index.json")
    index = {}
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as fh:
            index = json.load(fh)

    hairs = [h.strip() for h in args.hairs.split(",") if h.strip()]
    print("catalogue: %d hair(s), %d already indexed"
          % (len(hairs), len(index)))

    for i, hair in enumerate(hairs, 1):
        # SKIP ONLY COMPLETED ROWS. The row is written BEFORE the gate runs so
        # that a killed run leaves a trace, which means a hair interrupted
        # mid-flight is in the index with no verdict -- and a plain
        # `hair in index` test would skip it forever on resume, silently
        # dropping it from a catalogue that reads as complete. Resume on the
        # verdict, not on the row.
        prior = index.get(hair)
        if prior and prior.get("verdict") and not args.redo:
            print("[%d/%d] %-28s SKIP (%s)"
                  % (i, len(hairs), hair, prior.get("verdict")))
            continue
        if prior and not prior.get("verdict"):
            print("[%d/%d] %-28s RETRY (row had no verdict)"
                  % (i, len(hairs), hair))
        print("[%d/%d] %-28s ..." % (i, len(hairs), hair), flush=True)

        # RESPAWN BEFORE EVERY HAIR. Measured 2026-08-21: a groom component
        # re-assigned repeatedly without respawning degrades -- seven hairs in
        # a row read ABSENT at ~3,300 px / crown 43%, all within 6% of each
        # other, which is one thing measured seven times rather than seven
        # hairs failing. The SAME binding, re-tested after a respawn, rendered
        # 213,267 px at crown 35%. Cheap insurance; the alternative is a
        # catalogue of identical wrong numbers that all look plausible.
        _run([PY, os.path.join(_HERE, "place_hero_in_world.py"),
              "--main-view", "on", "--respawn", "yes",
              "--dist", str(args.dist), "--fov", str(args.fov),
              "--cam-up", str(args.cam_up), "--look-up", str(args.look_up),
              "--timeout", str(args.timeout)])
        # THE FRAMING GOES IN THE ROW. A verdict and a pixel count belong to
        # the framing that produced them, and this catalogue now has two.
        row = {"hair": hair,
               "framing": {"dist": args.dist, "fov": args.fov,
                           "cam_up": args.cam_up, "look_up": args.look_up},
               "started_utc": datetime.datetime.utcnow().strftime(
                   "%Y%m%dT%H%M%SZ")}

        rc, out = _run([PY, os.path.join(_HERE, "..", "..", "ue_exec.py"),
                        os.path.join(_HERE, "catalogue_bind_payload.txt"),
                        "--timeout", str(args.timeout),
                        "--stage-name", "cat_bind",
                        "--set", "HAIR=%s" % hair,
                        "--set", "BIND_DIR=%s" % args.bind_dir,
                        "--set", "GROOM_DIR=%s" % args.groom_dir,
                        "--set", "SUBJECT=HeroInWorld"])
        if rc != 0 or '"ok": true' not in out.lower():
            row["assign"] = "FAILED"
            row["detail"] = out[-400:]
            index[hair] = row
            with open(index_path, "w", encoding="utf-8") as fh:
                json.dump(index, fh, indent=2)
            print("      assign FAILED -- row recorded, continuing")
            continue
        row["assign"] = "ok"

        gate_dir = os.path.join(args.out_dir, "gate_" + hair)
        rc, out = _run([PY, os.path.join(_HERE, "groom_presence.py"),
                        "--stamp", hair, "--out-dir", gate_dir,
                        "--timeout", str(args.timeout)])
        row["gate_exit"] = rc
        gp = os.path.join(gate_dir, "groom_presence.json")
        if os.path.isfile(gp):
            with open(gp, "r", encoding="utf-8") as fh:
                rep = json.load(fh)
            h = (rep.get("final", {}).get("results", {}) or {}).get("Hair", {})
            row["verdict"] = h.get("verdict")
            row["changed_px"] = h.get("changed_px")
            row["crown_frac"] = round(h.get("crown_frac", 0.0), 3)
            row["floor_px"] = rep.get("final", {}).get("floor_px")
        else:
            row["verdict"] = "NO REPORT"

        rc, out = _run([PY, os.path.join(_HERE, "world_shot.py"),
                        "--out-dir", args.out_dir, "--name", "cat_" + hair,
                        "--warm", "50", "--timeout", str(args.timeout)])
        # `world_shot` prints BOTH "frame        : <path>" and
        # "frame counter: <n>", and a startswith("frame") test matched both
        # with the last one winning -- so every row recorded the frame COUNTER
        # as its path and the contact sheet found no images. Match the field,
        # not its prefix.
        for line in out.splitlines():
            head, _, rest = line.partition(":")
            if head.strip() == "frame" and rest.strip():
                row["frame"] = rest.strip()
        index[hair] = row
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=2)
        print("      %-12s %8s px  crown %s  -> indexed"
              % (row.get("verdict"), row.get("changed_px"),
                 row.get("crown_frac")))

    print()
    print("index:", index_path, "(%d rows)" % len(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
