"""push_heightmap.py — push a heightmap into the EXISTING landscape.

AUDIT STATUS — NOT BLOCKED. UNRESOLVED_BLOCKS is empty, so main() does not
refuse on entry. D1 (self-widening tolerance) and D2 (writing on argument,
not evidence) were RULED and CLOSED by Ryan on 2026-08-01 (full text in the
RESOLVED_BLOCKS below). The 2026-08-01 audit of the export read-back stage
raised D3 (the export value encoding) and D4 (`--expect-change`
reachability); D3 was CLOSED BY EVIDENCE (the --probe-export measurement:
flag-False writes the RAW uint16 into R, R==G — see decode_export()) and D4
was RULED by Ryan and RESOLVED IN CODE (main() now CLASSIFIES before the
gates, so a changed push with --expect-change routes through the changed
branch; the gates live in the not-changed branch). Both are in the
D3_RESOLVED / D4_RESOLVED records below, kept verbatim per conduct rule 8.
See LESSONS.md.

WHY THIS EXISTS (Priority 0 of the 2026-08-01 aesthetic brief)
Route B says the landscape is created by hand ONCE, and every later height
change is pushed by script. Without this, iterating on terrain means
delete -> New Landscape dialog -> rename -> verify -> save, about ten
minutes per attempt through a dialog that has silently produced the wrong
`sections_per_component` on BOTH imports so far (lesson 6.6). With it the
loop is: edit the generator, regenerate, push, capture.

It changes HEIGHTS ONLY. Resolution, component layout, scale and location
are untouched — which is why the dialog is not needed, and also why this
refuses unless the live landscape already matches the recipe's geometry: a
heightmap at a different resolution is not a push, it is a rebuild, and
rebuilds go through the dialog.

=====================================================================
THE VALUE ENCODING, READ AT THE SOURCE LINE (UE 5.8)
=====================================================================
`Engine/Source/Runtime/Landscape/Private/LandscapeEdit.cpp:8117-8141`,
`ALandscapeProxy::LandscapeImportHeightmapFromRenderTarget`:

    case RTF_RGBA16f:
    case RTF_RGBA32f:
        ...
        for (const FLinearColor& LinearColor : OutputRTHeightmap)
        {
            if (InImportHeightFromRGChannel) { ... }
            else { HeightData.Add((uint16)LinearColor.R); }   // :8138

**The red channel is the RAW uint16 height, not a 0..1 normalised value.**
Worth reading rather than assuming: the obvious guess — that a float render
target carries 0..1 and the engine scales it — produces a landscape 65535x
too flat, silently, because a flat landscape is a valid landscape.
`(uint16)` is a C cast, so it TRUNCATES toward zero; the drawing material
therefore emits `value * 65535 + 0.5` to round to nearest instead of losing
up to a full height unit on every texel.

**RTF_RGBA32f, never RTF_RGBA16f.** Both are accepted by the switch above,
which is the trap. fp16 carries a 10-bit mantissa, so consecutive integers
stop being exactly representable above 2048 and the spacing at the 32768
datum is 32 — a 16f target would quantise the terrain to ~1.6 m steps while
succeeding and looking plausible. fp32 is exact to 2^24.
(`TextureRenderTarget2D.h:61`: RTF_RGBA32f -> PF_A32B32G32R32F.)

**The same trap exists one stage earlier, in the TEXTURE.** `TextureDefines.h:399`
documents `TC_HDR` as *"HDR (RGBA16F, no sRGB)"* — fp16 again, same 10-bit
mantissa, same spacing of 32 height units (125 cm) across the top half of
the range. An intermediate at TC_HDR would terrace the terrain exactly as
an RTF_RGBA16f target would. `TextureDefines.h:409` documents `TC_HDR_F32`
as *"HDR High Precision (RGBA32F)"*, which is exact for all 65536 levels,
and that is what this script sets. TC_VectorDisplacementmap (`:398`,
"RGBA8") and TC_Displacementmap (`:397`, "G8/16 from source A") are both
wrong for a 16-bit greyscale source — the first is 8-bit outright, the
second reads the ALPHA channel.

`InImportHeightFromRGChannel` must be **False**; the True branch does
`LinearColor.ToFColor(false)` then `(R << 8) | G`, an 8:8 byte split that
clamps the float channels to 0..255 first.

**An undersized render target does not error.** `:8113` computes
    SampleRect = FIntRect(0, 0, Min(1 + MaxX - MinX, RT->SizeX),
                                Min(1 + MaxY - MinY, RT->SizeY))
so a too-small RT imports a SUB-RECTANGLE and leaves the rest of the
terrain untouched — a silent partial write. Gated before anything is drawn.

`LandscapeImportHeightmapFromRenderTarget` (`LandscapeProxy.h:1572`) is the
ONLY BlueprintCallable height-import path; `ALandscapeProxy::Import`
(`:1418`) is LANDSCAPE_API C++ and unreachable from Python. Its signature,
read at that line, is
    bool LandscapeImportHeightmapFromRenderTarget(
        UTextureRenderTarget2D* InRenderTarget,
        bool InImportHeightFromRGChannel = false,
        int32 InEditLayerIndex = 0);
so the call passes three arguments, the third being the EDIT LAYER index.
Since 5.7 every landscape uses the edit-layer system (`:1585-1586`), so
index 0 is the base layer and the rendered surface is the composite of all
edit layers. A landscape carrying more than one edit layer would not read
back as the source even after a correct push — see D2 below.

=====================================================================
HOW THE PIXELS GET IN
=====================================================================
Python cannot write texels into a render target, so:
  1. import the 16-bit PNG as a Texture2D through the editor import task,
  2. build a material that samples it and emits `v * 65535 + 0.5`,
  3. `DrawMaterialToRenderTarget` into an RTF_RGBA32f target,
  4. `landscape_import_heightmap_from_render_target(rt, False, 0)`.

The material's domain is **MD_UI**, not Surface. Not a preference:
`KismetRenderingLibrary.cpp` draws through `Canvas->K2_DrawMaterial(...)`,
a canvas tile, which is the UI path. It is drawn at
`ScreenPosition (0,0)`, `ScreenSize (SizeX, SizeY)`, `CoordinatePosition
(0,0)` with the default coordinate size, so UV0 spans exactly 0..1 across
the target and `TextureCoordinate(0)` maps the texture 1:1 onto it.

Step 1 is precision-critical and is NOT assumed. Note what can and cannot
be read back: `UTexture2D::GetPixelFormat` (`Texture2D.h:161`) is plain
`ENGINE_API`, NOT a `UFUNCTION`, and no `PixelFormat` UPROPERTY exists — so
the platform pixel format is simply not reachable from Python, and any gate
written against it can only ever refuse. The reachable evidence is: every
texture setting read back after it is set (the pattern proven by the
layer-texture import script), and the built texture size from
`Blueprint_GetBuiltTextureSize` (`Texture.h:1857`), which derives from the
SOURCE (`Texture.cpp:4079-4087`) and so — unlike `Blueprint_GetSizeX` — is
not the resident streamed mip.

=====================================================================
VERIFICATION — AND HOW THE INSTRUMENT CALIBRATES ITSELF
=====================================================================
**THE LINE-TRACE INSTRUMENT IS RETIRED.** It ran, but its RESULT is
unreadable from Python: every field of `FHitResult` is a bare
`UPROPERTY()` (`HitResult.h:100-140`) and the editor refuses them as
protected; `UGameplayStatics::BreakHitResult` is
`UFUNCTION(BlueprintPure, meta=(NativeBreakFunc))`
(`GameplayStatics.h:1077`) and the Python plugin exposes no NativeBreakFunc
helper; and `GetHeightAtLocation` (`LandscapeProxy.h:1101`) is LANDSCAPE_API
but not BlueprintCallable. Confirmed live: a dry run scored 289/289 samples
UNREADABLE and refused. `TRACE_SOURCE`, `_trace`, `_score`,
`_sample_texels`, `texel_to_world`, `LANDSCAPE_CLASSES`,
`EDGE_MARGIN_TEXELS` and `--grid` are all retained ONLY so the regression
tests keep their revert-proofs; **nothing in `main()` calls any of them.**

Heights are now read back by EXPORTING the live heightfield into an
RTF_RGBA32f render target with `LandscapeExportHeightmapToRenderTarget`
(`LandscapeProxy.h:1258-1259`, BlueprintCallable) and reading blocks of it
with `read_render_target_raw_pixel_area(..., bNormalize=False)`. Full
rationale, the layout proof, the residency gate and the OPEN QUESTION
about the value encoding are in the comment block above `EXPORT_SOURCE` in
this file — read it before trusting a number that comes out of it.

Expected world Z for heightmap value v, from the project's own datum:
    world_z_cm = actor_z_cm + (v - 32768) * scale_z / 128
(`LANDSCAPE_ZSCALE` is 1/128; the 512-unit full range gives
scale_z = z_scale_cm / 512.) Checked two ways: v=0 yields world Z 0 and
v=65535 yields 255996 cm against the recipe's 2560 m range.

**The instrument is calibrated BEFORE the push, against the terrain that is
already there.** That pre-flight does two jobs no post-hoc check can:

  (a) It establishes the texel->world ORIENTATION empirically instead of
      assuming it. ALL EIGHT symmetries of the square (identity, the three
      flips, and the same four transposed) are scored against the live
      terrain and the best is used — enumerating only some of them would
      leave a mirrored write reachable. Assuming the mapping is exactly
      how a mirrored terrain gets written and never noticed. The winner
      must beat the runner-up decisively, or the run refuses: a near-tie
      is not a close call, it is evidence the measurement is degenerate.
  (b) It measures a residual against the source heightmap. **Read D1 below
      before trusting that residual as an instrument-error measurement.**
      It only is one when the live terrain already equals the source.

After the push the same vertices are re-exported and compared against the
same source pixels through the same mapping — set equality on the vertex
keys, not merely the same count. A push that cannot be verified is
reported as UNKNOWN (exit 5), never as success, and that includes an
unexpected exception in the comparison itself.

**What this cannot distinguish, stated plainly:** pushing the heightmap
that the terrain was already built from is idempotent, so "heights match
the source" would also be true if the push had done nothing at all. The
positive evidence that the mechanism ran is separate — the engine's own
boolean return, and its `LogLandscapeBP` line "Took %f seconds to import
heightmap from render target" (`LandscapeEdit.cpp:8175`). Both are
reported. The first push of a CHANGED heightmap is what will exercise the
distinguishing case.

Identification is BY PROPERTY SIGNATURE, never by label: this is an
irreversible write to terrain and actor labels collide (hard-won lesson 4).
The signature is re-tested INSIDE the mutating payload, and so is the
current LEVEL: conduct rule 7 identifies the project, not the world, and
several round trips separate the dry run's gate from the write.

DRY RUN IS THE DEFAULT. It creates no ASSET and mutates no terrain:
`--push` is still required before anything is imported, saved, or written
to /Game/. It is no longer strictly read-only, and saying so plainly
rather than letting the old sentence stand: the export read-back allocates
a transient `UTextureRenderTarget2D` and runs a GPU draw into it.
`UKismetRenderingLibrary::CreateRenderTarget2D` does
`NewObject<UTextureRenderTarget2D>(WorldContextObject)`
(`KismetRenderingLibrary.cpp:84`), so that object's OUTER is the editor
world, not the transient package. It is unreferenced once the payload
returns and is never marked public or standalone, so it is not expected to
be saved with the level — expected, not proven.

Exit codes:
  8  another heavy operation holds the lock (scripts/resource_guard.py)
  0  dry run completed, or the push completed and verification PASSED
  1  unexpected error / bad arguments
  2  recipe or heightmap missing, outside REPO_ROOT, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  identification failed: no landscape matched the recipe's property
     signature, several did, or the identify probe could not be read
  5  the push ran but verification FAILED or could not be completed —
     terrain state is UNKNOWN and must not be trusted
  6  a precondition refused: an unresolved audit BLOCK, geometry mismatch,
     an incomplete or translated resident component set (the export origin
     gate), an encoding that is not R * 65535, an undegenerate orientation
     could not be established, an undersized render target, texture
     settings that did not read back, or a push payload that never left
     this machine
  7  LEVEL GATE REFUSED — a different level is open than
     `landscape.level_path`
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import resource_guard   # noqa: E402 — RAM check + heavy-op lock
import landscape_spec     # noqa: E402 — shared recipe loading + derive_spec
import verify_landscape   # noqa: E402 — shared node selection, gate_level
import make_landscape_material as mlm  # noqa: E402 — .py transport guard

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
PROBE_MARKER = "__LANDSCAPELAB_PUSH__"

# ---------------------------------------------------------------------
# UNRESOLVED AUDIT BLOCKS (conduct rule 8 — Ryan signs these off BEFORE
# any implementation; a rewrite does not retire them). Full text carried
# inline rather than by label, per conduct rule 9. While this tuple is
# non-empty main() refuses at exit 6 before contacting any editor.
# ---------------------------------------------------------------------
D3_RESOLVED = (
    # Closed 2026-08-01. The graph-reading conclusion (byte split, R high /
    # G low) was REFUTED by the --probe-export measurement: with flag-False
    # the export writes the RAW uint16 into R (R == G), and decode_export()
    # uses R directly. Byte-split is the flag-True path only. Original
    # finding, kept for the record:
    "D3 — THE EXPORT READ-BACK'S VALUE ENCODING IS ASSERTED IN ONE "
    "DIRECTION AND CONTRADICTED IN THE OTHER, IN THIS SAME FILE. The new "
    "pre-flight and post-push comparisons both compute `R * 65535` and "
    "treat the result as the heightmap value, i.e. they assume "
    "LandscapeExportHeightmapToRenderTarget with "
    "InExportHeightIntoRGChannel=False writes the height NORMALISED into "
    "the red channel. The engine source argues the opposite. The mirror "
    "import path, LandscapeImportHeightmapFromRenderTarget with the same "
    "flag false, does `HeightData.Add((uint16)LinearColor.R)` at "
    "Engine/Source/Runtime/Landscape/Private/LandscapeEdit.cpp:8138 — R "
    "carries the RAW 0..65535 value, which is precisely why this script's "
    "own push material emits `v * 65535 + 0.5` (PUSH_SOURCE step 4). "
    "Export and import are the two halves of one round trip through one "
    "flag (the flag is set as a scalar parameter on the engine material at "
    ":8247), so the straightforward reading is that the export also writes "
    "the RAW value and that `R * 65535` is 65535x too large. The engine "
    "material /Engine/EditorLandscapeResources/"
    "Landscape_Heightmap_To_RenderTarget2D is a .uasset and cannot be read "
    "from disk, so this is not settled either way — but the burden of "
    "proof now sits against the hypothesis, not for it. CONSEQUENCE IF "
    "WRONG: the ENCODING_MAX_UNITS gate refuses at exit 6 and no terrain "
    "is written, so this is fail-closed, not dangerous — but the script "
    "cannot succeed at all until the encoding is right, and the "
    "ENCODING_MAX_UNITS refusal cannot tell 'wrong encoding' apart from "
    "'the terrain legitimately differs from the source' (see D4). The "
    "auditor added `r_min`/`r_max` reporting to EXPORT_SOURCE so ONE dry "
    "run settles it: R within [0,1] means the export normalises and the "
    "hypothesis stands; R spanning roughly 0..65535 means it does not and "
    "every `* 65535.0` in main() must go. NEEDS RYAN: choosing the "
    "encoding, and choosing whether the gate should test the encoding "
    "against a content-independent discriminator (the observed R range) "
    "instead of against a residual versus the source. The auditor did not "
    "pick one — fitting the constant to whatever the first run returns is "
    "the same circularity the ENCODING_MAX_UNITS refusal exists to "
    "prevent, and guessing it is how a 65535x-flat terrain gets written.",
)

UNRESOLVED_BLOCKS = ()  # D3 closed by evidence, D4 ruled — see below

# D4 — RULED by Ryan 2026-08-01 ("push anyway, it's idempotent"), then
# RESOLVED IN CODE 2026-08-01 after that push succeeded. The pre-flight no
# longer refuses a changed push: it CLASSIFIES, and on a changed push the
# write is gated by the pre-import render-target check (source-independent)
# while the post-push export check becomes load-bearing. Original finding
# kept below for the reasoning.
#
# SUPERSEDED BY THE CODE (see the RESOLVED note above): --expect-change is
# now REACHABLE. main() classifies FIRST (`changed = best_units >
# ENCODING_MAX_UNITS`, line ~2705), and a changed push with --expect-change
# routes through the changed branch (DEFAULT_ORIENTATION, gated by the
# pre-import render-target check); the encoding/decisiveness gates live only
# in the not-changed branch, so a changed push never reaches them. The
# original finding below reasoned from the pre-resolution ordering and is
# kept for the record.
#
# WHAT THE RULING COVERS, exactly: pushing the heightmap the landscape was
# already built from. That push IS idempotent, both gates pass on it, and
# the limitation is not engaged. It does NOT cover a push of changed
# terrain — the first eroded heightmap (P1) will hit this and must not be
# forced past it. The fix shape recommended at the time: verify a changed
# push against the RENDER TARGET, which is already read and compared
# exactly before the import, and demote the export read-back to confirming
# that the write landed. That removes the circularity rather than widening
# anything.
D4_RESOLVED = (

    "D4 — `--expect-change` IS NOW UNREACHABLE, SO THE SCRIPT CAN ONLY "
    "PUSH A HEIGHTMAP THE TERRAIN ALREADY MATCHES — THE ONE THING IT "
    "EXISTS FOR IS THE ONE THING IT CANNOT DO. The export instrument "
    "establishes both the orientation and the encoding by scoring the "
    "LIVE terrain against the SOURCE PNG. Both gates run on `med_units`, "
    "the median |R*65535 - source| over the sampled vertices, and both "
    "return 6 BEFORE the classification block that consults "
    "`args.expect_change`. On a genuinely changed heightmap — the stated "
    "purpose of this script, per the docstring and per the D1 ruling — "
    "med_units is large for ALL EIGHT mappings, so either the "
    "ENCODING_MAX_UNITS gate fires ('R * 65535 is not the encoding', "
    "false) or the ORIENTATION_MARGIN ratio test fires ('the orientation "
    "search is not decisive', also false). Reordering does not help: the "
    "instrument is calibrated against the terrain it is about to "
    "overwrite, so it is only well-defined when the push is a no-op. Note "
    "the docstring already concedes that an idempotent push 'could not "
    "distinguish a correct push from no push at all' — with D4 in place "
    "that is the ONLY push the script will ever perform. This is "
    "fail-closed (exit 6, nothing written), not dangerous. THE ENGINE "
    "SOURCE OFFERS THE WAY OUT, which is why this is a design choice "
    "rather than a defect to patch: the texel->vertex layout does not "
    "need to be searched at all. LandscapeEdit.cpp:8261 draws each "
    "subsection at `SectionBase - ExportBaseOffset` and :8270-8286 place "
    "the triangles there, with ExportBaseOffset = ComponentsExtent.Min "
    "(:8228) accumulated by GetComponentExtent (:2876-2882). So RT texel "
    "(gx,gy) IS vertex (gx,gy) whenever the minimum section base over the "
    "resident components is (0,0) — which the auditor has now MEASURED "
    "and gated in EXPORT_SOURCE ('residency' stage) rather than assumed. "
    "The eight-mapping search is therefore not measuring the export "
    "layout; it is measuring how the MANUAL New Landscape dialog import "
    "laid the PNG onto vertices, and that relation is undefined once the "
    "PNG changes. OPTIONS, all needing Ryan: (i) keep the eight-mapping "
    "search as a PRE-FLIGHT-ONLY calibration that must be run once "
    "against a matching terrain, record the winning mapping in the recipe "
    "or in LESSONS.md, and have push runs read it rather than "
    "re-derive it; (ii) drop the search, rely on the source-proven "
    "identity mapping plus the new residency gate, and keep the eight-way "
    "scoring only as a diagnostic printout; (iii) keep the search but "
    "gate the encoding on the content-independent R range from D3 and "
    "require --expect-change to skip the orientation decisiveness test "
    "with an explicit recorded mapping. The auditor did NOT implement any "
    "of these: picking one changes what the script is allowed to write "
    "terrain on the strength of, and conduct rule 8 says a rewrite does "
    "not retire a design-level BLOCK — sign-off does.",
)
RESOLVED_BLOCKS = (
    "D1 — THE POST-PUSH TOLERANCE WIDENS ITSELF IN PROPORTION TO THE "
    "CHANGE BEING MADE. The tolerance is set from the PRE-flight residual: "
    "tol = max(4 * unit_cm, med * 3 + unit_cm), with a refusal only above "
    "med > 50 height units, so it can legitimately reach 151 height units "
    "(590 cm) and still 'pass'. The docstring calls that residual the "
    "instrument's own error, but it is only that when the live terrain "
    "ALREADY equals the source. On the script's stated purpose — pushing a "
    "CHANGED heightmap — the residual measures the size of the intended "
    "edit, so the acceptance band grows with the edit. Concretely: an fp16 "
    "intermediate terraces the terrain in 32-height-unit steps, and a "
    "151-unit tolerance accepts that silently. The tolerance is the last "
    "line of defence against terracing, and it is the one thing that "
    "loosens exactly when the terrain is changing most. Recommendation: "
    "stop deriving the tolerance from the pre-flight at all. Post-push the "
    "expected agreement is the same whatever the terrain was before, so "
    "make the budget FIXED and recipe-declared (a new "
    "`heightmap.push_tolerance_units`, default 4), and use the pre-flight "
    "only to CLASSIFY: residual <= budget means the terrain already "
    "matches the source and the instrument is proven adequate; residual > "
    "budget means the push will CHANGE the terrain and the pre-flight "
    "cannot separate instrument error from real difference — require an "
    "explicit --expect-change and do NOT widen the budget. Needs Ryan: it "
    "adds a recipe field (schema bump) and a CLI flag.",

    "D2 — THE PUSH WRITES ON ARGUMENT, NOT ON EVIDENCE: NOTHING MEASURES "
    "THE RENDER TARGET BEFORE THE IRREVERSIBLE WRITE. Between the PNG on "
    "disk and the import call sit four stages that can each fail silently "
    "into a plausible flat or terraced terrain, and none of them is "
    "measured: (i) texture platform data is built ASYNCHRONOUSLY after "
    "post_edit_change(), and a texture still compiling samples as a "
    "placeholder, which would push a FLAT terrain; (ii) "
    "MaterialEditingLibrary.RecompileMaterial appears to return void, so "
    "`compile_errors` is almost certainly always empty and a material that "
    "failed to compile would draw as the default material; (iii) the MD_UI "
    "domain, SAMPLERTYPE_LINEAR_COLOR and TextureCoordinate(0) 1:1 mapping "
    "are all argued from source but never observed; (iv) the platform "
    "pixel format is unreachable from Python, so the precision chain rests "
    "on the TC_HDR_F32 -> RGBA32F invariant rather than on a reading. ONE "
    "check closes all four: read texels back OUT of the drawn render "
    "target and compare them against the PNG's exact uint16 values BEFORE "
    "calling landscape_import_heightmap_from_render_target, refusing "
    "unless every sample matches within 0.5. The call is "
    "ReadRenderTargetRawPixel (KismetRenderingLibrary.h:174). BEFORE "
    "USING IT, resolve at source what bNormalize does to a "
    "PF_A32B32G32R32F read: KismetRenderingLibrary.cpp:328 selects "
    "`bNormalize ? FReadSurfaceDataFlags() : FReadSurfaceDataFlags("
    "RCM_MinMax)`, and RCM_MinMax RESCALES by min/max, which would destroy "
    "absolute height values. Confirm that the default (RCM_UNorm) path "
    "through ReadLinearColorPixels neither rescales nor clamps a float "
    "render target. The auditor did not implement this: adding an "
    "unverified readback stage to the highest-stakes script is the same "
    "mistake in a different place. Needs Ryan: it adds a stage and a "
    "refusal to the contract.",
)

# Scratch assets live under /Game/Debug/ so nothing this script creates can
# be mistaken for a pipeline deliverable.
HEIGHT_TEX = "/Game/Debug/T_PushHeight_Source"
PUSH_MATERIAL = "/Game/Debug/M_PushHeight"

# The texture settings that must read back exactly as set before anything
# is drawn. TC_HDR_F32 is RGBA32F (TextureDefines.h:409); TC_HDR would be
# RGBA16F (:399) and would terrace the terrain in 32-height-unit steps.
# There is deliberately no pixel-format gate: UTexture2D exposes no
# reflected pixel format (Texture2D.h:161 is not a UFUNCTION), so such a
# gate could only ever refuse.
REQUIRED_TEXTURE_SETTINGS = {
    "srgb": False,
    "compression_settings": "TC_HDR_F32",
    "mip_gen_settings": "TMGS_NO_MIPMAPS",
    "filter": "TF_NEAREST",
    "address_x": "TA_CLAMP",
    "address_y": "TA_CLAMP",
}

# UE's LANDSCAPE_ZSCALE. world_z = actor_z + (v - 32768) * scale_z / 128.
LANDSCAPE_ZSCALE_DIVISOR = 128.0
HEIGHT_DATUM = 32768

DEFAULT_SAMPLE_GRID = 17          # 17x17 = 289 interior points
EDGE_MARGIN_TEXELS = 8            # keep clear of the border

# A trace that hit anything else is not a height reading.
LANDSCAPE_CLASSES = ("Landscape", "LandscapeStreamingProxy")

# The orientation winner must beat the runner-up on BOTH counts, or the
# measurement is treated as degenerate and the run refuses. On a terrain
# that is not symmetric the correct mapping wins by orders of magnitude;
# a near-tie means every mapping is measuring the same thing, which is
# what a flat sample region or a collapsed trace set looks like.
ORIENTATION_MARGIN_RATIO = 8.0
ORIENTATION_MARGIN_UNITS = 20.0

# Post-push agreement budget, in HEIGHT UNITS (1 unit = scale_z/128 cm;
# 3.90625 cm for the alpine recipe).
#
# FIXED ON PURPOSE — this replaces a derived tolerance, and the derivation
# was the defect (audit finding D1, 2026-08-01). It was
# `max(4*unit, med*3 + unit)` where `med` is the PRE-flight residual. That
# residual is instrument error ONLY when the live terrain already equals
# the source; on this script's actual purpose — pushing a CHANGED
# heightmap — it measures the size of the intended edit, so the acceptance
# band grew with the edit and could legitimately reach 151 units (590 cm).
# An fp16 intermediate terraces in 32-unit steps, and a 151-unit budget
# swallows that in silence. A verification threshold that widens when the
# thing it verifies changes most is not a threshold.
#
# Post-push, expected agreement is the same whatever the terrain was
# before, so the budget is a constant. The pre-flight now only CLASSIFIES:
# residual <= budget means the terrain already matches the source and the
# trace instrument is proven adequate to this tolerance; residual > budget
# means this push will CHANGE the terrain, the pre-flight cannot separate
# instrument error from real difference, and `--expect-change` must be
# passed explicitly. The budget is never widened either way.
#
# SCHEMA v1.5: `heightmap.push_tolerance_units` may TIGHTEN this, never
# widen it. Ryan ruled 2026-08-01 that hard rule 2 ("every scene
# parameter comes from recipe JSON") does NOT bind verification
# thresholds — this is a property of the measuring instrument, not of
# the scene — so the recipe does not own it outright.
#
# The one-way clamp is not fussiness. Audit finding D1 was a SELF-
# WIDENING TOLERANCE: a check that relaxes its own threshold until it
# passes has stopped being a check. Making the budget recipe-settable
# without a ceiling re-creates that defect with an extra step, because
# the recipe is edited by whoever wants the push to succeed. Tightening
# is always safe: it can only cause a refusal that would otherwise have
# been a pass.
TOLERANCE_UNITS = 4


def tolerance_units(recipe):
    """Effective tolerance in height units — recipe may tighten only.

    UNUSED as of 2026-09-17: main() reads the module constant TOLERANCE_UNITS
    directly, so the recipe-tighten path this implements is NOT currently
    wired. Kept because SCHEMA v1.5 still documents the field; wiring it (one
    `eff_tol, warn = tolerance_units(recipe)` at the top of main, threaded to
    the tol sites) is a safe no-op for every current recipe — none set
    push_tolerance_units.
    """
    hm = (recipe or {}).get("heightmap") or {}
    want = hm.get("push_tolerance_units")
    if want is None:
        return TOLERANCE_UNITS, None
    if not isinstance(want, int) or isinstance(want, bool) or want < 1:
        return TOLERANCE_UNITS, (
            "heightmap.push_tolerance_units must be an integer >= 1; got "
            "{0!r}. Using the built-in {1}.".format(want, TOLERANCE_UNITS))
    if want > TOLERANCE_UNITS:
        return TOLERANCE_UNITS, (
            "heightmap.push_tolerance_units {0} would WIDEN the budget "
            "past the built-in {1}. Refusing to widen — a check that "
            "relaxes its own threshold until it passes is not a check "
            "(audit finding D1). Using {1}.".format(want, TOLERANCE_UNITS))
    return want, None

# Side of each square block of render-target texels read back before the
# import (audit D2). A 3x3 grid of blocks of this size is sampled.
RT_BLOCK = 16

# Encoding gate. If the best mapping still disagrees with the source by
# more than this, R * 65535 is not the export's encoding and the script
# refuses rather than fitting a scale/offset to whatever came back —
# fitting would calibrate the instrument on the data it exists to check.
ENCODING_MAX_UNITS = 4.0

# Explicit flat-result check. A flat terrain is the most likely silent
# failure of the whole route, and a flat landscape is a perfectly valid
# landscape that nothing downstream flags. Compared against the SOURCE's
# own relief so the check cannot pass by measuring nothing.
FLAT_MIN_SPREAD_UNITS = 50.0
FLAT_MIN_SPREAD_FRACTION = 0.5

# Extent gate. Fraction of a sampled block's vertices that must match the
# source for that block to count as populated. Deliberately high: the
# failure being caught is a whole region of the render target never being
# drawn, which reads as 0/256, not as a near miss.
EXTENT_MIN_FRACTION = 0.9

# How far the engine's export can be trusted, per axis. MEASURED, not
# assumed (--probe-size, 2026-08-01): the export reproduces vertices
# 0..1008 correctly and then TILES that block across the rest of the
# target — RT(x, y) == arr[y mod 1008, x mod 1008], confirmed on 17 of 19
# diagonal samples with the two exceptions being the tile edges. 1009 =
# 16*63 + 1, i.e. 16x16 of the terrain's 32x32 components.
#
# So the export is demoted to a "the write landed" check inside this
# region. The AUTHORITY is the pre-import render-target readback, which
# reads the buffer this script drew and is valid everywhere.
EXPORT_TRUSTED_MAX = 1008

# Texel -> vertex mapping used when a push CHANGES the terrain and the
# orientation therefore cannot be derived from a pre-flight (audit D4).
#
# MEASURED, not assumed: with the terrain equal to the source, `identity`
# scored a median |dv| of 0.000 height units over 1280 vertices while the
# next-best mapping scored 394 — a separation of orders of magnitude, on
# terrain that is not symmetric. It is also the mapping the engine's own
# layout implies, since the export draws each subsection at
# `SectionBase - ExportBaseOffset` (LandscapeEdit.cpp:8221-8265).
#
# Using it on a changed push is NOT trusting an assumption: the post-push
# export check re-derives agreement against the NEW source, so a wrong
# orientation fails there and fails loudly (exit 5, do not save). What
# this constant buys is a sane default to check AGAINST, not permission to
# skip checking.
DEFAULT_ORIENTATION = "identity"

# The landscape applies an imported heightmap DEFERRED, so an export taken
# immediately after the import can still read the pre-push terrain — seen
# on the first changed push, where all 1280 sampled vertices came back
# ~16000 height units out and a re-read moments later matched exactly.
# Poll rather than sleep a fixed amount: the attempt count is reported, so
# if it ever rises that is information rather than a silent slow path.
VERIFY_MAX_ATTEMPTS = 6
VERIFY_RETRY_DELAY_S = 2.0


# --------------------------------------------------------------------
# Texel -> world mappings. Deliberately enumerated rather than assumed:
# picking the wrong one writes a MIRRORED terrain that looks completely
# plausible. All EIGHT symmetries of the square are scored against the
# live terrain — enumerating a subset would leave the unenumerated ones
# reachable only as "best of the wrong ones".
# --------------------------------------------------------------------
# =====================================================================
# EXPORT PROBE — diagnostic only. Writes nothing, imports nothing.
# =====================================================================
# The export returned an all-zero render target while doing 4.14 s of real
# work and logging no warning. This walks the matrix that separates the
# three candidate causes in ONE editor round trip, because each round trip
# is another conduct-rule-6 attempt:
#   * the flag (False vs True) — per the material graph these route to the
#     SAME texture-sample node, so a DIFFERENCE here means the graph
#     reading is wrong, which is worth more than the probe itself;
#   * the target format (RTF_RGBA32F vs RTF_RGBA8) — separates "the draw
#     produced nothing" from "the fp32 target cannot be read back";
#   * the read normalisation (False vs True) — separates the draw from the
#     READ, since bNormalize=True clamps into [0,1] and would show
#     non-zero if the buffer held large values.
# Both channels are reported because at probe time the encoding was still
# unknown: under flag-False R turned out to carry the RAW uint16 (R == G),
# not a high byte — reporting G alongside R is what settled that.
PROBE_SOURCE = '''
import json as _json
import unreal as _unreal

_res = int({res!r})
_x0 = int({x0!r})
_y0 = int({y0!r})
_n = int({n!r})

_out = {{"ok": False, "runs": [], "stage": "start"}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()


def _resolve(_obj, _cands, _hint):
    for _nm in _cands:
        _f = getattr(_obj, _nm, None)
        if _f is not None:
            return _f, _nm
    raise AttributeError("none of %r; present: %r" % (
        list(_cands), sorted(_a for _a in dir(_obj) if _hint in _a)))


try:
    _mk, _mk_name = _resolve(
        _unreal.RenderingLibrary,
        ("create_render_target2_d", "create_render_target_2d",
         "create_render_target2d"), "render_target")
    _rd, _rd_name = _resolve(
        _unreal.RenderingLibrary,
        ("read_render_target_raw_pixel_area",), "read_render_target")
    _out["create_fn"] = _mk_name
    _out["read_fn"] = _rd_name

    _land = None
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _land = _a
        break
    if _land is None:
        _out["error"] = "no Landscape actor in this world"
    else:
        _out["landscape"] = _land.get_actor_label()
        _fmts = [("RGBA32F",
                  _unreal.TextureRenderTargetFormat.RTF_RGBA32F),
                 ("RGBA8", _unreal.TextureRenderTargetFormat.RTF_RGBA8)]
        for _fname, _fmt in _fmts:
            for _flag in (False, True):
                _rec = {{"format": _fname, "flag": _flag}}
                try:
                    _rt = _mk(_world, _res, _res, _fmt,
                              _unreal.LinearColor(0.0, 0.0, 0.0, 1.0),
                              False, False)
                    _rec["rt"] = [_rt.size_x, _rt.size_y] if _rt else None
                    _rec["exported"] = bool(
                        _land.landscape_export_heightmap_to_render_target(
                            _rt, _flag, True))
                    for _norm in (False, True):
                        _vals = _rd(_world, _rt, _x0, _y0, _n, _n, _norm)
                        _rs = [float(_c.r) for _c in (_vals or [])]
                        _gs = [float(_c.g) for _c in (_vals or [])]
                        _rec["norm_%s" % _norm] = {{
                            "count": len(_rs),
                            "r": [min(_rs), max(_rs)] if _rs else None,
                            "g": [min(_gs), max(_gs)] if _gs else None,
                            "first4": [[round(_rs[_i], 6), round(_gs[_i], 6)]
                                       for _i in range(min(4, len(_rs)))],
                        }}
                except Exception as _exc:
                    _rec["error"] = "%s: %s" % (type(_exc).__name__, _exc)
                _out["runs"].append(_rec)
        _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''

# =====================================================================
# LAYOUT PROBE — diagnostic only. Writes nothing, imports nothing.
# =====================================================================
# The encoding is settled (raw R). What is not settled is WHERE in the
# returned array a given texel lives. Measured evidence: a read at
# (1008,1008) returned element 0 == the PNG value at (1008,1008) but
# elements 1..3 == the PNG values at (1,1008), (2,1008), (3,1008).
#
# Two candidate readings of ReadRenderTargetRawPixelArea's last two
# arguments are in play, and the audit already flipped between them on a
# source trace that measurement has since contradicted:
#     A: (MinX, MinY, Width,  Height)
#     B: (MinX, MinY, MaxX,   MaxY)
# So this probe stops arguing and runs BOTH, at two different origins,
# and hands back the raw values for offline matching against the PNG.
# One export, several reads — the export is the slow part and warming it
# once also avoids the cold-first-export artefact seen earlier.
#
# A per-pixel control is included where available: if the area read and
# the single-pixel read disagree about the same coordinate, the area
# call's arguments are the problem; if they agree, the layout is.
LAYOUT_SOURCE = '''
import json as _json
import unreal as _unreal

_res = int({res!r})
_spots = {spots!r}
_n = int({n!r})

_out = {{"ok": False, "reads": [], "points": []}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()


def _resolve(_obj, _cands, _hint):
    for _nm in _cands:
        _f = getattr(_obj, _nm, None)
        if _f is not None:
            return _f, _nm
    raise AttributeError("none of %r; present: %r" % (
        list(_cands), sorted(_a for _a in dir(_obj) if _hint in _a)))


try:
    _mk, _ = _resolve(_unreal.RenderingLibrary,
                      ("create_render_target2_d", "create_render_target_2d",
                       "create_render_target2d"), "render_target")
    _rd, _ = _resolve(_unreal.RenderingLibrary,
                      ("read_render_target_raw_pixel_area",),
                      "read_render_target")
    _px, _px_name = None, None
    try:
        _px, _px_name = _resolve(_unreal.RenderingLibrary,
                                 ("read_render_target_raw_pixel",),
                                 "read_render_target")
    except Exception:
        pass
    _out["pixel_fn"] = _px_name

    _land = None
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _land = _a
        break
    _rt = _mk(_world, _res, _res,
              _unreal.TextureRenderTargetFormat.RTF_RGBA32F,
              _unreal.LinearColor(0.0, 0.0, 0.0, 1.0), False, False)
    # Export TWICE: the first export after an idle editor has been observed
    # to come back all zero. The second is the one that is read.
    _land.landscape_export_heightmap_to_render_target(_rt, False, True)
    _out["exported"] = bool(
        _land.landscape_export_heightmap_to_render_target(_rt, False, True))

    for (_x0, _y0) in _spots:
        for _label, _a3, _a4 in (
                ("A_width_height", _n, _n),
                ("B_max_coords", _x0 + _n - 1, _y0 + _n - 1)):
            try:
                _vals = _rd(_world, _rt, _x0, _y0, _a3, _a4, False)
                _out["reads"].append({{
                    "spot": [_x0, _y0], "interp": _label,
                    "args": [_x0, _y0, _a3, _a4],
                    "count": len(_vals or []),
                    "r": [float(_c.r) for _c in (_vals or [])][:40],
                }})
            except Exception as _exc:
                _out["reads"].append({{
                    "spot": [_x0, _y0], "interp": _label,
                    "error": "%s: %s" % (type(_exc).__name__, _exc)}})
        # Per-pixel control at the same origin and at origin+1 in x.
        if _px is not None:
            for _dx in (0, 1, 2):
                try:
                    _c = _px(_world, _rt, _x0 + _dx, _y0, False)
                    _out["points"].append(
                        [_x0 + _dx, _y0, float(_c.r)])
                except Exception as _exc:
                    _out["points"].append(
                        [_x0 + _dx, _y0,
                         "%s: %s" % (type(_exc).__name__, _exc)])
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''

# =====================================================================
# SIZE PROBE — diagnostic only. Discriminates BATCHING from EXTENT.
# =====================================================================
# The export populates 1009 of 2017 texels per axis. 1009 is exactly
# (2017 + 1) / 2, which is ambiguous between two very different causes:
#
#   EXTENT   — the canvas rasterises only half the target, whatever its
#              size. Then a 1009 target would fill only ~505 per axis,
#              because the covered region scales WITH the target.
#   BATCHING — only some components/heightmap-texture batches are drawn,
#              covering an ABSOLUTE region of ~1009 vertices regardless of
#              target size. Then a 1009 target fills COMPLETELY, and a
#              LARGER target still covers only ~1009.
#
# So the two predictions differ, and one run settles it: export into
# 1009, 2017 and 3025 and report where the data stops on each. A third,
# larger size is included because 1009-vs-2017 alone cannot tell an
# absolute 1009 from "half of 2017" if the smaller run happens to fill.
#
# Coverage is measured by walking outward along the diagonal and asking
# where values stop being non-trivial, then the host confirms against the
# source heightmap. Both are reported: "the engine wrote something" and
# "it wrote the RIGHT something" are different claims.
SIZE_PROBE_SOURCE = '''
import json as _json
import unreal as _unreal

_sizes = {sizes!r}
_probe_at = {probe_at!r}

_out = {{"ok": False, "runs": []}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()


def _resolve(_obj, _cands, _hint):
    for _nm in _cands:
        _f = getattr(_obj, _nm, None)
        if _f is not None:
            return _f, _nm
    raise AttributeError("none of %r; present: %r" % (
        list(_cands), sorted(_a for _a in dir(_obj) if _hint in _a)))


try:
    _mk, _ = _resolve(_unreal.RenderingLibrary,
                      ("create_render_target2_d", "create_render_target_2d",
                       "create_render_target2d"), "render_target")
    _px, _ = _resolve(_unreal.RenderingLibrary,
                      ("read_render_target_raw_pixel",), "read_render_target")

    _land = None
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _land = _a
        break

    for _size in _sizes:
        _rec = {{"size": _size}}
        try:
            _rt = _mk(_world, _size, _size,
                      _unreal.TextureRenderTargetFormat.RTF_RGBA32F,
                      _unreal.LinearColor(0.0, 0.0, 0.0, 1.0), False, False)
            _rec["rt"] = [_rt.size_x, _rt.size_y]
            # Export twice: a cold first export has been seen to return an
            # all-zero target.
            _land.landscape_export_heightmap_to_render_target(_rt, False, True)
            _rec["exported"] = bool(
                _land.landscape_export_heightmap_to_render_target(
                    _rt, False, True))
            # Diagonal walk: last index whose value is non-trivial.
            _last = -1
            _samples = []
            for _i in _probe_at:
                if _i >= _size:
                    continue
                _v = float(_px(_world, _rt, _i, _i, False).r)
                _samples.append([_i, _v])
                if _v > 1.0:
                    _last = _i
            _rec["diag"] = _samples
            _rec["last_nontrivial_diag"] = _last
        except Exception as _exc:
            _rec["error"] = "%s: %s" % (type(_exc).__name__, _exc)
        _out["runs"].append(_rec)
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''

# =====================================================================
# EDIT-LAYER PROBE — diagnostic only. Read-only.
# =====================================================================
# Since 5.7 every landscape uses the edit-layer system, and the push
# targets index 0 (LandscapeProxy.h:1572, third argument). The rendered
# surface is the COMPOSITE of all edit layers, so a landscape carrying
# more than one would not read back as the source even after a perfectly
# correct push — and we would learn that only after writing terrain.
# `GetEditLayersBP` is UFUNCTION(BlueprintCallable, DisplayName =
# GetEditLayers) at Landscape.h:394-395, so the reflected name derives
# from the DISPLAY name, not the C++ one.
LAYER_PROBE_SOURCE = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "landscapes": []}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()
try:
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _rec = {{"label": _a.get_actor_label()}}
        _fn = None
        for _nm in ("get_edit_layers", "get_edit_layers_bp"):
            _fn = getattr(_a, _nm, None)
            if _fn is not None:
                _rec["fn"] = _nm
                break
        if _fn is None:
            _rec["error"] = ("no edit-layer accessor; present: %r"
                             % sorted(_x for _x in dir(_a)
                                      if "layer" in _x.lower()))
        else:
            _layers = list(_fn() or [])
            _rec["count"] = len(_layers)
            _names = []
            for _l in _layers:
                try:
                    _names.append(str(_l.get_name()))
                except Exception:
                    _names.append("<unnamed>")
            _rec["names"] = _names
        _out["landscapes"].append(_rec)
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''

def decode_export(rec):
    """Heightmap value from one exported render-target texel.

    THE ENCODING, ESTABLISHED BY MEASUREMENT (--probe-export, 2026-08-01),
    after a reading of the engine material's graph got it WRONG.

    With `bInExportHeightIntoRGChannel = False` — what this script passes —
    the render target's R channel carries the **RAW uint16 height**,
    broadcast to RGB (R == G). Measured over an 8x8 block at the terrain
    centre in an RTF_RGBA32F target read with bNormalize=False:

        R range 140.0 .. 44883.0,  first texels [44883, 44883], [35192,
        35192], ... — R and G identical.

    Cross-validated against the OTHER branch rather than trusted alone:
    with the flag True the same texel reads R=0.686275, G=0.325490, i.e.
    bytes 175 and 83, and 175*256 + 83 = 44883 — exactly the raw value the
    flag-False path reports. Two independent encodings agreeing on the same
    number is what makes this decode safe to rely on.

    So the flag does exactly what its NAME says, and the export is
    symmetric with the import — which reads `(uint16)LinearColor.R`
    (LandscapeEdit.cpp:8138).

    WHAT I GOT WRONG, recorded because the method failed, not just the
    answer: I read the material's If node via MaterialTools and concluded
    that the `A > B` and `A == B` inputs were the same TextureSample node,
    therefore that the flag changed nothing and the output was always the
    texture's byte split. The measurement contradicts that flatly. Reading
    a node graph through an introspection API is NOT the same as reading
    source, and I presented it with more confidence than it earned. The
    probe matrix — vary one input at a time and watch the output — settled
    in one run what two rounds of inference could not.
    """
    return float(rec[0])


def texel_to_vertex(mapping, col, row, res):
    """Landscape VERTEX index (gx, gy) for a heightmap texel.

    The export render target is laid out on the landscape grid — the
    engine draws each subsection at `SectionBase - ExportBaseOffset`
    (LandscapeEdit.cpp:8222-8265) — so RT texel (gx, gy) IS landscape
    vertex (gx, gy). That makes the texel->vertex mapping the whole of the
    orientation question, with no world-space arithmetic in between.
    """
    last = res - 1
    if mapping == "identity":
        gx, gy = col, row
    elif mapping == "flip_col":
        gx, gy = (last - col), row
    elif mapping == "flip_row":
        gx, gy = col, (last - row)
    elif mapping == "flip_both":
        gx, gy = (last - col), (last - row)
    elif mapping == "transpose":
        gx, gy = row, col
    elif mapping == "transpose_flip_row":
        gx, gy = row, (last - col)
    elif mapping == "transpose_flip_col":
        gx, gy = (last - row), col
    elif mapping == "transpose_flip_both":
        gx, gy = (last - row), (last - col)
    else:
        raise ValueError("unknown mapping {0!r}".format(mapping))
    return gx, gy


def texel_to_world(mapping, col, row, res, ox, oy, sxy):
    """World XY (cm) for a heightmap texel under `mapping`."""
    gx, gy = texel_to_vertex(mapping, col, row, res)
    return ox + gx * sxy, oy + gy * sxy


MAPPINGS = ("identity", "flip_col", "flip_row", "flip_both",
            "transpose", "transpose_flip_row", "transpose_flip_col",
            "transpose_flip_both")


def expected_world_z(value, actor_z, scale_z):
    return actor_z + (float(value) - HEIGHT_DATUM) * scale_z / \
        LANDSCAPE_ZSCALE_DIVISOR


IDENTIFY_SOURCE = '''
import json as _json
import unreal as _unreal

_res = int({res!r})
_spacing = int({spacing!r})
_scale_xy = float({scale_xy!r})
_scale_z = float({scale_z!r})
_loc = {loc!r}

_out = {{"ok": False, "candidates": [], "matched": None}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

# Identify BY PROPERTY SIGNATURE, never by label. Labels collide and this
# write is irreversible.
_proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.LandscapeStreamingProxy))


# Proxy -> owning landscape. The property is `LandscapeActorRef`
# (LandscapeStreamingProxy.h:35-36), NOT `LandscapeActor`: the latter is
# `LandscapeActor_DEPRECATED` at :29-30. The trap is that LandscapeActorRef
# carries Meta = (DisplayName = "Landscape Actor"), so the editor UI, the
# details panel and every screenshot call it "Landscape Actor" while the
# reflected name is landscape_actor_ref. Reading the display name cost this
# script its first live run.
#
# It is a TSoftObjectPtr, so comparison goes through the same idiom
# the verify_landscape module has proven live, GUID as fallback.
# LESSON 9: an unreadable ref is recorded as UNKNOWN, never silently
# treated as "not mine" — quietly dropping a proxy would shrink the
# component set and could make a correct landscape fail its own signature.
def _owns(_p, _a):
    try:
        _ref = _p.get_editor_property("landscape_actor_ref")
        if _ref is not None:
            return bool(_ref == _a)
    except Exception as _exc:
        _unreadable.append("landscape_actor_ref: %s: %s"
                           % (type(_exc).__name__, _exc))
        return False
    try:
        _g = _a.get_editor_property("landscape_guid")
        return bool(_p.get_editor_property("landscape_guid") == _g)
    except Exception as _exc:
        _unreadable.append("landscape_guid: %s: %s"
                           % (type(_exc).__name__, _exc))
        return False

_matches = []
for _a in _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape):
    _t = _a.get_actor_transform()
    _s, _l = _t.scale3d, _t.translation
    _bx = set()
    _unreadable = []
    _mine = [_a] + [_p for _p in _proxies if _owns(_p, _a)]
    _ncomp = 0
    for _p in _mine:
        _cs = _p.get_components_by_class(_unreal.LandscapeComponent)
        _ncomp += len(_cs)
        for _c in _cs:
            # LESSON 9: a negative result from an API probe must be
            # distinguishable from a FAILED probe. Swallowing this left
            # _bx empty, which makes _implied None, which fails the
            # signature match — and the run would then report "no
            # landscape matched the recipe signature" when the truth is
            # "I could not read section_base_x". Same words, opposite
            # meaning, on the gate of a script that writes terrain.
            try:
                _bx.add(int(_c.get_editor_property("section_base_x")))
            except Exception as _exc:
                _unreadable.append("%s: %s" % (type(_exc).__name__, _exc))
    _sx = sorted(_bx)
    _step = (_sx[1] - _sx[0]) if len(_sx) > 1 else None
    _implied = (max(_sx) + _step + 1) if (_sx and _step) else None
    _row = {{"label": _a.get_actor_label(),
            "scale": [_s.x, _s.y, _s.z],
            "location": [_l.x, _l.y, _l.z],
            "step": _step, "implied_resolution": _implied,
            "components": _ncomp,
            "unreadable": len(_unreadable),
            "unreadable_first": _unreadable[0] if _unreadable else None}}
    _ok = (not _unreadable
           and _implied == _res and _step == _spacing
           and abs(_s.x - _scale_xy) < 1e-4 and abs(_s.y - _scale_xy) < 1e-4
           and abs(_s.z - _scale_z) < 1e-4
           and abs(_l.x - _loc[0]) < 0.5 and abs(_l.y - _loc[1]) < 0.5
           and abs(_l.z - _loc[2]) < 0.5)
    _row["signature_match"] = _ok
    _out["candidates"].append(_row)
    if _ok:
        _matches.append(_a)

_blind = [_r for _r in _out["candidates"] if _r["unreadable"]]
if _blind:
    # LESSON 9. "I could not read section_base_x" is NOT "nothing
    # matched". Reported as its own condition so the operator is never
    # told the landscape is absent when the probe is what failed.
    _out["error"] = (
        "%d landscape(s) had unreadable section_base_x on %d component(s) "
        "— the signature could not be COMPUTED, which is not the same as "
        "not matching. First failure: %s"
        % (len(_blind), sum(_r["unreadable"] for _r in _blind),
           _blind[0]["unreadable_first"]))
    _out["blind"] = True
elif len(_matches) == 1:
    _out["matched"] = _matches[0].get_actor_label()
    _out["ok"] = True
else:
    _out["error"] = ("expected exactly one landscape matching the recipe "
                     "signature, found %d" % len(_matches))

print("{marker}" + _json.dumps(_out))
'''


# =====================================================================
# EXPORT READ-BACK — replaces the line-trace instrument entirely.
# =====================================================================
# WHY THE TRACES WENT. They ran, but their RESULT is unreadable from
# Python: every field of FHitResult is a bare UPROPERTY() with no
# BlueprintReadOnly and no EditAnywhere (HitResult.h:100-140), which this
# project already knows means "unreadable from Python — plan a
# derivation"; the editor refuses them as protected. The engine's intended
# accessor, UGameplayStatics::BreakHitResult, is
# UFUNCTION(BlueprintPure, meta=(NativeBreakFunc)) (GameplayStatics.h:1077)
# and the Python plugin does not expose NativeBreakFunc helpers. And
# GetHeightAtLocation (LandscapeProxy.h:1101) is LANDSCAPE_API, not
# BlueprintCallable. All three routes closed.
#
# WHAT REPLACES THEM, and why it is better rather than merely different.
# LandscapeExportHeightmapToRenderTarget IS BlueprintCallable
# (LandscapeProxy.h:1258-1259). Reading its output:
#   * reads the HEIGHTFIELD, not the collision proxy — so the "collision
#     may be built at a lower mip" worry disappears, and with it the whole
#     self-calibrating-tolerance machinery that existed to accommodate it;
#   * reuses the RCM_MinMax read path already source-verified for the
#     pre-import check, rather than adding a second unproven instrument;
#   * reads WHOLE BLOCKS of adjacent texels, so the orientation search is
#     an exact comparison over hundreds of vertices rather than an
#     argument about sampling.
#
# LAYOUT, read at source. The engine clears the canvas to black and draws
# each subsection as two UV triangles positioned at
# `SectionBase - ExportBaseOffset` (LandscapeEdit.cpp:8221-8265), so RT
# texel (gx, gy) is landscape vertex (gx, gy) with the origin at the
# minimum component extent. InExportLandscapeProxies=True is required
# here: our 1024 components live on 256 streaming proxies, and with it
# false only the parent actor's own components would be drawn
# (:8194-8208).
#
# ENCODING — STATED AS A HYPOTHESIS, AND THE ENGINE SOURCE ARGUES AGAINST
# IT. The values come from a MATERIAL, not a memcpy:
# /Engine/EditorLandscapeResources/Landscape_Heightmap_To_RenderTarget2D,
# with a scalar parameter ExportHeightIntoRGChannel set from the flag
# (LandscapeEdit.cpp:8247). We pass False. The code below assumes the
# height arrives NORMALISED in R — that R * 65535 == the heightmap value.
#
# READ THE COUNTER-EVIDENCE BEFORE TRUSTING THAT. The mirror-image import
# path, in this same file, does
#     HeightData.Add((uint16)LinearColor.R);      (LandscapeEdit.cpp:8138)
# with the SAME flag false — i.e. on import R carries the RAW 0..65535
# value, not a normalised one, which is exactly why this script's own push
# material emits `v * 65535 + 0.5` (see PUSH_SOURCE step 4). Export and
# import are the two halves of one round trip through one flag, so the
# straightforward reading is that the export also writes the RAW value
# into R and that `R * 65535` is 65535x too large. The material is a
# .uasset and cannot be read from here, so this is not settled — but the
# burden of proof is against the hypothesis, not for it.
#
# THE HYPOTHESIS IS TESTED, NEVER FITTED: the pre-flight checks it and
# REFUSES (ENCODING_MAX_UNITS) rather than fitting a scale/offset to
# whatever came back, which would calibrate the instrument on the very
# data it exists to check. `r_min`/`r_max` are reported so ONE live run
# settles it: R in [0,1] means normalised, R in [0,65535] means raw.
#
# WHAT THE RETURN VALUE IS WORTH: nothing. LandscapeExportHeightmapToRender
# Target returns true on every path except "engine material not found"
# (:8188-8192) — including the zero-components early-out at :8210-8213,
# which returns true having drawn nothing at all. `export_returned` is
# reported as a fact, never treated as evidence.
#
# RESIDENCY IS PART OF THE LAYOUT, NOT A SEPARATE WORRY. The engine draws
# each subsection at `SectionBase - ExportBaseOffset` (:8261) where
# `ExportBaseOffset = ComponentsExtent.Min` (:8228) accumulated by
# GetComponentExtent (:2876-2882) over the components it actually
# exported — and it exports only the proxies ULandscapeInfo currently
# holds (:8199-8208), i.e. only the LOADED ones. So "RT texel (gx,gy) IS
# vertex (gx,gy)" is true ONLY when the minimum section base over the
# whole resident set is (0,0) and the set is complete. Under World
# Partition that is exactly the thing that is silently false. It is
# therefore MEASURED below and refused, not assumed.
EXPORT_SOURCE = '''
import json as _json
import unreal as _unreal

# Reflected-name resolution, with the failure carrying its own fix.
#
# Three live runs have now been lost to invented or mis-cased reflected
# names (landscape_actor, landscape_components, create_render_target2_d).
# The engine derives Python names from C++ identifiers by a rule that is
# NOT reliably guessable around digits — CreateRenderTarget2D could
# pythonize as create_render_target2_d, create_render_target_2d or
# create_render_target2d, and no header, generated stub or engine
# Python file in this install answers it.
#
# So: try the candidates, and if none resolves, REPORT EVERY MATCHING
# ATTRIBUTE THE OBJECT ACTUALLY HAS. That turns "wrong name" from a
# guess-and-retry loop into a single run that hands back the answer —
# lesson 15 (when attempts are scarce, spend one read verifying
# everything) enforced in code rather than in intent.
def _resolve(_obj, _candidates, _hint):
    for _n in _candidates:
        _f = getattr(_obj, _n, None)
        if _f is not None:
            return _f, _n
    _have = sorted(_a for _a in dir(_obj)
                   if _hint in _a and not _a.startswith("_"))
    raise AttributeError(
        "none of %r exists on %s; matching attributes present: %r"
        % (list(_candidates), getattr(_obj, "__name__", _obj), _have))



_res = int({res!r})
_spacing = int({spacing!r})
_scale_xy = float({scale_xy!r})
_scale_z = float({scale_z!r})
_loc = {loc!r}
_block = int({block!r})
_blocks = {blocks!r}
_want_components = int({ncomp!r})

_out = {{"ok": False, "values": {{}}, "stage": "start"}}
_unreadable = []


def _owns(_p, _a):
    try:
        _ref = _p.get_editor_property("landscape_actor_ref")
        if _ref is not None:
            return bool(_ref == _a)
    except Exception as _exc:
        _unreadable.append("landscape_actor_ref: %s: %s"
                           % (type(_exc).__name__, _exc))
        return False
    try:
        _g = _a.get_editor_property("landscape_guid")
        return bool(_p.get_editor_property("landscape_guid") == _g)
    except Exception as _exc:
        _unreadable.append("landscape_guid: %s: %s"
                           % (type(_exc).__name__, _exc))
        return False


def _export():
    _world = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world()
    if _world is None:
        _out["stage"] = "world"
        _out["error"] = "no editor world"
        return

    _out["stage"] = "identify"
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
    _matches = []
    _census = None
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _t = _a.get_actor_transform()
        _s, _l = _t.scale3d, _t.translation
        _bx = set()
        _by = set()
        _ncomp = 0
        for _p in [_a] + [_q for _q in _proxies if _owns(_q, _a)]:
            for _c in _p.get_components_by_class(_unreal.LandscapeComponent):
                _ncomp += 1
                # section_base_x/y are UPROPERTY(VisibleAnywhere,
                # BlueprintReadOnly) at LandscapeComponent.h:437 and :441 —
                # read at the source line, not guessed.
                try:
                    _bx.add(int(_c.get_editor_property("section_base_x")))
                    _by.add(int(_c.get_editor_property("section_base_y")))
                except Exception as _exc:
                    _unreadable.append("section_base: %s: %s"
                                       % (type(_exc).__name__, _exc))
        _sx = sorted(_bx)
        _sy = sorted(_by)
        _step = (_sx[1] - _sx[0]) if len(_sx) > 1 else None
        _implied = (max(_sx) + _step + 1) if (_sx and _step) else None
        if (_implied == _res and _step == _spacing
                and abs(_s.x - _scale_xy) < 1e-4
                and abs(_s.y - _scale_xy) < 1e-4
                and abs(_s.z - _scale_z) < 1e-4
                and abs(_l.x - _loc[0]) < 0.5 and abs(_l.y - _loc[1]) < 0.5
                and abs(_l.z - _loc[2]) < 0.5):
            _matches.append(_a)
            _census = {{"components": _ncomp,
                       "min_section_base": [_sx[0] if _sx else None,
                                            _sy[0] if _sy else None]}}

    if _unreadable:
        _out["error"] = ("a property needed for the signature was UNREADABLE "
                         "(%d), so the signature could not be COMPUTED, "
                         "which is not the same as not matching. First: %s"
                         % (len(_unreadable), _unreadable[0]))
        return
    if len(_matches) != 1:
        _out["error"] = ("expected exactly one landscape matching the recipe "
                         "signature, found %d" % len(_matches))
        return

    _land = _matches[0]
    _out["matched"] = _land.get_actor_label()
    _out["census"] = _census

    # ---- RESIDENCY / EXPORT-ORIGIN GATE -----------------------------
    # The whole "RT texel (gx,gy) IS vertex (gx,gy)" premise is
    # `SectionBase - ExportBaseOffset` with ExportBaseOffset =
    # ComponentsExtent.Min over the EXPORTED (i.e. loaded) components
    # (LandscapeEdit.cpp:8228, :8261, :2876-2882). If the minimum section
    # base is not (0,0) the whole render target is TRANSLATED and every
    # texel is read against the wrong source pixel; the eight symmetries
    # searched below do not include translations, so nothing downstream
    # would name this correctly. If the component count is short, the
    # unexported area is left at the canvas clear colour (black, :8220)
    # and reads as height 0 — a silent partial census, which is the World
    # Partition failure this project has already been bitten by.
    _out["stage"] = "residency"
    if _census["min_section_base"] != [0, 0]:
        _out["error"] = ("the minimum section base over the RESIDENT "
                         "components is %s, not [0, 0]. The engine sets "
                         "ExportBaseOffset from that minimum, so the export "
                         "would be TRANSLATED and every texel compared "
                         "against the wrong source pixel. Load the whole "
                         "landscape (all World Partition regions) and "
                         "re-run." % (_census["min_section_base"],))
        return
    if _census["components"] != _want_components:
        _out["error"] = ("%d landscape components are resident, the recipe "
                         "geometry implies %d. The export draws only the "
                         "components it can see and leaves the rest at the "
                         "canvas clear colour, which reads back as height "
                         "0 — a partial census that would look like real "
                         "terrain. Load the whole landscape and re-run."
                         % (_census["components"], _want_components))
        return

    _out["stage"] = "render_target"
    _mk_rt, _mk_rt_name = _resolve(
        _unreal.RenderingLibrary,
        ("create_render_target2_d", "create_render_target_2d",
         "create_render_target2d"), "render_target")
    _out["create_fn"] = _mk_rt_name
    _rd_rt, _rd_rt_name = _resolve(
        _unreal.RenderingLibrary,
        ("read_render_target_raw_pixel_area",
         "read_render_target_raw_pixel_area2_d"), "read_render_target")
    _out["read_fn"] = _rd_rt_name
    _rt = _mk_rt(
        _world, _res, _res,
        _unreal.TextureRenderTargetFormat.RTF_RGBA32F,
        _unreal.LinearColor(0.0, 0.0, 0.0, 1.0), False, False)
    if _rt is None or _rt.size_x < _res or _rt.size_y < _res:
        _out["error"] = "could not create a %dx%d render target" % (_res, _res)
        return

    # ---- RESIDENCY: load every landscape actor before exporting -----
    # LandscapeExportHeightmapToRenderTarget builds its component list over
    # LandscapeInfo->ForEachLandscapeProxy (LandscapeEdit.cpp:8194-8208),
    # and under World Partition that sees only what is LOADED. Measured
    # 2026-08-01: the export filled exactly one quadrant — 256 of 1024
    # components, 64 of 256 proxies — while a census in this same payload
    # counted all 1024. So actor-enumerable is NOT the same as
    # registered-for-export, and counting components does not catch it.
    #
    # This is the capture module's audited residency pattern: enumerate
    # the actor DESCRIPTORS on disk (complete regardless of what is
    # loaded) and load every landscape one before touching anything.
    _out["stage"] = "residency"
    _want_l, _want_p, _guids = 0, 0, []
    try:
        for _d in _unreal.WorldPartitionBlueprintLibrary.get_actor_descs():
            _cls = _d.get_editor_property("native_class")
            _nm = _cls.get_name() if _cls is not None else ""
            if _nm == "Landscape":
                _want_l += 1
            elif _nm == "LandscapeStreamingProxy":
                _want_p += 1
            else:
                continue
            _guids.append(_d.get_editor_property("guid"))
        if _guids:
            _unreal.WorldPartitionBlueprintLibrary.load_actors(_guids)
        _out["residency_error"] = None
    except Exception as _exc:
        _out["residency_error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _have_l = len(list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape)))
    _have_p = len(list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy)))
    _out["residency"] = {{"want": [_want_l, _want_p],
                         "have": [_have_l, _have_p]}}
    if (_out["residency_error"] is not None
            or _have_l != _want_l or _have_p != _want_p):
        _out["error"] = (
            "World Partition terrain is not fully resident: %d/%d "
            "landscapes and %d/%d proxies loaded%s. The export enumerates "
            "LOADED proxies only, so it would write a partial target."
            % (_have_l, _want_l, _have_p, _want_p,
               (" (" + str(_out["residency_error"]) + ")")
               if _out["residency_error"] else ""))
        return

    _out["stage"] = "export"
    # InExportLandscapeProxies=True: the components live on streaming
    # proxies, not on the parent actor (LandscapeEdit.cpp:8199-8208).
    # NOTE: this returns true on every path but "engine material missing"
    # (:8188-8192) and it returns true for zero components (:8210-8213),
    # so it is recorded, not believed.
    # EXPORT TWICE. MEASURED, not defensive habit: the FIRST export after
    # the editor has been restarted or left idle returns an all-zero
    # target, and every export after it returns real data (observed
    # 2026-08-01, twice — once mid-session and once immediately after the
    # restart, where the pre-flight read raw R range 0.0 .. 0.0 on a
    # landscape that renders correctly). The engine reports success both
    # times, so nothing downstream can tell the two apart except by the
    # values. The first call is treated as a warm-up whose result is
    # discarded; the second is the one that is read. Both return values
    # are recorded so a future failure can tell which call was refused.
    _warm = _land.landscape_export_heightmap_to_render_target(_rt, False, True)
    _out["export_returned_warmup"] = bool(_warm)
    _ok = _land.landscape_export_heightmap_to_render_target(_rt, False, True)
    _out["export_returned"] = bool(_ok)
    if not _ok:
        _out["error"] = "the engine refused the heightmap export"
        return

    _out["stage"] = "read"
    # ARGUMENT MEANING, READ AT THE SOURCE. The parameters the reflected
    # signature calls MaxX/MaxY are NOT maxima:
    # UKismetRenderingLibrary::ReadRenderTargetRawPixelArea
    # (KismetRenderingLibrary.cpp:454) forwards them straight into
    # ReadRenderTargetHelper's `Width` and `Height` parameters (:295-304),
    # which then builds SampleRect(X, Y, X + Width, Y + Height) (:326).
    # Passing `x0 + block - 1` therefore reads a (x0+block-1)-wide region,
    # not a block-wide one, and the row stride used to un-flatten the
    # result would be wrong for every texel after the first row. Pass the
    # WIDTH and HEIGHT.
    _rmin, _rmax = None, None
    for (_bx0, _by0) in _blocks:
        _vals = _rd_rt(
            _world, _rt, _bx0, _by0, _block, _block, False)
        _vals = list(_vals or [])
        if len(_vals) != _block * _block:
            _out["error"] = ("block at (%d, %d) returned %d texels, expected "
                             "%d — the read rectangle was clamped or the "
                             "format was rejected, so the un-flattening "
                             "stride cannot be trusted"
                             % (_bx0, _by0, len(_vals), _block * _block))
            return
        for _i, _c in enumerate(_vals):
            # BOTH channels are read for the diagnostic. Under flag-False
            # (what this script passes) the export writes the RAW uint16 into
            # R (R == G), so R alone is the FULL value; G is redundant and
            # read only so the r_min/r_max range can confirm which encoding
            # is live. Byte-split (R high / G low) is the flag-True encoding,
            # which this script does not use.
            _r = float(_c.r)
            _g = float(_c.g)
            _rmin = _r if _rmin is None else min(_rmin, _r)
            _rmax = _r if _rmax is None else max(_rmax, _r)
            _out["values"]["%d,%d" % (_bx0 + (_i % _block),
                                      _by0 + (_i // _block))] = [_r, _g]
    # Reported so ONE run decides the encoding question: R within [0,1]
    # means the export normalises, R spanning 0..65535 means it does not.
    _out["r_min"] = _rmin
    _out["r_max"] = _rmax
    _out["stage"] = "done"
    _out["ok"] = True


try:
    _export()
except Exception as _exc:
    _out["ok"] = False
    _out["error"] = "unhandled %s at stage %r: %s" % (
        type(_exc).__name__, _out.get("stage"), _exc)

# ONE print, on every path. Without this a raise anywhere above produced
# no marker at all, which upstream cannot tell apart from "the payload
# never ran" — "I could not look" collapsing into "I looked".
try:
    _payload = _json.dumps(_out)
except Exception as _exc:
    _payload = _json.dumps({{"ok": False, "stage": str(_out.get("stage")),
                            "error": "result not serialisable: %s"
                                     % type(_exc).__name__}})
print("{marker}" + _payload)
'''


# RETIRED — NOT CALLED BY main(). Kept only so the regression tests in the
# push_heightmap test module keep their revert-proofs for the `hit_actor`
# fix. See the VERIFICATION section of the module docstring for why the
# trace instrument was replaced. Do not reintroduce it without re-reading
# HitResult.h:100-140.
TRACE_SOURCE = '''
import json as _json
import unreal as _unreal

_pts = _json.loads({points!r})
_top = float({top!r})
_bottom = float({bottom!r})

_out = {{"hits": [], "unreadable": 0, "read_error": None, "error": None}}
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

# Downward traces read the terrain physically. GetHeightAtLocation is
# LANDSCAPE_API but not BlueprintCallable, so this is the reachable route.
# A line trace is a physics query: it creates nothing, sets nothing and
# dirties nothing, which is what keeps the dry run read-only.
#
# READING THE HIT, AT THE SOURCE. FHitResult in 5.8 has NO actor property.
# HitResult.h:126-127 declares `FActorInstanceHandle HitObjectHandle` and
# :130-131 `TWeakObjectPtr<UPrimitiveComponent> Component`. `hit_actor` is
# a BREAK-NODE PIN name (GameplayStatics.h:1078), not a property, so
# get_editor_property("hit_actor") RAISES on every sample. The hit
# component's owner is the reflected route; BreakHitResult is the
# fallback, and its 18 outputs are counted before index 9 is trusted.
#
# Three outcomes are kept APART, never collapsed: MISSED (no blocking
# hit), UNREADABLE (hit, but the result could not be read — with the
# reason recorded), and a reading. "I could not look" is not "I looked and
# it is absent".
for _p in _pts:
    _start = _unreal.Vector(float(_p[0]), float(_p[1]), _top)
    _end = _unreal.Vector(float(_p[0]), float(_p[1]), _bottom)
    try:
        _hit = _unreal.SystemLibrary.line_trace_single(
            _world, _start, _end,
            _unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            _unreal.DrawDebugTrace.NONE, True)
    except Exception as _exc:
        _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
        break
    if _hit is None:
        _out["hits"].append(None)
        continue

    _z = None
    _cls = None
    _why = ""
    try:
        _z = float(_hit.get_editor_property("location").z)
    except Exception as _exc:
        _why += "location: %s: %s | " % (type(_exc).__name__, _exc)
    try:
        _comp = _hit.get_editor_property("component")
        _actor = _comp.get_owner() if _comp is not None else None
        _cls = _actor.get_class().get_name() if _actor is not None else None
    except Exception as _exc:
        _why += "component: %s: %s | " % (type(_exc).__name__, _exc)
    if _z is None or _cls is None:
        try:
            _brk = _unreal.GameplayStatics.break_hit_result(_hit)
            _n = len(_brk) if hasattr(_brk, "__len__") else -1
            if _n == 18:
                if _z is None:
                    _z = float(_brk[4].z)
                if _cls is None and _brk[9] is not None:
                    _cls = _brk[9].get_class().get_name()
            else:
                _why += "break returned %d outputs, expected 18 | " % _n
        except Exception as _exc:
            _why += "break: %s: %s | " % (type(_exc).__name__, _exc)

    if _z is None or _cls is None:
        _out["unreadable"] += 1
        if _out["read_error"] is None:
            _out["read_error"] = _why or "hit could not be read"
        _out["hits"].append("unreadable")
    else:
        _out["hits"].append([_z, _cls])

print("{marker}" + _json.dumps(_out))
'''


PUSH_SOURCE = '''
import json as _json
import unreal as _unreal

# Reflected-name resolution, with the failure carrying its own fix.
#
# Three live runs have now been lost to invented or mis-cased reflected
# names (landscape_actor, landscape_components, create_render_target2_d).
# The engine derives Python names from C++ identifiers by a rule that is
# NOT reliably guessable around digits — CreateRenderTarget2D could
# pythonize as create_render_target2_d, create_render_target_2d or
# create_render_target2d, and no header, generated stub or engine
# Python file in this install answers it.
#
# So: try the candidates, and if none resolves, REPORT EVERY MATCHING
# ATTRIBUTE THE OBJECT ACTUALLY HAS. That turns "wrong name" from a
# guess-and-retry loop into a single run that hands back the answer —
# lesson 15 (when attempts are scarce, spend one read verifying
# everything) enforced in code rather than in intent.
def _resolve(_obj, _candidates, _hint):
    for _n in _candidates:
        _f = getattr(_obj, _n, None)
        if _f is not None:
            return _f, _n
    _have = sorted(_a for _a in dir(_obj)
                   if _hint in _a and not _a.startswith("_"))
    raise AttributeError(
        "none of %r exists on %s; matching attributes present: %r"
        % (list(_candidates), getattr(_obj, "__name__", _obj), _have))



_res = int({res!r})
_spacing = int({spacing!r})
_scale_xy = float({scale_xy!r})
_scale_z = float({scale_z!r})
_loc = {loc!r}
_level = {level!r}
_tex_path = {tex!r}
_mat_path = {mat!r}
_png = {png!r}
_want = {want!r}
# Render-target verification inputs (audit D2). _expect maps "x,y" -> the
# SOURCE heightmap value at that texel, computed host-side from the PNG so
# the comparison never derives its expectation from anything the push
# produced.
_block = int({block!r})
_blocks = {blocks!r}
_expect = _json.loads({expect!r})

_out = {{"ok": False, "stage": "start", "engine_returned": None,
        "error": None}}


def _refuse(_stage, _msg):
    _out["stage"] = _stage
    _out["error"] = _msg
    return False


def _push():
    _world = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world()
    if _world is None:
        return _refuse("world", "no editor world")

    # ---- 0. re-gate the LEVEL inside the mutating payload -----------
    # Conduct rule 7 identifies the PROJECT; it cannot tell one world in
    # that project from another, and that is exactly what bit this repo
    # on 2026-08-01. The dry run gated the level several round trips ago.
    # This is the payload that writes, so it asks again. The world's
    # OUTER package path is compared, matching the shared level gate.
    _out["stage"] = "level"
    try:
        _om = _world.get_outer()
        _lvl = _om.get_path_name() if _om is not None else None
    except Exception as _exc:
        return _refuse("level", "could not read the current level: %s: %s"
                       % (type(_exc).__name__, _exc))
    _out["level"] = _lvl
    if not _lvl:
        return _refuse("level", "the editor reported no current level — "
                                "that is 'I could not look', not 'the "
                                "level is correct'")
    if _lvl != _level:
        return _refuse("level", "the editor has %r open, not the recipe's "
                                "%r — refusing to write terrain into a "
                                "world the recipe does not name"
                                % (_lvl, _level))

    # ---- 1. re-identify BY SIGNATURE inside the mutating payload ----
    # The dry run's match is not a licence for this one: state could have
    # changed between the two round trips, and this is the payload that
    # writes.
    _out["stage"] = "identify"
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
    # Proxy -> owning landscape. The property is `LandscapeActorRef`
    # (LandscapeStreamingProxy.h:35-36), NOT `LandscapeActor`: the latter is
    # `LandscapeActor_DEPRECATED` at :29-30. The trap is that LandscapeActorRef
    # carries Meta = (DisplayName = "Landscape Actor"), so the editor UI, the
    # details panel and every screenshot call it "Landscape Actor" while the
    # reflected name is landscape_actor_ref. Reading the display name cost this
    # script its first live run.
    #
    # It is a TSoftObjectPtr, so comparison goes through the same idiom
    # the verify_landscape module has proven live, GUID as fallback.
    # LESSON 9: an unreadable ref is recorded as UNKNOWN, never silently
    # treated as "not mine" — quietly dropping a proxy would shrink the
    # component set and could make a correct landscape fail its own signature.
    def _owns(_p, _a):
        try:
            _ref = _p.get_editor_property("landscape_actor_ref")
            if _ref is not None:
                return bool(_ref == _a)
        except Exception as _exc:
            _unreadable.append("landscape_actor_ref: %s: %s"
                               % (type(_exc).__name__, _exc))
            return False
        try:
            _g = _a.get_editor_property("landscape_guid")
            return bool(_p.get_editor_property("landscape_guid") == _g)
        except Exception as _exc:
            _unreadable.append("landscape_guid: %s: %s"
                               % (type(_exc).__name__, _exc))
            return False
    _matches = []
    for _a in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.Landscape):
        _t = _a.get_actor_transform()
        _s, _l = _t.scale3d, _t.translation
        _bx = set()
        _unreadable = []
        _mine = [_a] + [_p for _p in _proxies if _owns(_p, _a)]
        for _p in _mine:
            for _c in (_p.get_components_by_class(_unreal.LandscapeComponent)):
                # LESSON 9, on the write path: an unreadable property must
                # not degrade into "no match" and let the caller believe
                # the landscape is absent.
                try:
                    _bx.add(int(_c.get_editor_property("section_base_x")))
                except Exception as _exc:
                    _unreadable.append("%s: %s" % (type(_exc).__name__, _exc))
        if _unreadable:
            return _refuse("identify",
                           "section_base_x unreadable on %d component(s); "
                           "the signature could not be COMPUTED, which is "
                           "not the same as not matching. First failure: %s"
                           % (len(_unreadable), _unreadable[0]))
        _sx = sorted(_bx)
        _step = (_sx[1] - _sx[0]) if len(_sx) > 1 else None
        _implied = (max(_sx) + _step + 1) if (_sx and _step) else None
        if (_implied == _res and _step == _spacing
                and abs(_s.x - _scale_xy) < 1e-4
                and abs(_s.y - _scale_xy) < 1e-4
                and abs(_s.z - _scale_z) < 1e-4
                and abs(_l.x - _loc[0]) < 0.5 and abs(_l.y - _loc[1]) < 0.5
                and abs(_l.z - _loc[2]) < 0.5):
            _matches.append(_a)
    if len(_matches) != 1:
        return _refuse("identify",
                       "signature match returned %d landscapes inside the "
                       "push payload" % len(_matches))
    _land = _matches[0]
    _out["matched"] = _land.get_actor_label()

    # ---- 2. import the PNG as a Texture2D ---------------------------
    _out["stage"] = "import_texture"
    _task = _unreal.AssetImportTask()
    _task.set_editor_property("filename", _png)
    _task.set_editor_property("destination_path", _tex_path.rsplit("/", 1)[0])
    _task.set_editor_property("destination_name", _tex_path.rsplit("/", 1)[1])
    _task.set_editor_property("automated", True)
    _task.set_editor_property("replace_existing", True)
    _task.set_editor_property("save", False)
    _unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([_task])
    _tex = _unreal.EditorAssetLibrary.load_asset(_tex_path)
    if _tex is None:
        return _refuse("import_texture",
                       "heightmap texture import produced no asset")

    # Linear data, uncompressed at FULL float precision, no mips, clamped,
    # unfiltered. Every one is a precision or edge-correctness
    # requirement. TC_HDR_F32 is RGBA32F (TextureDefines.h:409); TC_HDR is
    # RGBA16F (:399) and its 10-bit mantissa would quantise the terrain in
    # 32-height-unit steps — the same trap RTF_RGBA16f is refused for.
    _tex.set_editor_property("srgb", False)
    _tex.set_editor_property(
        "compression_settings",
        _unreal.TextureCompressionSettings.TC_HDR_F32)
    _tex.set_editor_property(
        "mip_gen_settings",
        _unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    _tex.set_editor_property("filter", _unreal.TextureFilter.TF_NEAREST)
    _tex.set_editor_property("address_x", _unreal.TextureAddress.TA_CLAMP)
    _tex.set_editor_property("address_y", _unreal.TextureAddress.TA_CLAMP)
    # NO post_edit_change(): it does not exist on Texture2D in 5.8. The
    # generated stub has 0 hits for it and the live editor raised
    # AttributeError, which is what refused this run at stage
    # import_texture — before anything was written. The idiom proven live
    # by the layer-texture import is set -> READ BACK -> save_asset, and
    # the read-back gate immediately below is exactly that.

    # ---- 3. precision gate ------------------------------------------
    # Read every setting BACK. Enum reads come back as enum objects, so
    # compare on .name — a str() would render "TextureAddress.TA_CLAMP"
    # and a naive equality check would fail for the wrong reason.
    _out["stage"] = "format_gate"

    def _rb(_prop):
        _v = _tex.get_editor_property(_prop)
        _n = getattr(_v, "name", None)
        return _n if _n is not None else _v

    _settings = {{}}
    for _p in sorted(_want.keys()):
        try:
            _settings[_p] = _rb(_p)
        except Exception as _exc:
            _settings[_p] = "UNREADABLE: %s: %s" % (type(_exc).__name__, _exc)
    _out["texture_settings"] = _settings
    _wrong = [_k for _k in sorted(_want.keys())
              if _settings.get(_k) != _want[_k]]
    if _wrong:
        return _refuse(
            "format_gate",
            "texture settings did not read back as set: %s. An 8-bit or "
            "fp16 intermediate would terrace the terrain silently."
            % ", ".join("%s=%r (want %r)" % (_k, _settings.get(_k),
                                             _want[_k]) for _k in _wrong))

    # Blueprint_GetSizeX/Y report the RESIDENT streamed mip, not the asset
    # (a fresh import can read 32x32). Blueprint_GetBuiltTextureSize
    # (Texture.h:1857) derives from the SOURCE (Texture.cpp:4079-4087), so
    # it is the honest dimension. An undersized texture would draw into
    # part of the target and push a sub-rectangle.
    try:
        _v = _tex.blueprint_get_built_texture_size()
        _dims = [int(_v.x), int(_v.y), int(_v.z)]
    except Exception as _exc:
        return _refuse("format_gate",
                       "could not read the imported texture's built size "
                       "(%s: %s)" % (type(_exc).__name__, _exc))
    _out["texture_built_size"] = _dims
    try:
        _out["resident_mip"] = [_tex.blueprint_get_size_x(),
                                _tex.blueprint_get_size_y()]
    except Exception:
        _out["resident_mip"] = None
    if _dims[0] != _res or _dims[1] != _res:
        return _refuse("format_gate",
                       "imported texture is %dx%d, the landscape is %dx%d"
                       % (_dims[0], _dims[1], _res, _res))

    # ---- 4. build the drawing material ------------------------------
    _out["stage"] = "material"
    _pkg, _name = _mat_path.rsplit("/", 1)
    if _unreal.EditorAssetLibrary.does_asset_exist(_mat_path):
        _mat = _unreal.EditorAssetLibrary.load_asset(_mat_path)
    else:
        _mat = _unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            _name, _pkg, _unreal.Material, _unreal.MaterialFactoryNew())
    if _mat is None:
        return _refuse("material", "could not create or load the push "
                                   "material at %s" % _mat_path)
    _mel = _unreal.MaterialEditingLibrary
    _mel.delete_all_material_expressions(_mat)

    # MD_UI, not Surface: DrawMaterialToRenderTarget goes through
    # Canvas->K2_DrawMaterial, which is the UI path.
    _mat.set_editor_property("material_domain", _unreal.MaterialDomain.MD_UI)

    _uv = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionTextureCoordinate, -800, 0)
    _ts = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionTextureSample, -550, 0)
    _ts.set_editor_property("texture", _tex)
    _ts.set_editor_property(
        "sampler_type", _unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    _mel.connect_material_expressions(_uv, "", _ts, "UVs")

    _mul = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionMultiply, -300, 0)
    _mel.connect_material_expressions(_ts, "R", _mul, "A")
    _k = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionConstant, -500, 200)
    _k.set_editor_property("r", 65535.0)
    _mel.connect_material_expressions(_k, "", _mul, "B")

    # +0.5 because the engine's (uint16) cast TRUNCATES.
    _add = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionAdd, -100, 0)
    _mel.connect_material_expressions(_mul, "", _add, "A")
    _half = _mel.create_material_expression(
        _mat, _unreal.MaterialExpressionConstant, -300, 200)
    _half.set_editor_property("r", 0.5)
    _mel.connect_material_expressions(_half, "", _add, "B")

    _mel.connect_material_property(
        _add, "", _unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    _mel.layout_material_expressions(_mat)
    # NOTE (audit D2): RecompileMaterial appears to return void, in which
    # case this list is always empty and this is NOT a compile gate. It is
    # reported as evidence, not relied on.
    _errs = _mel.recompile_material(_mat)
    _out["compile_errors"] = [str(_e) for _e in (_errs or [])]
    _unreal.EditorAssetLibrary.save_asset(_mat_path, only_if_is_dirty=False)
    if _out["compile_errors"]:
        return _refuse("material", "push material failed to compile")

    # ---- 5. render target -------------------------------------------
    _out["stage"] = "render_target"
    _mk_rt, _mk_rt_name = _resolve(
        _unreal.RenderingLibrary,
        ("create_render_target2_d", "create_render_target_2d",
         "create_render_target2d"), "render_target")
    _out["create_fn"] = _mk_rt_name
    _rd_rt, _rd_rt_name = _resolve(
        _unreal.RenderingLibrary,
        ("read_render_target_raw_pixel_area",
         "read_render_target_raw_pixel_area2_d"), "read_render_target")
    _out["read_fn"] = _rd_rt_name
    _rt = _mk_rt(
        _world, _res, _res,
        _unreal.TextureRenderTargetFormat.RTF_RGBA32F,
        _unreal.LinearColor(0.0, 0.0, 0.0, 1.0), False, False)
    if _rt is None:
        return _refuse("render_target", "could not create the render target")
    _out["rt_size"] = [_rt.size_x, _rt.size_y]
    _out["rt_format"] = str(_rt.get_editor_property("render_target_format"))
    # An undersized RT imports a SUB-RECT rather than erroring
    # (LandscapeEdit.cpp:8113). Refuse instead.
    if _rt.size_x < _res or _rt.size_y < _res:
        return _refuse(
            "render_target",
            "render target %dx%d is smaller than the landscape %d — the "
            "engine would import a sub-rectangle silently"
            % (_rt.size_x, _rt.size_y, _res))
    # RTF_RGBA16f is accepted by the engine and would quantise to 32
    # height units. Confirm the target really is the 32-bit one.
    if "32" not in _out["rt_format"]:
        return _refuse(
            "render_target",
            "render target format reads back as %r, which is not the "
            "32-bit float format this push requires"
            % _out["rt_format"])

    # ---- 6. draw ----------------------------------------------------
    _out["stage"] = "draw"
    _unreal.RenderingLibrary.draw_material_to_render_target(_world, _rt, _mat)

    # ---- 6b. MEASURE THE RENDER TARGET BEFORE THE WRITE (audit D2) ---
    # The four stages between the PNG and the import call can each fail
    # silently into a plausible flat or terraced terrain: the texture's
    # platform data is built ASYNCHRONOUSLY after post_edit_change() and a
    # texture still compiling samples as a placeholder; RecompileMaterial
    # returns nothing usable so a failed compile draws as the default
    # material; the MD_UI / sampler / UV chain is argued from source but
    # never observed; and the platform pixel format is unreachable from
    # Python. Reading the drawn texels closes all four at once, and does
    # it while the write is still avoidable.
    #
    # bNormalize=False IS THE WHOLE POINT, and it is the opposite of what
    # the name suggests. KismetRenderingLibrary.cpp:328 selects
    #     bNormalize ? FReadSurfaceDataFlags() : FReadSurfaceDataFlags(RCM_MinMax)
    # and FReadSurfaceDataFlags() defaults to RCM_UNorm (RHITypes.h:23).
    # RHIDefinitions.h:790-800 defines them:
    #     RCM_UNorm  — "if you read values that go outside [0,1], they are
    #                   scaled to fit inside [0,1]"
    #     RCM_MinMax — "read values without changing them"
    # with the header comment "RCM_MinMax means 'leave the values alone'
    # and is recommended as what you should use". So the DEFAULT
    # (bNormalize=True) would crush our 0..65535 into [0,1] and every
    # sample would read ~1.0. The rescaling mode is RCM_MinMaxNorm, which
    # is not what is selected here.
    #
    # AND bNormalize IS NOT THE ONLY MISLEADING ARGUMENT. The parameters
    # the reflected signature calls MaxX/MaxY are WIDTH and HEIGHT:
    # UKismetRenderingLibrary::ReadRenderTargetRawPixelArea
    # (KismetRenderingLibrary.cpp:454) forwards them into
    # ReadRenderTargetHelper's `Width`/`Height` (:295-304), which builds
    # SampleRect(X, Y, X + Width, Y + Height) (:326). Passing
    # `x0 + block - 1` reads an (x0+block-1)-wide rectangle, so the row
    # stride assumed by `_i % _block` / `_i // _block` is wrong for every
    # texel past the first row and each sample is attributed to the wrong
    # texel. The call succeeds, the values land, the meaning is wrong.
    _out["stage"] = "verify_rt"
    _rt_bad = []
    _rt_seen = 0
    _rt_min, _rt_max = None, None
    for (_bx0, _by0) in _blocks:
        _vals = _rd_rt(
            _world, _rt, _bx0, _by0, _block, _block, False)
        _vals = list(_vals or [])
        if len(_vals) != _block * _block:
            return _refuse(
                "verify_rt",
                "block at (%d, %d) returned %d texels, expected %d — the "
                "read rectangle was clamped or the format was rejected, so "
                "the un-flattening stride cannot be trusted. Nothing was "
                "imported." % (_bx0, _by0, len(_vals), _block * _block))
        for _i, _c in enumerate(_vals):
            _px = _bx0 + (_i % _block)
            _py = _by0 + (_i // _block)
            # NAMED _want_v, NOT _want. `_want` is the module-level texture
            # settings table this same function reads at the format gate;
            # assigning it anywhere in _push() makes it LOCAL for the whole
            # function under Python's scoping rules, so the earlier
            # `sorted(_want.keys())` raised UnboundLocalError and the push
            # could never reach the write.
            _want_v = _expect.get("%d,%d" % (_px, _py))
            if _want_v is None:
                continue
            _rt_seen += 1
            _r = float(_c.r)
            _rt_min = _r if _rt_min is None else min(_rt_min, _r)
            _rt_max = _r if _rt_max is None else max(_rt_max, _r)
            # The material emits v + 0.5 so the engine's (uint16) TRUNCATE
            # lands on v. Checking the truncation directly is checking the
            # thing the engine will actually do.
            if int(_r) != int(_want_v):
                _rt_bad.append([_px, _py, _r, _want_v])
    _out["rt_samples"] = _rt_seen
    _out["rt_min"] = _rt_min
    _out["rt_max"] = _rt_max
    _out["rt_mismatches"] = len(_rt_bad)
    _out["rt_first_bad"] = _rt_bad[:6]
    if _rt_seen == 0:
        return _refuse("verify_rt",
                       "could not read any texel back out of the render "
                       "target, so the drawn buffer is unverified. Nothing "
                       "was imported.")
    if _rt_min is not None and _rt_max is not None and \\
            (_rt_max - _rt_min) < 1.0:
        return _refuse("verify_rt",
                       "the drawn render target is FLAT (all sampled "
                       "texels within 1.0 of each other, min %.3f max "
                       "%.3f). That is what a still-compiling texture or "
                       "a failed material draws. Nothing was imported."
                       % (_rt_min, _rt_max))
    if _rt_bad:
        return _refuse("verify_rt",
                       "%d of %d sampled render-target texels do not "
                       "truncate to the source heightmap value; first: "
                       "%s. The buffer that would have been written is "
                       "wrong, so nothing was imported."
                       % (len(_rt_bad), _rt_seen, _rt_bad[0]))

    # ---- 7. import --------------------------------------------------
    # Nothing between here and the import call can raise: the terrain
    # must not be half-written because a diagnostic threw.
    _out["stage"] = "import"
    _ret = _land.landscape_import_heightmap_from_render_target(_rt, False, 0)
    _out["engine_returned"] = bool(_ret)
    _out["pushed"] = bool(_ret)
    _out["stage"] = "done"
    _out["ok"] = bool(_ret)

    # ---- 8. staging cleanup: TRIED, REVERTED, DO NOT RE-ADD ---------
    # Deleting /Game/Debug/T_PushHeight_Source after a successful push
    # was implemented on 2026-08-02 and REMOVED the same day, because it
    # broke the next push. The finding is worth more than the feature:
    #
    #   THE PERSISTENT STAGING TEXTURE IS LOAD-BEARING FOR MIP
    #   RESIDENCY, and nothing said so.
    #
    # Deleting it forces the next run to re-import, and a freshly
    # imported texture is not streamed in yet. Two consecutive runs
    # after the delete reported `resident mip [2017, 2017]` and
    # `resident mip [32, 32]` — a race. On the [32, 32] run the material
    # sampled a 32x32 mip and `draw_material_to_render_target` produced
    # a FLAT target (min 0.500 max 0.500), which the verify_rt gate
    # refused at stage `verify_rt` with nothing imported.
    #
    # That is section 10.3 arriving from a new direction: the engine
    # reporting "how much of this is currently in memory" while the
    # caller needs "how big this is". Keeping the texture between runs
    # meant it was ALREADY resident by the time the material sampled
    # it, and that accident was doing real work.
    #
    # The problem the deletion was meant to solve — ~65 MB of RGBA32F
    # sitting dirty and one "Save All" away from the repo — is solved
    # by .gitignore instead, which cannot introduce a race into the
    # terrain write path. A footgun removed at zero risk beats a
    # footgun removed at the cost of flakiness in the one script that
    # writes terrain.
    #
    # If this is ever revisited: force the texture resident and VERIFY
    # residency before the draw, rather than assuming the import
    # completed. Do not simply re-add the delete.
    # Nothing is deleted here. `_out["staging_cleanup"]` is still
    # emitted so the host has a definite answer rather than a
    # missing key, which would read as "the probe did not run".
    _out["staging_cleanup"] = {{"requested": False,
                                "note": "disabled 2026-08-02 — the staging texture is load-bearing for mip residency"}}

    return bool(_ret)


try:
    _push()
except Exception as _exc:
    _out["error"] = "unhandled %s at stage %r: %s" % (
        type(_exc).__name__, _out.get("stage"), _exc)

# One print, on every non-fatal path. If the result cannot be serialised,
# say so rather than printing nothing: printing nothing is read upstream as
# "this may have written", which is the strictest reading but also the
# least informative one.
try:
    _payload = _json.dumps(_out)
except Exception as _exc:
    _payload = _json.dumps({{"ok": False, "stage": str(_out.get("stage")),
                            "error": "result not serialisable: %s"
                                     % type(_exc).__name__}})
print("{marker}" + _payload)
'''


# Stages at which the push payload had NOT yet called the import. An error
# reported at any of these means the terrain was not touched (exit 6);
# anything else means it may have been (exit 5).
# "draw" is INCLUDED: drawing into a scratch render target touches no
# terrain, and the whole point of the D2 readback is that a bad draw is
# caught while the write is still avoidable. "verify_rt" likewise refuses
# before the import call. Everything from "import" onward is UNKNOWN.
STAGES_BEFORE_WRITE = ("start", "world", "level", "identify",
                       "import_texture", "format_gate", "material",
                       "render_target", "draw", "verify_rt")


# _run records WHY it returned None. "guard" and "connect" mean the payload
# never left this machine; "command" and "parse" mean it did, so a mutating
# payload may have run. That distinction is the difference between exit 6
# (a precondition refused, nothing written) and exit 5 (UNKNOWN), and
# collapsing it would report a definitively untouched terrain as unknown.
LAST_RUN_PHASE = None


def _parse(text, marker=PROBE_MARKER):
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source, marker=PROBE_MARKER):
    global LAST_RUN_PHASE
    LAST_RUN_PHASE = None
    try:
        source = mlm._guard_payload(source)
    except Exception as exc:
        LAST_RUN_PHASE = "guard"
        print("  REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return None
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        LAST_RUN_PHASE = "connect"
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            LAST_RUN_PHASE = "command"
            print("  command did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        payload = _parse(bootstrap._collect_output(result), marker)
        if payload is None:
            LAST_RUN_PHASE = "parse"
        return payload
    except Exception as exc:
        LAST_RUN_PHASE = "command"
        print("  command errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _sample_texels(res, grid, margin):
    """Deterministic interior grid of (col, row) texels."""
    lo, hi = margin, res - 1 - margin
    if hi <= lo:
        return []
    step = (hi - lo) / float(max(1, grid - 1))
    pts = []
    for i in range(grid):
        for j in range(grid):
            pts.append((int(round(lo + j * step)), int(round(lo + i * step))))
    return pts


def _trace(remote_exec, remote, node_id, world_pts, top, bottom):
    """Run one trace batch. Returns the whole probe dict, or None."""
    return _run(remote_exec, remote, node_id,
                TRACE_SOURCE.format(points=json.dumps(world_pts), top=top,
                                    bottom=bottom, marker=PROBE_MARKER))


def _score(texels, idxs, hits, arr, actor_z, scale_z):
    """Score one mapping against one trace batch.

    Returns (median_cm_or_None, pairs, counts). `pairs` is
    [((col, row), |dz| cm)] for samples that produced a reading; `counts`
    separates missed / unreadable / foreign-actor, because a sample that
    could not be read is not a sample that says the terrain is absent.
    """
    pairs = []
    counts = {"missed": 0, "unreadable": 0, "foreign": 0}
    for (c, r), i in zip(texels, idxs):
        h = hits[i] if 0 <= i < len(hits) else None
        if h is None:
            counts["missed"] += 1
            continue
        if not isinstance(h, list) or len(h) != 2:
            counts["unreadable"] += 1
            continue
        if h[1] not in LANDSCAPE_CLASSES:
            counts["foreign"] += 1
            continue
        try:
            d = abs(float(h[0]) - expected_world_z(arr[r, c], actor_z,
                                                   scale_z))
        except (TypeError, ValueError):
            counts["unreadable"] += 1
            continue
        # A non-finite residual passes every `d > tol` test silently. That
        # defect class has already been fixed three times in this repo
        # (lesson 2.9); it is a failure here, never a pass.
        if not math.isfinite(d):
            counts["unreadable"] += 1
            continue
        pairs.append(((c, r), d))
    med = statistics.median([p[1] for p in pairs]) if pairs else None
    return med, pairs, counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    # NO EFFECT. It sized the retired line-trace sample grid; the export
    # instrument reads fixed blocks (RT_BLOCK, `vblocks`). Kept so existing
    # invocations do not break, but said out loud rather than accepted and
    # silently dropped — a parameter that reaches nothing is exactly the
    # `fov_deg` defect this project already paid for.
    parser.add_argument("--grid", type=int, default=DEFAULT_SAMPLE_GRID,
                        help="NO EFFECT (retired with the line-trace "
                             "instrument). The export read-back samples "
                             "fixed blocks of RT_BLOCK vertices.")
    parser.add_argument("--probe-layers", action="store_true",
                        help="DIAGNOSTIC ONLY. Report the landscape's edit "
                             "layers. More than one means a correct push "
                             "will not read back as the source.")
    parser.add_argument("--probe-size", action="store_true",
                        help="DIAGNOSTIC ONLY. Export into several render "
                             "target sizes and report where the data "
                             "stops, discriminating a canvas-extent cause "
                             "from a component-batching one.")
    parser.add_argument("--probe-layout", action="store_true",
                        help="DIAGNOSTIC ONLY. Dump raw returned values "
                             "under BOTH readings of the area-read "
                             "arguments, at two origins, for offline "
                             "matching against the source heightmap.")
    parser.add_argument("--probe-export", action="store_true",
                        help="DIAGNOSTIC ONLY. Walk the export matrix "
                             "(flag x target format x read normalisation) "
                             "and print what each returns, then exit. "
                             "Writes nothing and imports nothing.")
    parser.add_argument("--expect-change", action="store_true",
                        help="Acknowledge that this push will CHANGE the "
                             "terrain. Required when the pre-flight finds "
                             "the live terrain already differs from the "
                             "heightmap by more than TOLERANCE_UNITS, "
                             "because the pre-flight then cannot separate "
                             "instrument error from real difference. It "
                             "does NOT widen the tolerance.")
    parser.add_argument("--push", action="store_true",
                        help="Actually write heights. Without this the run "
                             "identifies, calibrates and reports, and "
                             "creates nothing.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    # Fail closed on the audit gate BEFORE anything else happens — before
    # a recipe is read, before an editor is contacted. Conduct rule 8: a
    # BLOCK is retired by Ryan's sign-off, not by a rewrite.
    if UNRESOLVED_BLOCKS:
        print("REFUSE: this script carries {0} unresolved audit BLOCK "
              "finding(s). Code may not run against the live editor with an "
              "unresolved BLOCK verdict (CLAUDE.md, AUDIT GATE). Full text "
              "follows; retire them by Ryan's sign-off, then empty "
              "UNRESOLVED_BLOCKS.".format(len(UNRESOLVED_BLOCKS)))
        for block in UNRESOLVED_BLOCKS:
            print("")
            print("  " + block)
        return 6

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        print("REFUSE: numpy and Pillow are required to verify the "
              "push ({0}).".format(exc))
        return 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    # derive_spec returns (spec, errors) — the errors list is the geometry
    # legality check, and an illegal recipe must stop here rather than be
    # pushed into terrain.
    try:
        spec, spec_errors = landscape_spec.derive_spec(recipe)
    except Exception as exc:
        print("REFUSE: recipe geometry could not be derived: {0}".format(exc))
        return 2
    if spec_errors:
        print("REFUSE: recipe geometry is illegal:")
        for e in spec_errors:
            print("  - {0}".format(e))
        return 2

    # os.path.join DISCARDS the left operand when the right one is
    # absolute, and does not collapse "..", so a recipe carrying
    # "C:/elsewhere/x.png" or "../../x.png" would hand the editor a file
    # outside REPO_ROOT to import. Conduct rule 1 is scoped by containment,
    # not by intent — check it.
    png = os.path.abspath(os.path.join(REPO_ROOT, recipe["heightmap"]["source"]))
    repo_norm = bootstrap._norm(REPO_ROOT)
    if bootstrap._norm(png) != repo_norm and not bootstrap._norm(
            png).startswith(repo_norm + os.sep):
        print("REFUSE: heightmap.source resolves to {0}, which is outside "
              "REPO_ROOT ({1}).".format(png, REPO_ROOT))
        return 2
    if not os.path.isfile(png):
        print("REFUSE: heightmap not found at {0}".format(png))
        return 2

    res = int(spec["resolution"])
    ox, oy, az = [float(v) for v in recipe["landscape"]["location_cm"]]
    sxy = float(recipe["landscape"]["scale_xy_cm"])
    sz = float(spec["scale_z"])
    level_path = (recipe.get("landscape") or {}).get("level_path")

    img = Image.open(png)
    arr = np.asarray(img)
    if arr.ndim != 2 or arr.shape[0] != res or arr.shape[1] != res:
        print("REFUSE: heightmap is {0}, expected a {1}x{1} single-channel "
              "image".format(arr.shape, res))
        return 2
    if arr.dtype != np.uint16:
        print("REFUSE: heightmap dtype is {0}, expected uint16. A push from "
              "an 8-bit source would terrace the terrain.".format(arr.dtype))
        return 2

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("Heightmap       : {0}  ({1}x{1}, {2}, values {3}..{4})".format(
        png, res, arr.dtype, int(arr.min()), int(arr.max())))
    print("Landscape       : origin ({0:.0f}, {1:.0f}, {2:.0f}) cm, "
          "scale {3}/{3}/{4}".format(ox, oy, az, sxy, sz))
    print("Mode            : {0}".format("PUSH" if args.push else "DRY RUN"))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")
        nid = node["node_id"]

        print("--- level gate ---")
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, nid, level_path,
            lambda s, m: _run(remote_exec, remote, nid, s, m))
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            return 7
        print("  level {0}".format(detail))
        print("")

        if args.probe_layers:
            print("--- EDIT-LAYER PROBE (diagnostic; read-only) ---")
            lp = _run(remote_exec, remote, nid,
                      LAYER_PROBE_SOURCE.format(marker=PROBE_MARKER))
            if lp is None or lp.get("error"):
                print("FAIL: {0}".format(
                    (lp or {}).get("error", LAST_RUN_PHASE)))
                return 6
            for rec in lp.get("landscapes") or []:
                if rec.get("error"):
                    print("  {0}: {1}".format(rec["label"], rec["error"]))
                    continue
                print("  {0}: {1} edit layer(s) via {2} -> {3}".format(
                    rec["label"], rec.get("count"), rec.get("fn"),
                    rec.get("names")))
                if (rec.get("count") or 0) > 1:
                    print("      WARNING: more than one edit layer. The "
                          "rendered surface is their COMPOSITE, so a "
                          "correct push to layer 0 will NOT read back as "
                          "the source.")
            print("")
            print("=" * 70)
            print("PROBE ONLY — nothing was written.")
            print("=" * 70)
            return 0

        if args.probe_size:
            print("--- SIZE PROBE (diagnostic; writes nothing) ---")
            sizes = [1009, res, 3025]
            at = sorted(set([0, 100, 250, 400, 500, 504, 505, 600, 750,
                             900, 1000, 1008, 1009, 1200, 1500, 1512,
                             1513, 1800, 2016, 2400, 3024]))
            sr = _run(remote_exec, remote, nid, SIZE_PROBE_SOURCE.format(
                sizes=sizes, probe_at=at, marker=PROBE_MARKER))
            if sr is None or sr.get("error"):
                print("FAIL: {0}".format(
                    (sr or {}).get("error", LAST_RUN_PHASE)))
                return 6
            for rec in sr.get("runs") or []:
                size = rec.get("size")
                print("")
                print("  RT {0}x{0}  rt={1}  exported={2}".format(
                    size, rec.get("rt"), rec.get("exported")))
                if rec.get("error"):
                    print("      ERROR {0}".format(rec["error"]))
                    continue
                last = rec.get("last_nontrivial_diag")
                print("      last non-trivial diagonal index : {0}".format(
                    last))
                if last is not None and last >= 0:
                    frac = (last + 1) / float(size)
                    print("      covered fraction of target      : "
                          "{0:.3f}".format(frac))
                # Confirm the covered values are RIGHT, not merely present.
                agree = tot = 0
                for (i, v) in rec.get("diag") or []:
                    if i < res and v > 1.0:
                        tot += 1
                        if abs(v - float(arr[i, i])) <= TOLERANCE_UNITS:
                            agree += 1
                print("      of the non-trivial samples, {0}/{1} match the "
                      "source".format(agree, tot))
                print("      diag = {0}".format(
                    [[i, int(v)] for (i, v) in (rec.get("diag") or [])]))
            print("")
            print("=" * 70)
            print("PROBE ONLY — nothing was written, nothing was imported.")
            print("=" * 70)
            return 0

        if args.probe_layout:
            print("--- LAYOUT PROBE (diagnostic; writes nothing) ---")
            spots = [[1008, 1008], [100, 200]]
            lr = _run(remote_exec, remote, nid, LAYOUT_SOURCE.format(
                res=res, spots=spots, n=8, marker=PROBE_MARKER))
            if lr is None or lr.get("error"):
                print("FAIL: {0}".format(
                    (lr or {}).get("error", LAST_RUN_PHASE)))
                return 6
            print("  exported  : {0}".format(lr.get("exported")))
            print("  pixel fn  : {0}".format(lr.get("pixel_fn")))
            out = os.path.join(REPO_ROOT, "_trash", "layout_probe.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(lr, fh)
            print("  raw result written to {0}".format(out))
            for rec in lr.get("reads") or []:
                if rec.get("error"):
                    print("  {0:<16} at {1} ERROR {2}".format(
                        rec["interp"], rec["spot"], rec["error"]))
                    continue
                print("  {0:<16} args={1} count={2}".format(
                    rec["interp"], rec["args"], rec["count"]))
                print("      first8 = {0}".format(
                    [int(v) for v in rec["r"][:8]]))
            if lr.get("points"):
                print("  per-pixel control:")
                for pt in lr["points"]:
                    print("      ({0},{1}) -> {2}".format(*pt))
            print("")
            print("=" * 70)
            print("PROBE ONLY — nothing was written, nothing was imported.")
            print("=" * 70)
            return 0

        if args.probe_export:
            print("--- EXPORT PROBE (diagnostic; writes nothing) ---")
            centre = res // 2
            pr = _run(remote_exec, remote, nid, PROBE_SOURCE.format(
                res=res, x0=centre, y0=centre, n=8, marker=PROBE_MARKER))
            if pr is None:
                print("FAIL: the probe returned nothing ({0}).".format(
                    LAST_RUN_PHASE))
                return 6
            if pr.get("error"):
                print("FAIL: {0}".format(pr["error"]))
                return 6
            print("  create fn : {0}".format(pr.get("create_fn")))
            print("  read fn   : {0}".format(pr.get("read_fn")))
            print("  landscape : {0}".format(pr.get("landscape")))
            print("")
            for rec in pr.get("runs") or []:
                print("  format {0:<8} flag={1!s:<5} exported={2!s:<5} "
                      "rt={3}".format(rec.get("format"), rec.get("flag"),
                                      rec.get("exported"), rec.get("rt")))
                if rec.get("error"):
                    print("      ERROR {0}".format(rec["error"]))
                    continue
                for norm in ("False", "True"):
                    d = rec.get("norm_{0}".format(norm)) or {}
                    print("      normalize={0:<5} n={1:<4} R{2} G{3}  "
                          "first4={4}".format(
                              norm, d.get("count"), d.get("r"), d.get("g"),
                              d.get("first4")))
            print("")
            print("=" * 70)
            print("PROBE ONLY — nothing was written, nothing was imported.")
            print("=" * 70)
            return 0

        print("--- identify by property signature ---")
        ident = _run(remote_exec, remote, nid, IDENTIFY_SOURCE.format(
            res=res, spacing=spec["quads_per_component"], scale_xy=sxy,
            scale_z=sz, loc=[ox, oy, az], marker=PROBE_MARKER))
        if ident is None:
            print("FAIL: the identify probe could not be read ({0}). That is "
                  "'I could not look', not 'no landscape "
                  "matched'.".format(LAST_RUN_PHASE))
            return 4
        for c in ident.get("candidates") or []:
            print("  {0:<26} res={1} step={2} comps={3} {4}".format(
                c.get("label"), c.get("implied_resolution"), c.get("step"),
                c.get("components"),
                "MATCH" if c.get("signature_match") else "no match"))
        if not ident.get("ok"):
            print("REFUSE: {0}".format(ident.get("error")))
            return 4
        print("  matched: {0}".format(ident.get("matched")))
        print("")

        # ---- pre-flight: orientation + instrument calibration --------
        print("--- pre-flight (export read-back vs the LIVE terrain) ---")
        unit_cm = sz / LANDSCAPE_ZSCALE_DIVISOR

        # Blocks of ADJACENT vertices, so every mapping is scored on the
        # same physical readings from ONE export. Four quadrant centres
        # plus the middle: enough spread that a mirrored or transposed
        # terrain cannot coincidentally agree on all five.
        # THE EXPORT IS A LANDING CHECK, NOT THE AUTHORITY. It reproduces
        # only the first EXPORT_TRUSTED_MAX vertices per axis and tiles
        # that block across the rest of the target, so blocks are drawn
        # ONLY from the region it can represent. Sampling outside it would
        # not be a stricter test — it would be a guaranteed false failure.
        t = EXPORT_TRUSTED_MAX - RT_BLOCK
        vblocks = [(t // 4, t // 4), (3 * t // 4, t // 4),
                   (t // 4, 3 * t // 4), (3 * t // 4, 3 * t // 4),
                   (t // 2, t // 2)]
        print("  exporting the live heightmap and reading {0} vertices "
              "across {1} blocks, all within the trusted region "
              "x,y <= {2}".format(
                  len(vblocks) * RT_BLOCK * RT_BLOCK, len(vblocks),
                  EXPORT_TRUSTED_MAX))

        exp = _run(remote_exec, remote, nid, EXPORT_SOURCE.format(
            res=res, spacing=spec["quads_per_component"], scale_xy=sxy,
            scale_z=sz, loc=[ox, oy, az], block=RT_BLOCK, blocks=vblocks,
            ncomp=spec["total_components"], marker=PROBE_MARKER))
        if exp is None:
            print("  FAIL: the export probe could not be read ({0}). That "
                  "is 'I could not look'.".format(LAST_RUN_PHASE))
            return 6
        if not exp.get("ok"):
            print("REFUSE at stage {0}: {1}".format(
                exp.get("stage"), exp.get("error")))
            return 6
        live = exp.get("values") or {}
        # export_returned is NOT evidence: the engine returns true on every
        # path but a missing engine material, including the zero-component
        # early-out (LandscapeEdit.cpp:8210-8213). Printed as a fact.
        print("  export returned {0} (not evidence); {1} vertices read"
              .format(exp.get("export_returned"), len(live)))
        print("  resident census    : {0}".format(exp.get("census")))
        # The single most informative number for the encoding question:
        # R within [0,1] means the export normalises, R spanning 0..65535
        # means it writes the raw uint16 and `R * 65535` is 65535x wrong.
        print("  raw R range        : {0} .. {1}".format(
            exp.get("r_min"), exp.get("r_max")))
        if not live:
            print("REFUSE: the export produced no readable texels.")
            return 6

        # ENCODING HYPOTHESIS — a hypothesis, and the engine source argues
        # AGAINST it. `R * 65535 == the heightmap value` assumes the export
        # material normalises. The mirror import path with the same flag
        # false does `HeightData.Add((uint16)LinearColor.R)`
        # (LandscapeEdit.cpp:8138) — RAW, which is why this script's own
        # push material emits `v * 65535 + 0.5`. See the block above
        # EXPORT_SOURCE. It is TESTED and refused below, never fitted:
        # fitting a scale/offset would calibrate the instrument on the very
        # measurement it exists to check.
        #
        # NON-FINITE VALUES ARE A FAILURE, NEVER A SAMPLE. json.dumps emits
        # bare NaN/Infinity and json's decoder accepts them, so a NaN texel
        # arrives intact; it then poisons statistics.median (ordering is
        # undefined with NaN) and slips through every `> threshold` test.
        # That is the defect class this repo has already fixed three times
        # (hard-won lesson 8), and the post-push loop guards it — this loop
        # did not. Counted and refused, not silently dropped.
        # Each entry is [R, G] — both channels, because R alone would be
        # the high byte under the flag-True encoding and a block whose top
        # byte happened to be constant would look identical to a failed
        # export. This check was written when the payload still returned a
        # bare float and rejected every sample once the shape changed:
        # it reported "1280 of 1280 non-finite" on a perfectly good export.
        # A validity check that cannot read the data it validates fails
        # closed, which is right, but it accuses the wrong component.
        nonfinite = 0
        for r_val in live.values():
            ok = (isinstance(r_val, (list, tuple)) and len(r_val) == 2
                  and all(isinstance(v, (int, float)) and math.isfinite(v)
                          for v in r_val))
            if not ok:
                nonfinite += 1
        if nonfinite:
            print("REFUSE: {0} of {1} exported texels came back non-finite "
                  "or non-numeric. A NaN survives json transport intact, "
                  "orders undefined inside a median, and passes every "
                  "'> tolerance' test. The export cannot be scored."
                  .format(nonfinite, len(live)))
            return 6

        scored = []
        for mapping in MAPPINGS:
            resid = []
            for key, r_val in live.items():
                gx, gy = [int(v) for v in key.split(",")]
                if not (0 <= gx < res and 0 <= gy < res):
                    continue
                col, row = texel_to_vertex(mapping, gx, gy, res)
                if not (0 <= col < res and 0 <= row < res):
                    continue
                d = abs(decode_export(r_val) - float(arr[row, col]))
                if not math.isfinite(d):
                    continue
                resid.append(d)
            if resid:
                scored.append((float(statistics.median(resid)), mapping,
                               len(resid), float(max(resid))))
        for med_m, mapping_m, n_m, mx_m in sorted(scored):
            print("  {0:<22} {1} vertices  median |dv| {2:10.3f} units  "
                  "worst {3:.3f}".format(mapping_m, n_m, med_m, mx_m))
        if not scored:
            print("REFUSE: no mapping produced a comparable reading.")
            return 6

        # ---- IS THIS AN IDEMPOTENT PUSH OR A CHANGED ONE? ------------
        # D4 RESOLVED. Everything between here and the write that compares
        # the LIVE terrain to the SOURCE is only meaningful when the two
        # are supposed to be equal. On a changed heightmap — the script's
        # actual purpose — they are supposed to DIFFER, so those gates stop
        # being tests and become guaranteed false failures. That is why
        # --expect-change was unreachable: three separate gates refused
        # before anything could consult it.
        #
        # What is and is not derivable from a pre-flight, stated exactly:
        #   * ENCODING and ORIENTATION are properties of the ENGINE, not of
        #     the terrain, and they can only be derived when the live
        #     terrain already equals the source. On a changed push they
        #     CANNOT be derived, and this script does not pretend to.
        #   * Whether the terrain currently matches the source IS derivable
        #     and is the only thing the pre-flight is used for.
        #
        # So on a changed push the write is gated by the PRE-IMPORT RENDER
        # TARGET check alone — which compares the exact buffer about to be
        # written against the source, texel for texel, and is completely
        # independent of what the terrain currently holds — and the
        # post-push export check becomes load-bearing: after a correct
        # push the terrain IS the source, so a wrong orientation or
        # encoding shows up there as a FAILURE (exit 5, do not save),
        # never as a silent pass.
        best_units = scored[0][0]
        changed = best_units > ENCODING_MAX_UNITS

        if changed and not args.expect_change:
            print("")
            print("REFUSE: the live terrain differs from this heightmap by "
                  "a median of {0:.1f} height units, so this push would "
                  "CHANGE the terrain. The pre-flight cannot tell that "
                  "apart from an encoding or orientation fault, because "
                  "both look like 'the export disagrees with the source'. "
                  "Pass --expect-change to say the difference is intended. "
                  "The tolerance is NOT widened by doing so — it stays at "
                  "{1} height units, and the pre-import render-target "
                  "check still has to pass on every sampled texel before "
                  "anything is written.".format(best_units, TOLERANCE_UNITS))
            return 6

        if changed:
            mapping = DEFAULT_ORIENTATION
            med_units, med = float("nan"), float("nan")
            good_pre, worst_pre = 0, float("nan")
            unit_cm = sz / LANDSCAPE_ZSCALE_DIVISOR
            tol = TOLERANCE_UNITS * unit_cm
            print("")
            print("  classification     : the live terrain DIFFERS from "
                  "this heightmap (best mapping median {0:.1f} units), so "
                  "this push will CHANGE it. --expect-change given."
                  .format(best_units))
            print("  orientation        : NOT derivable pre-flight against "
                  "a terrain that is meant to differ; using {0!r}, which "
                  "was established by measurement when an idempotent push "
                  "was possible.".format(DEFAULT_ORIENTATION))
            print("  encoding           : likewise not confirmable here.")
            print("  what gates the write: the pre-import render-target "
                  "check, which compares the buffer about to be written "
                  "against the source and does not involve the terrain.")
            print("  what proves it landed: the post-push export check, "
                  "which is now load-bearing — a wrong orientation or "
                  "encoding fails it, and a failure is exit 5 UNKNOWN with "
                  "an explicit do-not-save.")
            print("  tolerance (FIXED)  = {0} height units = {1:.2f} cm"
                  .format(TOLERANCE_UNITS, tol))
            print("")
        else:
            # ---- EXTENT GATE -----------------------------------------
            # A PARTIAL EXPORT IS ITS OWN FAILURE AND MUST SAY SO.
            # Measured 2026-08-01: the export filled exactly one quadrant while
            # every stage reported success. The only symptom downstream was
            # that all eight mappings scored alike and the decisiveness guard
            # refused — which is the right outcome for the wrong reason, and it
            # names the wrong component. A quadrant of CORRECT data is exactly
            # what slips past a looser check.
            #
            # The blocks are spread across the terrain on purpose, so this is
            # per-BLOCK, not pooled: pooling lets a fully-correct quadrant
            # average out against three empty ones. Under the identity mapping
            # — now established by measurement, 40 of 40 values at (100,200) —
            # every block must be substantially correct or the target is not
            # fully populated.
            per_block = []
            for (bx0, by0) in vblocks:
                hit = tot = 0
                for dy in range(RT_BLOCK):
                    for dx in range(RT_BLOCK):
                        rec = live.get("{0},{1}".format(bx0 + dx, by0 + dy))
                        if rec is None:
                            continue
                        tot += 1
                        if abs(decode_export(rec)
                               - float(arr[by0 + dy, bx0 + dx])) <= TOLERANCE_UNITS:
                            hit += 1
                per_block.append(((bx0, by0), hit, tot))
            print("  populated check (identity, per block):")
            for (spot, hit, tot) in per_block:
                print("      block {0!s:<14} {1:4d}/{2:<4d} within tolerance"
                      .format(spot, hit, tot))
            empty = [b for b in per_block
                     if b[2] == 0 or (b[1] / float(b[2])) < EXTENT_MIN_FRACTION]
            if empty and len(empty) < len(per_block):
                print("")
                print("REFUSE: the export is PARTIAL. {0} of {1} sampled blocks "
                      "match the source and {2} do not, so the render target is "
                      "populated in some regions and not others. That is not a "
                      "mapping problem and not a terrain problem — it is an "
                      "incomplete export, and a partially-correct target is "
                      "exactly what a pooled check would have averaged away."
                      .format(len(per_block) - len(empty), len(per_block),
                              len(empty)))
                for (spot, hit, tot) in empty:
                    print("      unpopulated: block {0!s} ({1}/{2})".format(
                        spot, hit, tot))
                return 6

            scored.sort(key=lambda x: x[0])
            med_units, mapping, good_pre, worst_pre = scored[0]
            med = med_units * unit_cm

            # ORDER MATTERS, AND IT WAS WRONG. The encoding gate runs FIRST.
            # If the decode is the wrong encoding, every one of the eight mappings
            # scores similarly enormous residuals, the ratio test fails, and
            # the run refuses with "the orientation search is not decisive" —
            # the wrong diagnosis for an encoding fault, on the one run the
            # operator has to spend. A failed encoding invalidates the
            # decisiveness test; it does not compete with it.
            if med_units > ENCODING_MAX_UNITS:
                print("")
                print("REFUSE: the best mapping still disagrees with the source "
                      "by a median of {0:.1f} height units, so the raw-R decode "
                      "(decode_export) does not reproduce it — a wrong encoding "
                      "or a terrain that differs (see D4) — and this script will "
                      "not fit a scale/offset to make it fit — that would "
                      "calibrate the instrument on the data it exists to "
                      "check. The raw R range above decides it: within [0,1] "
                      "the export normalises; spanning 0..65535 it writes the "
                      "raw uint16, which is what the import path's "
                      "`(uint16)LinearColor.R` (LandscapeEdit.cpp:8138) implies "
                      "for the mirror flag. Read the material "
                      "/Engine/EditorLandscapeResources/"
                      "Landscape_Heightmap_To_RenderTarget2D and encode what it "
                      "actually does.".format(med_units))
                return 6

            # A near-tie is not a close call. On terrain that is not symmetric
            # the correct mapping wins by orders of magnitude; if it does not,
            # every mapping is measuring the same thing — which is what a flat
            # region or a degenerate read looks like — and picking the first of
            # a tie is exactly how a MIRRORED terrain gets written and never
            # noticed.
            if len(scored) > 1:
                runner = scored[1][0]
                by_ratio = runner >= ORIENTATION_MARGIN_RATIO * max(med_units,
                                                                   1e-9)
                by_margin = (runner - med_units) >= ORIENTATION_MARGIN_UNITS
                if not (by_ratio and by_margin):
                    print("")
                    print("REFUSE: the orientation search is not decisive. "
                          "{0} scored {1:.3f} units and {2} scored {3:.3f}; a "
                          "winner must beat the runner-up by both {4}x and {5} "
                          "height units. A near-tie means the measurement is "
                          "degenerate.".format(
                              mapping, med_units, scored[1][1], runner,
                              ORIENTATION_MARGIN_RATIO, ORIENTATION_MARGIN_UNITS))
                    return 6
            print("  ENCODING CONFIRMED: the raw-R decode reproduces the "
                  "heightmap value (median {0:.3f} units).".format(med_units))

            # D1 RESOLVED (Ryan, 2026-08-01): FIXED budget, never derived.
            # The pre-flight no longer sets the tolerance — it only classifies
            # what kind of push this is. See TOLERANCE_UNITS.
            tol = TOLERANCE_UNITS * unit_cm
            print("")
            print("  ORIENTATION: {0} (median |dz| {1:.2f} cm = {2:.2f} height "
                  "units)".format(mapping, med, med / unit_cm))
            print("  one height unit    = {0:.3f} cm".format(unit_cm))
            print("  tolerance (FIXED)  = {0} height units = {1:.2f} cm"
                  .format(TOLERANCE_UNITS, tol))

            # CLASSIFY, do not widen.
            if med <= tol:
                print("  classification     : the live terrain ALREADY matches "
                      "this heightmap to within the budget, so the trace "
                      "instrument is proven adequate at this tolerance and "
                      "this push is IDEMPOTENT.")
            else:
                print("  classification     : the live terrain DIFFERS from "
                      "this heightmap by {0:.1f} height units (median), so "
                      "this push will CHANGE the terrain.".format(med / unit_cm))
                if not args.expect_change:
                    print("")
                    print("REFUSE: the pre-flight cannot separate instrument "
                          "error from a real difference, so it cannot certify "
                          "that a post-push disagreement would be the "
                          "instrument's fault. Pass --expect-change to push "
                          "terrain that is genuinely different. The tolerance "
                          "is NOT widened either way — it stays at {0} height "
                          "units.".format(TOLERANCE_UNITS))
                    return 6
                print("  --expect-change given; proceeding with the SAME {0}"
                      "-unit budget.".format(TOLERANCE_UNITS))
        print("")

        if not args.push:
            print("=" * 70)
            print("DRY RUN — nothing was created and nothing was written.")
            print("The landscape is identified, the orientation is "
                  "established and the read-back instrument is calibrated. "
                  "Re-run with --push to write.")
            print("=" * 70)
            return 0

        # ---- render-target expectation, computed from the PNG ---------
        # A 3x3 grid of blocks — so a flat, mirrored, offset or terraced
        # draw is caught wherever it happens, at the cost of nine GPU stalls
        # rather than one per texel.
        # PRIMARY VERIFICATION. This reads the render target THIS script
        # drew — not the engine's export — so it is valid across the whole
        # terrain and is unaffected by the period-1008 tiling. It compares
        # the exact buffer that is about to be written, texel for texel,
        # against the source heightmap, BEFORE the irreversible import.
        # A 3x3 grid rather than the old 5 blocks: as the authority it
        # should cover the terrain, including the far corners the export
        # can never reach.
        rt_blocks = []
        for gy in range(3):
            for gx in range(3):
                bx = int(round(gx * (res - 1 - RT_BLOCK) / 2.0))
                by = int(round(gy * (res - 1 - RT_BLOCK) / 2.0))
                rt_blocks.append((bx, by))
        rt_expect = {}
        for (bx0, by0) in rt_blocks:
            for dy in range(RT_BLOCK):
                for dx in range(RT_BLOCK):
                    # RT pixel (x, y) samples texture texel (x, y), which is
                    # PNG arr[row=y, col=x]. This checks the DRAW only and
                    # is independent of the landscape orientation question.
                    rt_expect["{0},{1}".format(bx0 + dx, by0 + dy)] = int(
                        arr[by0 + dy, bx0 + dx])
        print("  render-target check: {0} texels across {1} blocks"
              .format(len(rt_expect), len(rt_blocks)))
        print("")

        # ---- push -----------------------------------------------------
        print("--- push ---")
        pr = _run(remote_exec, remote, nid, PUSH_SOURCE.format(
            res=res, spacing=spec["quads_per_component"], scale_xy=sxy,
            scale_z=sz, loc=[ox, oy, az], level=level_path, tex=HEIGHT_TEX,
            mat=PUSH_MATERIAL, png=png.replace("\\", "/"),
            want=REQUIRED_TEXTURE_SETTINGS, block=RT_BLOCK,
            blocks=rt_blocks, expect=json.dumps(rt_expect),
            marker=PROBE_MARKER))
        if pr is None:
            if LAST_RUN_PHASE in ("guard", "connect"):
                print("REFUSE: the push payload never left this machine "
                      "({0}). The terrain was NOT touched.".format(
                          LAST_RUN_PHASE))
                return 6
            print("FAIL: the push payload was sent but returned nothing "
                  "({0}). It may have written; terrain state is UNKNOWN. "
                  "Re-run the dry run before doing anything else, and do "
                  "NOT save the level.".format(LAST_RUN_PHASE))
            return 5
        print("  stage reached      : {0}".format(pr.get("stage")))
        print("  level              : {0}".format(pr.get("level")))
        print("  texture settings   : {0}".format(pr.get("texture_settings")))
        print("  texture built size : {0}  (resident mip {1})".format(
            pr.get("texture_built_size"), pr.get("resident_mip")))
        print("  render target      : {0} {1}".format(
            pr.get("rt_size"), pr.get("rt_format")))
        print("  engine returned    : {0}".format(pr.get("engine_returned")))
        if pr.get("ok"):
            # Said every run rather than left for someone to rediscover:
            # the staging texture is SUPPOSED to still be there.
            print("  staging texture    : kept (deliberate — it must stay "
                  "resident for the next push's draw; gitignored, do not "
                  "save it)")
        if pr.get("error"):
            print("")
            print("REFUSE/FAIL at stage {0}: {1}".format(
                pr.get("stage"), pr["error"]))
            if pr.get("stage") in STAGES_BEFORE_WRITE:
                return 6
            print("The failure is at or after the draw, so the terrain may "
                  "have been written. State is UNKNOWN — do NOT save the "
                  "level.")
            return 5
        if not pr.get("ok"):
            print("FAIL: the engine did not report a successful import. "
                  "State is UNKNOWN — do NOT save the level.")
            return 5
        print("")

        # ---- verify ---------------------------------------------------
        print("--- verification (export read-back vs the SOURCE) ---")
        # THE IMPORT IS NOT SYNCHRONOUS WITH THE EXPORT. Measured
        # 2026-08-01 on the first CHANGED push: the import returned true,
        # the pre-import render-target check had already passed on every
        # texel, and the immediate post-push export still read the OLD
        # terrain — every one of 1280 vertices "off" by ~16000 height
        # units, with a height spread matching the pre-push terrain rather
        # than the new one. A re-read moments later matched the source
        # EXACTLY, median 0.000 units. So the write was correct and the
        # verification was early: the landscape applies the edit-layer
        # update deferred, and the export samples whatever has been
        # applied so far.
        #
        # Retry rather than sleep-and-hope: poll until the read agrees
        # with the source or the attempts run out, and REPORT how many it
        # took. A fixed sleep would be a magic number that silently rots
        # on a slower machine or a larger landscape; the attempt count is
        # evidence, and if it ever climbs it is telling us something.
        after = {}
        attempts = 0
        for attempts in range(1, VERIFY_MAX_ATTEMPTS + 1):
            exp2 = _run(remote_exec, remote, nid, EXPORT_SOURCE.format(
                res=res, spacing=spec["quads_per_component"], scale_xy=sxy,
                scale_z=sz, loc=[ox, oy, az], block=RT_BLOCK,
                blocks=vblocks, ncomp=spec["total_components"],
                marker=PROBE_MARKER))
            if exp2 is None or not exp2.get("ok"):
                print("FAIL: could not re-export after the push ({0}). The "
                      "push reported success but is UNVERIFIED — terrain "
                      "state is UNKNOWN. Do NOT save the level.".format(
                          (exp2 or {}).get("error", LAST_RUN_PHASE)))
                return 5
            after = exp2.get("values") or {}
            # Cheap agreement probe on the same vertices the full check
            # will use, so the retry decision and the verdict cannot
            # disagree about what "matches" means.
            worst = 0.0
            for key, rec in after.items():
                gx, gy = [int(v) for v in key.split(",")]
                col, row = texel_to_vertex(mapping, gx, gy, res)
                if 0 <= col < res and 0 <= row < res:
                    d = abs(decode_export(rec) - float(arr[row, col]))
                    if math.isfinite(d):
                        worst = max(worst, d)
            if worst <= TOLERANCE_UNITS:
                break
            if attempts < VERIFY_MAX_ATTEMPTS:
                print("  attempt {0}: worst |dv| {1:.0f} units — the "
                      "landscape has not finished applying the import; "
                      "re-reading.".format(attempts, worst))
                time.sleep(VERIFY_RETRY_DELAY_S)
        print("  export agreed after {0} attempt(s)".format(attempts))
        # The post-push comparison must be against the SAME vertices, not
        # merely the same NUMBER of them. Comparing counts was no check at
        # all: each block read returns exactly block*block texels whatever
        # the residency, so the count is constant by construction and the
        # test could never fire. Set equality is what was meant.
        if set(after) != set(live):
            missing = sorted(set(live) - set(after))[:6]
            added = sorted(set(after) - set(live))[:6]
            print("FAIL: the post-push export read a DIFFERENT set of "
                  "vertices than the pre-flight ({0} before, {1} after; "
                  "missing e.g. {2}, new e.g. {3}). The comparison would "
                  "not be against the calibrated set. UNVERIFIED — do NOT "
                  "save the level.".format(len(live), len(after), missing,
                                           added))
            return 5

        # EVERYTHING FROM HERE IS AFTER THE WRITE. An unexpected exception
        # in the comparison used to escape main() and exit 1, which reads
        # as "bad arguments" on a run that has already mutated terrain.
        # Any failure to compare is exit 5 (UNKNOWN), never anything else.
        try:
            resid, bad, heights = [], [], []
            for key, r_val in after.items():
                gx, gy = [int(v) for v in key.split(",")]
                col, row = texel_to_vertex(mapping, gx, gy, res)
                if not (0 <= col < res and 0 <= row < res):
                    continue
                want = float(arr[row, col])
                got = decode_export(r_val)
                heights.append(got)
                d = abs(got - want)
                if not math.isfinite(d):
                    bad.append(((gx, gy), float("nan")))
                    continue
                resid.append(d)
                if d > TOLERANCE_UNITS:
                    bad.append(((gx, gy), d))
        except Exception as exc:
            print("FAIL: the post-push comparison could not be completed "
                  "({0}: {1}). The push already ran, so terrain state is "
                  "UNKNOWN. Do NOT save the level.".format(
                      type(exc).__name__, exc))
            return 5
        if not resid:
            print("FAIL: no post-push vertex could be compared. "
                  "UNVERIFIED. Do NOT save the level.")
            return 5
        med2 = float(statistics.median(resid))
        mx = float(max(resid))
        good = len(resid)
        print("  vertices verified  : {0}".format(good))
        print("  median |dv|        : {0:.4f} height units ({1:.2f} cm)"
              .format(med2, med2 * unit_cm))
        print("  worst  |dv|        : {0:.4f} height units ({1:.2f} cm)"
              .format(mx, mx * unit_cm))
        print("  tolerance          : {0} height units".format(
            TOLERANCE_UNITS))
        print("  outside tolerance  : {0}".format(len(bad)))

        # EXPLICIT FLAT-RESULT CHECK (Ryan, 2026-08-01). A flat terrain is
        # the single most likely silent failure of this whole route — a
        # still-compiling texture, a failed material, or a mis-set render
        # target all produce one, and a flat landscape is a perfectly
        # valid landscape that nothing downstream would flag. The source
        # heightmap's own spread is the reference, so this cannot pass by
        # measuring nothing.
        try:
            got_spread = (max(heights) - min(heights)) if heights else 0.0
            want_vals = []
            for key in after:
                gx, gy = [int(v) for v in key.split(",")]
                col, row = texel_to_vertex(mapping, gx, gy, res)
                if 0 <= col < res and 0 <= row < res:
                    want_vals.append(float(arr[row, col]))
            want_spread = ((max(want_vals) - min(want_vals))
                           if want_vals else 0.0)
        except Exception as exc:
            print("FAIL: the flat-result check could not be completed "
                  "({0}: {1}). The push already ran, so terrain state is "
                  "UNKNOWN. Do NOT save the level.".format(
                      type(exc).__name__, exc))
            return 5
        print("  height spread      : pushed {0:.1f} units vs source "
              "{1:.1f} units".format(got_spread, want_spread))
        if (want_spread > FLAT_MIN_SPREAD_UNITS
                and got_spread < want_spread * FLAT_MIN_SPREAD_FRACTION):
            print("")
            print("FAIL: the pushed terrain is FLAT relative to the source "
                  "({0:.1f} units of relief where the source has {1:.1f}). "
                  "That is what a placeholder texture or a failed material "
                  "produces. UNVERIFIED — do NOT save the level.".format(
                      got_spread, want_spread))
            return 5
        # Say which it is. When the source region itself has less relief
        # than FLAT_MIN_SPREAD_UNITS the check cannot discriminate, and
        # printing "PASS (relief preserved)" for that case would be a pass
        # awarded for measuring nothing (hard-won lesson 12).
        if want_spread <= FLAT_MIN_SPREAD_UNITS:
            print("  flat-result check  : NOT APPLICABLE — the source over "
                  "these vertices has only {0:.1f} units of relief, below "
                  "the {1:.1f}-unit floor, so this check discriminates "
                  "nothing here. The per-vertex tolerance above is what "
                  "carries the result.".format(want_spread,
                                               FLAT_MIN_SPREAD_UNITS))
        else:
            print("  flat-result check  : PASS (relief preserved)")

        if bad:
            for (cr, d) in bad[:8]:
                print("      vertex {0} off by {1:.2f} height units"
                      .format(cr, d))
            print("")
            print("FAIL: the pushed terrain does not match the source "
                  "heightmap. Terrain state is UNKNOWN and must not be "
                  "trusted. Do NOT save the level.")
            return 5
        print("")
        print("=" * 70)
        # UNITS. `mx` comes from `resid`, which is |R - source| (raw R) — a
        # difference of HEIGHT UNITS, not cm. It was printed as cm and
        # then DIVIDED by unit_cm again to produce the "height units"
        # figure, so both numbers on this line were wrong after the
        # cm -> units swap. cm = units * unit_cm.
        print("PUSH VERIFIED. {0} samples, worst {1:.2f} height units "
              "({2:.2f} cm), all within {3} height units ({4:.2f} cm)."
              .format(good, mx, mx * unit_cm, TOLERANCE_UNITS, tol))
        print("")
        print("NOTE ON WHAT THIS PROVES. The engine returned True and its")
        print("own log carries 'Took N seconds to import heightmap from")
        print("render target' (LandscapeEdit.cpp:8175) — that is the")
        print("evidence the mechanism RAN. The height comparison shows the")
        print("result equals the source. Pushing the heightmap the terrain")
        print("was already built from is idempotent, so the comparison")
        print("alone could not distinguish a correct push from no push at")
        print("all; the first push of a CHANGED heightmap is what")
        print("exercises that case.")
        print("")
        print("THE WRITE IS IN EDITOR MEMORY ONLY. Nothing here saves the")
        print("level, and git cannot restore a level that was never")
        print("written. Until it is saved the push is not durable; once it")
        print("is saved it is not reversible.")
        print("=" * 70)
        print("")
        print("Next: run scripts/verify_landscape.py (geometry unchanged) "
              "and scripts/capture.py, then a one-line changelog note.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    # RESOURCE GUARD. Heavy operations log the memory situation before
    # they start and hold a lock so two never drive the same editor at
    # once (scripts/resource_guard.py). Low memory WARNS; a concurrent
    # heavy op REFUSES at exit 8.
    try:
        with resource_guard.HeavyOp('landscape heightmap push (landscape rebuild)') as _guard_ok:
            if not _guard_ok:
                sys.exit(8)
            sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
