"""check_collision_truth.py — does the landscape COLLIDE what it RENDERS?

THE QUESTION NOTHING IN THIS PROJECT HAD EVER ASKED.

On 2026-08-06 the landscape was found to RENDER `alpine_heightmap_v2` and
COLLIDE the pre-stamp `alpine_heightmap` — p90 **30.98 m** apart, max
**217.21 m**. It had been that way for three days, through a terrain
adoption, a weight re-bake, a 157,554-instance re-placement and 1328
saved packages, with every gate green. Every gate was green because every
gate read the HEIGHTMAP, or something derived from it.

This is non-negotiable 0 made executable: a confirming instrument that
reads a DIFFERENT REPRESENTATION. It asks the collision surface where the
ground is and compares that to the heightmap that defines the visible
one. Cheap — 100 traces — and it is the only check here whose source
artefact is not the heightmap.

WHY RANDOM WORLD POINTS AND NOT INSTANCES
`trace_grounding` samples where the TREES are, which is where the
acceptance mask put them — a biased sample of the world, and blind to any
region foliage never reached. This samples the FOOTPRINT, so a collision
fault in an empty quarter of the map is still found.

THRESHOLD, AND WHY IT IS NOT INVENTED
p90 <= 0.30 m. The pre-stamp map's own measured self-agreement was
p50 0.017 / p90 0.097 / max 0.30, so a correctly-built collision surface
demonstrably reaches this class. The bar is what the engine has been
observed to achieve, not a number that felt safe.

FAIL DIRECTION FOLLOWS THE FAILURE MODE: disagreement-positive is a FAIL.
And a NULL READ IS NOT A PASS — if too few traces resolve, this reports
"could not measure" and fails, because a landscape that returns no hits
is exactly as broken as one that returns wrong ones, and silence is how
the original defect survived.

REUSES `trace_grounding.PROBE` rather than copying it. Two payloads that
must agree are one payload, badly stored (non-negotiable 24).

Exit codes:
  0  PASS — collision agrees with the rendered heightmap
  1  unexpected error, OR a pre-flight REFUSE (chunk payload over the ceiling)
  2  recipe/heightmap unreadable
  3  editor identity gate refused
  4  COULD NOT MEASURE — a chunk command failed, or too few traces resolved
     (never a pass)
  5  FAIL — collision disagrees with the heightmap beyond threshold
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import landscape_spec     # noqa: E402
import trace_grounding    # noqa: E402 — shared trace payload
import verify_landscape   # noqa: E402

CHUNK = 20


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=landscape_spec.DEFAULT_RECIPE)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--p90-max-m", type=float, default=0.30)
    ap.add_argument("--min-hit-rate", type=float, default=0.60)
    ap.add_argument("--seed", type=int, default=None,
                    help="Omit for a FRESH random sample each run (better "
                         "coverage for a standing guard); the seed used is "
                         "printed so any run is reproducible.")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    ls, hm = recipe["landscape"], recipe["heightmap"]
    ox = float(ls["location_cm"][0])
    oy = float(ls["location_cm"][1])
    actor_z = float(ls["location_cm"][2])
    z_scale = float(ls["z_scale_cm"])
    sc = float(ls["scale_xy_cm"])
    res = int(hm["resolution"])
    span = (res - 1) * sc

    try:
        import numpy as np
        from PIL import Image
        arr = np.asarray(Image.open(os.path.join(
            bootstrap.REPO_ROOT, str(hm["source"])))).astype(np.float64)
    except Exception as exc:                          # noqa: BLE001
        print("REFUSE: cannot read heightmap: {0}".format(exc))
        return 2

    seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    margin = 200.0 * sc / 100.0
    pts = []
    for _ in range(args.n):
        x = rng.uniform(ox + margin, ox + span - margin)
        y = rng.uniform(oy + margin, oy + span - margin)
        c = min(max((x - ox) / sc, 0.0), res - 1.001)
        r = min(max((y - oy) / sc, 0.0), res - 1.001)
        c0, r0 = int(c), int(r)
        fc, fr = c - c0, r - r0
        v = (arr[r0, c0] * (1 - fc) * (1 - fr)
             + arr[r0, c0 + 1] * fc * (1 - fr)
             + arr[r0 + 1, c0] * (1 - fc) * fr
             + arr[r0 + 1, c0 + 1] * fc * fr)
        hz = actor_z + (v / 65535.0 - 0.5) * z_scale
        # ROUNDED because the points are interpolated INTO the payload and
        # the channel has a size ceiling. Unrounded uniform floats repr to
        # ~18 chars each and pushed the chunk over it; the failure surfaced
        # as a bare "no result", which is why the size is now asserted
        # below rather than discovered.
        # float() IS LOad-BEARING, NOT TIDINESS. `hz` comes off a numpy
        # array, so it is np.float64, and numpy 2.x reprs that as
        # "np.float64(-172345.6)". These values are interpolated INTO the
        # payload via {pts!r}, so that repr crosses to the editor, where
        # `np` does not exist — the command dies with
        #     NameError: name 'np' is not defined
        # and the host sees only success=False with zero bytes back, which
        # reads as a transport fault. It cost three wrong diagnoses here
        # (send size, ray length, receive buffer) before the editor's own
        # traceback was read.
        # Rounding is separate and only trims payload bytes.
        pts.append([round(float(x), 1), round(float(y), 1),
                    round(float(hz), 1)])

    # RAY LENGTH AND CHUNK ARE THE PROVEN ONES, not chosen for reach.
    # An 800 m ray x 40 points over 1024 components made the editor-side
    # command FAIL outright (success=False, zero bytes back) - it reads as
    # a transport fault and is a timeout. 350 m x 20 is what
    # trace_grounding has executed repeatedly. 300 m of downward reach
    # still covers the worst disagreement measured here (217 m).
    print("COLLISION TRUTH CHECK  (source artefact: LANDSCAPE COLLISION,")
    print("  compared against: {0})".format(hm["source"]))
    print("  samples {0}   seed {1}   p90 threshold {2:.2f} m".format(
        args.n, seed, args.p90_max_m))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))

        rows, nohit = [], 0
        chunks = [pts[i:i + CHUNK] for i in range(0, len(pts), CHUNK)]
        probe_bytes = len(trace_grounding.PROBE.format(
            pts=chunks[0], up=5000.0, down=30000.0,
            marker=trace_grounding.MARKER).encode("utf-8"))
        print("  chunk payload  : {0} bytes (ceiling 8683)".format(
            probe_bytes))
        if probe_bytes > 8683:
            print("REFUSE: chunk payload over the proven ceiling. Lower "
                  "CHUNK; an oversized command is reported by the editor "
                  "as a missing FILE, not as a size fault.")
            return 1
        for ci, chunk in enumerate(chunks):
            src = trace_grounding.PROBE.format(
                pts=chunk, up=5000.0, down=30000.0,
                marker=trace_grounding.MARKER)
            try:
                remote.open_command_connection(node["node_id"])
                res_cmd = remote.run_command(
                    src, unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                text = bootstrap._collect_output(res_cmd or {})
                i = text.find(trace_grounding.MARKER)
                part = json.JSONDecoder().raw_decode(
                    text[i + len(trace_grounding.MARKER):].lstrip())[0] \
                    if i >= 0 else None
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass
            if not part or not part.get("ok"):
                print("  chunk {0} FAILED: {1}".format(
                    ci, (part or {}).get("error", "no result")))
                print("")
                print("COULD NOT MEASURE — a chunk failed, so the sample is "
                      "incomplete. Not reported as a pass.")
                return 4
            rows.extend(part.get("rows") or [])
            nohit += part.get("nohit") or 0

        hit_rate = len(rows) / float(len(pts))
        print("  landscape hits : {0} of {1}  ({2:.0%})".format(
            len(rows), len(pts), hit_rate))
        if hit_rate < args.min_hit_rate:
            print("")
            print("COULD NOT MEASURE: only {0:.0%} of traces found the "
                  "landscape (floor {1:.0%}). A null read is NOT a pass — "
                  "a landscape that returns no hits is as broken as one "
                  "that returns wrong ones.".format(
                      hit_rate, args.min_hit_rate))
            return 4

        # rows are [x, y, heightmap_z, collision_z] — the third column is
        # the heightmap height this script computed, not a plan value.
        diffs = sorted(abs(r[2] - r[3]) / 100.0 for r in rows)
        n = len(diffs)
        p50 = diffs[n // 2]
        p90 = diffs[min(n - 1, int(n * 0.90))]
        worst = diffs[-1]
        print("")
        print("  |collision - heightmap| :  p50 {0:.3f}   p90 {1:.3f}   "
              "max {2:.3f}  (m)".format(p50, p90, worst))
        print("")
        if p90 > args.p90_max_m:
            print("FAIL: THE LANDSCAPE DOES NOT COLLIDE WHAT IT RENDERS.")
            print("  p90 {0:.3f} m exceeds {1:.2f} m. Traces, physics and "
                  "the player walk on a surface that is not the one on "
                  "screen.".format(p90, args.p90_max_m))
            print("  Do NOT reproject anything onto this collision surface "
                  "(R-FOLIAGE-GROUND P0). Rebuild collision first.")
            return 5
        print("PASS: collision agrees with the rendered heightmap "
              "(p90 {0:.3f} m <= {1:.2f} m).".format(p90, args.p90_max_m))
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
