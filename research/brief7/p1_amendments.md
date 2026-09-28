# Brief 7 Phase 1 amendments (desk, after reading the six p0 stills)

Applied before the Phase 1 world run. 2026-09-24, live editor `/Game/Alpine8K`.

## A1 — sun elevation as a Look-profile field — DONE

Added `sun_elevation_deg` to the profile switch (`brief7_p0e_setprofile_payload.txt`):
Look raises the atmosphere sun to **35°** (pitch −35) to lift the low-sun sepia; bench
**restores the ruled 12°** (pitch −12) so the bench never sees the Look sun. Runtime
toggle (not saved); the on-disk sun stays at the ruled −12. Yaw/roll unchanged.

Verified by reading the light's rotation under each profile:

| profile | sun_elevation_deg (read back) | sun pitch |
|---|---|---|
| look | 35.0 | −35.0 |
| bench | 12.0 | −12.0 |

**Owed at recipe-lock:** the Look-profile fields (sun 35°, WB 5600, contrast 0.90, shafts,
sg Epic, PPV_Look grade) live in the payload today; they should move to a recipe/profile JSON
(pipeline rule 2). Noted, not blocking.

## A2 — why the far-forest HLOD proxies render black — READ-BACK (fix in P2 step 0)

`brief7_a2_hlod_payload.txt`. 1042 WorldPartitionHLOD actors, 1029 distinct proxy materials.

| aspect | reading | verdict |
|---|---|---|
| proxy shading model | **`MSM_DEFAULT_LIT`** (every one of 1029) | NOT unlit — rules out a bad material |
| blend / two-sided / nanite | OPAQUE / False / Nanite True | normal |
| `r.LumenScene.FarField` | **0 (OFF)** | ← the lever |
| `r.LumenScene.FarField.MaxTraceDistance` | 1,000,000 | (inert while FarField off) |
| `r.Lumen.TraceMeshSDFs` | 0 (software SDF off) | no software fallback either |
| `r.Lumen.HardwareRayTracing` | 1 | on |
| `r.Lumen.HardwareRayTracing.LightingMode` | 1 (hit-lighting) | on |
| `r.RayTracing.Geometry.InstancedStaticMeshes` | 1 | proxies are in RT geometry |
| SkyLight | intensity 1.0, affects world, real-time capture, lower-hemisphere black | on |

**Diagnosis:** the proxies are lit materials — the black is not an unlit/masked material. With
`r.LumenScene.FarField=0` and software SDF tracing off, surfaces beyond Lumen's near-field screen
trace get **no Lumen GI**; the far HLOD band receives neither indirect nor a far-field trace, so it
reads black. **P2-step-0 fix:** enable `r.LumenScene.FarField` (the Brief 7 P4 lever, pulled
forward), verify the far proxies then receive GI (RT-on-proxies + sky already on). Any distant view
is wrong until this is done.

## A3 — snow/grass boundary weightmap — READ-BACK → note & continue

The recipe weightmap is `textures/alpine_8k_weights.png` (`w8a`/`w8b`, channel a[0]=snow).

| measure | value |
|---|---|
| source resolution | **8129 × 8129** = the terrain grid, **1 m/texel** |
| quantisation | 8-bit, 256 distinct snow levels (continuous, not a coarse step) |
| transition band | 4.67% of texels mid-value (0.1–0.9) — a real feathered boundary, not a hard cut |
| isolated single-texel (1 m) snow flips | **0.19%** (126,568 of 66.1 M) — the salt-and-pepper "checker" |
| block size at the boundary | **1 m** (per-texel) |

**Block size 1 m ≤ 2 m → note and continue** (the desk rule re-bakes only above 2 m). The visible
mid_slope checker is 1 m salt-and-pepper at grazing angles; the source weightmap is already at full
resolution. The new material's height-blend reweight (k=4) is the relevant change at that boundary —
judge it on the post-rebuild slope still; if the 1 m checker still reads, a ≤1.5 m blur is the
next lever (BACKLOG-able), not a re-bake.

## Then Phase 1 — BLOCKED on a builder bug (see LESSONS 2026-09-24)

The material rebuild is the first-ever editor run of the merged builder and it fails with
`NameError: __file__` before the destructive clear (M_Alpine8K intact). Fix is a ~6-line staging
change to `make_landscape_material.py:_run`; gated by the branch rule. Reported to Ryan.
