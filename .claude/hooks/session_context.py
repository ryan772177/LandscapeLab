"""session_context.py — SessionStart: inject CURRENT STATE + open defects.

Verified against the docs before building: **SessionStart CANNOT BLOCK.**
It is a context-only event, and the injection mechanism is

    {"hookSpecificOutput": {"hookEventName": "SessionStart",
                            "additionalContext": "..."}}

FAILURE MODE IS DIFFERENT FROM A DENY HOOK, DELIBERATELY.
`guard.py` fails closed because its failure would let a guarded action
through. This hook cannot block anything, so its failure mode is
*missing context*, not *unguarded action*. Crashing would therefore be
strictly worse than degrading: it produces no context AND a scary error.

So every failure path here emits VALID JSON that says what could not be
read. Direction 3 for this hook is a corrupted, truncated or missing
CURRENT STATE — it must still return usable JSON and name the gap,
never raise.

That is non-negotiable 6 at the session boundary: a failed read reports
*"I could not read this"*, never silence that looks like *"there is
nothing to report"*.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATE_MD = os.path.join(REPO, "STATE.md")
MAX_CHARS = 6000          # keep the injection cheap


def build():
    parts = []
    missing = []

    # CURRENT STATE lives in STATE.md (moved out of CLAUDE.md 2026-09-13). The
    # old code read CLAUDE.md and matched the first "# CURRENT STATE" string,
    # which is now protocol PROSE near the top -- so it injected the wrong text
    # entirely. Read STATE.md, and fall back to the CLAUDE.md pointer only if
    # STATE.md cannot be read.
    try:
        with io.open(STATE_MD, encoding="utf-8", errors="replace") as fh:
            state = fh.read()
        if len(state) > MAX_CHARS:
            parts.append(state[:MAX_CHARS]
                         + "\n\n[...STATE.md truncated at %d of %d chars; open "
                           "STATE.md for the rest...]" % (MAX_CHARS, len(state)))
        else:
            parts.append(state)
    except OSError as exc:
        missing.append("STATE.md unreadable ({0}); read STATE.md manually for "
                       "CURRENT STATE".format(exc))

    # Git state is a fact about the tree, not a claim in a document.
    try:
        st = subprocess.run(["git", "status", "--short"], cwd=REPO,
                            capture_output=True, text=True, timeout=15)
        dirty = [l for l in (st.stdout or "").splitlines() if l.strip()]
        head = subprocess.run(["git", "log", "-1", "--format=%h %s"],
                              cwd=REPO, capture_output=True, text=True,
                              timeout=15)
        parts.append("## Tree at session start\n"
                     "HEAD: {0}\nuncommitted files: {1}{2}".format(
                         (head.stdout or "?").strip(), len(dirty),
                         ("\n  " + "\n  ".join(dirty[:12])) if dirty else ""))
    except Exception as exc:            # noqa: BLE001
        missing.append("git state unreadable: {0}".format(exc))

    if missing:
        parts.append("## COULD NOT READ\n" + "\n".join(
            "  - " + m for m in missing) +
            "\nThese are gaps in this injection, NOT statements that the "
            "underlying facts are absent.")
    return "\n\n".join(parts)


def main():
    try:
        sys.stdin.read()               # drain; payload not needed
    except Exception:                  # noqa: BLE001
        pass
    try:
        ctx = build()
    except BaseException as exc:       # noqa: BLE001
        ctx = ("SESSION CONTEXT HOOK FAILED: {0}: {1}\n"
               "Read CLAUDE.md CURRENT STATE manually. This hook cannot "
               "block, so the session continues without its context."
               .format(type(exc).__name__, str(exc)[:200]))
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
