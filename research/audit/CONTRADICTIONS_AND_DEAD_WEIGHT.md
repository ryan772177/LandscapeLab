# Contradiction and dead-weight report — 2026-09-14

**Read-only audit. Nothing here was fixed, removed or applied.** This
report is evidence for the desk's ruling; the acting happens later.

---

## 0 — HOW MUCH OF THIS TO TRUST, STATED BEFORE THE FINDINGS

The ledgers are a **mechanical index**, deliberately over-inclusive so
nothing is missed, and their precision is measured rather than assumed.

**The contradiction finder was validated against five contradictions the
project already knows about. It rediscovers two of the five.**

    contrast   0.9025 vs 0.95        FOUND   LESSONS.md:34462 -> REGISTER B3.13
    warm-up    300 vs 40             FOUND   LESSONS.md:7270 -> RECIPES.md:2057
    shadow_tint 1.10-1.60 vs 2.184   MISSED
    range      768 vs 512            MISSED
    exposure   -4.1268 vs -13.5898   MISSED

So **recall on known cases is about 40%**, and the 4,726 claims carrying
a contradiction link are a floor, not a census. The three misses share a
shape the finder cannot see: a value written as a RANGE (`1.10–1.60`),
or a value that changed without ever appearing on a line beside its
predecessor. A human reading the register finds those; a token-pair
matcher does not.

Two of my own instruments failed during this audit and are recorded
because the same failure could reach a ledger:

* The **seed check itself was wrong** — it used OR, so a claim
  mentioning the subject with *either* value counted as rediscovered. It
  reported 2 of 5 found while the finder had in fact found **none**. A
  validation that can pass without the thing it validates is not a
  validation.
* The first contradiction pass keyed on **any shared word over four
  letters** and produced **152,372 links across 133,480 claims** — two
  unrelated sentences that both said "camera" and both held a number.
  A finder that fires on everything has found nothing.

---

## 1 — WRONG (contradicted by a measurement)

### 1.1 High-confidence, from the project's own record

These are not inferred; the corpus states them.

| what | wrong value | corrected to | where |
|---|---|---|---|
| Grade contrast exponent | 0.95 declared, **0.9025 effective** | 0.95 after `3525bc87` | `LESSONS.md:34455`, REGISTER B3.13 |
| `shadow_tint_B` band | 1.10–1.60 | struck; card-pair 2.184–2.940 | `research/brief3/REGISTER_ADDENDUM.md:116` |
| Exposure compensation | −4.1268 | −13.5898 on PPI0 | `RECIPES.md:18656`, `LESSONS.md:32608` |
| The "1 m grid" period | 1.07 m | a SEARCH-WINDOW EDGE, not a period | `LESSONS.md:34601`, `RECIPES.md:19637` |
| Scree tiling FAIL attribution | "texture-tile repeat" | not the scan's tile — UV randomisation did not move it | REGISTER B3.17 |
| 30–100 m tiling verdicts | FAIL (all layers) | **not player-visible**; aliasing at temporal 1 | REGISTER B3.20 |
| Meadow albedo variation | 0.4283 | 0.2278 — the first was a LIGHTING statistic | R-MEADOWALBEDO |
| Normal convention `corr(G, dH/drow)` | positive for DirectX | **GL positive, DX negative** — six of six packs read inverted | REGISTER (2026-09-12) |
| `make_foliage_material` save | "saved after the verdict" | saved nothing for **five weeks** | REGISTER B3.18 |
| HLOD MeshApproximate settings | "expose ZERO properties to Python" | reachable, nested | REGISTER B3.19 note |

### 1.2 Mechanical, with a reversal marker on the later side

17 parameter-level pairs survive deduplication (`report_groups.json`
→ `WRONG`). The ones that look real:

* `layer_gain` 0 vs 0.30 — `LESSONS.md:22450` → `RECIPES.md:11047`
* `collision_prims` — `PHASE2_PLAN.md:98` → `LESSONS.md:17293`, which
  says the field "appears only in `recipes/alpine.json`, the superseded
  2017² world"
* `root_uv` 100943 vs 7 — `RECIPES.md:11876` → `LESSONS.md:23554`,
  "arithmetic done by eye over a printed table and it was wrong"

