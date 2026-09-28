# Proposal — the external-asset pipeline

Status: **built, running, and fully resolved.** All six open questions are
answered below, the last of them by Ryan's ruling (c) on 2026-08-02.
Nothing here needs a decision.

Written 2026-08-02, after importing ambientCG surface sets and Poly Haven
meshes into the alpine biome and finding three silent-wrong defects in
the process. The full defect write-ups are `docs/lessons.md` §23; the
rulings are `docs/decisions.md`, 2026-08-02 (late).

---

## What the pipeline is now

Five stages, each of which refuses rather than guesses, and each of which
verifies with an instrument other than the one that made the claim.

    Free/<vendor files>
      |
      | scripts/make_asset_manifest.py      inventory: role per file,
      |                                     extent per asset, PROVENANCE
      |                                     per number
      v
    Free/manifest.json
      |
      | scripts/blender/normalize_asset.py  split multi-object files,
      |                                     bake foliage pivots,
      |                                     re-read from disk to verify
      v
    Free/_normalized/*.fbx + Free/_measured/normalized.json
      |
      | scripts/import_static_mesh.py --normalized
      | scripts/import_surface_set.py       per-role import settings,
      |                                     read back and compared
      v
    /Game/Meshes, /Game/Surfaces
      |
      | scripts/make_foliage_material.py    masked/opaque, GL->DX flip
      | scripts/make_landscape_material.py  surfaces into layer bands,
      |                                     grass output into the mask
      v
    the scene, driven entirely from recipes/alpine.json

### The three gates that matter

1. **Provenance is a field, not a comment.** Every dimension in
   `manifest.json` carries `<field>_source` of `vendor`, `assumed` or
   `measured`. A consumer that would behave differently for an assumed
   value must branch on it. This is what made D1 (below) a two-line fix
   rather than an archaeology exercise.
2. **The normalisation report is a precondition, not a hint.**
   `import_static_mesh.py --normalized` reads
   `Free/_measured/normalized.json` and refuses if the object is absent,
   marked failed, or has no file on disk. It never falls back to the
   vendor file.
3. **Every measurement is taken twice, by different instruments.**
   Blender measures the pivot after the bake and again after re-reading
   its own export from disk; UE then measures it a third time off the
   imported asset, after the FBX round-trip and UE's own import
   transform. All three agreed at 0.0 m for all 23 objects.

---

## The six open questions

### Q1 — Which vendor conventions do we adopt wholesale? ANSWERED
Adopted: the size-class authoring pattern (`tiny/small/mid/tall/large`),
which maps directly onto `LandscapeGrassType`'s variety list and is now
schema v1.10 `varieties`. Rejected: the side-by-side scene layout, which
is a product-shot convention and is actively harmful downstream (D2).

### Q2 — Do we keep vendor material graphs or author our own? ANSWERED
Author our own. The vendor FBXs ship material NAMES and texture files but
no graph, and `path_mode="STRIP"` on export drops the texture references
deliberately — binding is a pipeline concern so that sampler types match
the compression settings we chose at import. Three sampler-type
mismatches in one session (§23.5) are the argument for keeping both ends
in one place.

### Q3 — What happens to material slots the vendor does not texture?
ANSWERED. `fir_tree_01` uses four materials per LOD and ships maps for
two. There is nothing upstream to recover — the FBX package IS the whole
delivery. Untextured slots are bound to a SUBSTITUTE named on the command
line, and the substitution is printed on every run, because a silent
fallback reads as an authored choice. Currently `dead_branches` and
`trunk_c` are both bound to bark.

### Q4 — Normal-map convention, per asset or per pipeline? ANSWERED
**Per asset, derived from the files that ship.** This was originally
ruled the other way — a global DX convention — and that ruling was
withdrawn by Ryan on 2026-08-02 after it was applied to Poly Haven meshes
that ship GL only. `make_asset_manifest.py` now derives the convention
per asset from the shipped file set, and `make_foliage_material.py`
inserts the green-channel flip only where the source is GL.

### Q5 — Nanite, on or off? ANSWERED, with a caveat
Off, for alpha-masked foliage, set at import time and never toggled
afterwards. See D4. The caveat is real and is recorded as an open item,
not as a resolved question: the fir is 505,494 triangles with ONE LOD at
28,302 instances. The right answer is generated LODs; that is an audited
change this session did not have room for.

### Q6 — How does an `assumed` footprint get promoted? **THE PREMISE WAS
WRONG.**

The question as originally posed was "how does an assumed footprint get
promoted to a calibrated one after visual tuning". The answer turned out
to be that visual tuning is not the promotion path and should not be.

`grass_medium_01` carried a vendor extent of 7.3 m. It is a correct
number describing the whole laid-out set. The largest single tuft is
0.327 m — wrong by a factor of 22, in the direction that makes everything
derived from it invisible. That is exactly what happened, and no amount
of visual tuning would have diagnosed it, because the object being tuned
was 1.6 cm tall and therefore not visible to tune.

**Ruled:** measurement is the promotion path, and it costs one headless
Blender run. `vendor` does not outrank `measured`; it answers whatever
question the publisher was asking.

This does NOT dispose of the four `assumed` surface tiling periods
(Rock026, Rock051, Rock063, Snow006, all 4.0 m). Those are the tiling
period of a repeating texture, which no file measurement can recover —
ambientCG simply does not publish Dimensions for them. They stay
`assumed`, stay flagged, and are the one place where visual calibration
genuinely is the only instrument available.

---

## RESOLVED — Ryan chose option (c), 2026-08-02

**Ryan chose (c):** `--normalized` is mandatory for any mesh a RECIPE
names; ad-hoc vendor imports stay ungated. Implemented at four points and
audited PASS (auditor-corrected). Full reasoning, and the vertical-pivot
ruling that came out of that audit, are in `docs/decisions.md`,
2026-08-02, "RULING (c)".

  1. the recipe validator, via `landscape_spec.recipe_normalization_errors`
  2. `import_static_mesh`, refusing a recipe-claimed target without
     `--normalized`
  3. `place_foliage`, measuring `get_bounds()` before adding an instance
  4. `make_landscape_material`, same, before building a GrassVariety

1 and 2 are NAME checks against a report on disk, and are defeated by
importing a vendor file under a name that happens to be verified. 3 and 4
measure the asset itself and are not. Both layers exist because the first
pair refuses early and cheaply, and the second pair is the proof.

Also ruled, by the implementer under the standing autonomy grant, because
the audit found nothing was checking it: `MAX_BASE_OFFSET_M = 0.25` gates
the VERTICAL pivot. A mesh with a correct XY pivot and its origin at the
bounding-box CENTRE passed every other gate and would bury each instance
to half its height — minus 7.26 m for `fir_tree_01_c`. Ryan's ruling
settled WHEN normalisation is mandatory, not WHAT counts as normalised.

**Caveat carried forward:** gates 3 and 4 have never run against a live
editor — it was closed when they were written — so their first live run
is their first execution.

**Nothing in this proposal now needs Ryan.** The question is kept below
exactly as it stood, for the record.

### The question as it stood

**The vendor-import pivot gate.** `import_static_mesh.py` currently FAILS
on a pivot offset over 1 m when `--normalized` was used, and WARNS when
it was not. The warning is not a gate, and lesson §17 is explicit that a
flagged risk nobody actions is a defect with paperwork.

The reason it is not a gate is that the script cannot tell why a vendor
file is being imported. Importing one to measure it is legitimate;
importing one to instance it is not. Options:

  (a) leave as is — warn on the vendor path, fail on the normalised path;
  (b) fail on both, and add an explicit `--allow-offset-pivot` for the
      measurement case;
  (c) make `--normalized` mandatory for any mesh named by a recipe, and
      let ad-hoc vendor imports stay ungated.

(c) is the closest to how the pipeline actually works — the recipe is
what decides whether something gets instanced — but it moves the check
from the importer to the recipe validator, which is a bigger change than
it sounds. No implementation until this is signed off (conduct rule 8).
