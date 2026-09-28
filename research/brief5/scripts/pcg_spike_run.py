#!/usr/bin/env python3
"""pcg_spike_run.py -- Brief 5 Part C P3 driver.

ONE gated editor session (rule 11: refuse if any editor already running; launch on the
KNOWN level /Game/Alpine8K; close by launched PID). Runs payloads/pcg_clutter_spike.py
via ue_exec. The level is NEVER saved; the only write is /Game/Scratch/PCG (pruned by the
census). Brackets the session with an item8_census snapshot to PROVE the shipped world
byte-identical.

Writes research/brief5/input/pcg_cost.json.

Usage: python research/brief5/scripts/pcg_spike_run.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import bootstrap          # noqa: E402
import ue_exec            # noqa: E402
import item8_census as ic  # noqa: E402
import item8_capture as cap  # noqa: E402  (reuse launch/close/pids -- stable idioms)

PAYLOAD = os.path.join(SCRIPTS, "payloads", "pcg_clutter_spike.py")
OUT_JSON = os.path.join(REPO, "research", "brief5", "input", "pcg_cost.json")
MAP = "/Game/Alpine8K"
MARKER = "__LLPCG__"

# forest_floor station (forest_cost.json station)
STATION_X, STATION_Y = -166400.0, 192000.0
DISC_R_CM = 51200.0   # 512 m
SEED = 20260921


def main():
    if cap.editor_pids():
        print("REFUSE: editor already running (rule 11).")
        return 2
    before = ic.snapshot()
    print("CENSUS before: umap", (before.get("world_umap_sha256") or "?")[:12],
          "assets", before.get("_count", before.get("count", "?")))

    if not cap.launch_editor(MAP):
        return 2
    try:
        if not cap.wait_ready(timeout=600):
            cap.close_editor()
            return 2
        text = open(PAYLOAD, encoding="utf-8").read()
        for tok, val in {"__SEED__": str(SEED), "__STATION_X__": str(STATION_X),
                         "__STATION_Y__": str(STATION_Y),
                         "__DISC_R_CM__": str(DISC_R_CM)}.items():
            text = text.replace(tok, val)
        code, parsed, raw = ue_exec.run(text, timeout=900, marker=MARKER)
        print("ue_exec code", code)
    finally:
        info = cap.close_editor()
        # ensure zero editors
        if cap.editor_pids():
            cap.kill_all_editors()

    after = ic.snapshot()
    verdict = ic.compare(before, after)
    clean = bool(verdict.get("world_umap_identical")) and \
        not verdict.get("refused_zero_sample") and \
        not verdict.get("stat_changed_non_scratch") and \
        not verdict.get("added_non_scratch") and not verdict.get("removed_non_scratch")
    print("CENSUS verdict clean=", clean, json.dumps(verdict)[:400])

    out = {
        "_what": "Brief 5 Part C P3: ground-clutter game-thread generation/spawn cost, "
                 "measured in-editor on Alpine8K (level NEVER saved), plus PCG-graph "
                 "feasibility. GPU render cost is NOT measured here (owed: -game MRQ pass).",
        "ue_exec_code": code,
        "payload": parsed if code == 0 else {"raw_tail": (raw or "")[-800:]},
        "census_clean": bool(clean),
        "census_verdict": verdict,
        "close_info": info,
        "station_cm": [STATION_X, STATION_Y], "disc_r_cm": DISC_R_CM, "seed": SEED,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", os.path.relpath(OUT_JSON, REPO))
    return 0 if (code == 0 and clean) else 1


if __name__ == "__main__":
    sys.exit(main())
