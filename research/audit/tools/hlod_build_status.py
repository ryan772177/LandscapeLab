"""hlod_build_status.py -- was an HLOD build started, what did it build, under which layer?

READ-ONLY. Audit item 1. Reads the 2026-09-13 run logs under `_verify/hlod/`
and answers three separate questions that are easy to conflate:

  1. Did a build RUN?              -- a section log exists
  2. Did it BUILD anything?        -- ApproveRebuild decisions, and
                                      HLOD actor packages written
  3. Under WHICH LAYER?            -- the layer named on each built cell

⛔ THE THIRD QUESTION IS THE ONE THAT MATTERS HERE and it is the one a
rebuild-count cannot answer. `Alpine8K_HLODLayer_Landscape` is
referenced by nothing (0 of 4,339 actors; not in the world default
chain), so a build that reports "46 cells built" built them under
Instanced and Merged, and a reader who sees only the count will believe
the Landscape settings were exercised.

Cell names carry the layer, e.g.
    Alpine8K_HLOD_Instanced_...   Alpine8K_HLOD_Merged_...
so attribution is read off the name, not inferred from the count.
"""
import io
import json
import os
import re
import sys
from collections import Counter


def _find_repo(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md above %s" % start)
        d = nd


REPO = _find_repo(__file__)
HLOD = os.path.join(REPO, "_verify", "hlod")

# ⭐ ONE IMPLEMENTATION OF THE PAIRING, NOT TWO. The build script and
# this audit tool read the same log format, and they had already drifted
# once: this tool paired each cell with its decision while the build
# script counted approvals and rejections in separate buckets with no
# cell identity at all. Two readers of one format are one reader badly
# stored (NN24), so the pairing now lives in scripts/hlod_attribution.py
# and both import it.
sys.path.insert(0, os.path.join(REPO, "scripts"))
import hlod_attribution  # noqa: E402

RE_DECISION = re.compile(r"final decision:\s*(\w+)")
RE_POLICY = re.compile(r"\*\s+(\w+)\s+->\s+(\w+)")
# A built/saved HLOD actor package. The layer is embedded in the name.
# ⭐ THE ATTRIBUTION LINE, and it PRECEDES the decision rather than
# following it:
#   LogWorldPartitionHLODsBuilder: [6 / 6] Building HLOD actor
#     Alpine8K_HLODLayer_Merged/Alpine8K_HLODLayer_Instanced_L0_X-8_Y10...
# Two layer names appear per line -- the FOLDER the actor is filed under
# and the CELL's own name -- and they are NOT always the same, so both
# are captured and neither is assumed to be "the layer".
#
# Attribution pairs each Building line with the NEXT decision line,
# because a decision line carries no cell identity at all. This is why a
# bare Approve/Reject count cannot answer "under which layer", and why
# the previous run's "46 cells" told nobody whether the Landscape layer
# was exercised.
RE_BUILDING = re.compile(
    r"Building HLOD actor\s+([A-Za-z0-9_]+)/([A-Za-z0-9_\-]+)")


def scan_dir(d):
    rows = {"dir": os.path.basename(d), "logs": 0,
            "decisions": Counter(), "policies": Counter(),
            "by_cell_layer": Counter(), "by_folder_layer": Counter(),
            "cells_seen": 0, "decisions_without_a_cell": 0,
            "approved_cells_sample": []}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".log"):
            continue
        rows["logs"] += 1
        p = os.path.join(d, f)
        pending = None          # the most recent Building line
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                m = RE_BUILDING.search(ln)
                if m:
                    pending = (m.group(1), m.group(2))
                    rows["cells_seen"] += 1
                    continue
                m = RE_DECISION.search(ln)
                if m:
                    d_ = m.group(1)
                    rows["decisions"][d_] += 1
                    if pending is None:
                        rows["decisions_without_a_cell"] += 1
                    else:
                        folder, cell = pending
                        # The CELL name is the attribution that matters:
                        # it is what the builder wrote, under the layer
                        # whose name it carries.
                        # Strip the grid suffix at ANY level. Splitting
                        # on "_L0_"/"_L1_" alone left every L2 cell as
                        # its own "layer" -- 1,400 one-count rows that
                        # read as 1,400 layers.
                        mm = re.match(r"^(.*?)_L\d+_X", cell)
                        layer = mm.group(1) if mm else cell
                        rows["by_cell_layer"]["%s:%s" % (layer, d_)] += 1
                        rows["by_folder_layer"]["%s:%s" % (folder, d_)] += 1
                        if (d_ == "ApproveRebuild"
                                and len(rows["approved_cells_sample"]) < 8):
                            rows["approved_cells_sample"].append(
                                "%s/%s" % (folder, cell))
                        pending = None
                    continue
                m = RE_POLICY.search(ln)
                if m:
                    rows["policies"]["%s->%s" % (m.group(1), m.group(2))] += 1
    for k in ("decisions", "policies", "by_cell_layer", "by_folder_layer"):
        rows[k] = dict(rows[k])
    return rows


def main():
    out = {"_what": "HLOD build status from the run logs on disk",
           "runs": []}
    for name in sorted(os.listdir(HLOD)):
        d = os.path.join(HLOD, name)
        if os.path.isdir(d):
            out["runs"].append(scan_dir(d))

    # The other instrument: HLOD actor packages actually on disk, and
    # when they were last written. A decision log says what the builder
    # DECIDED; the packages say what LANDED. NN8 -- different instrument.
    ext = os.path.join(REPO, "LandscapeLab", "Content",
                       "__ExternalActors__", "Alpine8K")
    newest = []
    for root, _dirs, files in os.walk(ext):
        for f in files:
            if not f.endswith(".uasset"):
                continue
            p = os.path.join(root, f)
            try:
                mt = os.path.getmtime(p)
            except OSError:
                continue
            newest.append((mt, os.path.relpath(p, REPO)))
    newest.sort()
    out["n_external_actor_packages"] = len(newest)
    out["newest_10_external_actor_writes"] = [
        {"mtime_epoch": m, "path": p} for m, p in newest[-10:]]

    dst = os.path.join(REPO, "research", "audit", "inputs",
                       "hlod_build_status.json")
    with io.open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    for r in out["runs"]:
        if not r["logs"]:
            continue
        print("%-28s logs=%-3d decisions=%s"
              % (r["dir"], r["logs"], r["decisions"]))
        print("%-28s cells=%d  orphan decisions=%d"
              % ("", r["cells_seen"], r["decisions_without_a_cell"]))
        if r["by_cell_layer"]:
            for k in sorted(r["by_cell_layer"]):
                print("%-28s   by cell layer   %-46s %d"
                      % ("", k, r["by_cell_layer"][k]))
        if r["approved_cells_sample"]:
            print("%-28s   sample approved: %s"
                  % ("", r["approved_cells_sample"][0]))
    print("")
    print("external actor packages: %d" % out["n_external_actor_packages"])
    print("wrote %s (%d bytes)" % (dst, os.path.getsize(dst)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
