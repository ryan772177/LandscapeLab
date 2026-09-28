"""subagent_output.py — SubagentStop: NN18 on fleet output.

**A REQUIRED OUTPUT FIELD IS AN INSTRUCTION.** A mandatory field in a
subagent's output schema ASSERTS THAT THE THING EXISTS. If it may not
apply to every input, it must be optional or explicitly nullable, and
the brief must say what null means.

*What this cost:* an `import_plan` was required for a pack that had been
labelled, by the same brief, "a PIPELINE INPUT, not an engine import".
The agent resolved the contradiction by **inventing something to
import** — a terrain replacement nobody wanted — and a diligent reviewer
then spent a third of an expensive audit finding real defects in the
fiction that had been commissioned.

**When a reviewer's findings concern work you did not request, that is a
BRIEF defect, not a reviewer defect.**

WHY THIS IS A HOOK AND NOT AGENT FRONTMATTER
Plugin-shipped agents cannot carry `hooks` — verified in the docs:
*"for security reasons, hooks, mcpServers and permissionMode are not
supported for plugin-shipped agents."* So the gate lives here and
matches on agent type.

FAIL DIRECTION: **DEGRADE, NOT BLOCK.** Blocking a subagent's return
would discard work already paid for, and the failure mode here is a
misleading report rather than an unguarded action. So this appends a
caution to the conversation and never refuses. Fail direction follows
from failure mode.
"""

from __future__ import annotations

import json
import re
import sys

# Phrases that mark a fabricated-because-required field: the agent
# saying, in effect, "I had to fill this in".
INVENTION = (
    r"\bnot applicable\b", r"\bn/?a\b(?!\w)", r"\bnone required\b",
    r"\bno (?:import|plan|changes) (?:needed|required)\b",
    r"\bassum(?:ed|ing)\b", r"\bplaceholder\b", r"\bif applicable\b",
    r"\bcould not (?:determine|verify|find)\b", r"\bunclear\b",
)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
        msg = str(data.get("last_assistant_message") or "")
        agent = str(data.get("agent_type") or "subagent")
    except Exception:                       # noqa: BLE001
        sys.stdout.write("")
        return 0

    if not msg.strip():
        sys.stdout.write("")
        return 0

    hits = sorted({m.group(0).strip().lower()
                   for pat in INVENTION
                   for m in re.finditer(pat, msg, flags=re.I)})
    if not hits:
        sys.stdout.write("")
        return 0

    note = (
        "NN18 CHECK on {0} output — hedging language present: {1}.\n"
        "A REQUIRED OUTPUT FIELD IS AN INSTRUCTION: a mandatory field "
        "asserts the thing EXISTS, so an agent handed one that does not "
        "apply will invent something to fill it. Before acting on this "
        "report, check whether any section describes work that was never "
        "requested — findings about work you did not ask for are a BRIEF "
        "defect, not a reviewer defect.\n"
        "If a field may not apply, make it optional or explicitly "
        "nullable and say what null means."
        .format(agent, ", ".join(repr(h) for h in hits[:6])))

    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStop",
            "additionalContext": note,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