⛔ **And several rows are artefacts of my own extractor**, stated rather
than left for the desk to trip over: `bounds_volumes 08 vs 1`,
`aaicontroller 080 vs 168`, `get_viewport_size 05 vs 14`. These pair
unrelated numbers that happen to share a line — `08` is part of a date.
A row whose "values" include a zero-padded fragment should be read as
noise.

---

## 2 — STALE (superseded by a ruling)

**164 claims** carry their own supersession marker
(`report_groups.json` → `STALE`). The structural ones:

* **`recipes/alpine.json` and the `alpinelab_*` recipes** describe the
  pre-8K 2017² world. They load and nothing current reads them
  (`CLAUDE.md` index). Every number in them contradicts the 8129² world
  by construction.
* **`docs/archive/`** — six pre-8K docs plus 31 superseded CURRENT STATE
  blocks. Banner-marked, and excluded from the claims ledger for that
  reason; in the zip for history only.
* **`PHASE2_PLAN.md`** carries three overturned rulings behind a banner.
  The banner is honoured by readers who read the banner.
* **`REPLAY_BURNDOWN.md`** — 13 UNPROVEN recipes, "designed, never
  scheduled".

---

## 3 — DEAD (nothing uses it)

### 3.1 Levers written to an engine that does not have them

Nine seeded dead levers; **four are actually written by scripts**:

| lever | writes | status |
|---|---|---|
| `r.LandscapeLODBias` | **6** | DOES NOT EXIST in 5.8 (enumerated on the running editor) |
| `r.TonemapperFilm` | **5** | recorded dead/ineffective |
| `r.ExpandGamut` | **3** | recorded dead/ineffective |
| `r.LocalExposure.HighlightContrastScale` | **2** | recorded dead/ineffective |
| `r.LocalExposure.ShadowContrastScale` | **2** | recorded dead/ineffective |
| `r.Shadow.Virtual.Nanite.Enable` | **1** | DOES NOT EXIST in 5.8 |
| `landscape.ForcedLOD`, `r.Wind.Enable`, `foliage.WindEnabled` | 0 | do not exist; named in prose only |

**None of the six written ones has a single read-back site.** A cvar
that does not exist accepts the write and changes nothing, so the only
way this was ever going to surface is the enumeration that found it.

### 3.2 Levers written and never read back

**170 levers** have at least one write and **zero** reads
(`report_groups.json` → `LEVERS_WRITTEN_NEVER_READ_BACK`). Standing rule
12 says a value that is not read back is prose; this is the size of that
debt.

⛔ And `has_read_back` in the ledger means **a read exists**, not that it
reads the object that honours the value. Two same-day examples show the
difference: `grass_varieties` handed out **copies** (per-element write
read back True on the copy, False on the asset), and the HLOD builder
settings are **nested structs** where the same trap applies.

### 3.3 Scripts nothing calls

**153 landscape-pipeline scripts** are referenced by no other script
(`report_groups.json` → `DEAD_SCRIPTS`). This over-reports: a
command-line entry point is legitimately uncalled. The signal is the
subset that is *also* untested — **899 of 973 scripts have no selftest
at all**.

### 3.4 Tools of record

* **listed-but-missing: 6** — and after fixing my own regex (`image.py`
  was yielding a tool called `mage`), the survivors are mostly prose
  mentions, not real tools.
* **listed-but-unused: 43**, of which exactly one is a desk tool:
  **`hydro_derive`** — filed this month, selftest run, and nothing calls
  it yet. That is expected for a just-delivered tool and is listed so it
  is not forgotten.
* **exists-but-unlisted: 266** — the long tail of payloads and one-offs
  that no document names.

---

## 4 — UNAPPLIED (a finding with no implementation)

**405 findings** carry a derived number or a named identifier and have
**no trace in any script or in the shipped recipe**
(`report_groups.json` → `UNAPPLIED`). Concentration:

    LESSONS.md                        104
    RECIPES.md                         68
    ASSETS.md                          10
    PHASE2_PLAN.md                      9
    plans/RECIPES_draft_closure.md      9
    BACKLOG.md                          8
    plans/RECIPES_draft_understory.md   6
    research/UNRESOLVED_2026-09-12.md   5

⛔ **Precision caveat, measured by reading a sample**: many rows are
*sentence fragments* (the scan is line-based, and a finding that wraps
across two lines yields a half-sentence), and many ASSETS.md rows are
*measurements of record* rather than findings awaiting implementation.
The desk should treat this as an index to review, not a work list to
execute.

