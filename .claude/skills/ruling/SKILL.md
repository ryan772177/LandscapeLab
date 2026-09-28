---
name: ruling
description: Record an operator ruling at both altitudes with today's LOCAL date, preserving any superseded version.
disable-model-invocation: true
argument-hint: [the ruling]
allowed-tools: Read, Grep, Glob, Bash
---

# Record a ruling

Rulings are decisions the next session must not re-litigate. A decision
without its reason gets reopened.

## Date it from the clock, not from a stamp

```bash
date "+%Y-%m-%d %H:%M %Z"
```

**A timestamp is a value with a DATUM.** `written_utc` in a sidecar is
UTC; this project's prose is LOCAL. Reading one as the other dated seven
records a day ahead. Machine stamps stay UTC and keep the suffix; human
records use the local date.

## Both altitudes, same commit

- **`RECIPES.md`** — the SPECIFICATION. Exact values, bounds, and the
  REJECTED entry if this ruling closes a wrong approach:
  `WRONG VALUE/APPROACH → SYMPTOM YOU WILL SEE → CORRECT VALUE → ref`
- **`LESSONS.md`** — the NARRATIVE, if a failure produced this ruling.
  **Append only.** What was attempted, what happened, root cause at a
  source line or a measured number, the general rule it implies.

The completeness test: *could a fresh session repeat this mistake
without opening LESSONS.md?* If yes, it is not yet captured.

## Superseding

Loop (d): a locked recipe can be improved, but **log the old version as
superseded with the reasoning — never delete it.** Mark the original
`SUPERSEDED <date>` in place and append the correction above it, so the
chronology reads forward.

If the ruling reverses something ratified, say so plainly and carry the
date of both.

## Then

- If the ruling names a recipe, **verify it exists** — `commit-claims`
  will block the commit otherwise, and it exists because a message
  described an `R15` that had never been written.
- Commit with the message in a FILE.

$ARGUMENTS
