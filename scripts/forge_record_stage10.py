"""forge_record_stage10.py — fold a stage-10 run's measurements back into the
forge's own records.

    python scripts/ue_exec.py scripts/forge_scale_payload.txt ... > s10.txt
    python scripts/forge_record_stage10.py --asset wood_stack --from s10.txt

WHY THIS EXISTS.
Stage 10 runs in a live editor through `ue_exec`, so its result comes back on
stdout and lands NOWHERE. Until 2026-08-30 the only way to record it was to
read the JSON and retype the numbers into `forge_report.json` and `ASSETS.md`.

That is precisely the defect stage 8 shipped with: a value computed, printed,
and written to no file, with a human quietly doing the write. It went unnoticed
for a whole asset because the church's row had been typed by hand. Repeating
the pattern one stage later, having just fixed it, would be the same mistake
twice -- which the operating loop calls a process failure, not an accident.

WHAT IT REFUSES
  * a payload that reported ok:false -- a failed stage 10 is not a record
  * a report whose orientation gate did not pass
  * an asset with no forge_report.json to fold into

It writes the FULL payload output, not a summary, because the summary is what
drifts.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
OUTROOT = os.path.join(REPO, "_verify", "20260830_forge")
ASSETS_MD = os.path.join(REPO, "ASSETS.md")


def _write_atomic(path, text, newline=None):
    """Write via a temp file + os.replace so a crash mid-write cannot leave a
    truncated forge_report.json or a corrupted ASSETS.md (non-atomic in-place
    writes are how a partial write silently damages a tracked file)."""
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
    os.replace(tmp, path)


def extract(text):
    """Pull the payload's JSON out of a ue_exec transcript.

    ue_exec prints discovery lines first, then the payload's `__LL__`-marked
    JSON, then a timing line. Split on the last `__LL__` and parse the FIRST
    balanced JSON object in that tail, rather than assuming the whole file is
    JSON.
    """
    marker = "__LL__"
    if marker in text:
        text = text.split(marker)[-1]
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in the transcript")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON in the transcript")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--from", dest="src", required=True,
                    help="file holding the ue_exec transcript or raw JSON")
    ap.add_argument("--frames", nargs="*", default=[],
                    help="evidence frames to cite in the ASSETS.md row")
    args = ap.parse_args(argv)

    with io.open(args.src, encoding="utf-8", errors="replace") as fh:
        s10 = extract(fh.read())

    outdir = os.path.join(OUTROOT, args.asset)
    rep_p = os.path.join(outdir, "forge_report.json")
    if not os.path.exists(rep_p):
        print("REFUSE: no forge_report.json at %s" % rep_p)
        return 2

    if not s10.get("ok"):
        print("REFUSE: the stage-10 payload reported ok=false. A failed run "
              "is not a record.\n  error: %s" % str(s10.get("error"))[:300])
        return 2
    if not s10.get("orientation_ok"):
        print("REFUSE: orientation_ok is not true. The orientation gate is "
              "the whole reason stage 10 exists -- a scale hit on the wrong "
              "axis reports a PERFECT score. Nothing is recorded.")
        return 2

    # Do not record a MISSING measurement as verified: the row/stages string
    # below pull these with .get(), so an absent key would write "None cm top"
    # into the verified-in-engine column and read as a real result.
    required = ("top_cm", "target_cm", "height_error_cm", "footprint_cm",
                "mesh_tris", "level")
    missing = [k for k in required if s10.get(k) is None]
    if missing:
        print("REFUSE: the stage-10 payload is missing measurement(s) %s; "
              "refusing to record them as verified." % missing)
        return 2

    with io.open(rep_p, encoding="utf-8") as fh:
        rep = json.load(fh)
    # forge_report.json is the folded-into target; a malformed one must refuse,
    # not KeyError on rep["stages"] / rep["name"].
    if not isinstance(rep.get("stages"), dict) or "name" not in rep:
        print("REFUSE: %s lacks a 'stages' dict and/or 'name'." % rep_p)
        return 2
    rep["stage10"] = s10
    rep["stages"]["10_scale"] = (
        "ok -- %s cm top against a %s cm target (error %s cm), orientation "
        "gate PASSED, level %s"
        % (s10.get("top_cm"), s10.get("target_cm"), s10.get("height_error_cm"),
           s10.get("level")))
    if args.frames:
        rep["stage10_frames"] = list(args.frames)
    _write_atomic(rep_p, json.dumps(rep, indent=1))
    # Read back: a write that did not persist stage10 is not a record.
    with io.open(rep_p, encoding="utf-8") as fh:
        if json.load(fh).get("stage10") is None:
            print("REFUSE: forge_report.json did not persist stage10.")
            return 2
    print("forge_report.json <- stage10 (%d keys)" % len(s10))

    # ---- ASSETS.md: flip the "verified in engine" column ------------------
    name = rep["name"]
    cite = ", ".join("`%s`" % f for f in args.frames) if args.frames else ""
    verdict = ("YES — %s cm top vs a %s cm target (error %s cm), footprint "
               "%s cm, orientation gate PASSED, %s tris in engine%s"
               % (s10.get("top_cm"), s10.get("target_cm"),
                  s10.get("height_error_cm"), s10.get("footprint_cm"),
                  s10.get("mesh_tris"),
                  (" — " + cite) if cite else ""))

    with io.open(ASSETS_MD, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    key = "/" + name + "`"
    hit = [i for i, ln in enumerate(lines)
           if ln.startswith("|") and key in ln]
    if len(hit) != 1:
        print("REFUSE: expected exactly 1 ASSETS.md row for %s, found %d. "
              "Not editing a table I cannot identify a row in."
              % (name, len(hit)))
        return 2
    i = hit[0]
    cells = lines[i].split("|")
    # A markdown row is normally  '' | c1 | ... | cN | ''  (leading AND trailing
    # pipe, so first and last split elements are empty). But a row WITHOUT a
    # trailing pipe has its last data cell at [-1], and blindly editing [-2]
    # would overwrite the wrong column. Pick the index from the actual shape.
    last = -2 if cells and cells[-1].strip() == "" else -1
    if len(cells) < 3:
        print("REFUSE: ASSETS.md row for %s has too few cells to edit." % name)
        return 2
    cells[last] = " " + verdict + " "
    lines[i] = "|".join(cells)
    _write_atomic(ASSETS_MD, nl.join(lines), newline="")
    # Read back: confirm the verdict landed in the row before claiming success.
    with io.open(ASSETS_MD, encoding="utf-8", newline="") as fh:
        back = fh.read().replace("\r\n", "\n").split("\n")
    if not (i < len(back) and verdict.strip() in back[i]):
        print("REFUSE: ASSETS.md row did not read back with the new verdict.")
        return 2
    print("ASSETS.md      <- verified-in-engine for %s" % name)
    print("  " + verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
