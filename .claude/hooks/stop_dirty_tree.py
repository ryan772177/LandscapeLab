"""stop_dirty_tree.py — Stop: no session ends with uncommitted work.

Session protocol: *"No session ends with uncommitted work or a stale
CURRENT STATE."* This is that rule at the Stop boundary.

    {"decision": "block", "reason": "..."}   prevents stopping
    exit 2                                    same effect

THIS HOOK FAILS **OPEN**, AND THAT IS A DELIBERATE EXCEPTION.
Every deny hook in `guard.py` fails closed, because its failure would
let a guarded action through. Here the asymmetry reverses: **the failure
mode of a Stop hook is TRAPPING THE OPERATOR**, and an operator who
cannot stop cannot fix anything — including the very condition being
complained about. A guard that can lock the door from the inside is
worse than the mess it prevents.

So anything this hook cannot establish, it allows, and says why:

  * `stop_hook_active` already set  -> allow. Loop guard; blocking twice
    is how a Stop hook becomes a trap.
  * git unreadable / not a repo     -> allow with a note. "I could not
    check" is never "you may not stop" (non-negotiable 6).
  * MERGE_HEAD / REBASE_HEAD present -> allow with a note. A mid-merge
    tree is *expected* to be dirty; blocking there would trap someone in
    the middle of a conflict resolution, which is precisely when they
    most need to stop and think.

Only a plain, readable, non-merge tree with uncommitted changes blocks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def allow(note=None):
    out = {}
    if note:
        out = {"hookSpecificOutput": {"hookEventName": "Stop",
                                      "additionalContext": note}}
    sys.stdout.write(json.dumps(out) if out else "")
    raise SystemExit(0)


def block(reason):
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    raise SystemExit(0)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:                       # noqa: BLE001
        allow("Stop hook: could not parse its own input; allowing the "
              "stop rather than trapping the session.")

    # Loop guard. Documented field; blocking again after we already
    # blocked once is how this becomes inescapable.
    if data.get("stop_hook_active"):
        allow()

    try:
        gitdir = os.path.join(REPO, ".git")
        for marker in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD"):
            if os.path.exists(os.path.join(gitdir, marker)):
                allow("Stop hook: {0} present, so the tree is expected to "
                      "be dirty. Allowing the stop — blocking mid-merge "
                      "would trap you exactly when stopping is the right "
                      "move.".format(marker))
        st = subprocess.run(["git", "status", "--short"], cwd=REPO,
                            capture_output=True, text=True, timeout=20)
        if st.returncode != 0:
            allow("Stop hook: `git status` failed ({0}). Allowing — 'I "
                  "could not check' is not 'you may not stop'."
                  .format((st.stderr or "").strip()[:120]))
        dirty = [l for l in (st.stdout or "").splitlines() if l.strip()]
    except BaseException as exc:            # noqa: BLE001
        allow("Stop hook: internal failure ({0}: {1}). Allowing the stop "
              "rather than trapping the session."
              .format(type(exc).__name__, str(exc)[:150]))

    if not dirty:
        allow()

    block(
        "SESSION PROTOCOL: no session ends with uncommitted work.\n"
        "{0} uncommitted path(s):\n  {1}\n\n"
        "Commit them (message through a FILE — `git commit -F <path>`), "
        "or say so explicitly if leaving them is deliberate. Under full "
        "autonomy git is the only thing between a wrong idea and a lost "
        "day.".format(len(dirty), "\n  ".join(dirty[:15])))


if __name__ == "__main__":
    main()
