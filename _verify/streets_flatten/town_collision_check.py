"""Read-only: does the landscape COLLISION in the town carry the FLATTENED heights (not the pre-streets ones)?

check_collision_truth.py samples the whole map at random and push_heightmap's read-back samples only x,y <= 1008,
so neither sees the town. This picks the N changed vertices with the largest |delta| (outside house footprints),
traces them with the shared trace_grounding.PROBE (landscape hits only), and compares the hit Z with BOTH maps.
PASS = p90 |collision - flattened| <= 0.10 m AND the hit is nearer the flattened height on >= 95 % of points.
Writes only _verify/streets_flatten/town_collision_check.json.
"""
import io, json, os, sys
import numpy as np
from PIL import Image
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "scripts"))
import bootstrap, trace_grounding, verify_landscape  # noqa: E402
Image.MAX_IMAGE_PIXELS = None
N, CHUNK = 120, 20
rec = json.load(io.open(os.path.join(R, "recipes", "alpine_8k.json"), encoding="utf-8"))
ls = rec["landscape"]
ox, oy, oz = [float(v) for v in ls["location_cm"]]
zs, px = float(ls["z_scale_cm"]), float(ls["scale_xy_cm"])
H0 = np.asarray(Image.open(os.path.join(R, rec["heightmap"]["street_flatten"]["pre_source"]))).astype(np.float64)
H1 = np.asarray(Image.open(os.path.join(R, rec["heightmap"]["source"]))).astype(np.float64)
D = np.abs(H1 - H0)
r, c = np.nonzero(D * zs / 65535.0 >= 20.0)                 # changed by >= 20 cm
if len(r) < N:
    sys.exit("REFUSE: only %d vertices changed >= 20 cm" % len(r))
order = np.argsort(-D[r, c])
step = max(1, len(order) // N)
pick = order[::step][:N]
zc = lambda H, j, i: oz + (H[j, i] / 65535.0 - 0.5) * zs
pts, ref = [], []
for k in pick:
    j, i = int(r[k]), int(c[k])
    x, y = ox + i * px, oy + j * px
    pts.append([round(x, 1), round(y, 1), round(float(zc(H1, j, i)), 1)])
    ref.append((float(zc(H0, j, i)), float(zc(H1, j, i))))
remote_exec = bootstrap._load_remote_execution()
remote = remote_exec.RemoteExecution()
remote.start()
rows = []
try:
    node, why = verify_landscape._select_verified_node(remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 25.0)
    if node is None:
        sys.exit("REFUSE (rule 7): %s" % why)
    for ci in range(0, len(pts), CHUNK):
        src = trace_grounding.PROBE.format(pts=pts[ci:ci + CHUNK], up=5000.0, down=30000.0, marker=trace_grounding.MARKER)
        try:
            remote.open_command_connection(node["node_id"])
            res = remote.run_command(src, unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            text = bootstrap._collect_output(res or {})
            i = text.find(trace_grounding.MARKER)
            part = json.JSONDecoder().raw_decode(text[i + len(trace_grounding.MARKER):].lstrip())[0] if i >= 0 else None
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
        if not part or not part.get("ok"):
            sys.exit("COULD NOT MEASURE: chunk %d failed: %s" % (ci // CHUNK, (part or {}).get("error")))
        rows.extend(part["rows"])
finally:
    remote.stop()
lut = {(p[0], p[1]): rf for p, rf in zip(pts, ref)}
d_flat, nearer = [], 0
for x, y, _, hz in rows:
    z0, z1 = lut[(x, y)]
    d_flat.append(abs(hz - z1) / 100.0)
    nearer += int(abs(hz - z1) < abs(hz - z0))
n = len(rows)
out = {"points": N, "landscape_hits": n,
       "missed_xy": [p[:2] for p in pts if (p[0], p[1]) not in {(r_[0], r_[1]) for r_ in rows}][:10]}
if n == 0:
    out["verdict"] = "COULD NOT MEASURE (0 hits)"
else:
    d = np.array(d_flat)
    out.update({"abs_coll_minus_flat_m": {"p50": round(float(np.percentile(d, 50)), 3),
                                          "p90": round(float(np.percentile(d, 90)), 3), "max": round(float(d.max()), 3)},
                "nearer_flat_than_pre": nearer,
                "mean_abs_delta_at_points_m": round(float(np.mean([abs(a - b) for a, b in ref])) / 100.0, 3)})
    ok = out["abs_coll_minus_flat_m"]["p90"] <= 0.10 and nearer >= 0.95 * n
    out["verdict"] = ("PASS" if ok else "FAIL") + ("" if n >= 0.6 * N else
                                                   " on a PARTIAL sample (hit rate %.0f %%)" % (100.0 * n / N))
json.dump(out, io.open(os.path.join(R, "_verify", "streets_flatten", "town_collision_check.json"), "w", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
sys.exit(0 if out["verdict"] == "PASS" else 4)
