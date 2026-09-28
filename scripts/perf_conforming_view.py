"""perf_conforming_view.py -- make a check_perf-readable view of a standalone run.

    python scripts/perf_conforming_view.py <raw perf_standalone.json> <out.json>

⭐ WHY THIS EXISTS. `perf_standalone.py` writes a RAW artefact that does not
declare `_measurement_class` -- the ratified 2026-09-07 run does not declare
it either. `check_perf` REFUSES an artefact without it when
`gates.require_measurement_class_standalone` is set (check_perf.py:293-294),
so the project's established pattern is a separate CONFORMING VIEW:
`_verify/perf/20260910_standalone4k_e3.json` is exactly that for the 09-07
run. This builds the same thing for any later run instead of hand-authoring
JSON, which is how a transcription error gets into a gate's input.

⛔ A VIEW IS NOT A SECOND MEASUREMENT. It copies its source's stats
VERBATIM. R-PERFBUDGET REJECTED records the trap: the view, its source and
the budgets derived from that source are ONE measurement
(non-negotiable 0), so a check_perf PASS against a view of the run the
budgets came from proves conformance to itself, not headroom.

**That trap does NOT apply when the source is a NEW run.** Comparing a run
taken today against budgets derived from 2026-09-07 is a real comparison,
because the numbers being checked were not used to set the bar. The
`_independent_of_budgets` field below records which case a given view is,
so the next reader does not have to work it out.
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The run the ratified budgets were derived from. A view of THIS run is not
# independent of the budgets; a view of anything else is.
BUDGET_BASIS = "standalone_2026-09-07"


def main():
    if len(sys.argv) != 3:
        print(__doc__.split("\n")[2].strip())
        return 2
    src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])

    with io.open(src, encoding="utf-8") as fh:
        raw = json.load(fh)

    zones = raw.get("zones") or {}
    stations, missing = [], []
    for zone, rec in zones.items():
        stats = rec.get("stats_ms")
        if not stats:
            missing.append((zone, rec.get("error") or "no stats_ms"))
            continue
        stations.append({"zone": zone, "stats_ms": stats})

    # ⛔ Rule 13: a view built from nothing must refuse, not emit an empty
    # artefact that a gate would read as "no zones exceeded budget".
    if not stations:
        print("REFUSING: 0 stations carry stats. An empty view would PASS a "
              "gate by having nothing to check.")
        for z, why in missing:
            print(f"   {z}: {why}")
        return 4
    if missing:
        print(f"WARNING: {len(missing)} zone(s) carry no stats and are OMITTED "
              f"from the view -- a partial board, not a clean one:")
        for z, why in missing:
            print(f"   {z}: {why}")

    rel_src = os.path.relpath(src, REPO_ROOT).replace(os.sep, "/")
    independent = BUDGET_BASIS not in rel_src

    # check_perf selects an artefact by the WORLD's loading range
    # (check_perf.py:254-263) and refuses one that does not declare it: a
    # perf artefact is evidence about the world it was measured in.
    # ⚠ THIS IS THE RECIPE'S DECLARED VALUE, NOT A READ-BACK FROM THE RUN.
    # `perf_standalone` does not record the loading range in force, so this
    # asserts "the world was at its recipe value when measured". That holds
    # only while nothing changed streaming between the recipe and the run,
    # and it is recorded as a declaration rather than a measurement so the
    # next reader does not mistake it for one (standing rule 12).
    wp = os.path.join(REPO_ROOT, "recipes", "alpine_8k.json")
    with io.open(wp, encoding="utf-8") as fh:
        world = json.load(fh)
    rng = (world.get("streaming") or {}).get("main_loading_range_cm")
    if rng is None:
        print("REFUSING: recipes/alpine_8k.json declares no "
              "streaming.main_loading_range_cm, so no artefact can claim one.")
        return 4

    view = {
        "_what": "check_perf-conforming view of a STANDALONE -game run. Stats "
                 "are copied VERBATIM from _source; this file measures "
                 "nothing itself.",
        "_measurement_class": (
            "STANDALONE -game process, 4K (%s read back from CsvProfiler "
            "metadata), FOV %s, BugItGo at the ratified stations."
            % (raw.get("requested_res"), raw.get("fov_h_deg"))),
        "_source": rel_src,
        "declared_loading_range_cm": rng,
        "_declared_loading_range_provenance": (
            "recipes/alpine_8k.json streaming.main_loading_range_cm. A "
            "DECLARATION copied from the recipe, NOT read back from the run "
            "-- perf_standalone does not record the range in force."),
        "_independent_of_budgets": independent,
        "_independence_note": (
            "Source is a NEW run; the ratified budgets were derived from "
            "%s, so checking this against them is a real comparison."
            % BUDGET_BASIS) if independent else (
            "⛔ Source IS the run the budgets were derived from. This view, "
            "its source and the budgets are ONE measurement "
            "(non-negotiable 0). A PASS here proves conformance to itself."),
        "_shader_dispatch": {
            "noxgecontroller": raw.get("noxgecontroller"),
            "no_remote_shader_compile": raw.get("no_remote_shader_compile"),
            "local_ddc_path_override": raw.get("local_ddc_path_override"),
        },
        "stations": stations,
    }
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8", newline="") as fh:
        json.dump(view, fh, indent=1)
    print(f"wrote {dst}")
    print(f"  stations={len(stations)}  independent_of_budgets={independent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
