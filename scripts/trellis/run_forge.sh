#!/usr/bin/env bash
# Forge stage 2+3: guard every input, then generate. Driven by a JOB FILE.
#
#   bash scripts/trellis/run_forge.sh /mnt/c/.../forge_job.json
#
# Environment is R-TRELLIS's, VERBATIM, not re-derived:
#   ATTN_BACKEND=xformers   NOT sdpa -- sdpa is SILENTLY IGNORED by
#                           trellis/modules/sparse, which takes only
#                           xformers/flash_attn, while the DENSE module
#                           accepts it. The run then prints a backend line
#                           that looks fine and uses something else.
#   SPCONV_ALGO=native
#   XFORMERS_DISABLED=1     routes DINOv2 away from xformers only
#
# ⛔ THE AI-INPUT GUARD RUNS ON EVERY VIEW, BEFORE ANY WEIGHTS LOAD.
# R-AIGATE: a generated mesh carries no provenance, so a licence violation
# here cannot be detected afterwards and there is nothing to revert. `set -e`
# makes a refusal abort before the model is touched. Guarding only the first
# view would be "guarding only the script you are worried about".
set -euo pipefail

JOB="$1"
PY=/opt/miniforge3/envs/trellis/bin/python
REPO=/mnt/c/Users/Admin/UE5LandscapePipeline

# jq is not assumed present; the job file is read with the same python that
# will run the model, so there is one parser and no shell-side JSON guessing.
mapfile -t VIEWS < <("$PY" -c "import json,sys; print('\n'.join(json.load(open(sys.argv[1]))['views']))" "$JOB")

if [ "${#VIEWS[@]}" -eq 0 ]; then
    echo "REFUSE: the job declares no views. A forge run with no reference has no provenance."
    exit 2
fi

for v in "${VIEWS[@]}"; do
    # A guard refusal is a GATE VERDICT: mark it so forge.py can exit 2
    # (refused) instead of narrating it as a stage-3 instrument failure
    # (Pass 3 2026-09-16 F2). set -e still stops the run either way.
    if ! "$PY" "$REPO/scripts/ai_input_guard.py" --strict "$v"; then
        echo "__FORGE_GUARD_REFUSED__ $v"
        exit 2
    fi
done

export ATTN_BACKEND=xformers
export SPCONV_ALGO=native
export XFORMERS_DISABLED=1
export PYTHONPATH=/opt/trellis

cd /opt/trellis
"$PY" "$REPO/scripts/trellis/_forge_generate_body.py" "$JOB"
