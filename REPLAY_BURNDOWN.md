# THE NIGHTLY REPLAY BURNDOWN — design

**OPEN: cold replay is a Brief 5 acceptance — the 13 UNPROVEN recipes remain real.**

**Status: DESIGNED, NOT SCHEDULED. The first run is supervised.**

Purpose: burn down the UNPROVEN-recipe backlog. **13 conforming recipes,
75+ REJECTED entries, and not one replayed cold.** Written down carefully
is not the same as reproducible.

---

## THE RULE THAT GOVERNS THE WHOLE DESIGN

**A batch that mutates verification state unattended earns that trust by
one watched pass.** The first run is supervised by Ryan before it is
ever scheduled. This is not caution theatre: this batch is allowed to
flip `UNPROVEN` tags, and a tag flipped wrongly is worse than no tag —
it converts *"nobody has checked this"* into *"someone checked this and
it passed"*, which is a false clearance that nothing downstream
re-examines.

## WHAT A REPLAY IS

Executing a recipe **purely from its written steps**, making no
judgement calls, and diffing the result against the recipe's own
VERIFICATION section.

**Every gap found IS the finding.** A recipe that cannot be followed
without prior knowledge is exactly what UNPROVEN means, and fixing that
is the deliverable — not a clean pass. A batch that reports 13/13 green
on its first night has almost certainly tested nothing.

---

## EDITOR SERIALIZATION — the constraint that shapes the runner

Overnight changes nothing about the hardware. From R8/R10 and this
session's measurements:

- **ONE editor, ONE remote-exec port.** The port serves whichever editor
  holds it, so two batch entries touching the editor concurrently would
  race for it and rule 7's identity gate cannot save them — it proves
  *which* editor answered, not that only one asked.
- **Heavy operations run one at a time**, RAM logged first. Free RAM has
  been observed at **0.63 GB** on this host; the floor is 1.0 GB and the
  guard warns below 4.0.
- Cold-loading Alpine takes **minutes** (256 proxies, 158k instances),
  and a capture after a material change waits on shader compilation —
  measured at **>900 s per camera**, which is a timeout, not a hang.

**Therefore the runner:**

1. **QUEUES. It never parallelizes editor work.** One recipe in the
   editor at a time, strictly sequential.
2. **Checks `resource_guard` before each entry** and **ABORTS CLEAN on
   saturation** rather than pushing on — partial results written, the
   remaining queue left unrun and reported as unrun.
3. **Never runs two editor-touching batches in the same window**, and
   holds the heavy-op lock for the duration.
4. **Uses a SCRATCH MAP per recipe**, never `/Game/Alpine`, so a failed
   replay cannot damage the region. Level switching goes through
   `scripts/open_level.py` (R14) — never a hand-rolled payload.

## THE LEDGER

Append-only `_verify/replay_ledger.jsonl`, one row per attempt:

```
{ "utc": "...", "recipe": "R12", "commit": "<sha>",
  "verdict": "PASS|FAIL|UNRUN|ABORTED",
  "gaps": ["step 3 assumes the editor is already on Alpine"],
  "diff_vs_reference": {...}, "duration_s": 000 }
```

**`UNRUN` and `ABORTED` are first-class verdicts.** A recipe the batch
never reached must not be silently absent from the ledger — absence
reads as "not attempted" only if someone counts rows, and nobody counts
rows at 3am.

## TAG FLIPPING — the narrow part

`UNPROVEN` → `PROVEN` **only on PASS**, and only when:

- every VERIFICATION number in the recipe was reproduced within its
  stated tolerance, **by the recipe's own named instrument**;
- no step required a judgement call the recipe did not specify;
- the run used a scratch map and left `/Game/Alpine` untouched.

**A FAIL files a defect** with the diff against reference, at both
altitudes, and **leaves the tag UNPROVEN**. It does not retry — standing
rule 6 applies to a batch as much as to a person, and an unattended
retry loop against a live editor is the exact brute-force the rule
forbids.

## INVOCATION

```
claude -p --permission-mode acceptEdits \
  "/replay-batch R0,R3,R2,R11" \
  --output-format stream-json
```

Order is by **TRAFFIC, not by cost**: R0 first because it gates every
other recipe's verification, then the most-trafficked (R3, R2, R11) —
a replay failure there teaches the most.

**On this machine R0's honest replay is partial**: follow the written
procedure, run `recover_state.py`, diff against `PROJECT_STATE.json`.
The FULL acceptance test is R0 on the future GPU desktop, and the ledger
records that limitation per row rather than pretending otherwise.

## STAGING

1. **Attended dry run** — `--dry-run`, no editor contact, no tag
   changes. Proves the queue, the ledger and the abort path.
2. **Attended live run, ONE recipe.** Ryan watching. R12 is the
   candidate: newest, most instrumented, and its scatter is already
   scratch-map safe.
3. **Attended full batch.**
4. **Only then** consider scheduling — and scheduling is a separate
   ratification, not a consequence of step 3 passing.
