#!/bin/bash
# fringe agent cycle runner. usage: _fringe_run.sh <name>
set -e
cd /c/Users/Admin/UE5LandscapePipeline
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="C:/Users/Admin/UE5LandscapePipeline/hero/groomloop"
R="C:/Users/Admin/UE5LandscapePipeline"
N="$1"
timeout 600 "$BL" --background --python "$R/hero/groomloop/scripts/edit_engine.py" -- \
  "$W/hero_src/hero_base.blend" "$W/params/$N.json" \
  "$W/blends/$N.blend" "$W/exports/$N.abc" "$W/logs/$N.json" 2>&1 | grep -E "__EDIT__|REFUSE|Error" | head -3
timeout 900 "$BL" --background "$W/blends/$N.blend" --python "$R/scripts/blender/preview_hair.py" -- \
  "$R/_verify/20260822_agents/$N" 2>&1 | grep -q "__PREVIEW__"
python hero/groomloop/scripts/front_metrics.py \
  "_verify/20260822_agents/$N/preview_front.png" "hero/groomloop/survey/${N}_front.json" >/dev/null
python hero/groomloop/scripts/_fringe_score.py "$N"
