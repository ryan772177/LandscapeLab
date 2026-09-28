# Phase D bakeoff — 2026-08-30

## THE COMPARISON TABLE

| candidate | installed | licence | ran | load s | infer s | VRAM peak | output | intake verdict |
|---|---|---|---|---|---|---|---|---|
| **TRELLIS** | **yes**, `/opt/trellis` | **MIT** | **yes** | 24.7 | 9.3 | **9,770 MiB** | 74,904 v / 149,610 f | **REFUSED — flat** |
| TRELLIS *(control: its own castle)* | — | — | yes | — | 14.7 | 11,201 MiB | 570,703 v / 1,141,334 f | **PASSES — volumetric** |
| Hunyuan3D 2.1 | **no** | community (commercial constraints) | no | — | — | **NOT MEASURED** | — | not evaluated |
| anything else | **no** | — | no | — | — | — | — | **no roster exists in this repo** |

Environment is R-TRELLIS's, verified in the log rather than assumed:
`[SPARSE] Backend: spconv, Attention: xformers` / `spconv algo: native`.

## ⭐ THE POSITIVE CONTROL SETTLES IT, AND IT WAS NECESSARY

    church   extent 1.0009 x 0.5603 x 0.0114   thin/long 0.0114   FLAT
    castle   extent 0.8773 x 0.8509 x 1.0022   thin/long 0.8491   VOLUMETRIC
                                               ratio between them:  74x

Both measured **independently from the `.obj`**, not read off TRELLIS's own
report, and both through the identical code path.

**The pipeline is sound. The church's flatness is the INPUT.** Had the castle
also come back flat, nothing about the church run would have meant anything —
which is exactly why the control was run before any verdict was issued.

The vertex counts corroborate from a second direction: 570,703 for a real
volume against 74,904 for a sheet, a 7.6× difference in geometry for a
comparable object class.

## ⛔ THE BLOCKER, QUANTIFIED

    church crop        80 x 115 px = 9,200 source pixels
    of the concept     0.87% of its area
    fed as             518 x 518 after a 4.5x LANCZOS upscale

**Upscaling adds no information.** 9,200 source pixels stay 9,200 source
pixels, and at that density the model has nothing to infer depth from, so it
returns a relief on a plane. This was predicted *before* the run and recorded
then, so it is a confirmed prediction rather than a retrofitted excuse.

**Phase D is not blocked on a model. It is blocked on an INPUT.**

## VRAM — AND THE TWO INSTRUMENTS DISAGREE

    nvidia-smi, Windows, editor up     9,710 MiB free of 16,303
    torch mem_get_info inside WSL     15,045 MiB free of 16,303
    TRELLIS measured peak              9,770 MiB (church) / 11,201 (castle)

A 5.3 GB gap between the two views: WSL's CUDA view under GPU-PV is not the
Windows allocator's. Plan against the conservative one.

**TRELLIS's peak plus a loaded editor is 16,064 of 16,303 MiB.** They do not
comfortably coexist on this machine — closing the editor was necessary, not
tidy. That is a measured scheduling constraint for every future run.

## NO FORGE WRAPPER, FOR TWO INDEPENDENT REASONS

1. **One surviving candidate cannot be an unambiguous winner.** The brief said
   the wrapper is built only if a winner is unambiguous by intake numbers.
2. **The subject is not servable yet.** A forge fed 9,200-pixel crops would
   industrialise the production of flat sheets.

Winner ratification is the operator's in any case, and there is no ratifiable
comparison to bring — only a working pipeline and a bad input.

---

# ⭐ AMENDED 2026-08-30b — THE INPUT WAS FIXED AND THE TABLE'S VERDICT CHANGES

The operator delivered a four-view reference set against `CHURCH_VIEW_SPEC.md`.
Re-run through the identical code path:

| candidate | views | thin/long | vertices | faces | VRAM peak | intake verdict |
|---|---|---|---|---|---|---|
| TRELLIS, church | 1 | 0.0114 | 74,904 | 149,610 | 9,770 | REFUSED -- flat |
| TRELLIS, castle control | 1 | 0.8491 | 570,703 | 1,141,334 | 11,201 | PASSES -- volumetric |
| **TRELLIS, church MULTI-VIEW** | **4** | **0.4317** | **190,498** | **381,228** | **10,082** | **PASSES -- volumetric, watertight** |

"Phase D is not blocked on a model. It is blocked on an INPUT." -- confirmed
from the other side. Full numbers, the watertightness method, the genus-59
caveat, the looked-at orthographic views, and **the ratification question**
are in `MULTIVIEW_RESULT.md`.

**The "no forge wrapper" ruling had two independent reasons. One is resolved;
the other is now permanent and needs an operator decision** -- see
MULTIVIEW_RESULT.md, THE RATIFICATION QUESTION.

