#!/usr/bin/env bash
set -e
PY=/opt/miniforge3/envs/trellis/bin/python
cd /mnt/c/Users/Admin/UE5LandscapePipeline
for n in alpine_village_01 alpine_village_02; do "$PY" /mnt/c/Users/Admin/Gemini2UE/scripts/depth_moge.py refs/$n.jpg _verify/20261010_camera_solve/$n 2>&1 | grep -E "__DEPTH__|Error" | cut -c1-400; done
