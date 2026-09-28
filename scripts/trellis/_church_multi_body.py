"""Multi-view TRELLIS reconstruction of the church, and its intake measurement.

Run by `run_church_multi.sh`, which sets the R-TRELLIS environment and runs the
AI-input guard over every reference first. Kept as a FILE rather than a heredoc
because this project has had heredoc bodies mangled by shell escape handling
three separate times -- a `\\n` inside the OBJ writer is exactly the character
that gets eaten.

The report carries its own comparison baselines so a reader does not have to
fetch them: an intake number is meaningless without the two runs it sits
between.
"""
import json
import os
import time

import torch
from PIL import Image

REPO = "/mnt/c/Users/Admin/UE5LandscapePipeline"
OUT = os.path.join(REPO, "_verify", "20260830_bakeoff")
REFS = os.path.join(REPO, "refs", "church_refs")

VIEWS = ["church_az000.png.jpg", "church_az035.png.jpg",
         "church_az090.png.jpg", "church_az270.png.jpg"]

# The two runs this one is judged against, quoted from their own report files.
BASELINES = {
    "flat_sheet_single_view": {"thin_over_long": 0.0114, "vertices": 74904,
                               "extent": [0.5603, 0.0114, 1.0009],
                               "input_source_pixels": 9200},
    "castle_positive_control": {"thin_over_long": 0.8491, "vertices": 570703,
                                "extent": [0.8773, 0.8509, 1.0022]},
}

rep = {
    "candidate": "TRELLIS multi-view",
    "inputs": VIEWS,
    "n_views": len(VIEWS),
    "model_repo": "JeffreyXiang/TRELLIS-image-large",
    "sampler_params_source": "example_multi_image.py (steps 12 / cfg 7.5, "
                             "steps 12 / cfg 3), as REQUESTED into "
                             "run_multi_image -- not read back off the pipeline, "
                             "so treat as the requested params, not confirmed "
                             "applied (rule 12). The single-view bakeoff used "
                             "pipeline DEFAULTS -- this run differs from its "
                             "baseline in view count AND sampler params.",
    "mode": "stochastic (run_multi_image default)",
    "error": None,
    "baselines": BASELINES,
}

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

    images = []
    for name in VIEWS:
        p = os.path.join(REFS, name)
        im = Image.open(p)
        images.append(im)
        rep.setdefault("input_sizes", []).append([name, im.size[0], im.size[1]])

    t1 = time.time()
    out = pipe.run_multi_image(
        images,
        seed=20260830,
        formats=["mesh"],
        sparse_structure_sampler_params={"steps": 12, "cfg_strength": 7.5},
        slat_sampler_params={"steps": 12, "cfg_strength": 3},
    )
    rep["run_s"] = round(time.time() - t1, 1)

    m = out["mesh"][0]
    vs = m.vertices.detach().cpu().numpy()
    fs = m.faces.detach().cpu().numpy()
    rep["vertices"] = int(vs.shape[0])
    rep["faces"] = int(fs.shape[0])
    rep["bbox_min"] = [round(float(x), 4) for x in vs.min(0)]
    rep["bbox_max"] = [round(float(x), 4) for x in vs.max(0)]
    ext = [float(a - b) for a, b in zip(vs.max(0), vs.min(0))]
    rep["extent"] = [round(e, 4) for e in ext]

    # THE INTAKE NUMBER. min/max extent -- the same ratio that separated the
    # castle (0.8491, a volume) from the church crop (0.0114, a sheet).
    if max(ext) > 0:
        rep["thin_over_long"] = round(min(ext) / max(ext), 4)
        rep["verdict_vs_flat_sheet"] = (
            "VOLUMETRIC" if rep["thin_over_long"] > 0.30 else "STILL FLAT")
    else:
        rep["thin_over_long"] = None
        rep["verdict_vs_flat_sheet"] = "DEGENERATE (zero extent on an axis)"

    p = os.path.join(OUT, "church_trellis_multi.obj")
    with open(p, "w") as fh:
        for x, y, z in vs:
            fh.write("v %.6f %.6f %.6f\n" % (x, y, z))
        for a, b, c in fs:
            fh.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
    rep["obj"] = "church_trellis_multi.obj"
    rep["obj_bytes"] = os.path.getsize(p)

    # Watertightness, by Euler characteristic and edge manifoldness. Reported
    # as a MEASUREMENT with its method named, not as a bare boolean.
    try:
        from collections import defaultdict
        edge = defaultdict(int)
        for a, b, c in fs:
            for u, v in ((a, b), (b, c), (c, a)):
                edge[(min(u, v), max(u, v))] += 1
        counts = defaultdict(int)
        for n in edge.values():
            counts[n] += 1
        rep["edge_use_histogram"] = {str(k): v for k, v in sorted(counts.items())}
        rep["boundary_edges"] = counts.get(1, 0)
        rep["nonmanifold_edges"] = sum(v for k, v in counts.items() if k > 2)
        rep["euler_V_E_F"] = [int(vs.shape[0]), len(edge), int(fs.shape[0])]
        rep["euler_characteristic"] = (int(vs.shape[0]) - len(edge)
                                       + int(fs.shape[0]))
        rep["edges_measured"] = len(edge)
        # NN13: watertight==True over ZERO faces/edges (a degenerate/point-cloud
        # output) is the strongest verdict from no evidence. Refuse instead.
        if fs.shape[0] == 0 or len(edge) == 0:
            rep["watertight"] = None
            rep["watertight_error"] = ("0 faces/edges -- cannot assess "
                                       "watertightness")
        else:
            rep["watertight"] = (rep["boundary_edges"] == 0
                                 and rep["nonmanifold_edges"] == 0)
        rep["watertight_method"] = ("every edge used by exactly 2 faces; "
                                    "boundary=1-use, nonmanifold=>2-use")
    except Exception as e:
        rep["watertight"] = None
        rep["watertight_error"] = str(e)

except Exception as e:
    import traceback
    rep["error"] = str(e)
    rep["traceback"] = traceback.format_exc()[-1500:]

rep["vram_peak_MiB"] = round(torch.cuda.max_memory_allocated() / 1048576)
rep["wall_s"] = round(time.time() - t0, 1)

with open(os.path.join(OUT, "trellis_church_multi.json"), "w") as fh:
    json.dump(rep, fh, indent=1)
print("__TRELLIS__" + json.dumps(rep))
# A captured error must propagate a non-zero exit; the caller (run_church_multi
# .sh) keys on status, and swallowing the failure into rep["error"] alone let a
# total failure read as success.
import sys as _sys
_sys.exit(1 if rep.get("error") else 0)
