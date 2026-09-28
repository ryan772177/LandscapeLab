# The first forge run — the church, end to end, 2026-08-30

`scripts/forge.py --asset church`. Nine stages, exit 0, **44 s** for the full
run including generation. Frame: `church_beside_kit.png`.

## THE NUMBERS

    [1] input floors     4 views, 192k-308k subject px vs a 150k floor
    [2] ai_input_guard   all 4 cleared --strict BEFORE the weights loaded
    [3] generate         190,562 v / 381,364 f   thin/long 0.4317
                         watertight   genus 61   VRAM peak 10,082 MiB
                         load 21.4 s   inference 5.5 s
    [4] retopo           381,364 -> 60,000 tris (hero_prop ceiling 60,000)
    [5] pivot            base-centre, base_at_origin TRUE
    [6] UVs              none -> 1 channel (smart_project, MACHINE unwrap)
    [7] intake           0.4317 >= 0.30, watertight, 60,000 <= 60,000
    [8] ASSETS.md row    written
    [9] FORGE_LOG line   written

In the engine: **1341.3 cm to the spire, 11.2 x 5.8 m footprint, 2.50x the
chalet silhouette** — ruling 1, satisfied by real geometry rather than by the
cone-and-cylinder stand-in.

## ⛔ THREE THINGS THE WRAPPER DOES NOT DO, STATED PLAINLY

### 1. DECIMATION DID NOT REDUCE GENUS, AND WAS NEVER GOING TO

    genus 61 -> 61        chi -120 -> -120
    triangles 381,364 -> 60,000

Edge collapse preserves topology. The triangle budget is met and all 61
handles remain. `within_budget` is not `clean`, and the report says so in its
own text rather than leaving a reader to diff two numbers. **Closing the
handles needs a real retopology or hole-filling pass and is NOT claimed here.**

### 2. THE FORGE IS NOT BIT-REPRODUCIBLE, DESPITE A FIXED SEED

    standalone run   190,498 v   381,228 f   chi -116   genus 59
    forge run        190,562 v   381,364 f   chi -120   genus 61

Same seed (20260830), same sampler params, same model repo, same four inputs.
CUDA and spconv are not bitwise deterministic, so the seed fixes the sampling
path and not the result. **This breaks pipeline rule 3** (re-running a recipe
rebuilds deterministically) for generated assets specifically.

The VERDICT was stable across both runs -- `thin_over_long` 0.4317 both times,
watertight both times -- so the intake floors are robust even though the mesh
is not. A replay will produce an equivalent asset, never the same bytes. The
forged `.fbx` is therefore the artefact of record and must be kept, not
regenerated on demand.

### 3. A GENERATED MESH CARRIES NO UNITS — AND NO RULED STAGE CATCHES IT

TRELLIS normalises its output. The church's bbox is 0.763 x 0.395 x 0.915, so
imported raw it is **39.5 cm tall**: a doll's house that renders perfectly.
The triangle budget, the watertight check, the pivot and the UV pass are all
**scale-invariant**, so nothing in stages 1-9 would ever notice.

Scale is now derived from the ruling -- spire = 2.5x the 536.5 cm chalet
silhouette = 1341.3 cm -- and read back from the placed actor. **Proposed as
forge stage 10**, in `scripts/forge_scale_payload.txt`.

## ⛔⛔ THE DEFECT THAT MATTERED MOST: A PERFECT SCORE ON THE WRONG AXIS

The FBX round trip rotates the mesh **-90 degrees about X**. UE reported raw
extents `X 76.3 / Y 91.47 / Z 39.49` cm against a Blender bbox of
`0.763 / 0.395 / 0.915` — UE's Y held Blender's Z, and UE's Z held Blender's Y.
**The church imported lying on its side.**

The scale step then stretched its DEPTH to the ruled 1341.3 cm and reported:

    church_top_cm      1341.3          <- the ruled number, hit exactly
    church_over_chalet 2.5             <- ruling 1, a perfect score
    church_footprint   2591 x 3107 cm  <- a 26 x 31 m church, 13 m tall

Two of those three numbers are the ones anyone would check. **The footprint is
the only one that gave it away**, and only because it was measured.

### WHAT DID NOT FIX IT, RECORDED SO IT IS NOT RETRIED

* `axis_forward="X", axis_up="Z"` on the FBX export — **byte-identical UE
  extents.** UE applies its own Y-up to Z-up conversion regardless of what the
  file declares. The axis flags are not the lever.
* `obj.rotation_euler` + `bpy.ops.object.transform_apply` — **silently did not
  take in background mode.** The report logged the rotation as applied while
  the exported FBX was unchanged. An operator that depends on context is not a
  transform; it is a request.
* `replace_existing=True` on the import task — **did not re-import.** The FBX
  was re-exported three times with different content (mtime and sha256 both
  changed) and UE returned the same bounds every time, reporting success and
  handing back the stale asset. The destination is now deleted first, guarded
  to `/Game/Scratch/`.

### WHAT FIXED IT

Rotating the **vertices** directly — the same technique the pivot step uses,
which has no operator context to fail — with a **self-check that refuses to
export** if the rotation did not take. And an **orientation gate at import**
that compares UE's per-axis extents to the exported Blender bbox and refuses
rather than scaling a mesh that came in sideways.

Both directions are now covered: the exporter proves it rotated, and the
importer proves it received what was sent.

## WHAT THE FRAME SHOWS

`church_beside_kit.png`, 2032 x 1273, mean 0.5831 std 0.2424.

**The church reads as architecture:** nave with pitched roof, side porch,
buttresses, tower with belfry openings, onion dome and finial. It is a
landmark beside the house, which is what 2.5x is for. Untextured grey — UVs
exist, textures do not.

**And the chalet beside it shows ruling 4's roof defect at full strength.** The
kit roof sits on the greybox box narrower on one axis and proud on the other,
drooping at the eaves. Next to a real building it is unmistakable. R4a/R4b/R4c
are no longer an abstraction about tolerances.

*The chalet appears on the LEFT although it is at x=+1600: at yaw 90 the
camera's right is -X. The mirror rule from `docs/ue58-api-protocol.md` held.*
