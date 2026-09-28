---
name: checkpoint
description: Create a risky-op restore point — a tag NAMED FOR THE OPERATION, before anything that touches many assets or is not cleanly undoable.
disable-model-invocation: true
argument-hint: [operation-name]
allowed-tools: Read, Grep, Glob, Bash
---

# Risky-op checkpoint

**Before any operation touching many assets, or not cleanly undoable:
create a tagged commit NAMED FOR THE OPERATION.**

This is not ordinary commit discipline. Standing rule 3 says commit
before anything where a restore point matters; this says the restore
point must be **findable by name six weeks later**, when nobody
remembers which of forty commits preceded the bad reimport.

Applies at minimum to: bulk reimport, landscape resize, mass foliage
regeneration, engine or plugin version change, batch retarget, terrain
adoption, and any `--place` run.

## Do

```bash
git status --short          # must be clean, or commit first
python .claude/hooks/prove_hooks.py 2>&1 | tail -3
python scripts/prove_gates.py 2>&1 | tail -3
```

Then tag with a name that says what is about to happen, and a message
that says **what is at risk and what state the tag captures**:

```bash
git tag -a "pre-<operation>-<YYYYMMDD>" -F <message-file>
```

A good tag message names: the operation, what it could destroy, and why
a reload will not restore it. `pre-rock-placement-20260804` recorded
that the orphan sweep could take the whole conifer set and that
placement is saved to the level.

## Remember what git does not cover

Git is the undo button for the REPO. It is **not** an undo button for:

- editor state saved to `.umap` / `__ExternalActors__`
- instances spawned and saved
- assets imported into `Content/`

For those the tag records the *pre* state of the recipe and scripts, so
the operation can be re-derived — not reversed. Say which you have.

## After

Verify the operation with an instrument that did not perform it (NN8),
and only then move on.

$ARGUMENTS

## Collision truth — cross-representation gate (added 2026-08-06)

**Before ratifying any checkpoint that saves scene state, or that
precedes a placement / physics / trace-based operation:**

```bash
python scripts/check_collision_truth.py --n 100
```

`0` PASS · `4` COULD NOT MEASURE (never a pass) · `5` FAIL

**Why it belongs at a checkpoint specifically.** A checkpoint is where
state becomes durable. On 2026-08-06 the landscape was found to RENDER
`alpine_heightmap_v2` and COLLIDE the pre-stamp map — p90 **94.4 m**,
max **267.8 m** on a footprint sample — after a terrain adoption, a
weight re-bake, a 157,554-instance re-placement and **1328 saved
packages**, with every gate green. Every gate was green because every
gate read the heightmap. This is the only check whose source artefact is
the COLLISION (non-negotiable 0).

**Exit 4 is not a pass.** A landscape returning no hits is as broken as
one returning wrong ones, and silence is how the original defect
survived three days.

**KNOWN FAILING until the collision rebuild lands.** It should FAIL every
run right now — that is correct behaviour, not a broken gate. Do not
disable it to get a clean checkpoint; the thing it is reporting is real.
