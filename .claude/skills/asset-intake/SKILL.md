---
name: asset-intake
description: Bringing a new mesh or surface into the project — R-ASSET's ordered steps, the ORM unpack path, provenance and hashing, the coherence check's current limits, and the vendor-folder rule. Use when importing, unpacking, cataloguing or evaluating any new asset from Fab, Megascans, ambientCG or elsewhere.
when_to_use: a new pack landed; importing a surface or mesh; unpacking ORM; writing an ASSETS.md row; deciding whether an asset belongs; cataloguing vendor content
allowed-tools: Read, Grep, Glob
---

# Asset intake

Sources: `RECIPES.md` R-ASSET and R3, `scripts/unpack_orm.py`,
`scripts/import_surface_set.py`, `scripts/surface_coherence.py`.

## Order (R-ASSET), and why it is this order

1. **Record source + licence + role in `ASSETS.md` — BEFORE importing.**
   An asset whose licence nobody recorded is one we may not ship, and
   that is cheapest to discover before the import work.
2. **Photoreal-coherence check.** See limits below.
3. R3 steps 1–5 (manifest, normalize, import, material).
4. R5 for the LOD chain.
5. Skeletal only: IK Rig + Retargeter. **UNVERIFIED, never executed.**
6. **Spawn one instance and RENDER it.**
7. Flip verified-in-engine to YES — **only now.** Settings read-backs
   are not sufficient.

## The vendor-folder rule

**Never author into a Fab/vendor folder.** Their contents are replaced
wholesale on reinstall, so an edit there is lost work that looks like
committed work. Copy to a project-owned path and edit the copy. Enforced
by the `fab-protection` hook.

**ASSETS ENTER THE PROJECT; SYSTEMS GET STUDIED.** A complete
shader-side system (MW Landscape Auto Material) is catalogued
REFERENCE-ONLY and never becomes a dependency; techniques it teaches
enter through the front door — designed, cited, asserted, recipe'd.

## ORM-packed surfaces

**UNPACK TO DISCRETE ROLES AT INTAKE.** Never teach the material
declaration a packed form: the preflight, sampler rules and post-build
assertion are three projections of ONE declaration over discrete roles,
and a packed branch forks every one of those guarantees for one vendor's
packaging.

**Verify the channel mapping PER PACK.** `unpack_orm.py` does this, and
the primary discriminator is **HEIGHT**, not albedo:

    R  corr(height) POSITIVE and > G's   -> ambient occlusion
    G  corr(albedo)  larger than R's     -> roughness

The **albedo-only test is rock-calibrated and does not transfer** — its
premise is geometry-driven albedo, which is false for pigment-driven
surfaces. On Wild Grass it FAILED a correct mapping. Occlusion tracks
DEPTH regardless of pigment; that premise is class-portable.

**Channel B stays undiscriminated on any dielectric.** Zero-and-say-so
per NN21. Upgrade only when a metallic-bearing asset shows a nonzero B
landing where metal is visibly present.

## Megascans specifics

- **Raw omits displacement.** Only `High/<id>_tier_1` carries `_H`, so
  High is **required** for the HeightLerp path, not merely sufficient.
- `export_assets` writes 8-bit PNG. **Check the source depth before
  converting**: `blueprint_get_texture_source_disk_and_memory_size()`
  over pixel count gives bytes/pixel — 4 is BGRA8, 8 is 16-bit RGBA. An
  8-bit export of a 16-bit source is silent precision loss wearing a
  familiar extension.

## Normal convention — measure it

A wrong convention inverts lighting across the whole surface. If the
pack ships a height map, measure rather than assume: for a heightfield
the normal is ∝ `(-dH/dx, -dH/dy, 1)`, rows increase downward, and
OpenGL's +Y runs UP the image, so `dH/dy_GL = -dH/drow` and
`N_y ∝ +dH/drow`:

    GL  ->  corr(G, dH/drow) POSITIVE
    DX  ->  corr(G, dH/drow) NEGATIVE

**⛔ THIS LINE SAID THE OPPOSITE UNTIL 2026-09-12**, and the error was
copied into `scan_surface_stats.py`, which then reported all six
ambientCG packs on disk — including the three already BOUND — as
disagreeing with their own filenames. Six packs are not all mislabelled.

**The paragraph refuted itself from the inside**: the same minus sign in
`(-dH/dx, -dH/dy, 1)` that makes red correlate NEGATIVELY with the
column gradient makes DX's green correlate negatively with the row
gradient. One expression cannot carry the minus for X and drop it for Y.
The concrete case agrees — on a hill's upslope (`dH/drow > 0`) the
surface faces UP the image, which is +Y in a y-up frame, so GL's green
goes above mid.

**Use the red channel as the CONTROL** — it must correlate negatively
with the column gradient regardless of convention. Symmetric magnitude,
opposite sign, method self-checked. **But note what the control could
not do here:** it passed on every pack while the green verdict was
inverted, because it tests the GRADIENT's sign, not the y-flip. A
control that shares no term with the thing it guards is the only kind
that guards it (NN0). The sign is now pinned by
`scan_surface_stats.py --selftest`, which builds normals ANALYTICALLY
under each convention rather than trusting either this file or the
packs.

## The coherence check — know what it cannot do

`surface_coherence.py` exists but **REFUSES on its own calibration
set**: no feature separates photoreal from stylized, because the
photoreal class spans snow to gravel and **material identity dominates
authoring method**. Controlled on material (grass vs grass) two of three
features do separate.

So **no verdict is issued** until there is a photoreal calibration
specimen per material family. Do not substitute judgement for the
instrument and record it as a measurement — that is the
unfalsifiable-adjective problem the instrument exists to remove.

## Provenance

Original retained, outputs **hash-linked** to it. Adopted artefacts are
copies at stable names, hash-proven against their source at adoption
time (NN20). Never point a consumer at a generator's live output.
