# DOC CONSOLIDATION — INVENTORY AND VERDICTS

**2026-08-29.** This is the reviewable plan for the doc-consolidation unit, and
it is committed **before anything moves**. Every verdict below carries the
evidence line that produced it, so a reader can disagree with the verdict
without re-deriving the evidence.

## THE RULE THIS INVENTORY OBEYS

**When genuinely unsure whether a doc is live, it stays LIVE and is flagged
here.** Miscategorising live doctrine as dead is the expensive error: an
archived rule stops being applied silently, whereas a flagged live doc merely
costs a reader thirty seconds. Six files are moved. Five more are named as
*live-but-carrying-superseded-content*, and they are **corrected in place, not
archived**, because their live half is load-bearing.

## SCOPE, MEASURED

    tracked .md files      146
    tracked .md bytes      4,743,602
    CLAUDE.md              497,506 chars, 31 CURRENT STATE headings
    recipes/               14 files (11 JSON + schema.md + 2 draft/scratch)

**Nothing in this unit is deleted.** Every action is a `git mv` or an added
banner. Byte conservation is proven mechanically in Phase 6.

---

## 1. VERDICT SUMMARY

| Verdict | Count | Action |
|---|---|---|
| **ARCHIVE → `docs/archive/pre8k/`** | 6 | `git mv` + ⛔ banner |
| **ARCHIVE → `docs/archive/current_state_history.md`** | 30 blocks | verbatim split out of CLAUDE.md |
| **LIVE, but carries superseded content** | 5 | correction note in place, **not moved** |
| **LIVE** | rest | indexed in CLAUDE.md |
| **Already archived** (`_trash/`) | 7 | left alone |

---

## 2. ARCHIVE — pre-8K / pre-kit, with evidence

The current direction is `/Game/Alpine8K` (8129², 1 m/vertex, adopted
2026-08-14) with a **kit-driven** town. Everything below describes the world
that preceded it: `/Game/Alpine` at 2017², 4 m/vertex, or a ruling the board
has since overturned.

### 2.1 `SWEEP_REPORT.md` — 13,802 B, last substantive 2026-08-06

> **Evidence.** Line 1: *"STEP 7 — THE SWEEP: report, re-established 2026-08-06
> on the CORRECTED terrain"*. Its provenance block is entirely about
> `alpine_heightmap.png` vs `alpine_heightmap_v2.png` — **both 2017² maps of
> `/Game/Alpine`**. Mechanical: `Alpine8K` appears **0 times**.

The whole report grades the pre-8K world against Pass 7's criteria. Its
per-criterion verdicts (tiling, seams, cliff stretching) were measured on a
terrain that no longer exists in the project.

### 2.2 `VERIFICATION.md` — 6,147 B, last substantive 2026-08-04

> **Evidence.** Line 1: *"ALPINE REGION — VERIFICATION REPORT"*, *"This is Pass
> 7's verification half"*, generated 2026-08-05. `Alpine8K` appears **0 times**;
> `2017` appears once.

Additional cause: this file was **already reverted once for containing false
claims** — CLAUDE.md's 2026-08-08 audit, item 5, found it rewritten from
`plans/alpine_execution_plan.md` so that every planned step read as a completed
one. It is a hazard as well as stale.

### 2.3 `IMPORT_CHECKLIST.md` — 6,542 B, last substantive 2026-08-09

> **Evidence.** Its **opening claim is now false**: *"UE 5.8 Python cannot
> create a landscape."* Superseded 2026-08-12 by **R-CREATE** — the
> `LandscapeLabEditor` plugin exposes `create_landscape_from_heightmap`, and
> CLAUDE.md records *"R-GAEA's 'UE 5.8 Python cannot create a landscape' is now
> FALSE."*

It also scopes itself to `AlpineLab_v1`, the evaluation terrain, not the shipped
world. **This is the single most dangerous file in the set**: a session reading
it would perform a manual click-through for something now scripted.

### 2.4 `plans/alpine_execution_plan.md` — 3,700 B, last substantive 2026-08-08

> **Evidence.** Pass 0 reads *"Run cold replay on
> `recipes/alpine_palette_curation.json` / `recipes/alpine.json`"* — the
> **pre-8K** recipe pair. `Alpine8K` appears 0 times.

