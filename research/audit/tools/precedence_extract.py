"""precedence_extract.py -- audit item 3: who wins, GameOverride or the cvars.

READ-ONLY. Reads the engine log BETWEEN two byte marks, so each render's
lines are attributable to that render and not to its neighbour.

THE QUESTION (AUDIT.md P1-1). MoviePipelineGameOverrideSetting's
`bCinematicQualitySettings` calls Scalability::SetQualityLevels(max) at
pipeline setup (MoviePipelineGameOverrideSetting.cpp:53-65). The bench's
dev profile writes sg.*=1 through MoviePipelineConsoleVariableSetting at
the same moment. Which one the frames render at was unknown.

THE INSTRUMENTS, and there are two independent ones (NN8):

 1. MRQ'S OWN APPLY LOG. MoviePipelineConsoleVariableSetting.cpp:253
    logs, for every cvar it writes:
        Applying CVar "sg.ShadowQuality" PreviousValue: %f NewValue: %f
    PreviousValue is the value the cvar held the instant before that
    setting wrote it. If GameOverride had already raised scalability to
    Cinematic, PreviousValue would read as the cinematic level. So the
    PreviousValue column alone orders the two settings.

 2. THE ECHOED CONSOLE QUERIES. `sg.X` with no argument prints the
    variable's current value; `Scalability` prints every level. Both
    lists run inside the render -- StartConsoleCommands at :271, after
    that setting's own writes; EndConsoleCommands at :279 at teardown.

These share no code path: one is MRQ narrating its own writes, the other
is the console reporting engine state. Agreement between them is
evidence; disagreement is the finding.
"""
import io
import json
import os
import re
import sys

RE_APPLY = re.compile(
    r'Applying CVar "([^"]+)" PreviousValue: ([-\d.]+) NewValue: ([-\d.]+)')
RE_RESTORE = re.compile(
    r'Restoring CVar "([^"]+)" PreviousValue: ([-\d.]+) NewValue: ([-\d.]+)')
RE_EXEC = re.compile(r'Executing Console Command "([^"]+)" (before|after) shot')
# ⛔ A BARE `sg.X` ECHOES NOTHING. The first version of this parser
# expected `LogConsoleResponse: sg.ShadowQuality = "1"` and found ZERO
# matches in both runs -- which would have left the verdict resting on
# instrument 1 alone while the report claimed two. Measured 2026-09-14:
# the log line after `Executing Console Command "sg.ShadowQuality"` is
# EMPTY. Scalability group cvars do not print on a valueless query.
#
# What DOES report is the `Scalability` command, which prints a block:
#   LogConsoleResponse: Display: Current Scalability Settings:
#   LogConsoleResponse: Display:   ShadowQuality (0..3): (custom)
#   LogConsoleResponse: Display:   GlobalIlluminationQuality (0..3): 3
# "(custom)" means the group's cvars were set individually and match no
# canonical preset -- which is exactly what writing sg.*=1 by hand does,
# and is itself informative: a Cinematic override would read 3, not
# custom.
RE_SCAL_HEAD = re.compile(r'Current Scalability Settings:')
RE_SCAL_ROW = re.compile(r'Display:\s+([A-Za-z]+Quality)\s*\(0\.\.3\):\s*(\S+)')


def segment(path, lo, hi):
    with io.open(path, "rb") as fh:
        fh.seek(lo)
        raw = fh.read(hi - lo)
    return raw.decode("utf-8", errors="replace").splitlines()


