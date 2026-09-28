"""site_ground_cameras.py — ground-level stations across the terrain, sited by
what the masks say is there and grounded by an ENGINE LINE TRACE.

MUTATES the recipe's `capture.cameras` only with --write-recipe. It spawns
nothing, saves no asset, and moves nothing in the world.

=====================================================================
WHY THE TRACE, AND NOT JUST THE HEIGHTMAP
=====================================================================
A ground camera whose Z is wrong by a few metres is either buried in the hill
or floating over it, and both look like a broken level rather than a bad
number. The heightmap can predict Z, but predicting it uses an assumption this
project has NOT verified for this landscape: that the PNG's column maps to
world X and its row to world Y. `recipes/alpinelab_8129.json` carries that as
an explicit `_axis_caveat`.

So the heightmap only chooses WHERE to stand. The engine's own collision
decides HOW HIGH, by tracing straight down at each station:

    SystemLibrary.line_trace_single(world, start, end, TRACE_TYPE_QUERY1, ...)

and the two answers are printed side by side. That comparison is the first
thing in this project to test the row/column mapping against a partly-
independent representation: the collision heightfield and the PNG share an
ancestor (recipe `_axis_caveat`), so this discriminates the row/column
MAPPING but is NOT two independent sources in the non-negotiable-0 sense. A
systematic disagreement above ~25 m (the VERDICT pass boundary below) means
the axes are transposed; agreement under it means they are not.

A station whose trace MISSES is dropped, loudly. A camera placed at a guessed
height because the trace failed is exactly the "report the number the broken
measurement produced" failure.

=====================================================================
HOW STATIONS ARE CHOSEN
=====================================================================
One per terrain character, so scrolling between them shows different ground
rather than six views of the same slope. Each is the best-scoring cell for its
feature, subject to a minimum separation so they do not cluster:

    valley_drain    high flow, low altitude      -- drainage, wet rock
    sediment_flat   high deposits, low slope     -- the sediment surface
    snow_edge       snow_depth near its midpoint -- the snow boundary
    ridge_wear      high wear, high altitude     -- stripped ridge
    mid_slope       moderate slope, mid altitude -- the ordinary case
    basin_open      low slope, low altitude      -- open ground, grass

Each looks toward the terrain's highest point so there is something in frame,
at a shallow downward pitch.

Exit codes:
  0  stations sited and traced
  1  could not look, or the trace payload errored / returned an unusable
     result count
  2  refused before contacting the editor
  3  rule 7: no verified editor node
  4  one or more traces missed — no cameras written
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alpinelab_source  # noqa: E402
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_SITE__"
DEFAULT_RECIPE = "recipes/alpinelab_8129.json"
EYE_M = 1.7
MIN_SEPARATION_M = 600.0

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_pts = _json.loads(r"""__PTS__""")
_top = __TOP__
_bottom = __BOTTOM__
_out = {"error": None, "hits": []}
try:
    _world = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world()
    for _p in _pts:
        _start = _unreal.Vector(float(_p[0]), float(_p[1]), _top)
        _end = _unreal.Vector(float(_p[0]), float(_p[1]), _bottom)
        _rec = {"x": _p[0], "y": _p[1], "z": None, "why": None}
        try:
            _hit = _unreal.SystemLibrary.line_trace_single(
                _world, _start, _end,
                _unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                _unreal.DrawDebugTrace.NONE, True)
        except Exception as _exc:
            _rec["why"] = "trace raised: %s: %s" % (type(_exc).__name__, _exc)
            _out["hits"].append(_rec)
            continue
        if _hit is None:
            _rec["why"] = "no hit between %.0f and %.0f" % (_top, _bottom)
            _out["hits"].append(_rec)
            continue
        # FHitResult's fields are PROTECTED in 5.8 -- get_editor_property
        # refuses every one ("Property 'Location' ... is protected and cannot
        # be read"), and the first version of this script used
        # get_editor_property("location") and reported six clean MISSES on six
        # traces that had all HIT. break_hit_result was tried next and does
        # NOT exist on this build. What the struct DOES expose, confirmed by
        # dir() against the running editor, is to_dict() -- used below. Two
        # guesses were spent before asking the object; the probe settled it.
        try:
            _dd = _hit.to_dict()
            _rec["keys"] = sorted(_dd.keys())
            _loc = None
            for _k in _dd:
                if _k.lower() in ("location", "impact_point"):
                    _loc = _dd[_k]
                    _rec["from_key"] = _k
                    break
            if _loc is None:
                _rec["why"] = "to_dict() has no location-like key"
            else:
                _rec["z"] = float(_loc.z)
        except Exception as _exc:
            _rec["why"] = "to_dict failed: %s: %s" % (
                type(_exc).__name__, str(_exc)[:120])
        _out["hits"].append(_rec)
    del _world
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_SITE__" + _json.dumps(_out))
'''


def _load(path):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    return np.asarray(Image.open(path)).astype(np.float32) / 65535.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--downsample", type=int, default=8,
                    help="analyse every Nth texel; 8129/8 is plenty to site a camera")
    ap.add_argument("--write-recipe", action="store_true",
                    help="replace the ground_* cameras in capture.cameras")
    args = ap.parse_args(argv)

    rpath = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    with io.open(rpath, encoding="utf-8") as fh:
        recipe = json.load(fh, object_pairs_hook=collections.OrderedDict)

    try:
        pkg, mask_png, height_png = alpinelab_source.resolve(recipe, args.recipe)
    except alpinelab_source.SourceError as exc:
        print("REFUSE:", exc)
        return 2

    land = recipe["landscape"]
    scale_xy = float(land["scale_xy"])
    scale_z = float(land["scale_z"])
    origin = float(land["origin_cm"])

    print("reading heightmap and masks (downsample %d) ..." % args.downsample)
    d = args.downsample
    h = _load(os.path.join(pkg, height_png))[::d, ::d]
    flow = _load(os.path.join(pkg, mask_png["flow"]))[::d, ::d]
    wear = _load(os.path.join(pkg, mask_png["wear"]))[::d, ::d]
    dep = _load(os.path.join(pkg, mask_png["deposits"]))[::d, ::d]
    snow = np.maximum(_load(os.path.join(pkg, mask_png["snow_depth"]))[::d, ::d],
                      _load(os.path.join(pkg, mask_png["snow_hard"]))[::d, ::d])

    n = h.shape[0]
    # World Z in cm, the same arithmetic the landscape uses: value 32768 is 0,
    # and the full uint16 range spans 512 m at scale 100.
    z_cm = (h * 65535.0 - 32768.0) / 128.0 * scale_z
    # Slope from the downsampled grid.
    gy, gx = np.gradient(z_cm, scale_xy * d)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    alt = (z_cm - z_cm.min()) / max(z_cm.max() - z_cm.min(), 1e-6)

    features = collections.OrderedDict([
        ("valley_drain", flow * 3.0 + (1.0 - alt) - snow * 2.0),
        ("sediment_flat", dep * 200.0 + (1.0 - slope / 90.0) - snow * 2.0),
        ("snow_edge", 1.0 - np.abs(snow - 0.5) * 4.0),
        ("ridge_wear", wear * 8.0 + alt * 2.0),
        ("mid_slope", 1.0 - np.abs(slope - 25.0) / 25.0),
        ("basin_open", (1.0 - alt) + (1.0 - slope / 90.0) * 2.0 - snow * 2.0),
    ])

    # The global peak, so every station has something to look at.
    pk = np.unravel_index(int(np.argmax(z_cm)), z_cm.shape)

    def world_xy(row, col):
        # column -> X, row -> Y. UNVERIFIED for this landscape; the trace below
        # is what tests it.
        return (origin + col * d * scale_xy, origin + row * d * scale_xy)

    peak_xy = world_xy(pk[0], pk[1])

    chosen = []
    taken = []
    for name, score in features.items():
        s = np.array(score, dtype=np.float32)
        # Keep stations apart so they do not all land on one slope.
        for (ty, tx) in taken:
            yy, xx = np.ogrid[:n, :n]
            far = ((yy - ty) * d * scale_xy / 100.0) ** 2 + \
                  ((xx - tx) * d * scale_xy / 100.0) ** 2
            s[far < MIN_SEPARATION_M ** 2] = -1e9
        idx = np.unravel_index(int(np.argmax(s)), s.shape)
        taken.append(idx)
        wx, wy = world_xy(idx[0], idx[1])
        chosen.append({
            "name": "ground_" + name,
            "row": int(idx[0]), "col": int(idx[1]),
            "x": float(wx), "y": float(wy),
            "predicted_z_cm": float(z_cm[idx]),
            "slope_deg": float(slope[idx]),
            "snow": float(snow[idx]),
        })

    print()
    print("%-22s %10s %10s %12s %8s %6s"
          % ("station", "world X", "world Y", "predicted Z", "slope", "snow"))
    for c in chosen:
        print("%-22s %10.0f %10.0f %12.0f %7.1f° %6.2f"
              % (c["name"], c["x"], c["y"], c["predicted_z_cm"],
                 c["slope_deg"], c["snow"]))
    print()

    span_cm = scale_z / 100.0 * 51200.0
    top = span_cm
    bottom = -span_cm

    payload = (PAYLOAD
               .replace("__PTS__", json.dumps([[c["x"], c["y"]] for c in chosen]))
               .replace("__TOP__", repr(float(top)))
               .replace("__BOTTOM__", repr(float(bottom))))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(payload, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            print("NO MARKER — could not look.")
            print(text[:2500])
            return 1
        d_out, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d_out.get("error"):
        print("PAYLOAD ERROR:", d_out["error"])
        return 1

    hits = d_out.get("hits", [])
    if len(hits) != len(chosen):
        print("Trace returned %d results for %d stations." % (len(hits), len(chosen)))
        return 1

    print("=== ENGINE LINE TRACE vs HEIGHTMAP PREDICTION ===")
    print("Disagreement here is the first test of the column->X / row->Y")
    print("assumption. Under ~25 m is interpolation; hundreds is transposed axes.")
    print()
    print("%-22s %12s %12s %10s" % ("station", "predicted", "traced", "delta m"))
    missed = []
    deltas = []
    for c, hit in zip(chosen, hits):
        if hit.get("z") is None:
            print("%-22s %12.0f %12s  %s"
                  % (c["name"], c["predicted_z_cm"], "MISS", hit.get("why")))
            missed.append(c["name"])
            continue
        delta_m = (hit["z"] - c["predicted_z_cm"]) / 100.0
        deltas.append(delta_m)
        c["traced_z_cm"] = float(hit["z"])
        print("%-22s %12.0f %12.0f %10.2f"
              % (c["name"], c["predicted_z_cm"], hit["z"], delta_m))
    print()

    if missed:
        print("TRACE MISSED at: %s" % ", ".join(missed))
        print("No cameras written. A camera placed at a guessed height because")
        print("the trace failed is the defect this tool exists to avoid.")
        return 4

    a = np.array(deltas)
    print("delta: mean %.2f m, median %.2f m, max |%.2f| m over %d stations"
          % (a.mean(), np.median(a), np.abs(a).max(), len(a)))
    if np.abs(a).max() < 25.0:
        print("VERDICT: the heightmap and the engine agree. column->X, row->Y")
        print("         is CONSISTENT with collision — the axis caveat in the")
        print("         recipe is now tested, not merely declared.")
    else:
        print("VERDICT: they DISAGREE by more than interpolation explains.")
        print("         Treat the row/column mapping as unresolved. The cameras")
        print("         below still use the TRACED height, so they are on the")
        print("         ground either way — but the station CHOICE may describe")
        print("         a different part of the map than intended.")

    cams = []
    for c in chosen:
        dx = peak_xy[0] - c["x"]
        dy = peak_xy[1] - c["y"]
        yaw = float(np.degrees(np.arctan2(dy, dx)))
        cams.append(collections.OrderedDict([
            ("name", c["name"]),
            # Filter on THIS, not on the name prefix. The first version of this
            # tool replaced every camera whose name began with "ground_" and
            # silently ate `ground_origin`, a hand-authored station that
            # already had a 4K frame in _verify/ referenced from CURRENT STATE.
            # A name prefix is a convention; an explicit provenance field is a
            # fact, and only the second is safe to delete on.
            ("_generated_by", "scripts/site_ground_cameras.py"),
            ("_what", "eye height on %s; slope %.1f deg, snow %.2f, traced ground %.1f m"
             % (c["name"].replace("ground_", ""), c["slope_deg"], c["snow"],
                c["traced_z_cm"] / 100.0)),
            ("location_cm", [round(c["x"], 1), round(c["y"], 1),
                             round(c["traced_z_cm"] + EYE_M * 100.0, 1)]),
            ("rotation_deg", [-4.0, round(yaw, 1), 0.0]),
            ("fov_deg", 75.0),
        ]))

    if not args.write_recipe:
        print()
        print("NOT WRITTEN. Re-run with --write-recipe to add these to the recipe.")
        return 0

    cap = recipe.setdefault("capture", collections.OrderedDict())
    existing = [c for c in cap.get("cameras", [])
                if c.get("_generated_by") != "scripts/site_ground_cameras.py"]
    cap["cameras"] = existing + cams
    with io.open(rpath, "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print()
    print("WROTE %d ground_* cameras into %s" % (len(cams), args.recipe))
    for c in cams:
        print("   %-22s %s" % (c["name"], c["location_cm"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
