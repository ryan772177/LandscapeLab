#!/usr/bin/env bash
# POSITIVE CONTROL for the Phase D bakeoff.
#
# The church run returned a mesh measuring 1.0009 x 0.5603 x 0.0114 -- a FLAT
# SHEET, thinnest/longest 0.0114, where an onion-domed tower needs its two
# horizontal extents comparable. The intake numbers refuse it.
#
# THAT REFUSAL HAS TWO POSSIBLE CAUSES AND THEY MUST NOT BE CONFLATED:
#   (a) the input carried only 9,200 source pixels, or
#   (b) the pipeline, this environment, or my OBJ export is broken.
#
# "A control that fails everywhere is an instrument fault until proven
# otherwise." So this runs TRELLIS's OWN example image -- a castle, the same
# object class as a church, known-good by construction -- through the IDENTICAL
# code path and measures it the same way. If the castle comes back volumetric,
# the church's flatness is the input. If it comes back flat too, nothing about
# the church run means anything.
set -euo pipefail

PY=/opt/miniforge3/envs/trellis/bin/python

# AI-INPUT GUARD. The control uses TRELLIS's own bundled example, which carries
# no restriction -- but the check runs anyway, because a guard that only runs
# on the paths someone remembered to guard is not a guard.
"$PY" /mnt/c/Users/Admin/UE5LandscapePipeline/scripts/ai_input_guard.py \
      --strict /opt/trellis/assets/example_image/typical_building_castle.png

export ATTN_BACKEND=xformers
export SPCONV_ALGO=native
export XFORMERS_DISABLED=1
export PYTHONPATH=/opt/trellis
cd /opt/trellis

"$PY" - <<'PYEOF'
import json, os, time
import numpy as np
import torch
from PIL import Image

OUT = "/mnt/c/Users/Admin/UE5LandscapePipeline/_verify/20260830_bakeoff"
IN = "/opt/trellis/assets/example_image/typical_building_castle.png"
rep = {"control": "TRELLIS example castle", "input": IN, "error": None}

torch.cuda.reset_peak_memory_stats()
t0 = time.time()
try:
    from trellis.pipelines import TrellisImageTo3DPipeline
    pipe = TrellisImageTo3DPipeline.from_pretrained(
        "JeffreyXiang/TRELLIS-image-large")
    pipe.cuda()
    img = Image.open(IN)
    t1 = time.time()
    out = pipe.run(img, seed=20260830, formats=["mesh"])
    rep["run_s"] = round(time.time() - t1, 1)
    m = out["mesh"][0]
    vs = m.vertices.detach().cpu().numpy()
    fs = m.faces.detach().cpu().numpy()
    ext = vs.max(0) - vs.min(0)
    rep["vertices"] = int(vs.shape[0])
    rep["faces"] = int(fs.shape[0])
    rep["extent"] = [round(float(x), 4) for x in ext]
    rep["thin_over_long"] = round(float(ext.min() / ext.max()), 4)
    p = os.path.join(OUT, "control_castle.obj")
    with open(p, "w") as fh:
        for x, y, z in vs:
            fh.write("v %.6f %.6f %.6f\n" % (x, y, z))
        for a, b, c in fs:
            fh.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
    rep["obj"] = "control_castle.obj"
except Exception as e:
    import traceback
    rep["error"] = str(e)
    rep["traceback"] = traceback.format_exc()[-1000:]

rep["vram_peak_MiB"] = round(torch.cuda.max_memory_allocated() / 1048576)
rep["wall_s"] = round(time.time() - t0, 1)
with open(os.path.join(OUT, "trellis_control.json"), "w") as fh:
    json.dump(rep, fh, indent=1)
print("__CONTROL__" + json.dumps(rep))
PYEOF
