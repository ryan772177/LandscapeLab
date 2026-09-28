"""advisory.py — H11 and H12: the two NON-BLOCKING hooks.

Both were classified medium/low confidence in the migration table and
built last, deliberately. Both are ADVISORY, and each has a stated
reason — per the migration doc's standard, **a rule that is not enforced
states why, or it reads as a gap.**

THE ADVISORY CHANNEL, from the documented contract
--------------------------------------------------
For post-tool events the documented outcomes are: exit 2 blocks with
stderr as the reason; exit 0 with `{"decision": "block"}` blocks; and
**any other exit code is a NON-BLOCKING error whose FIRST LINE OF
STDERR is shown**. That last one is the advisory channel, and it carries
a hard constraint: **the message must fit on one line**, because only
the first is displayed.

H11 — CONSECUTIVE FAILURES (standing rule 6)
--------------------------------------------
*"If a script errors twice in a row, stop and diagnose. Do not
brute-force variations against a live editor."*

**Advisory, not blocking, and the reason is the rule itself.**
Diagnosing usually means editing the script and RE-RUNNING IT — the same
command failing twice with a fix in between is the SANCTIONED response,
not the violation. A block would prevent the very behaviour the rule
asks for. So it counts, and it points.

**It points at the LESSONS search the streak implies**, because a repeat
failure is the mechanical half of *the same mistake twice is a process
failure*: if this error has been seen before, the lesson exists and did
not fire, and THAT is the defect to fix.

The discriminator is command similarity — the executable plus the script
name — so two unrelated failures do not accumulate.

H12 — DEPENDENCY RECORDING (standing rule 5)
---------------------------------------------
*"Record any dependency added to the project's Python environment."*

**Advisory because there is nowhere canonical to record one.** There is
no `requirements.txt`, `pyproject.toml` or `environment.yml` in this
repo, so the hook cannot verify compliance — it can only ask. Reporting
that absence is worth more than the nag: **a rule with no artefact to
write to is unenforceable by construction**, and that is the finding.
"""

from __future__ import annotations

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATE_DIR = os.path.join(REPO, ".claude", "hooks", "_state")
DEP_FILES = ("requirements.txt", "pyproject.toml", "environment.yml",
             "setup.py", "Pipfile")


def note(line):
    """Non-blocking advisory. ONE LINE — only the first is shown."""
    sys.stderr.write(line.replace("\n", " ").strip() + "\n")
    raise SystemExit(1)


def quiet():
    raise SystemExit(0)


def _sig(cmd):
    """Coarse command signature: interpreter + script name."""
    toks = re.findall(r"[\w./\\-]+", cmd or "")
    exe = os.path.basename(toks[0]) if toks else ""
    script = ""
    for t in toks[1:]:
        if t.endswith(".py"):
            script = os.path.basename(t)
            break
    return (exe + "|" + script).lower()


def _state_path(data):
    os.makedirs(STATE_DIR, exist_ok=True)
    sid = re.sub(r"[^\w-]", "_", str(data.get("session_id") or "nosession"))
    return os.path.join(STATE_DIR, sid + ".json")


def h11_failure(data):
    cmd = (data.get("tool_input") or {}).get("command") or ""
    sig = _sig(cmd)
    if not sig.strip("|"):
        quiet()
    path = _state_path(data)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            st = json.load(fh)
    except Exception:                       # noqa: BLE001
        st = {}
    n = (st.get("count", 0) + 1) if st.get("sig") == sig else 1
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"sig": sig, "count": n}, fh)
    except Exception:                       # noqa: BLE001
        pass
    if n < 2:
        quiet()
    note("STANDING RULE 6: {0} has failed {1}x in a row - stop and "
         "diagnose, do not brute-force. Search first: grep -in "
         "'<error phrase>' LESSONS.md - if this is already a logged "
         "lesson, the lesson did not fire and THAT is the defect."
         .format(sig.replace("|", " "), n))


def h11_success(data):
    """Any success clears the streak."""
    try:
        os.remove(_state_path(data))
    except Exception:                       # noqa: BLE001
        pass
    quiet()


def h12_dependency(data):
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\b(pip|pip3|python -m pip|conda|uv)\b[^|;&]*"
                     r"\binstall\b", cmd):
        quiet()
    have = [f for f in DEP_FILES if os.path.isfile(os.path.join(REPO, f))]
    if have:
        note("STANDING RULE 5: record this dependency in {0} - a "
             "dependency nobody wrote down is a rebuild that fails on a "
             "fresh machine.".format(have[0]))
    note("STANDING RULE 5 IS UNENFORCEABLE HERE: no requirements.txt, "
         "pyproject.toml or environment.yml exists, so there is nowhere "
         "canonical to record this dependency. Create one, or the rule "
         "cannot be kept.")


HANDLERS = {
    "consecutive-failures": h11_failure,
    "clear-streak": h11_success,
    "dependency-record": h12_dependency,
}


def main():
    try:
        which = sys.argv[1] if len(sys.argv) > 1 else ""
        fn = HANDLERS.get(which)
        if fn is None:
            quiet()          # advisory hooks never obstruct on misconfig
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
        fn(data)
        quiet()
    except SystemExit:
        raise
    except BaseException:                   # noqa: BLE001
        # An advisory hook that fails should say NOTHING rather than
        # emit noise. Its failure mode is a missing hint, not an
        # unguarded action -- fail direction follows failure mode.
        raise SystemExit(0)


if __name__ == "__main__":
    main()
