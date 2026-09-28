"""Forge stage 3: TRELLIS multi-image generation, driven by a JOB FILE.

Run inside the trellis env by `run_forge.sh`, which sets R-TRELLIS's
environment and has ALREADY run the AI-input guard over every view.

GENERALISED from `_church_multi_body.py` on 2026-08-30 so the wood stacks and
everything after them go through the SAME code path as the church. Two bodies
that must agree about sampler params and export format is the
two-lists-one-badly-stored defect this project keeps paying for.

The job file is written by `scripts/forge.py` from `recipes/forge.json`; this
script invents nothing and refuses anything it was not given.
"""
import json
import os
import sys
import time

import torch
from PIL import Image

JOB = sys.argv[1]
with open(JOB, "r", encoding="utf-8") as fh:
    job = json.load(fh)

rep = {
    "candidate": "TRELLIS multi-view",
    "asset": job["asset_key"],
    "name": job["name"],
    "inputs": job["views"],
    "n_views": len(job["views"]),
    "model_repo": job["model_repo"],
    "seed": job["seed"],
    "sampler": job["sampler"],
    "error": None,
}

if not job["views"]:
    rep["error"] = ("no views declared -- refusing to generate from nothing. "
                    "A forge that produces an asset with no reference is a "
                    "forge with no provenance.")
    print("__FORGE_GEN__" + json.dumps(rep))
    sys.exit(2)

torch.cuda.reset_peak_memory_stats()
free0, total = torch.cuda.mem_get_info()
rep["vram_free_before_MiB"] = round(free0 / 1048576)
rep["vram_total_MiB"] = round(total / 1048576)

t0 = time.time()
try:
    from trellis.pipelines import TrellisImageTo3DPipeline

    pipe = TrellisImageTo3DPipeline.from_pretrained(job["model_repo"])
    pipe.cuda()
    rep["load_s"] = round(time.time() - t0, 1)

    images = []
    for p in job["views"]:
        im = Image.open(p)
        images.append(im)
        rep.setdefault("input_sizes", []).append(
            [os.path.basename(p), im.size[0], im.size[1]])

    t1 = time.time()
    out = pipe.run_multi_image(
        images,
        seed=job["seed"],
        formats=["mesh"],
        sparse_structure_sampler_params=job["sampler"]["sparse_structure"],
        slat_sampler_params=job["sampler"]["slat"],
    )
    rep["run_s"] = round(time.time() - t1, 1)

    m = out["mesh"][0]
    vs = m.vertices.detach().cpu().numpy()
    fs = m.faces.detach().cpu().numpy()
    rep["vertices"] = int(vs.shape[0])
    rep["faces"] = int(fs.shape[0])
    ext = [float(a - b) for a, b in zip(vs.max(0), vs.min(0))]
    rep["extent"] = [round(e, 4) for e in ext]
    rep["thin_over_long"] = round(min(ext) / max(ext), 4)

    op = job["out_obj"]
    os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, "w") as fh:
        for x, y, z in vs:
            fh.write("v %.6f %.6f %.6f\n" % (x, y, z))
        for a, b, c in fs:
            fh.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
    rep["out_obj"] = op
    rep["out_obj_bytes"] = os.path.getsize(op)

    from collections import defaultdict
    edge = defaultdict(int)
    for a, b, c in fs:
        for u, v in ((a, b), (b, c), (c, a)):
            edge[(min(u, v), max(u, v))] += 1
    counts = defaultdict(int)
    for n in edge.values():
        counts[n] += 1
    rep["boundary_edges"] = counts.get(1, 0)
    rep["nonmanifold_edges"] = sum(v for k, v in counts.items() if k > 2)
    rep["watertight"] = (rep["boundary_edges"] == 0
                         and rep["nonmanifold_edges"] == 0)
    rep["euler_characteristic"] = (int(vs.shape[0]) - len(edge)
                                   + int(fs.shape[0]))
    rep["genus"] = ((2 - rep["euler_characteristic"]) // 2
                    if rep["watertight"] else None)
except Exception as exc:
    import traceback
    rep["error"] = str(exc)
    rep["traceback"] = traceback.format_exc()[-1500:]

rep["vram_peak_MiB"] = round(torch.cuda.max_memory_allocated() / 1048576)
rep["wall_s"] = round(time.time() - t0, 1)

with open(job["out_report"], "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=1)
print("__FORGE_GEN__" + json.dumps(rep))
