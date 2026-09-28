#!/usr/bin/env bash
# Phase D bakeoff -- run TRELLIS on the church input and MEASURE it.
#
# Environment is R-TRELLIS's, verbatim, not re-derived:
#   ATTN_BACKEND=xformers   NOT sdpa -- sdpa is SILENTLY IGNORED by
#                           trellis/modules/sparse, which takes only
#                           xformers/flash_attn, while the DENSE module
#                           accepts it. The run then prints a backend line
#                           that looks fine and uses something else.
#   SPCONV_ALGO=native
#   XFORMERS_DISABLED=1     routes DINOv2 away from xformers only
#   formats=["mesh"]        geometry is the deliverable; the gaussian
#                           rasterizers were never installed.
set -euo pipefail

PY=/opt/miniforge3/envs/trellis/bin/python
IN=/mnt/c/Users/Admin/UE5LandscapePipeline/_verify/20260830_bakeoff/church_input_518.png

# ⛔ AI-INPUT GUARD, BEFORE THE MODEL LOADS. The C0 donor's Fab listing says
# "Allows usage with AI: No", and that restriction cannot be enforced after the
# fact: a generated mesh carries no provenance, so there is no artefact to
# inspect and nothing to revert. The only place the check can work is here,
# ahead of the run, and `set -e` makes a refusal abort the script.
#
# The guard is pure stdlib, so the trellis env's python runs it directly.
"$PY" /mnt/c/Users/Admin/UE5LandscapePipeline/scripts/ai_input_guard.py \
      --strict "$IN"
OUTDIR=/mnt/c/Users/Admin/UE5LandscapePipeline/_verify/20260830_bakeoff
mkdir -p "$OUTDIR"

export ATTN_BACKEND=xformers
export SPCONV_ALGO=native
export XFORMERS_DISABLED=1
export PYTHONPATH=/opt/trellis

cd /opt/trellis
"$PY" - <<'PYEOF'
import json, os, time
import torch
from PIL import Image

OUT = "/mnt/c/Users/Admin/UE5LandscapePipeline/_verify/20260830_bakeoff"
IN = os.path.join(OUT, "church_input_518.png")
rep = {"candidate": "TRELLIS", "input": "church_input_518.png",
       "input_source_pixels": 9200, "error": None}

torch.cuda.reset_peak_memory_stats()
free0, total = torch.cuda.mem_get_info()
rep["vram_free_before_MiB"] = round(free0 / 1048576)
rep["vram_total_MiB"] = round(total / 1048576)

t0 = time.time()
try:
    from trellis.pipelines import TrellisImageTo3DPipeline
    pipe = TrellisImageTo3DPipeline.from_pretrained(
        "JeffreyXiang/TRELLIS-image-large")
    pipe.cuda()
    rep["load_s"] = round(time.time() - t0, 1)

    img = Image.open(IN)
    t1 = time.time()
    out = pipe.run(img, seed=20260830, formats=["mesh"])
    rep["run_s"] = round(time.time() - t1, 1)

    m = out["mesh"][0]
    v = m.vertices.shape[0]
    f = m.faces.shape[0]
    rep["vertices"] = int(v)
    rep["faces"] = int(f)

    # Export .ply for intake measurement on the Windows side.
    import numpy as np
    vs = m.vertices.detach().cpu().numpy()
    fs = m.faces.detach().cpu().numpy()
    rep["bbox_min"] = [round(float(x), 4) for x in vs.min(0)]
    rep["bbox_max"] = [round(float(x), 4) for x in vs.max(0)]
    rep["extent"] = [round(float(a - b), 4)
                     for a, b in zip(vs.max(0), vs.min(0))]
    p = os.path.join(OUT, "church_trellis.obj")
    with open(p, "w") as fh:
        for x, y, z in vs:
            fh.write("v %.6f %.6f %.6f\n" % (x, y, z))
        for a, b, c in fs:
            fh.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
    rep["obj"] = "church_trellis.obj"
    rep["obj_bytes"] = os.path.getsize(p)
except Exception as e:
    import traceback
    rep["error"] = str(e)
    rep["traceback"] = traceback.format_exc()[-1200:]

rep["vram_peak_MiB"] = round(torch.cuda.max_memory_allocated() / 1048576)
rep["wall_s"] = round(time.time() - t0, 1)
with open(os.path.join(OUT, "trellis_church.json"), "w") as fh:
    json.dump(rep, fh, indent=1)
print("__TRELLIS__" + json.dumps(rep))
PYEOF
