---
name: handoff
description: Write the context-exhaustion handoff — what is committed, what is proven, what is decided-but-unbuilt, and the named open items with their decisions already made.
disable-model-invocation: true
argument-hint: [optional note]
allowed-tools: Read, Grep, Glob, Bash
---

# Handoff

**"I ran out of room" is not a handoff. The next session needs the
DECISIONS, not the fatigue.**

Context exhaustion is a liveness condition: commit the groundwork and
hand off cleanly rather than start a unit that cannot be finished
verifiably. A large authored artefact begun on a degraded context is
this project's most expensive failure mode — a builder that reports
success over a graph that is wrong, produced by an author who no longer
holds enough of the system to notice.

## Gather, do not recall

```bash
git status --short
git log --oneline -8
python .claude/hooks/prove_hooks.py 2>&1 | tail -3
python scripts/prove_gates.py 2>&1 | tail -3
```

## Write these four, in this order

1. **COMMITTED** — what is in the tree, by commit hash. Verified by
   `git log`, not from memory.
2. **PROVEN** — what has a measurement behind it, with the number and
   the instrument. Anything without one goes in section 4 instead.
3. **DECIDED BUT UNBUILT** — rulings already made, so the next session
   does not re-litigate them. Include *why*, because a decision without
   its reason gets reopened.
4. **NAMED OPEN ITEMS**, each with its decision already made where one
   exists, and explicitly marked UNKNOWN where none does.

## Then

- Update `CURRENT STATE` in `CLAUDE.md` — **from measurement, never from
  narrative** (NN15).
- State plainly anything **not done, not verified, or turned out wrong**
  (standing rule 10). Nothing else catches it now.
- Confirm two-altitude logging happened for every failure.

$ARGUMENTS
