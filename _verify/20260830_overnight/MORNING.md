# MORNING REPORT — overnight #2, 2026-08-30

**Tree clean. Zero editors. Suite: 24 checks, 1 FAIL — named below.**
Six units committed. Nothing in HARD LIMITS was touched; **no item is waiting
on you as a hard-limit choice.**

---

## THE ONE SUITE FAILURE, NAMED

    every plan against its inputs        exit 3
      city/alpine_basin_town_plan.json   STALE, cannot reproduce

**It now carries its reason in the file and prints it on every run**
(`_divergence_note`): `storey_m` 3.2 → 2.0 moved `recipes/city.json`, so
building heights and roof z all changed and re-planning also moves the count
303 → 348. Retires when the kit-driven re-plan unit runs. I did **not** give
it a suite finding-code — `run_offline_suite.py`'s own comment says a finding
declaration left in place excuses the next genuine breach in the same tool,
and it has retired three for exactly that. One honest red that states why beats
a green that has been taught to lie.

---

## PER-UNIT STATUS

| # | unit | status | blocking fact |
|---|---|---|---|
| Rulings | Poly Haven sourced direct | **DONE** | — |
| Rulings | MANIFEST generated; cart height derived | **DONE** | — |
| V1 | instrument debt | **DONE** | — |
| V2 | extent-derived FOV, iter2 | **DONE** | delta closed; **frame got worse** |
| V3 | plausibility bands | **DONE** | — |
| V4 | frames owed | **DONE** (earlier today) | — |
| V5 | church material pass | **HALF** | split done + read back; **the three materials are not built** |
| V6 | roof seating + live town push | **NOT STARTED** | ran out of session before it |
| V7 | MANIFEST kept regenerated | **DONE** | — |
| V8 | perf flythrough re-run | **NOT STARTED** | see note below |
| V9 | Phase C1 material derivation | **NOT STARTED** | — |
| S1–S4 | strands | **NOT STARTED** | village queue not exhausted |
| U1–U3 | suite queue | **NOT STARTED** | village queue not exhausted |

**On V8:** worth knowing before you spend a flythrough on it — the church, the
wood stack and the split all landed in **`/Game/Scratch/`**, not in the live
world. The live Alpine8K level is unchanged since the ratified baseline, so a
re-run would very likely re-measure the same thing. It is queued, not skipped,
but that is why it was not the thing I reached for.

---

## THE RULINGS YOU GAVE, AND WHAT CAME BACK

### stone/rock_wall — and the provenance is now PROVEN, not asserted

Fetched direct from polyhaven.com into `refs/polyhaven/`: `rock_wall_08` @2k,
`wood_planks_grey` @2k, `concrete_floor_worn_001` @4k. Licence read off
<https://polyhaven.com/license> — CC0, "any purpose, including commercial
work". In `ASSETS.md` (2026-08-30d) and `CREDITS.md`; hashes in
`Free/_measured/polyhaven_v1.json`.

**All three downloads are byte-identical to the `.fbm` copies.** I picked the
resolutions to match the bundled ones exactly (2k/2k/4k) so the comparison
would be a real test rather than a comparison of two different renders. The
match proves the provenance-by-filename claim: those bundled files really are
the Poly Haven CC0 assets their names say.

**Guard scope untouched** (HARD LIMIT 2), verified both directions:
`refs/polyhaven/…` PASSES, `…/Medival House _.fbm/…` still REFUSED.

The other four `.fbm` textures follow the same convention and were not
fetched — nothing tonight needed them. `rough_wood` is the one four C0 slots
consolidate onto, so it is the likely next.

### cart height — measurement beat proposal by 21%

`SM_WoodenWheelA` measures **87.2 × 87.3 cm** across the disc, consistent to
0.1%. Axle at 43.6; 87.2 is a hard floor for any cart carrying it.
**140.0 (my proposal) → 110.0 (derived).** The manifest states which half is
measured and which is the one modelling assumption, so the first frame checks
the right number.

### MANIFEST — now generated, never hand-edited

`scripts/gen_manifest.py` derives counts, kit coverage, roles→slots and
done-markers from live sources; only the classification is declared, in
`recipes/manifest_classes.json`. `--check` is in the suite and is proven in
both directions.

**It surfaced a data defect:** the v2 kit file has **33 rows but 31 unique
names** — `SM_LanternPost` and `SM_PorchBase` are measured twice, and the two
LanternPost rows disagree on `pivot_base_error_cm` by **75 cm**. Reported, not
silently de-duplicated. Given that a 201 cm pivot error is what buried the kit
roof this week, a 75 cm disagreement between two rows for the same mesh is an
intake question, not rounding.

### church slot split — option A, done and read back

    material_slots  M_Church_Stone, M_Church_Plaster, M_Church_Copper
    slot_count 3    sections_lod0 3    tris 60000    uv 1
    size_cm  76.3 x 39.49 x 91.47      <- Z up again; orientation survived

