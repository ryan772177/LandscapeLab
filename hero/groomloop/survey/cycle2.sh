#!/usr/bin/env bash
# cycle2.sh <name> -- one ROUND-2 SIDES cycle, exactly the briefed loop.
# Preview stdout goes to logs/<N>_preview.txt because judge.py reads
# __PREVIEW__ from a FILE and /tmp does not persist between bash calls here.
set -u
cd /c/Users/Admin/UE5LandscapePipeline || exit 1
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
W="C:/Users/Admin/UE5LandscapePipeline/hero/groomloop"
R="C:/Users/Admin/UE5LandscapePipeline"
N="$1"

timeout 600 "$BL" --background --python "$R/hero/groomloop/scripts/edit_engine.py" -- \
  "$W/hero_src/hero_base.blend" "$W/params/$N.json" \
  "$W/blends/$N.blend" "$W/exports/$N.abc" "$W/logs/$N.json" \
  > "hero/groomloop/logs/${N}_edit.txt" 2>&1
grep -E '__EDIT__|REFUSE|Error' "hero/groomloop/logs/${N}_edit.txt" | tail -2
[ -f "hero/groomloop/blends/$N.blend" ] || { echo "EDIT FAILED: no blend"; exit 2; }

timeout 900 "$BL" --background "$W/blends/$N.blend" \
  --python "$R/scripts/blender/preview_hair.py" -- \
  "$R/_verify/20260822_agents/$N" > "hero/groomloop/logs/${N}_preview.txt" 2>&1
[ -f "_verify/20260822_agents/$N/preview_front.png" ] || { echo "RENDER FAILED"; exit 3; }

python hero/groomloop/scripts/front_metrics.py \
  "_verify/20260822_agents/$N/preview_front.png" \
  "hero/groomloop/survey/${N}_front.json" > /dev/null || exit 4

python hero/groomloop/scripts/judge.py \
  "hero/groomloop/survey/${N}_front.json" \
  "hero/groomloop/logs/${N}_preview.txt"
echo "JUDGE_EXIT=$?"
python hero/groomloop/survey/sides_profile.py \
  "_verify/20260822_agents/$N/preview_front.png" "$N"
