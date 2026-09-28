#!/usr/bin/env bash
# Ruling 5/6 -- MULTI-VIEW TRELLIS on the operator's church reference set.
#
# WHY MULTI-VIEW. The 2026-08-30 bakeoff ran ONE view, an 80x115 crop lifted
# from the concept art carrying ~3,700 subject pixels, and TRELLIS returned a
# flat sheet: thin/long 0.0114 against the castle control's 0.8491. A positive
# control through the identical code path proved the model was fine, so the
# input was the fault. CHURCH_VIEW_SPEC.md was written from that measurement
# and the operator has now delivered against it.
#
# Environment is R-TRELLIS's, VERBATIM, not re-derived:
#   ATTN_BACKEND=xformers   NOT sdpa -- sdpa is SILENTLY IGNORED by
#                           trellis/modules/sparse, which takes only
#                           xformers/flash_attn, while the DENSE module
#                           accepts it. The run then prints a backend line
#                           that looks fine and uses something else.
#   SPCONV_ALGO=native
#   XFORMERS_DISABLED=1     routes DINOv2 away from xformers only
#   formats=["mesh"]        geometry is the deliverable; the gaussian
#                           rasterizers were never installed.
#
# MODEL REPO is JeffreyXiang/TRELLIS-image-large, matching run_church.sh and
# run_control.sh. example_multi_image.py says microsoft/... -- the two are
# mirrors of the same weights, and the comparison to the flat-sheet baseline
# is only honest if the repo does not change between them.
#
# SAMPLER PARAMS come from example_multi_image.py (steps 12 / cfg 7.5, steps
# 12 / cfg 3), which is the documented multi-image path. The single-image
# bakeoff used pipeline defaults. That is a DELIBERATE difference and it is
# recorded in the report as `sampler_params_source`, because a run that
# differs from its baseline in two ways at once cannot attribute its result
# to either.
set -euo pipefail

PY=/opt/miniforge3/envs/trellis/bin/python
REPO=/mnt/c/Users/Admin/UE5LandscapePipeline
REFS="$REPO/refs/church_refs"
OUTDIR="$REPO/_verify/20260830_bakeoff"
mkdir -p "$OUTDIR"

# AI-INPUT GUARD, BEFORE THE MODEL LOADS, ON EVERY INPUT.
# R-AIGATE: a generated mesh carries no provenance, so a licence violation
# here cannot be detected afterwards and there is nothing to revert. `set -e`
# makes a refusal abort before any weights are touched. Guarding only the
# first image would be "guarding only the script you are worried about".
for f in "$REFS"/church_az000.png.jpg \
         "$REFS"/church_az035.png.jpg \
         "$REFS"/church_az090.png.jpg \
         "$REFS"/church_az270.png.jpg; do
    "$PY" "$REPO/scripts/ai_input_guard.py" --strict "$f"
done

export ATTN_BACKEND=xformers
export SPCONV_ALGO=native
export XFORMERS_DISABLED=1
export PYTHONPATH=/opt/trellis

cd /opt/trellis
"$PY" "$REPO/scripts/trellis/_church_multi_body.py"
