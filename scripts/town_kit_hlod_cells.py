"""town_kit_hlod_cells.py -- rebuild ONLY the HLOD cells that contain kit houses, one label at a time (2026-10-09).

    python scripts/town_kit_hlod_cells.py            # list the labels it would build
    python scripts/town_kit_hlod_cells.py --go [--min-free-gb 10]

Why: a whole-world HLOD run after a fresh -SetupHLODs approves nearly every cell (~2,115, ~35 h) and fills the disk
(LESSONS 2026-10-08l). The town needs only the cells its houses fall in. Each label goes through
scripts/hlod_build_single.py (-BuildSingleHLOD forces that HLOD actor; a Merged-layer cell also builds its
Instanced children -- pilot 2026-10-08j). Order: every L0 label, then L1 (parents after children).

Labels (audit 2026-10-09 F2/F3): the census (LandscapeLab/Saved/town_hlod_cells.json, scripts/payloads/
town_kit_hlod_census.py) must be NEWER than the last -SetupHLODs log, and a label is kept when its recorded
BOUNDS contain at least one town point (town_kit_load_region.town_points: current houses + streets and, for an
organic plan, the deleted lattice houses + streets -- 2026-10-10 C1) -- no grid constants, and edge houses are
covered by every cell that holds them.
Per build (F1): the cellNN.json record must show true_exit, no fatal, attribution trustworthy, approved >= 1 and
scan.built >= 1, else STOP (hlod_build_single.py always exits 0). Writes BUILD_START_MARKER first (F4, for
town_kit_hlod_check.py --since). Stops before a build when the repo drive has < --min-free-gb.
"""
import argparse
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
CENSUS = os.path.join(REPO, "LandscapeLab", "Saved", "town_hlod_cells.json")


def last_setup_log():
    logs = glob.glob(os.path.join(REPO, "_verify", "hlod", "*_setup", "setup.log"))
    return max(logs, key=os.path.getmtime) if logs else None


def labels():
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    rows = json.load(io.open(CENSUS, encoding="utf-8"))
    # cells are SELECTED by every town actor that stands or stood there -- current houses and streets plus, for the
    # organic re-layout, the deleted lattice houses and streets (design review 2026-10-10 C1: a cell holding only a
    # deleted actor keeps its baked proxy unless rebuilt). One declaration: town_kit_load_region.town_points.
    import town_kit_load_region
    sel, _level = town_kit_load_region.town_points()
    houses = [(h["loc_cm"][0], h["loc_cm"][1]) for h in man["houses"]]
    keep = {0: [], 1: []}
    covered = set()
    for r in rows:
        lab = r["label"]
        lv = 1 if "_L1_" in lab else 0 if "_L0_" in lab else None
        if lv is None:
            continue

        def _in(x, y):
            return r["min"][0] <= x <= r["max"][0] and r["min"][1] <= y <= r["max"][1]
        if any(_in(x, y) for x, y in sel):
            keep[lv].append(lab)
            if lv == 0:
                covered.update(i for i, (x, y) in enumerate(houses) if _in(x, y))
    # coverage is still reported for the CURRENT houses: each must sit in some rebuilt L0 cell
    uncovered = [i for i in range(len(houses)) if i not in covered]
    return sorted(set(keep[0])), sorted(set(keep[1])), uncovered


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--min-free-gb", type=float, default=10.0)
    ap.add_argument("--start", type=int, default=0, help="first label index (L0 then L1 order)")
    ap.add_argument("--count", type=int, default=None, help="labels to build in this call")
    ap.add_argument("--run-root", default=None, help="reuse one run dir across sliced calls (absolute)")
    a = ap.parse_args(argv)
    setup = last_setup_log()
    if not setup or not os.path.isfile(CENSUS) or os.path.getmtime(CENSUS) <= os.path.getmtime(setup):
        print("REFUSE: the HLOD census (%s) is not newer than the last -SetupHLODs log (%s) -- re-run the census"
              % (CENSUS, setup))
        return 4
    l0, l1, uncovered = labels()
    print("L0 labels %d, L1 labels %d; houses in NO L0 cell: %d" % (len(l0), len(l1), len(uncovered)))
    for lab in l0 + l1:
        print("  " + lab)
    if uncovered or not l0:
        print("REFUSE: %d houses lie in no recorded L0 HLOD cell" % len(uncovered))
        return 4
    if not a.go:
        print("dry run (pass --go)")
        return 0
    # per-INVOCATION run dir by default (re-audit 2026-10-09 F1). --run-root reuses one for SLICED foreground runs
    # (2026-10-09: a tool call caps at 10 min, ~2 cells); the marker is written only when the dir is new, and every
    # record must be NEWER than its own build start, so a slice can never pass on an earlier attempt's cellNN.json.
    run_root = a.run_root or os.path.join(REPO, "_verify", "hlod", time.strftime("%Y%m%d_%H%M%S") + "_town_cells")
    os.makedirs(run_root, exist_ok=True)
    marker = os.path.join(run_root, "BUILD_START_MARKER")
    if not os.path.isfile(marker):
        io.open(marker, "w").write(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
    labs = l0 + l1
    end = len(labs) if a.count is None else min(len(labs), a.start + a.count)
    for i, lab in list(enumerate(labs))[a.start:end]:
        free = shutil.disk_usage(REPO).free / 1e9
        if free < a.min_free_gb:
            print("STOP: %.1f GB free < floor %.1f GB before %s" % (free, a.min_free_gb, lab))
            return 4
        t0 = time.time()
        tag = "cell%02d" % i
        subprocess.run([sys.executable, os.path.join(REPO, "scripts", "hlod_build_single.py"), "--label", lab,
                        "--run-dir", run_root.replace("\\", "/"), "--tag", tag], capture_output=True, text=True)
        rec_p = os.path.join(run_root, tag + ".json")
        rec = (json.load(io.open(rec_p, encoding="utf-8"))
               if os.path.isfile(rec_p) and os.path.getmtime(rec_p) > t0 else {})
        sc, at = rec.get("scan") or {}, rec.get("attribution") or {}
        ok = (rec.get("true_exit") is True and not sc.get("fatal") and at.get("trustworthy") is True
              and int(at.get("approved") or 0) >= 1 and int(sc.get("built") or 0) >= 1)
        print("[%2d/%d] %s  %.1f min  free %.1f GB  approved %s built %s fatal %s exit %s -> %s"
              % (i + 1, len(l0) + len(l1), lab, (time.time() - t0) / 60, free, at.get("approved"), sc.get("built"),
                 sc.get("fatal"), rec.get("true_exit"), "ok" if ok else "FAIL"))
        if not ok:
            print("STOP: %s (rule 6) -- record %s" % (lab, rec_p))
            return 4
    print("built labels %d..%d of %d; marker %s" % (a.start, end - 1, len(labs), marker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