---

# ⭐ RATIFIED 2026-08-30 BY RYAN — TRELLIS IS THE FORGE'S GENERATION ENGINE

**And the acceptance rule is FORMALLY AMENDED from COMPARATIVE to ABSOLUTE.**

## THE RATIONALE, IN THE OPERATOR'S OWN TERMS

The original brief built the forge wrapper only if a winner was unambiguous
**by comparison between candidates**. That rule can never be satisfied:
**ruling 7 DECLINED Hunyuan3D 2.1** — recorded as declined, not deferred — and
no other roster exists in this repo. The field is permanently one.

Ryan: *"ruling 7 made a comparative winner impossible by my own hand, so the
acceptance rule is formally amended."*

**A criterion that cannot be met by construction is not a high bar, it is a
dead letter.** Keeping it would have blocked the forge forever on a comparison
that will never exist, while the evidence needed to judge the tool was already
in hand.

## THE AMENDED RULE — ABSOLUTE FLOORS

A generation candidate is ratified against **absolute floors**, not rivals:

1. **VOLUMETRIC** — measured against this project's own flat-sheet baseline
   (`thin/long` 0.0114) rather than against a preferred number. The church
   multi-view run returns **0.4317, 38x the sheet**.
2. **WATERTIGHT / MANIFOLD** — every edge used by exactly 2 faces; 0 boundary,
   0 non-manifold. Measured, with the method named in the report.
3. **SUBJECT-READABLE IN INDEPENDENT RENDERS** — orthographic views rasterised
   from the `.obj` by a different tool than the one that made the claim, and
   LOOKED AT. Nave, tower, onion dome, finial all present.
4. **VRAM FIT** — measured peak against this machine, with the editor's
   occupancy accounted for.

**Plus the input half, which is not optional and is where the first attempt
actually failed:** `CHURCH_VIEW_SPEC.md`'s measured floors enforced by
`check_generation_input.py`, and `ai_input_guard.py --strict` before any
weights load.

**Why this is a real bar and not a rubber stamp:** the single-view church run
FAILED three of the four floors on the identical code path, three hours before
the multi-view run passed them. The rule discriminates because it already has.

## FORGE WRAPPER — AUTHORIZED, WITH MANDATORY STAGES

Ordered. **None is optional**, and the ones marked PROVEN already exist and
must be called rather than reimplemented.

    1  check_generation_input.py         PROVEN -- measured floors
    2  ai_input_guard.py --strict        PROVEN -- BEFORE weights load, under
                                         `set -e`; R-AIGATE, undetectable
                                         after the fact
    3  generate                          TRELLIS, formats=["mesh"]
    4  RETOPO / DECIMATE  -- MANDATORY   headless Blender. NEVER SHIPS RAW.
    5  pivot to BASE-CENTRE
    6  UV state recorded
    7  measured intake
    8  ASSETS.md row
    9  FORGE_LOG cost line

### ⛔ STAGE 4 IS THE ONE THIS RUN PROVED NECESSARY

**Genus-59 marching-cubes output never ships raw.** The multi-view church is
watertight AND carries 59 handles (chi = -116). Watertight was true and was not
the whole story — precisely the "two instruments agreeing" failure this project
keeps paying for.

The headless-Blender finish **must report before/after `verts`, `faces` and
`genus`**, so the stage is auditable rather than assumed.

**The target is MEASURED and already on disk** —
`recipes/perf_budgets.json` -> `asset_rules`:

    max_tris / hero_prop        60,000   "the church is a one-off focal anchor
                                          and may carry more than a wall module"
    max_tris / kit_module       20,000   (15 measured modules run 10.1k-19.7k)
    max_texture_mb / hero_prop     128

**The church is `hero_prop`. Raw output is 381,228 faces, so stage 4 must
achieve a 6.35 : 1 reduction to 60,000.** That number is not invented here; it
is read from the recipe.

*Note for whoever builds this: `budgets.nanite_triangles`,
`texture_memory_mb` and `draw_calls` are still **null and UNMEASURED** by
operator ruling. Those are SCENE-level and are NOT the per-asset rule — the
per-asset `asset_rules` above do exist and are derived from measurements. Do
not conflate them, and do not treat the nulls as blocking stage 4.*

### PROVENANCE THE ASSETS.md ROW MUST CARRY

    source   generated from operator concept references
    engine   TRELLIS, MIT
    inputs   refs/church_refs/church_az{000,035,090,270}.png.jpg
             all four cleared by ai_input_guard --strict before the run

## THE FIRST TWO FORGE RUNS, RULED

1. **This church**, through the FULL wrapper, standing in scratch **beside a
   kit mesh for scale** — the comparison that says whether a generated hero
   prop sits in the same world as the kit.
2. **The wood stacks**, per the earlier ruling.