def analyse(lines, label):
    out = {"label": label, "n_lines": len(lines),
           "applied": {}, "restored": {}, "echoed": [],
           "executed_commands": [], "scalability_blocks": []}
    for ln in lines:
        m = RE_APPLY.search(ln)
        if m:
            out["applied"][m.group(1)] = {"previous": float(m.group(2)),
                                          "new": float(m.group(3))}
            continue
        m = RE_RESTORE.search(ln)
        if m:
            out["restored"][m.group(1)] = {"from": float(m.group(2)),
                                           "to": float(m.group(3))}
            continue
        m = RE_EXEC.search(ln)
        if m:
            out["executed_commands"].append([m.group(1), m.group(2)])
            continue
        if "LogConsoleResponse" in ln:
            if RE_SCAL_HEAD.search(ln):
                # A new block starts; each `Scalability` call prints one.
                out["scalability_blocks"].append({})
                continue
            m = RE_SCAL_ROW.search(ln)
            if m and out["scalability_blocks"]:
                out["scalability_blocks"][-1][m.group(1)] = m.group(2)
    # The two blocks are the render's own before/after samples: the
    # first from StartConsoleCommands, the second from End.
    for i, blk in enumerate(out["scalability_blocks"]):
        for k, v in blk.items():
            out["echoed"].append(["%s@%s" % (k, "start" if i == 0 else
                                             ("end" if i == 1 else i)), v])
    return out


def main():
    log, marks, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    mk = {}
    for line in io.open(marks, encoding="utf-8"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            mk[k] = int(v)
    a = analyse(segment(log, mk["MARK_A"], mk["MARK_B"]),
                "cinematic_quality_settings=True")
    b = analyse(segment(log, mk["MARK_B"], mk["MARK_END"]),
                "cinematic_quality_settings=False")

    # THE VERDICT, derived rather than eyeballed. If GameOverride ran
    # first, the cvar setting would have seen cinematic levels as its
    # PreviousValue, and the two runs would differ in that column.
    keys = sorted(set(a["applied"]) & set(b["applied"]))
    prev_diff = {k: [a["applied"][k]["previous"], b["applied"][k]["previous"]]
                 for k in keys
                 if a["applied"][k]["previous"] != b["applied"][k]["previous"]}
    echo_a = dict(a["echoed"])
    echo_b = dict(b["echoed"])
    echo_diff = {k: [echo_a.get(k), echo_b.get(k)]
                 for k in sorted(set(echo_a) | set(echo_b))
                 if echo_a.get(k) != echo_b.get(k)}

    doc = {
        "_what": "audit item 3 -- GameOverride cinematic_quality_settings "
                 "vs the bench's sg.* cvars, measured on two dev-profile "
                 "captures that differ in that flag alone",
        "_instruments": {
            "1": "MRQ's own apply log, MoviePipelineConsoleVariableSetting"
                 ".cpp:253 -- PreviousValue orders the two settings",
            "2": "sg.* / Scalability echoed from inside the render via "
                 "Start and End console commands",
        },
        "capture_A_cinematic_true": a,
        "capture_B_cinematic_false": b,
        "previous_value_differences": prev_diff,
        "echoed_value_differences": echo_diff,
        "verdict": (
            "THE CVARS WIN: no sg.* PreviousValue and no echoed sg.* value "
            "differs between the two runs, so raising the flag changed "
            "nothing the frames were rendered with."
            if not prev_diff and not echo_diff else
            "DIFFERENCES FOUND -- see previous_value_differences and "
            "echoed_value_differences; the flag reached the render."),
    }
    with io.open(dst, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)

    print("A (cinematic=True ): %d lines, %d cvars applied, %d echoes"
          % (a["n_lines"], len(a["applied"]), len(a["echoed"])))
    print("B (cinematic=False): %d lines, %d cvars applied, %d echoes"
          % (b["n_lines"], len(b["applied"]), len(b["echoed"])))
    print("")
    print("%-42s %-18s %-18s" % ("cvar", "A prev -> new", "B prev -> new"))
    for k in keys:
        print("%-42s %-18s %-18s"
              % (k,
                 "%g -> %g" % (a["applied"][k]["previous"],
                               a["applied"][k]["new"]),
                 "%g -> %g" % (b["applied"][k]["previous"],
                               b["applied"][k]["new"])))
    print("")
    print("echoed sg.* A:", sorted(set(map(tuple, a["echoed"]))))
    print("echoed sg.* B:", sorted(set(map(tuple, b["echoed"]))))
    print("")
    print("PreviousValue differences:", prev_diff or "NONE")
    print("echoed differences       :", echo_diff or "NONE")
    print("")
    print("VERDICT:", doc["verdict"])
    print("wrote %s (%d bytes)" % (dst, os.path.getsize(dst)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
