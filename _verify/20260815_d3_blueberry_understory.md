# D3 — blueberry understory on the grass system

Executed 2026-08-15, attended (Ryan approved the material rebuild explicitly).
Restore point: tag `pre-d3-blueberry-material-rebuild-20260815`.

Ruled: **blueberry only, on the GRASS system, not instances.** Blackberry
and raspberry are montane-below-treeline and stay on disk; the demo ground
textures stay behind.

## Result

    GT_alpine_8k_Blueberry   8 varieties, densities sum to 12.0 /10m2
                             cull 4500 cm, every variety wind-OFF
    M_Alpine8K               147,145 bytes
                             sha 0152ecb529abe45c7aca3f23c3358d263b05eb31a941a211d3f1dfb03def4928
                             (was 146,819 / 03f0ac21…)
    graph                    298 expressions, 298 reachable, 0 ORPHANED
    samplers                 37 audited, 0 mismatches
    vendor boundary          11 changed files — the SAME pre-existing 11
    frame cost               GPU 7.74 ms  (baseline 7.75)

**Abort bar was +1.5 ms GPU. Measured delta is -0.01 ms** — below what this
instrument resolves (GPU p90 7.87 against a 7.74 mean), so the honest
statement is *under the measurement floor*, not *free*.

Frame: `_verify/20260815_alpine8k_d3_blueberry_forest_floor.png`. The
understory is visible as rounded dark-green shrubs through the paler grass,
absent from the pre-D3 frame at the same station.

## The gate the ruling asked for could not fire, because I had broken it

`uncorrected_pivot_errors()` exists because the grass system applies **no**
pivot correction: it puts the mesh's PIVOT on the surface and the geometry
falls where it falls. A box-centred pivot buries exactly 50% by construction.

`recipe_normalization_errors` merges two registries into one "verified" map
and then does `if ok: continue`. Earlier this session I added the
engine-derived registry to that map — so **registering a mesh as
engine-derived exempted it from the pivot gate entirely.** The two registries
do not carry the same guarantee:

    BLENDER-NORMALISED   pivot is AT THE BASE by construction
    ENGINE-DERIVED       somebody MEASURED it; the pivot is where the
                         vendor left it

Blueberry is a grass species made of vendor `.uasset` meshes — exactly the
combination the hole was shaped for. Fixed by TAGGING provenance at merge
time and running the check on engine-derived rows. Proven both ways: the real
recipe still validates with 0 errors, the three engine-derived tree rows now
reach the check and pass (sink 0.004–0.024%), and a synthetic box-centred
pivot is REFUSED at 50%.

**The eight blueberries pass with margin:**

    mesh            height    base_z     sink%   slots   LOD0 tris
    Blueberry_01    0.270m  -0.0188m     6.96%     1        195
    Blueberry_02    0.340m  -0.0078m     2.29%     1        436
    Blueberry_03    0.407m  -0.0049m     1.20%     1        344
    Blueberry_04    0.291m  -0.0038m     1.31%     1        434
    Blueberry_05    0.432m  -0.0188m     4.35%     1      1,168
    Blueberry_06    0.212m  -0.0016m     0.75%     1         96
    Blueberry_07    0.235m  -0.0093m     3.96%     1        284
    Blueberry_08    0.235m  -0.0093m     3.96%     1        476

Limit is 25%. The vendor authored these near their base.

## THE BUILDER REPORTED SUCCESS OVER A CLAIM THAT WAS FALSE

`MA_Blueberry` carries the same wind system as the PN trees — `Level 1/2/3
Wind`, `Level 1/2/3 Bending`, Wobble scalars. The grass system offers no
per-instance correction and the pack must not be edited, so the only route is
`GrassVariety.override_materials` (PythonStub :121628).

That was declared in the recipe, accepted by the validator, handled in the
payload, and the builder reported **success**. Connectivity passed.
Samplers passed. And all eight varieties read back **`overrides: NONE`** off
the saved asset.

Root cause at `make_landscape_material.py:2932`: the recipe's variety dicts
never reach the payload. They are TRANSFORMED into
`{mesh, density, smin, smax}` first, and `override_materials` was dropped
there. The payload was correct about a field it never received.

**Nothing else would have caught this.** The builder's own report, the
connectivity audit and the sampler audit are all blind to it — a grass type
with no overrides is a perfectly well-formed grass type. It took an
instrument that reads the SAVED asset and shares no code with the builder:
new tool `scripts/read_grass_type.py`, with `--expect-all-overridden` as a
REFUSAL rather than a printed observation.

After the fix, re-read from the saved asset:

    Blueberry_01 … Blueberry_08   overrides: MI_MI_Blueberry_0N_nowind

## Cost model, stated so the -0.01 ms is not mistaken for magic

45 m cull → a 6,362 m² disc → 636 units of 10 m² → **~7,634 instances** at
~500 triangles average ≈ **3.8M triangles**, against a grass budget of
29.8M and a scene already drawing 153,796 trees. Roughly +10% on grass
instance count. A delta that small is expected to sit under the noise of a
300-frame GPU mean, and it does.

## Open

- **`grass.FlushCache` could not be verified.** It is a command-style cvar
  that self-resets, so `render_condition` reads back 0 and REFUSES to vouch
  for it — correctly, since it cannot distinguish "ran and reset" from
  "never took". The capture below shows the understory rendering, so the
  cache is evidently current; the cvar's own read-back is simply not an
  available instrument here.
- **The wind-off claim for blueberry is structural, not rendered.** The
  overrides are proven present on the asset; no frame-pair test has been run
  on the understory specifically. The tree case was measured
  (`_verify/20260815_pn_wind_is_live.md`) and this shares its mechanism.
- The generated MI names carry a doubled prefix — `MI_MI_Blueberry_01_nowind`
  — because the source asset was already `MI_`-prefixed. Cosmetic, and
  renaming them later would break the recorded override paths.
- **Nothing was scattered and no world was saved.** D3 touches the landscape
  material and grass types only. The D4 re-scatter is still pending.
