"""Stamp an artefact produced by an IN-EDITOR payload with its inputs' hashes.

    python scripts/stamp_plan.py city/alpine_basin_town_reachable.json
    python scripts/stamp_plan.py --all

WHY THIS IS SEPARATE FROM THE PLANNERS
--------------------------------------
`plan_city` and `plan_encounters` stamp their own output at write time -- they
run offline, in this repo, with `plan_stamp` importable. The reachable sidecar
and the reachable lattice are produced by remote-exec PAYLOADS inside the
editor, where importing repo modules is awkward and where a payload has already
cost this project real time for carrying the wrong three characters. Keeping the
payload simple and stamping afterwards puts the hashing in ONE implementation
rather than two.

The stamp is still a fact on disk about the same inputs, and
`check_plan_freshness` cannot tell which route wrote it.

WHAT IT WILL NOT DO
-------------------
**It will not invent provenance.** Stamping requires the document to already
declare its inputs (`_produced_by`, `_recipe`, ...). An artefact that declares
none is reported and SKIPPED, never given a guessed one: a stamp asserting
inputs nobody measured is worse than no stamp, because it verifies clean.

It is also IDEMPOTENT and refuses to overwrite a stamp that already matches, so
running it twice cannot silently re-bless an artefact whose inputs moved in
between.
"""
import argparse
import io
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import plan_stamp                                            # noqa: E402

CANDIDATE_DIRS = ["city", "encounters", "foliage"]


def stamp_one(rel, dry=False):
    ap = os.path.join(REPO_ROOT, rel)
    try:
        doc = json.loads(io.open(ap, encoding="utf-8").read())
    except Exception as e:
        return "UNREADABLE", str(e)
    if not isinstance(doc, dict):
        return "NOT A PLAN", "top level is not an object"

    found, missing = plan_stamp.declared_inputs(doc, REPO_ROOT)
    if missing:
        return "DECLARES A MISSING INPUT", ", ".join(
            "%s=%s" % kv for kv in missing)
    if not found:
        return "NO DECLARED INPUTS", ("cannot stamp without provenance; a "
                                      "guessed stamp verifies clean and is "
                                      "worse than none")

    verdict, _ = plan_stamp.verify(doc, REPO_ROOT)
    if verdict == "MATCHES":
        return "ALREADY STAMPED", "%d inputs, all matching" % len(
            doc.get(plan_stamp.STAMP_KEY) or {})

    new = plan_stamp.stamp(doc, REPO_ROOT)
    if dry:
        return "WOULD STAMP", "%d inputs" % len(new)
    doc[plan_stamp.STAMP_KEY] = new
    io.open(ap, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, indent=1) + "\n")
    # read back and verify, rather than trusting the write
    back = json.loads(io.open(ap, encoding="utf-8").read())
    v2, bad = plan_stamp.verify(back, REPO_ROOT)
    if v2 != "MATCHES":
        return "WROTE BUT DOES NOT VERIFY", "%s %s" % (v2, bad)
    return "STAMPED", "%d inputs" % len(new)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true",
                    help="every json under %s" % ", ".join(CANDIDATE_DIRS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = list(args.paths)
    if args.all:
        for d in CANDIDATE_DIRS:
            ad = os.path.join(REPO_ROOT, d)
            if not os.path.isdir(ad):
                continue
            for n in sorted(os.listdir(ad)):
                if n.endswith(".json"):
                    targets.append("%s/%s" % (d, n))
    if not targets:
        print("nothing to do -- pass paths or --all")
        return 2

    counts = {}
    for rel in targets:
        rel = rel.replace("\\", "/")
        verdict, detail = stamp_one(rel, dry=args.dry_run)
        counts[verdict] = counts.get(verdict, 0) + 1
        print("  %-26s %-42s %s" % (verdict, rel, detail))

    print()
    for k in sorted(counts):
        print("  %-26s %d" % (k, counts[k]))
    bad = sum(v for k, v in counts.items()
              if k in ("UNREADABLE", "DECLARES A MISSING INPUT",
                       "WROTE BUT DOES NOT VERIFY"))
    if counts.get("NO DECLARED INPUTS"):
        print()
        print("  %d artefact(s) declare no inputs. Their PRODUCER must declare"
              % counts["NO DECLARED INPUTS"])
        print("  them before they can be stamped -- see place_foliage. Adding a")
        print("  guessed provenance here would make them verify clean while")
        print("  proving nothing.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
