"""hlod_build_single.py -- build ONE HLOD cell, for a measured pilot.

    python scripts/hlod_build_single.py --label "<actor label>" \
        --run-dir <ABSOLUTE PATH>

⭐ WHY THIS EXISTS. `hlod_build_batched` works at manifest-batch
granularity; the smallest unit it can build is a section. The engine
itself can do one cell:

    WorldPartitionHLODsBuilder.cpp:180   GetParamValue("BuildSingleHLOD=", ...)
                                 :1134   filters on HLODActorDesc.GetActorLabel()
                                 :185    bForceBuild = true when set

so `-BuildSingleHLOD=<label>` both scopes AND forces the rebuild, which
is exactly what a pilot needs: one cell, rebuilt whatever the policy
would have decided.

⛔ ABSOLUTE RUN DIR, ALWAYS. The run dir feeds `-abslog=`, and Unreal
resolves relative paths against the engine binaries folder -- a relative
path produced NO LOG AT ALL on 2026-09-14, not an empty one. This
refuses rather than repeating that.

⛔ AND `-noxgecontroller` IS MANDATORY, inherited from
`hlod_build_batched.base_args`: without it shader jobs go to a local
IncrediBuild that never returns them and the run wedges forever
(R-HLOD 08d, measured both ways).

The cell's package is git-tracked, so the caller restores with
`git checkout --` afterwards. This script does not mutate anything else.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hlod_build_batched as HB  # noqa: E402
import hlod_attribution  # noqa: E402

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--label", required=True,
                    help="the HLOD actor label, e.g. "
                         "Alpine8K_HLODLayer_Instanced/"
                         "Alpine8K_MainPartition_L2_X-2_Y0")
    ap.add_argument("--run-dir", required=True,
                    help="ABSOLUTE path; it feeds -abslog=")
    ap.add_argument("--tag", default="single")
    a = ap.parse_args()

    if not os.path.isabs(a.run_dir):
        print("REFUSE: --run-dir must be ABSOLUTE. A relative path feeds")
        print("  -abslog= and Unreal resolves it against the engine")
        print("  binaries folder -- on 2026-09-14 that produced no log at")
        print("  all, and the failure looked like a dead commandlet.")
        return 2

    live = HB.running_editors()
    if live:
        print("REFUSE: %d engine process(es) alive: %s" % (len(live), live))
        print("  Standing rule 11: wait for ZERO editors.")
        return 2

    os.makedirs(a.run_dir, exist_ok=True)
    log_path = os.path.join(a.run_dir, "%s.log" % a.tag)
    cmd = HB.base_args(log_path) + ["-BuildHLODs",
                                    "-BuildSingleHLOD=%s" % a.label]
    print("command:")
    print("  " + " ".join('"%s"' % c if " " in c else c for c in cmd))

    ram = HB.available_ram_gb()
    vram0 = HB.vram_used_mb()
    print("preflight  RAM %s GB   VRAM %s MiB" % (ram, vram0))

    t0 = time.time()
    proc = HB.launch(cmd)
    vram_peak = vram0 or 0
    while proc.poll() is None:
        time.sleep(5)
        v = HB.vram_used_mb()
        if v is not None:
            vram_peak = max(vram_peak, v)
    rc = proc.returncode
    minutes = (time.time() - t0) / 60.0
    # rc is RECORDED, not tested -- see hlod_build_batched's BASELINE_ERRORS.
    print("done rc=%d in %.2f min   VRAM peak %s MiB  (rc is not the verdict)"
          % (rc, minutes, vram_peak))

    left = HB.running_editors()
    if left:
        print("WARNING: process did not truly exit: %s" % left)

    s = HB.scan_log(log_path)
    att = hlod_attribution.attribute(log_path)
    print(hlod_attribution.format_attribution(att))

    rec = {
        "label": a.label, "command": cmd, "returncode": rc,
        "minutes": round(minutes, 3),
        "vram_before_mb": vram0, "vram_peak_mb": vram_peak,
        "log": os.path.relpath(log_path, HB.REPO_ROOT).replace(os.sep, "/"),
        "scan": s, "attribution": att,
        "true_exit": not left,
    }
    out = os.path.join(a.run_dir, "%s.json" % a.tag)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
