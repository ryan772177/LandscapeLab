# DECISIONS.md — overnight #2, 2026-08-30

Every decision taken unattended, what it was based on, and **how to reverse
it**. Advisor consults are logged with the question as it was put.

Reversible-by-construction is the standard: a git tag before any live-world or
rule change, a backup into `_trash/` before replacing anything, and a
one-line reversal here.

---

## D1 — Poly Haven textures sourced direct, and the `.fbm` provenance PROVEN

**Ruled by the operator, not decided here.** Logged because it has an
integrity result attached that was not known when the ruling was made.

**Done.** Fetched `rock_wall_08` @2k, `wood_planks_grey` @2k and
`concrete_floor_worn_001` @4k from polyhaven.com's public API into
`refs/polyhaven/`. Licence read from <https://polyhaven.com/license> — CC0,
"any purpose, including commercial work". Recorded in `ASSETS.md`
(2026-08-30d) and `CREDITS.md`, with hashes in
`Free/_measured/polyhaven_v1.json`.

**⭐ The measured result: all three downloads are BYTE-IDENTICAL to the
copies inside `Medival House _.fbm/`.** Resolutions were chosen to match the
bundled copies precisely so the comparison would be a real test. The match
proves the provenance-by-filename claim — the bundled files really are the
Poly Haven CC0 assets their names say, unmodified.

**Guard scope NOT touched** (HARD LIMIT 2). Verified both directions after
the change:

    refs/polyhaven/rock_wall_08_diff_2k.jpg                    PASSES
    Free/_intake/.../Medival House _.fbm/rock_wall_08_diff_2k  REFUSED

Reading the `.fbm` bytes to compute a digest is not a generation input.

**HOW TO REVERSE:** `git revert` the commit; move `refs/polyhaven/` to
`_trash/`. Nothing else consumed these yet at the time of writing.

---

## D2 — MANIFEST.md made generated; cart height derived; a kit data defect surfaced

**Ruled by the operator** (regenerate, never hand-edit; derive the cart height
from the measured wheel). Implemented as `scripts/gen_manifest.py` +
`recipes/manifest_classes.json`, with `--check` in the offline suite.

**Judgement I made inside the ruling:** classification cannot be derived, so it
is DECLARED in a data file rather than typed into the output. That keeps the
output fully generated while leaving the editorial call reviewable in one
place. No advisor consult — the ruling covered the intent and this is the only
shape that satisfies it.

**Measured result:** cart height 140.0 (my earlier proposal) -> **110.0**
derived from `SM_WoodenWheelA` at 87.2 cm diameter. Proposal was 21% high.

**Surfaced, not fixed:** the v2 kit file has 33 rows / 31 unique names;
`SM_LanternPost` and `SM_PorchBase` are measured twice and the LanternPost
rows disagree on `pivot_base_error_cm` by 75 cm. Reported in the manifest,
queued as an intake question. Not silently de-duplicated.

**HOW TO REVERSE:** `git revert` the commit. `refs/MANIFEST.md` returns to its
hand-written form; delete `recipes/manifest_classes.json` and
`scripts/gen_manifest.py`, and drop the suite entry.

---

## D3 — ADVISOR CONSULT: should a stamp waiver also suppress the HISTORY verdict?

**Question put:** the waiver suppresses only STAMP; HISTORY still fires, so a
fully-waived plan stays in the stale list. Should it cover both?

**The advisor corrected the premise, and I verified the correction myself
before acting.** The suite runs `--reproduce`, where `elif newer:` means
HISTORY never reaches the exit code for ANY plan. Measured: plain mode = 2
stale, `--reproduce` = 1 stale. So the waived sidecar already passed in the
suite's mode, and HISTORY was being dropped wholesale — a worse defect than
the one I asked about.

**Recommendation taken: (c)** — three parts in one commit. HISTORY additive;
waiver suppresses HISTORY only for paths the STAMP adjudicated
(`_stamp_covers`); waiver bound to the hash pair via `granted_for` so it
expires when the file moves again. Four new self-test cases.

**Reversibility (advisor's assessment, and mine):** the tool is offline and
read-only, mutates no artefact, touches no editor. One revert of one file.
The waiver text prints in full on every run so it cannot rot quietly, and the
waiver never applies to `--reproduce`, so the decisive instrument is unchanged.

**Failure mode I am accepting, stated by the advisor:** for
`alpine_basin_town_reachable.json` the waiver's prose is now the only thing
between a stale reachability claim and a clean run, because that artefact
cannot be reproduced offline by construction. If the reasoning in `why` is
wrong, no instrument fires. Mitigated by `granted_for`: the waiver dies the
next time `recipes/city.json` moves.

**The counter-argument, which I did not take:** two instruments with different
sources both going quiet leaves ZERO red marks on an artefact nobody
re-measured — the exact class this project keeps paying for. I judged the
hash-pair expiry answers it, and that a red line expected on every run is how
a suite is taught to be ignored. **If the operator disagrees, the fallback is
option (b) done properly — a separate history waiver — not the status quo,
because today's `elif` is the worst of both.**

**TAG:** `pre-waiver-scope-20260830`.
**HOW TO REVERSE:** `git checkout pre-waiver-scope-20260830 -- scripts/check_plan_freshness.py`
and drop `_stamp_waiver.granted_for` / `_divergence_note` from the two city plans.

---

## D4 — C0 tiling propagated; the re-read blocked on exposure, no verdict offered

**Ruled by the operator.** tile_m is now MEASURED for all seven C0 roles from
the Poly Haven originals each generated tile replaces. Rebuilt, read back,
stage rebuilt.

**It corrected the church too:** `church_roof` tile_m 1.5 (my declared intent)
→ 8.0 (measured), a 5.3× tiling error. The "visible tile repetition" I logged
as an accepted trade-off was that error.

**Judgement I made:** I did NOT offer a verdict on "too orange". My eye said
the orange reduced; the frames are not comparable (19.2% of my frame clipped
to white vs 0.0% in the reference), and clipping produces exactly that
impression with no material change. Reporting it would have been a measurement
artefact dressed as a finding.

**Two structural findings surfaced, neither fixed:** `beam_wood`'s four slots
disagree by 3.3× and one instance carries one Tiling; `floor_worn` needed a
50× correction.

**HOW TO REVERSE:** `git revert` the commit. tile_m fields drop out of both
recipes, the builder's `--uv-density` goes unused, and materials rebuild at
Tiling 1.0 by re-running the two build commands without the flag.

---
