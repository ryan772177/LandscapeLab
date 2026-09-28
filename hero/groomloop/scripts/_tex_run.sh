#!/usr/bin/env bash
# _tex_run.sh <name> -- one TEXTURE cycle: edit -> preview -> front metrics -> judge.
set -u
cd /c/Users/Admin/UE5LandscapePipeline || exit 1
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="C:/Users/Admin/UE5LandscapePipeline/hero/groomloop"
R="C:/Users/Admin/UE5LandscapePipeline"
N="$1"

timeout 600 "$BL" --background --python "$R/hero/groomloop/scripts/edit_engine.py" -- \
  "$W/hero_src/hero_base.blend" "$W/params/$N.json" \
  "$W/blends/$N.blend" "$W/exports/$N.abc" "$W/logs/$N.json" 2>&1 \
  | grep -E "__EDIT__|REFUSE|Error" | tail -2
[ -f "hero/groomloop/blends/$N.blend" ] || { echo "EDIT FAILED: no blend"; exit 2; }

timeout 900 "$BL" --background "$W/blends/$N.blend" \
  --python "$R/scripts/blender/preview_hair.py" -- \
  "$R/_verify/20260822_agents/$N" > "hero/groomloop/logs/${N}_preview.txt" 2>&1
[ -f "_verify/20260822_agents/$N/preview_front.png" ] || { echo "RENDER FAILED"; exit 3; }
grep -oE '"scalp_exposed_pct": [0-9.]+|"flare_max_ratio": [0-9.]+|"hair_px": [0-9]+' \
  "hero/groomloop/logs/${N}_preview.txt" | head -4

python hero/groomloop/scripts/front_metrics.py \
  "_verify/20260822_agents/$N/preview_front.png" \
  "hero/groomloop/survey/${N}_front.json" > /dev/null

python hero/groomloop/scripts/judge.py "hero/groomloop/survey/${N}_front.json" \
  "hero/groomloop/logs/${N}_preview.txt"
echo "JUDGE_EXIT=$?"
