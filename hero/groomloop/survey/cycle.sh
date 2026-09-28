#!/usr/bin/env bash
# cycle.sh <name> -- run one SIDES loop cycle: edit -> preview -> score.
# Fails loudly; two identical failures is a STOP condition per the brief.
set -u
cd /c/Users/Admin/UE5LandscapePipeline || exit 1
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="C:/Users/Admin/UE5LandscapePipeline/hero/groomloop"
R="C:/Users/Admin/UE5LandscapePipeline"
N="$1"

timeout 600 "$BL" --background --python "$R/hero/groomloop/scripts/edit_engine.py" -- \
  "$W/hero_src/hero_base.blend" "$W/params/$N.json" \
  "$W/blends/$N.blend" "$W/exports/$N.abc" "$W/logs/$N.json" 2>&1 \
  | grep -E '__EDIT__|REFUSE|Error' | tail -3
[ -f "hero/groomloop/blends/$N.blend" ] || { echo "EDIT FAILED: no blend"; exit 2; }

timeout 900 "$BL" --background "$W/blends/$N.blend" \
  --python "$R/scripts/blender/preview_hair.py" -- \
  "$R/_verify/20260822_agents/$N" 2>&1 \
  | grep -oE '"flare_max_ratio": [0-9.]+|"flare_p95_ratio": [0-9.]+|"scalp_exposed_pct": [0-9.]+|"hair_px": [0-9]+' \
  | head -6
[ -f "_verify/20260822_agents/$N/preview_front.png" ] || { echo "RENDER FAILED"; exit 3; }

python hero/groomloop/survey/score_sides.py "$N"
