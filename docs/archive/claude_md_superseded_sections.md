# ARCHIVE — CLAUDE.md SECTIONS SUPERSEDED BY THE INDEX

> # ⛔ SUPERSEDED — these sections were REPLACED, not deleted.
>
> Preserved verbatim 2026-08-29 by the doc-consolidation unit. The byte
> reconciliation found these were the ONLY pieces of the old `CLAUDE.md`
> that existed nowhere in the working tree afterwards, so they are kept here
> to make "nothing is destroyed" literally true rather than approximately
> true.
>
> **Nothing here may drive a decision.** `## The six files` is superseded by
> THE INDEX in `CLAUDE.md`, which lists the same six plus every other doc and
> adds a load-when trigger. `# REPO LAYOUT` is superseded by the index's own
> layout block. The title/mission section was rewritten to carry the current
> 8K spec.

---

## VERBATIM: `# CLAUDE.md — the constitution`

# CLAUDE.md — the constitution

**This project is phase one of an open-world RPG in Unreal Engine 5.8.**
Terrain came first because everything else is placed relative to it. Read
`WORLD_VISION.md` for the trajectory; terrain is a subsystem, not the
product.

**Separate exploration from the Unity/AnyRPGCore project — do not
cross-reference that repo.**

---

## VERBATIM: `## The six files`

## The six files

A fresh session needs these and nothing else.

| File | What it is | Rule |
|---|---|---|
| `CLAUDE.md` | This. How to operate. | Governs |
| `LESSONS.md` | Append-only NARRATIVE of everything learned the hard way — what happened, why, root cause. | **Never delete from it** |
| `RECIPES.md` | The executable SPEC and its ANTI-SPEC: exact values that work, exact values that failed. | **Never delete a locked recipe** |
| `WORLD_VISION.md` | Where this is going. | North star |
| `BACKLOG.md` | The scope-creep valve. Everything that is not this session's goal. | Add freely; **pull at session start only** |
| `ASSETS.md` | Intake register — source, licence, role, render proof. | No asset without a row |

**LESSONS and RECIPES are two altitudes on the same events, not
duplicates.** LESSONS is the story; RECIPES is the specification. A
failure belongs in both.

Plus four load-bearing non-documents, which are **code and data, not
prose**: `recipes/*.json` (biome data every script reads),
`recipes/schema.md` (its normative contract, referenced by twelve
files), `.claude/agents/auditor.md` (the auditor subagent definition),
and `PROJECT_STATE.json` (machine-recovered editor state backing the
recipes — regenerate with `scripts/recover_state.py`).

---

---

## VERBATIM: `# REPO LAYOUT`

# REPO LAYOUT

    CLAUDE.md  LESSONS.md  RECIPES.md  WORLD_VISION.md   the six
    BACKLOG.md  ASSETS.md                                 (see table above)
    PROJECT_STATE.json  machine-recovered editor state (recover_state.py)
    recipes/       biome JSON + schema.md  (CODE — scripts read this)
    scripts/       UE Python: import, assembly, lighting, capture
    scripts/blender/  headless asset normalisation
    terrain/       heightmaps (16-bit PNG) and erosion maps
    textures/      baked layer weightmaps and detail textures
    foliage/       computed instance transforms (JSON)
    captures/      automated screenshots for review loops
    Free/          vendor source assets + manifest
    _trash/        removals — never `rm -rf`

---

## VERBATIM: the one heading line rewritten in Phase 0

The 2026-08-27d block's heading was edited to mark it superseded when the
post-hoc 2026-08-28 block was inserted above it. Its BODY is byte-identical
in `docs/archive/current_state_history.md`; only this line changed.

**Before:**

    # CURRENT STATE — 2026-08-27d (the kit path holds 7,949 folders and zero files — and it is a MODULAR WALL KIT) — **⭐ THIS IS THE LIVE BLOCK. EVERY `# CURRENT STATE` BELOW IS SUPERSEDED, INCLUDING 27c.**

**After:**

    # CURRENT STATE — 2026-08-27d (the kit path holds 7,949 folders and zero files — and it is a MODULAR WALL KIT) — **SUPERSEDED by the 2026-08-28 block above.**
