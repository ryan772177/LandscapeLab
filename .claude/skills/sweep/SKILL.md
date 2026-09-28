---
name: sweep
description: NN4 defect-class sweep — when you find a defect, grep for the class everywhere, in the SAME commit as the fix, as a mechanical step.
disable-model-invocation: true
argument-hint: [defect description or pattern]
allowed-tools: Read, Grep, Glob, Bash
---

# Defect-class sweep

**When you find a defect class, grep for it everywhere IMMEDIATELY.**

NaN-passing-range-checks was fixed **five times** because it was fixed
locally each time. **The sweep happens in the SAME COMMIT as the fix, as
a mechanical step — not as an intention recorded for later.** Every
recurrence in this project was logged conscientiously and swept never.

**NN4a — automatic escalation:** a trap class that recurs across **TWO
DIFFERENT TOOLS** is promoted to shared infrastructure on the spot,
without waiting for a third. One implementation, one caller-visible API,
with a mandatory post-operation assertion. **Individually-patched copies
of the same fix then become a REJECTED pattern in their own right.**

## Do

1. **Name the class**, not the instance. Not "this script mangled a
   path" but "any script passing a content path through Git Bash".
2. **Grep the whole repo**, not the file you were in.
3. **Check the sweep can find the thing** — run it against the known
   instance first. A sweep that returns nothing because the pattern is
   wrong reads exactly like a clean repo.
4. **Fix every hit in this commit**, or list the ones you did not and
   say why.

## Sweeps that already exist

```bash
python .claude/hooks/prove_hooks.py     # hook layer, three directions
python scripts/prove_gates.py           # gates + DEAD-GATE sweep
```

`prove_gates` includes a structural sweep for **check-like functions
with no call site** — added after three invariant suites were found
dead, defined and correct and never called. That is the pattern to
imitate: **once a class is understood, encode the sweep so it runs
forever**, rather than relying on someone remembering to look.

## The generalisation is what catches the next one

The sweep ordered after the `load_level` crash found `open_level.py` on
its first hit — a tool that had already solved the problem twice — and
that discovery **overturned a rule that had just been written and
ratified**. The instruction to generalise caught an error in the
specific case.

$ARGUMENTS
