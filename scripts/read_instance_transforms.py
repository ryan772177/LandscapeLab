"""read_instance_transforms.py — do the instances sit where the plan says?

READ-ONLY. Mutates nothing, saves nothing.

WHY THIS EXISTS
---------------
The pass audit (2026-08-06) left the same caveat on Pass 3 AND Pass 4:

    "no instrument yet reads the engine's actual instance TRANSFORMS —
     both grounding instruments take instance Z from the PLAN and differ
     only in ground source, so 'instances are where the plan says they
     are' rests on pixels alone."

That is exactly non-negotiable 0. `verify_grounding` reads plan-vs-
heightmap. `trace_grounding` reads plan-vs-collision. **Both take the
instance position from the plan file**, so they can only ever disagree
about the GROUND — never about whether the engine actually placed the
instance there. A placement pass that silently dropped, displaced or
double-placed instances would satisfy both.

`get_instance_count()` closed the COUNT (157,554 conifers / 759
boulders). Count is not position.

WHAT THIS READS
---------------
The engine's own `get_instance_transform(i, world_space=True)` off every
foliage component whose static mesh matches the plan's mesh — a
representation that shares NOTHING with the plan file. It then matches
each sampled engine instance to its NEAREST plan entry in XY and reports
the residuals.

Nearest-neighbour, not index-order: instance ORDER is not a contract.
The engine may reorder, and matching by index would manufacture
disagreement out of a permutation. XY is the matching key and Z is the
measurement, so the Z residual is never used to find its own match.

HOW TO READ THE NUMBERS
-----------------------
  XY residual ~ 0        every sampled instance coincides with a planned
                         one; the placement is faithful in plan.
  XY residual LARGE      instances exist where the plan has none — a
                         displacement, a stale placement, or the wrong
                         plan for this world.
  Z residual ~ 0         the engine's Z equals the planned Z. NOTE this
                         is plan-vs-ENGINE, not instance-vs-GROUND;
                         grounding is `trace_grounding`'s question and
                         this instrument deliberately does not answer it.

SAMPLING IS DECLARED, NOT HIDDEN (non-negotiable 14). Reading 157,554
transforms across the wire is not the point and would be truncated
somewhere; this takes a SEEDED uniform sample over the global instance
index space and prints the sample size, the seed and the population with
every verdict. A sample is a sample and says so.

Exit codes:
  0  measured; every sampled instance matches a plan entry within
     tolerance
  2  editor gate refused (rule 7), or bad arguments
  3  measured; RESIDUALS EXCEED TOLERANCE
  4  COULD NOT MEASURE (no components found, no transforms read) —
     never a pass
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_INSTXFORM__"

PAYLOAD = '''
import json as _json
import random as _random
import unreal as _unreal

_out = {{"components": [], "samples": [], "total": 0, "error": None,
         "mesh_seen": []}}
try:
    _want = {mesh!r}
    _sub = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _comps = []
    for _a in _sub.get_all_level_actors():
        try:
            _cs = _a.get_components_by_class(
                _unreal.InstancedStaticMeshComponent)
        except Exception:
            continue
        for _c in _cs:
            try:
                _sm = _c.get_editor_property("static_mesh")
            except Exception:
                _sm = None
            if _sm is None:
                continue
            _path = _sm.get_path_name().split(".")[0]
            if _path not in _out["mesh_seen"]:
                _out["mesh_seen"].append(_path)
            if _path != _want:
                continue
            try:
                _n = int(_c.get_instance_count())
            except Exception:
                continue
            if _n > 0:
                _comps.append((_c, _n))
    _out["components"] = [_n for _c, _n in _comps]
    _total = sum(_n for _c, _n in _comps)
    _out["total"] = _total

    # seeded uniform sample over the GLOBAL index space
    _k = min(int({sample}), _total)
    _rng = _random.Random(int({seed}))
    _picks = sorted(_rng.sample(range(_total), _k)) if _total else []
    _i = 0
    _ci = 0
    _base = 0
    for _c, _n in _comps:
        while _i < len(_picks) and _picks[_i] < _base + _n:
            _local = _picks[_i] - _base
            try:
                _t = _c.get_instance_transform(_local, True)
                _loc = _t.translation
                _sc = _t.scale3d
                _out["samples"].append([
                    float(_loc.x), float(_loc.y), float(_loc.z),
                    float(_sc.x)])
            except Exception as _e:
                _out["samples"].append(None)
            _i += 1
        _base += _n
except Exception as _exc:
    _out["error"] = str(_exc)[:400]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _plan_points(plan):
    """(N,3) cm array of planned positions, from either plan shape."""
    rows = plan.get("instances")
    if not isinstance(rows, list) or not rows:
        for v in plan.values():
            if isinstance(v, list) and v and isinstance(v[0], list):
                rows = v
                break
    if not isinstance(rows, list) or not rows:
        return None
    arr = np.array([r[:3] for r in rows], dtype=np.float64)
    return arr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", default="foliage/alpine_Conifer.json")
    ap.add_argument("--sample", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260806)
    ap.add_argument("--perturb-cm", type=float, default=0.0,
                    help="NEGATIVE CONTROL: shift the PLAN by this many "
                         "cm in X, Y and Z before matching. A sound "
                         "instrument must then report residuals equal to "
                         "the shift. A perfect 0.000 is what a broken "
                         "comparison prints too (non-negotiable 2), so "
                         "this is how the reading is earned.")
    ap.add_argument("--tol-xy-cm", type=float, default=1.0)
    ap.add_argument("--tol-z-cm", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    plan_path = os.path.join(bootstrap.REPO_ROOT, args.plan) \
        if not os.path.isabs(args.plan) else args.plan
    if not os.path.isfile(plan_path):
        print("REFUSE: plan not found: {0}".format(plan_path))
        return 2
    with open(plan_path, encoding="utf-8") as fh:
        plan = json.load(fh)
    mesh = plan.get("mesh")
    pts = _plan_points(plan)
    if mesh is None or pts is None:
        print("REFUSE: plan has no mesh or no instance rows.")
        return 2

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("plan      : {0}".format(args.plan))
    print("mesh      : {0}".format(mesh))
    print("plan rows : {0}   declared count: {1}".format(
        len(pts), plan.get("count")))
    print("READ-ONLY. Sample is SEEDED and DECLARED: n={0}, seed={1}."
          .format(args.sample, args.seed))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(
                PAYLOAD.format(mesh=mesh, sample=args.sample,
                               seed=args.seed, marker=MARKER),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            if not r or not r.get("success"):
                print("command failed: {0}".format((r or {}).get("result")))
                return 2
            data = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None:
        print("COULD NOT MEASURE: no parseable result from the editor.")
        return 4
    if data.get("error"):
        print("COULD NOT MEASURE: editor-side error: {0}"
              .format(data["error"]))
        return 4

    total = data.get("total") or 0
    comps = data.get("components") or []
    print("engine components matching the mesh: {0}".format(len(comps)))
    print("engine instance total              : {0}".format(total))
    if total == 0:
        print("")
        print("COULD NOT MEASURE: no instances of this mesh among the")
        print("LOADED actors. World Partition — an unloaded cell is")
        print("invisible here, so this is 'none loaded', not 'none")
        print("placed'. Meshes actually seen:")
        for m in (data.get("mesh_seen") or [])[:15]:
            print("  {0}".format(m))
        return 4

    raw = data.get("samples") or []
    got = [s for s in raw if s is not None]
    if not got:
        print("COULD NOT MEASURE: no transform read back.")
        return 4
    if len(got) != len(raw):
        print("NOTE: {0} of {1} sampled transforms failed to read."
              .format(len(raw) - len(got), len(raw)))

    eng = np.array([s[:3] for s in got], dtype=np.float64)

    if args.perturb_cm:
        pts = pts + float(args.perturb_cm)
        print("")
        print("NEGATIVE CONTROL ACTIVE: plan shifted {0:+.1f} cm in X, Y "
              "and Z.".format(args.perturb_cm))
        print("Expect XY residual ~ {0:.1f} cm and |Z| ~ {1:.1f} cm. If "
              "this still reads 0.000, the comparison is not comparing."
              .format(abs(args.perturb_cm) * (2 ** 0.5),
                      abs(args.perturb_cm)))

    # nearest plan entry by XY, in chunks (157k x 400 is fine, but keep
    # the peak allocation bounded).
    resid_xy = np.empty(len(eng))
    resid_z = np.empty(len(eng))
    for i0 in range(0, len(eng), 64):
        blk = eng[i0:i0 + 64]
        d2 = ((pts[None, :, 0] - blk[:, None, 0]) ** 2
              + (pts[None, :, 1] - blk[:, None, 1]) ** 2)
        j = np.argmin(d2, axis=1)
        resid_xy[i0:i0 + 64] = np.sqrt(d2[np.arange(len(blk)), j])
        resid_z[i0:i0 + 64] = blk[:, 2] - pts[j, 2]

    def stat(a):
        return (float(np.median(a)), float(np.percentile(a, 90)),
                float(np.percentile(a, 99)), float(np.max(np.abs(a))))

    mxy, p90xy, p99xy, maxxy = stat(resid_xy)
    mz, p90z, p99z, maxz = stat(np.abs(resid_z))

    print("")
    print("COUNT   engine {0} vs plan {1}   delta {2}".format(
        total, len(pts), total - len(pts)))
    print("")
    print("XY residual to the NEAREST plan entry (cm)  n={0}"
          .format(len(eng)))
    print("   median {0:.3f}   p90 {1:.3f}   p99 {2:.3f}   max {3:.3f}"
          .format(mxy, p90xy, p99xy, maxxy))
    print("Z  residual, engine minus that plan entry (cm)")
    print("   median {0:.3f}   p90 {1:.3f}   p99 {2:.3f}   max {3:.3f}"
          .format(mz, p90z, p99z, maxz))
    print("   signed mean {0:+.3f}".format(float(np.mean(resid_z))))

    bad_xy = int((resid_xy > args.tol_xy_cm).sum())
    bad_z = int((np.abs(resid_z) > args.tol_z_cm).sum())
    print("")
    print("outside tolerance: XY {0}/{1} (>{2} cm), Z {3}/{1} (>{4} cm)"
          .format(bad_xy, len(eng), args.tol_xy_cm, bad_z, args.tol_z_cm))
    print("")
    print("SOURCE: engine get_instance_transform(world_space=True) — this")
    print("shares NO code and NO file with the plan. It is the different")
    print("representation Pass 3 and Pass 4 were both missing.")
    print("It answers 'is the instance where the plan put it', NOT 'is it")
    print("on the ground' — grounding stays trace_grounding's question.")
    print("")

    if total != len(pts):
        print("VERDICT: COUNT MISMATCH — engine {0}, plan {1}."
              .format(total, len(pts)))
        return 3
    if bad_xy or bad_z:
        print("VERDICT: RESIDUALS EXCEED TOLERANCE.")
        return 3
    print("VERDICT: every sampled instance coincides with a planned one")
    print("within {0} cm XY and {1} cm Z. Sample n={2} of {3}, seed {4}."
          .format(args.tol_xy_cm, args.tol_z_cm, len(eng), total,
                  args.seed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
