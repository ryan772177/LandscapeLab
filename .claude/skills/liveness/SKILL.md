---
name: liveness
description: Context-exhaustion self-check — decide whether to start the next unit or hand off, using the liveness condition rather than optimism.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash
---

# Liveness check

**CONTEXT EXHAUSTION IS A LIVENESS CONDITION.**

When working context nears its limit, **commit the groundwork and hand
off cleanly rather than start a unit that cannot be finished
verifiably.**

A large authored artefact begun on a degraded context is this project's
most expensive failure mode in its purest form: **a builder that reports
success over a graph that is wrong, produced by an author who no longer
holds enough of the system to notice.**

## The check

Ask, honestly:

1. **Can I finish the next unit AND verify it?** Not "start it" —
   finish, measure, and record. A half-built gate is worse than none,
   because it looks like coverage.
2. **Would I still catch a subtle error in it?** The failure mode is not
   running out mid-sentence; it is completing something plausible and
   wrong.
3. **Does the next unit mutate state a reload will not restore?** If so
   the bar is higher, not lower.
4. **Is the tree clean and is CURRENT STATE true right now?** If not,
   that is the next unit, whatever else was planned.

```bash
git status --short
git log --oneline -5
```

## Why this is instrument-distrust turned inward

This is the same discipline the gates get, applied to the author. **A
session that recognises its own degradation is applying non-negotiable 8
to itself — verify with a different instrument than the one that made
the claim — and right now the instrument IS the claim.**

So prefer the evidence you can check: the tree, the commit log, the
proof suites. Not the feeling of having room.

## If the answer is hand off

Run `/handoff`. The next session needs the **DECISIONS**, not the
fatigue. "I ran out of room" is not a handoff.

## If the answer is continue

Say what the unit is and what will prove it, **before** starting. A unit
whose acceptance test you cannot state is a unit you should not begin at
low context.