The Pass 0–7 campaign it plans completed on the old world.

### 2.5 `plans/clip_30s_proposal.md` — 19,551 B, last substantive 2026-08-08

> **Evidence.** *"STATUS: RATIFIED 2026-08-08 AS THE SEQUENCE OF RECORD"* —
> written *"against the board as it actually stands"* on 2026-08-08, six days
> before the 8K re-terrain. `Alpine8K` appears 0 times.

**This is a genuinely superseded RULING, which is why it is called out rather
than quietly moved.** Ratified sequences do not stop being ratified; they stop
being *applicable* when their subject is replaced. The banner says so.

### 2.6 `plans/conifer_asset_spec.md` — 7,084 B, last substantive 2026-08-13

> **Evidence.** *"`fir_tree_01` is the measured weak point"*, *"Ruled
> 2026-08-13: source a better conifer from Fab"*. **Resolved 2026-08-15** by
> adopting `SM_PVE_Norway_Spruce_01_A` (CLAUDE.md 2026-08-15: conifer
> `fir_tree_01_c_LOD0` → `SM_PVE_Norway_Spruce_01_A`).

A purchase spec whose purchase was made. Archived as *completed*, not as wrong.

### Link consequences of these six moves — checked, not assumed

    SWEEP_REPORT.md        <- scripts/measure_falloff_contours.py:3   (prose)
    IMPORT_CHECKLIST.md    <- scripts/ue5_import_alpinelab.py:227     (prose)
                           <- scripts/verify_build.py:326             (prose)
                           <- terrain/regions/README.md:509           (prose)
    conifer_asset_spec.md  <- scripts/measure_tree_packs.py:3,66      (prose)
                           <- _verify/20260814_canopy_atlas_comparison.md:68

**No script OPENS any of them** — verified with a grep for `open(...)` against
all three names; every hit is a docstring or comment. So the moves cannot break
execution. The four live references in `scripts/` and `terrain/regions/README.md`
are **updated to the archive path** in Phase 3.

**References inside `LESSONS.md` and `RECIPES.md` are deliberately NOT updated.**
Those files are append-only law, and rewriting a path inside a narrative record
would falsify what was true when it was written — the exact precedent CLAUDE.md
sets for the `ryanb` → `Admin` path migration, which was also left unswept. The
stale-link checker therefore **exempts both files by name**, and the exemption
is declared in the checker rather than remembered.

---

## 3. LIVE, BUT CARRYING SUPERSEDED CONTENT — corrected in place, NOT moved

These are the "leave it live and flag it" cases. Each has a load-bearing live
half, so archiving the whole file would take working doctrine offline.

### 3.1 `PHASE2_PLAN.md` — 37,386 B — **LIVE**

Units 10, 11 and 12 are still the active work programme; unit 12's enemy pawn is
named in the live CURRENT STATE as a blocker. **But it carries at least two
rulings the board has overturned:**

- **Ruling 14 (no MetaHuman for the player character)** — overturned by Ryan
  2026-08-15, who ruled MetaHuman in.
- **Ruling 19 (navmesh agent no steeper than `primary_movement_mode`)** —
  overturned 2026-08-26; the agent is now `walk` (44.765°), derived from the
  pawn, because ruling 19 was comparing the wrong two things.
- **Unit 6's `CustomNavigableGeometry = No`** (`PHASE2_PLAN.md:124`, and in
  ruling 16 at `:40`) — recorded in CLAUDE.md as **backwards**: `No` still runs
  the default collision export, `dont_export` is what excludes. Ruling 16 is
  already self-marked `[OVERRULED]` in the file, but the prescription survives
  unmarked in unit 6's body at `:124`, which is the line a builder would read.

**Action: a correction banner at the top listing the overturned rulings**, body
untouched. Archiving it would remove the live unit programme.

### 3.2 `WORLD_ARCHITECTURE.md` — 27,659 B — **LIVE**

Its own header presents multi-region as *"A RECOMMENDATION, NOT A RULING"*.
**Ryan ruled it in on 2026-08-15** (multi-region, 2×2 atlas, ≤2 co-resident).
The document is now the ruled architecture and its status line understates it.

**Action: status correction at the top.** The content is current.