Bands: stone 0–0.115 (vertex density drops 2235→637 there), plaster to 0.80,
copper above (r_max begins monotonic decline; the concept's 1.5/2.5 ratio puts
the nave top at 0.60, so 0.80 is well clear). Faces 17,969 / 40,933 / 1,098.
The splitter refuses if any band comes out empty.

**Cost was under the 2× stop rule**, so option B stays unused.

⚠ **The dome spring point was not resolved radially.** The tower is off-centre
from the nave, so radius about the mesh centre mixes offset with local radius
and shows no clean bulge. The copper edge is read off r_max decline plus the
ruled ratio — defensible, not surveyed. `TEXTURING_SCOPE.md` predicted exactly
this: that edge needs a frame, not arithmetic.

**Still owed on V5:** the three materials themselves. **Waiting on your copper
tile: `M_Church_Copper` only** — stone has its CC0 source and plaster is in
`textures_v1`.

---

## TWO FINDINGS THAT ARE MORE IMPORTANT THAN THE UNITS

### 1. The suite's freshness check was suppressing HISTORY entirely

I reported this backwards to you earlier and the advisor caught it. Measured:

    check_plan_freshness.py              exit 3, stale = BOTH plans
    check_plan_freshness.py --reproduce  exit 3, stale = the town plan ONLY

The suite runs `--reproduce`, where `elif newer:` meant **the HISTORY verdict
never reached the exit code for any plan, waived or not.** A plan that was
STALE by HISTORY, STAMP MATCHES and CANNOT REPRODUCE exited 0 in the thorough
mode and 3 in the cheap one — the more decisive flag was the weaker
instrument. Fixed additively; it turned no previously-green plan red.

Waivers now also carry `granted_for {path: {from, to}}` so they **expire when
the file they excused moves again**, and suppress HISTORY only where the STAMP
actually adjudicated the input. Four new self-test cases; 12 of 12 pass.

### 2. The concept loop closed its framing delta by making the frame worse

iter2's extent-derived FOV works exactly as ruled — 66.7° → **78.6°**, chalets
outside **1 → 0**, "no render-free deltas remain". I opened the frame. The
village is now a thin strip in the right third with ~60% empty foreground.

**Every measured delta in that loop is a CONTAINMENT test, and containment is
monotonic in FOV.** So a framing delta can always be closed by widening, and
no measured dimension will ever object. The loop is blind to the cost of its
own remedy.

**Proposed, not taken** (it changes the loop's contract): add a subject-fill
dimension with a **floor** as well as the current ceiling. A floor is what
stops widen-until-it-fits being free. The cheaper fixes — camera closer,
cluster tighter — change concept-recorded values and were not authorized.

---

## THE PLAUSIBILITY BAND, AND WHY ITS CONTROL IS THIS WEEK'S DEFECT

    silhouette band  620-820    old 536.5 TRIPS    new 738.0 passes
    nave     derived 930-1230   old 804.8 TRIPS    new 1107.0 passes
    spire    derived 1550-2050  old 1341.3 TRIPS   new 1845.0 passes

**The ratios are 1.50 and 2.50 in both cases — identical, and correct.** That
is the whole point: a ratio cannot detect an error in the quantity it is a
ratio of. The band is derived from geometry, not chosen — 400 cm of wall plus
a 30–45° roof over the 8 m span — and 536.5 falls out as an **18.8° pitch**,
far too shallow for the shingled roof with deep overhang both concepts
describe.

One declaration only; every part band derives by ratio, so there is no second
list to drift. Both the loop and forge stage 10 enforce it, both refuse, and
the refusing direction is in the suite.

---

## DECISIONS — see DECISIONS.md for full text and reversal lines

    D1  Poly Haven direct + hash proof         REVERSE: revert; refs/polyhaven -> _trash
    D2  MANIFEST generated; cart derived       REVERSE: revert the commit
    D3  ADVISOR: waiver/HISTORY scope          REVERSE: git checkout
                                               pre-waiver-scope-20260830 -- <file>

**One advisor consult (D3).** It corrected my premise, I verified the
correction myself before acting, and I took its recommendation (c) whole. Its
own strongest counter-argument is recorded in DECISIONS.md: two instruments
with different sources both going quiet leaves zero red marks on an artefact
nobody re-measured. I judged the hash-pair expiry answers it. **If you
disagree, the fallback is a separate history waiver — not the status quo,
because the old `elif` was the worst of both.**

Tags: `pre-waiver-scope-20260830`, `pre-stage10-woodstack`.

---

## HARD LIMITS

**None arose.** No purchases; the only licence claim is CC0 and it cites
<https://polyhaven.com/license>. No restricted content fed to any model and
the guard's scope is byte-for-byte unchanged. Nothing deleted — the forged
`.fbx` is untouched and the split wrote a new file beside it.

---

## WHERE I WOULD START

1. **V5 second half** — three materials on the split church, then stand and
   frame it. Only the copper tile is yours; stone and plaster are on disk.
2. **The loop's subject-fill floor** — it is a contract change and it is the
   difference between the loop converging and the loop *appearing* to.
3. **V6, the town push** — untouched, and the largest remaining item.
4. **The kit duplicate rows** — 75 cm of disagreement on `SM_LanternPost`.