The structurally interesting group is **`plans/RECIPES_draft_*.md` — 15
rows across closure and understory**. `CLAUDE.md`'s own index says these
are "three drafts staged, never merged" that "found 5 numeric errors in
our own artefacts". Findings that identified errors, and were never
merged, are the cleanest example of the category Ryan asked for.

Also live: **`research/UNRESOLVED_2026-09-12.md`** — a file whose name
says it, five rows.

---

## 5 — DUPLICATE (the same thing in two places)

**77 findings** appear verbatim in more than one file
(`report_groups.json` → `DUPLICATE`). This is the project's own
two-altitude practice working as designed — a lesson lands in
`LESSONS.md` *and* in the commit message *and* often in a docstring.

The risk is **drift**: three copies, one edited. The ledger records the
canonical row and every duplicate location so the desk can diff them.

Structural duplicates worth a ruling:

* **`dist/forge-0.1.1/` and `dist/forge-0.4.0/`** — two packaged copies
  of the forge, 428 `.py` files, inside the landscape repo. They are
  excluded from the claims ledger precisely because they manufacture
  duplicate contradictions.
* **`CLAUDE.md` × 249 versions, `LESSONS.md` × 332, `RECIPES.md` × 253**
  — exported in full at the ruling of 2026-09-14. I had proposed
  dropping LESSONS/RECIPES on the argument that they are append-only so
  nothing true could be lost. **That argument was overruled and the
  overrule was right**: an audit looking for where the record and the
  behaviour diverged cannot assume the record obeyed its own law.

---

## 6 — THE THREE API CALLS MOST LIKELY TO RETURN A VALUE WHERE THEY SHOULD RAISE

Ranked by whether the failure mode is unconditional and by how often the
result is consumed by a comparison or a verdict.

1. **`does_asset_exist`** — 127 sites, **47 consumed by a verdict**.
   Returns `False` for a missing asset *and* for a malformed path, so a
   typo reads as "the asset is absent". This session hit it twice:
   `/Game/Alpine8K/M_Alpine8K` (wrong folder) and
   `/Game/Meshes/Materials/` + empty name.

2. **`save_asset`** — 103 sites, **26 consumed**. Neither raises nor
   returns anything the caller reads when the path is bad. It printed
   "saved after the verdict" while `M_grass_medium_01` sat **five weeks
   stale** on disk, through three captures that rendered the new
   material correctly from memory. This is the worst of the three
   because the failure is *invisible in the render*.

3. **`connect_material_expressions`** — 141 sites, **21 consumed**.
   Returns false on a failed connect and carries on
   (`MaterialEditingLibrary.cpp:928-943`). The repo already wraps it in
   `_ll_wire`, which raises — but the wrapper is only injected where
   `WIRE_SRC` is, and `make_foliage_material` was missing that block
   until this session.

Runners-up, listed because each is already a known defect:
`delete_all_material_expressions` (28 sites, 12 consumed — "does not
delete all material expressions", 7 wired survivors on `M_fir_bark`);
`get_console_variable_string_value` (8 sites, 7 consumed — `""` for a
cvar that does not exist is indistinguishable from an empty value, and
is exactly how `r.LandscapeLODBias` was found absent);
`get_lod_material_slot` (6 sites, **all 6 consumed** — returns −1 rather
than raising, so a walk that stops on an exception runs to 64).

---

## 7 — WHAT THIS AUDIT DID NOT COVER

* **No engine was launched**, so nothing here is checked against live
  editor behaviour. Every "DOES NOT EXIST in 5.8" is quoted from an
  earlier enumeration, not re-run today.
* The **lever inventory reads source text, not execution**. A lever set
  through a data file the scanner does not parse, or built by string
  concatenation, is invisible to it.
* **`applied_where` is a text search.** A finding implemented under a
  different name, or implemented as behaviour rather than a constant,
  will read as UNAPPLIED. That is the main reason the 405 needs review
  rather than execution.
* One stray directory, `research/research/audit/`, was created by this
  session's first run when the repo root was computed by counting
  `dirname()` calls and was off by one. It was moved to `_trash/` and
  the root is now found by walking up to `CLAUDE.md`.