### 3.3 `plans/characters_brief.md` — 11,977 B — **LIVE, UNSURE**

> Its skeleton ruling — *use the UE5 mannequin from the engine template* — was
> **partly** superseded by the MetaHuman ruling. But its animation inventory
> (102 anims measured, 68 Rifle/Pistol, **42 usable**, 8 hit-reacts filed under
> `Anims/Rifle/`) is still exactly what `ABP_Unarmed` drives on the live pawn.

**Genuinely unsure, so it stays live and is flagged for your ruling.** Splitting
it would mean editing a measured brief, which this unit does not do.

### 3.4 `REPLAY_BURNDOWN.md` — 4,886 B — **LIVE**

*"Status: DESIGNED, NOT SCHEDULED."* The 13-UNPROVEN-recipe backlog it burns
down is still open and still in BACKLOG.md. Never executed ≠ superseded.

### 3.5 `plans/RECIPES_draft_{closure,pn_trees,understory}.md` — 63,487 B total — **LIVE**

Staged for review, never merged into `RECIPES.md`. CLAUDE.md records they
*"found 5 numeric errors in this project's own artefacts"*. Pending, not dead.

---

## 4. `recipes/` — AUDIT SCOPE, NO MOVES

**`recipes/*.json` is CODE, not prose** — CLAUDE.md's own words: *"the four
load-bearing non-documents … `recipes/*.json` (biome data every script reads)"*.
Moving a recipe JSON would break the scripts that read it by path, so **no JSON
is moved in this unit**. Phase 5 audits the prose *about* them against the code
that consumes them.

    recipes/alpine_8k.json          116,696   LIVE   the shipped world
    recipes/city.json                17,743   LIVE   the town, kit work targets it
    recipes/encounters.json           8,033   LIVE   317 placed markers
    recipes/character.json            5,079   LIVE   the pawn
    recipes/schema.md                74,304   LIVE   normative contract, 12 readers
    recipes/alpine.json              71,177   LIVE-legacy  /Game/Alpine, pre-8K world
    recipes/alpinelab_8129.json      32,825   LIVE-legacy  Gaea evaluation terrain
    recipes/alpinelab_v1.json        15,696   LIVE-legacy  Gaea evaluation terrain
    recipes/alpine_palette_curation.json 20,460  LIVE-legacy
    recipes/pve_export_settings.json  3,633   LIVE   the PVE export procedure
    recipes/tree_lods.json            4,250   LIVE   marked DO NOT RUN in-file
    recipes/tree_scratch*.json        5,436   LIVE   scratch measurement recipes
    recipes/drafts/*.draft.json      12,707   LIVE   draft

### PHASE 5 AUDIT RESULT — recipe fields vs the code that reads them

Every `.py` and `.txt` under `scripts/` was scanned for each non-prose key
declared in `city.json`, `encounters.json` and `character.json`.
**Narrowing the denominator to the obvious consumers first gave 21 false
positives for `city.json` alone** — fields read by a payload I had not listed —
so the figures below are against the WHOLE `scripts/` tree (non-negotiable 22:
state the denominator).

**Two genuine findings, both confirmed by reading the code, neither fixed:**

1. **`landmark.spire_mesh` IS INERT.** `scripts/city_place_payload.txt:77`
   hardcodes `("spire", "/Engine/BasicShapes/Cone.Cone")` instead of reading the
   key. The two agree today, so nothing is broken and nothing *looks* broken —
   which is the dangerous shape: **change the recipe value and the spire does not
   change.** Violates pipeline rule 2 ("every scene parameter comes from recipe
   JSON, never hardcoded") and non-negotiable 24. **It is a RECURRENCE** — the
   `_INERT_FIELD_CORRECTED` note in the same file records this exact class being
   found and fixed for `meshes.roof` on 2026-08-25.

2. **Three `gates` booleans in `city.json` are read by nobody** —
   `all_inside_radius`, `no_footprint_overlap`, `streets_are_one_network`
   (and in `encounters.json`, `all_reachable_from_player_start` and
   `min_separation_from_archetypes`). **They are not unenforced invariants:**
   `plan_city` applies both unconditionally (`rej["outside_radius"]`,
   `rej["overlap"]`) and prunes streets to the plaza's component. The flags are
   **decorative mirrors**. The trap is that they sit in the same `gates` block as
   `max_pad_cut_fill_m`, `min_buildings` and `min_street_segments`, which *are*
   read — so the block reads as uniform and **setting any of the three to false
   would change nothing.**

**Why these were NOT annotated inside the recipe.** I wrote both notes into
`recipes/city.json` first, and that **moved the recipe's SHA-256**, which
immediately made `city/alpine_basin_town_reachable.json` report `STAMP DIFFERS`.
Regenerating the town plan proved the annotation changed no content — only
`_input_sha256` moved, with buildings, streets, counts, landmark and spire all
byte-identical across 303 rows — **but the reachability sidecar is produced by an
in-editor payload and cannot be refreshed offline**, and this unit is
explicitly offline-only. The annotations were reverted and the findings live
here and in `BACKLOG.md` instead. All 19 checkable plans are fresh.

**The lesson is worth keeping:** documentation written INTO a hashed input is not
free — it invalidates every downstream stamp, and some of those cost an editor.

**The known doc/code contradiction fixed in Phase 5** is
`_verify/20260828_kit/COVERAGE.md`: it frames `storey_m` 3.20 → 2.00 as a 33%
height cut, but `plan_city.py:392-395` snaps a *continuous* falloff to a storey
multiple, so changing `storey_m` re-quantises rather than preserving storey
count. Measured this session: mean height moves 9.99 → 9.91 m (−0.8%), not −33%.
**CODE IS TRUTH; the doc gets corrected.**

---

## 5. BULK CLASSES — indexed by class, not per file

| Class | Files | Bytes | Verdict |
|---|---|---|---|
| `_verify/**` | 45 | 546,451 | **LIVE-as-evidence.** Dated measurement artefacts. Never doctrine; a session cites them, never obeys them. Indexed as a class. |
| `plans/phase2_lanes/**` | 12 | 185,032 | **Historic working artefacts** — agent lane outputs, 2026-08-15, inputs to PHASE2_PLAN. Superseded by the plan they produced. |
| `plans/region_lanes/**` | 12 | 120,380 | Same, inputs to WORLD_ARCHITECTURE. |
| `plans/region_authoring/**` | 7 | 33,228 | Same, inputs to `terrain/regions/`. |
| `hero/**` + 4 root hero reports | 13 + 4 | ~211,000 | **PARKED, not superseded.** Ryan: *"I'll revisit this later since we have a working prototype."* Post-8K work, so it is not pre-8K quarantine material. |
| `terrain/regions/**` | 6 | 151,672 | **LIVE.** The multi-region ruling is in force. |
| `.claude/**` | 15 | 49,875 | **LIVE.** Skills and agent definitions, loaded by the harness. |
| `_trash/**` | 7 | 378,341 | **Already archived** 2026-08-02. Untouched. |

**The three lane directories are the one bulk class I considered quarantining
and did not.** They are inputs whose outputs are live, they live under `plans/`
where nobody mistakes them for doctrine, and moving 31 files to gain ~338 KB of
tidiness is a poor trade against the risk of burying a measurement. They are
indexed as *historic working artefacts* instead, which achieves the same
protection at zero risk.

---

## 6. WHAT IS NOT TOUCHED, AND WHY

- **`LESSONS.md` (1,366,873 B) and `RECIPES.md` (687,521 B)** — append-only law.
  Not moved, not trimmed, not link-swept. They receive a **generated TOC at the
  top only**; bodies are byte-identical afterwards, which Phase 6 proves.
- **`recipes/*.json`** — code. See §4.
- **`_trash/`** — already archived.
- **`BACKLOG.md`** — live, and the pull-at-session-start rule depends on it.

---

## 7. LEFT LIVE-BUT-FLAGGED — for your ruling

1. **`plans/characters_brief.md`** (§3.3) — skeleton ruling partly superseded by
   MetaHuman, animation inventory still current. Split, archive, or leave?
2. **The three lane directories** (§5) — indexed as historic rather than
   quarantined. Say the word and they move.
3. **`recipes/alpine.json` and the two `alpinelab_*` recipes** — the pre-8K and
   Gaea-evaluation worlds. They are code and still load, so they stay, but
   nothing in the current direction consumes them.
