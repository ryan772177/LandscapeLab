"""sg_trial_armb.py -- Shape Grammar trial ARM B: PCG grammar fill -> kit pieces -> placed on the rig.

    python scripts/sg_trial_armb.py plan          # offline: the facade runs, written to _verify/sg_trial/armb_runs.json
    python scripts/sg_trial_armb.py generate      # editor: build the PCG graphs and fill every run (front, side)
    python scripts/sg_trial_armb.py place [--go]  # offline assembly + placement through town_kit_build_house

research/town_kit/SHAPE_GRAMMAR_TRIAL.md (review changes 1-12). Same 8 houses, courses and roofs as ARM A (so the
only variable is the facade fill). Per course and side the run is L - 2 x corner arm (change 8: corners from
Python). The door side of course 0 uses grammar_front, every other run grammar_side. The door replaces the middle
fitted module of a door-capable width (as arms A/C). Fit failures (a run the grammar did not fill exactly) are
COUNTED and reported (change 6) and the house is placed WITHOUT that run's walls -- a visible hole is the honest
picture of accept_incomplete_subdivision=false (zero points). Seeds per run (change 7). Determinism (change 10):
generate twice and compare the sorted symbol sequences.
"""
import argparse
import io
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402
import sg_trial_place as stp  # noqa: E402

REPO = bootstrap.REPO_ROOT
TRIAL = stp.TRIAL
OUT = os.path.join(REPO, TRIAL["outputs"])
SYM_MESH = TRIAL["arm_b"]["symbol_mesh"]          # audit F3: recipe, not code
SEED = TRIAL["arm_b"]["seed"]


def runs():
    """Every facade run of the 8 houses: (house index, course, side, length, grammar kind, seed)."""
    plans = json.load(io.open(os.path.join(OUT, "plans.json"), encoding="utf-8"))
    out = []
    for r in plans["houses"]:
        for c in range(int(r["courses_a"])):
            for si, (_p0, _u, _n, L) in enumerate(tkp._side_frames(r["W_cm"], r["D_cm"])):
                kind = "front" if (c == 0 and si == r["door_side"]) else "side"
                out.append({"house": r["index"], "course": c, "side": si, "kind": kind,
                            "length_cm": int(L - 2 * tkp.CORNER_ARM_CM),
                            "seed": SEED["per_house"] * r["index"] + SEED["per_course"] * c + si})
    return out


def generate(tag_suffix=""):
    import ue_exec
    ab = TRIAL["arm_b"]
    tpl = io.open(os.path.join(REPO, "scripts", "payloads", "sg_trial_armb.py"), encoding="utf-8").read()
    pr = tkp._R["probe"]
    result = {}
    for kind in ("front", "side"):
        segs = [r for r in runs() if r["kind"] == kind]
        tag = kind + tag_suffix
        cfg = {"mode": "build", "tag": tag, "level": pr["level"], "segments": segs,
               "modules_cm": ab["modules_cm"], "grammar": ab["grammar_" + kind],
               "accept_incomplete_subdivision": ab["accept_incomplete_subdivision"],
               "volume_loc_cm": [pr["camera_xy_cm"][0], pr["camera_xy_cm"][1] + float(ab["volume_offset_y_cm"]), 0.0],
               "component_seed": int(SEED["component"])}
        code, out, raw = ue_exec.run(tpl.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                     stage_name="sg_armb_build")
        if not (isinstance(out, dict) and out.get("ok")):
            raise SystemExit("build %s FAILED: %s" % (kind, out if isinstance(out, dict) else (raw or "")[-800:]))
        print("built %s: pins %s, edges %s" % (kind, out.get("pins"), out.get("edges_per_output_pin")))
        cfg["mode"] = "read"
        for attempt in range(30):
            time.sleep(2.0)
            code, out, raw = ue_exec.run(tpl.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                         stage_name="sg_armb_read")
            if not (isinstance(out, dict) and out.get("ok")):
                raise SystemExit("read %s FAILED: %s" % (kind, out if isinstance(out, dict) else (raw or "")[-800:]))
            if "points" in out:
                break
        else:
            raise SystemExit("REFUSE: %s never finished generating (60 s)" % kind)
        if not out.get("point_datas") or not out.get("n_points"):
            # audit F2 / rule 13: an all-zero read is instrument silence, not a fill
            raise SystemExit("REFUSE: %s read back %s point datas, %s points (classes %s)"
                             % (kind, out.get("point_datas"), out.get("n_points"), out.get("point_data_classes")))
        lanes = {}
        for x, y, sym in out["points"]:
            lanes.setdefault(int(round(y / 1000.0)), []).append((x, sym))
        per = []
        for i, seg in enumerate(segs):
            row = sorted(lanes.get(i, []))
            per.append(dict(seg, symbols=[s for _, s in row], centres_cm=[x for x, _ in row]))
        result[kind] = per
        print("%s: %d runs, %d points" % (kind, len(segs), out.get("n_points")))
    return result


def assemble(gen):
    """Kit pieces per house from the grammar fill, arm A's roof/gables/foundation, Python corners and door."""
    plans = json.load(io.open(os.path.join(OUT, "plans.json"), encoding="utf-8"))
    sizes = TRIAL["arm_b"]["modules_cm"]
    arm_a = {r["index"]: r["pieces"] for r in plans["arm_a"]}
    fills = {(r["house"], r["course"], r["side"]): r for k in gen for r in gen[k]}
    houses, fit_fail = [], []
    for h in plans["houses"]:
        pieces = [p for p in arm_a[h["index"]] if p.get("role") not in ("wall", "door")]   # corners, roof, ...
        for c in range(int(h["courses_a"])):
            z = c * tkp.COURSE_CM
            for si, (p0, u, n, L) in enumerate(tkp._side_frames(h["W_cm"], h["D_cm"])):
                f = fills[(h["index"], c, si)]
                ws = [int(sizes[s]) for s in f["symbols"]]
                if sum(ws) != f["length_cm"]:
                    fit_fail.append({"house": h["index"], "course": c, "side": si, "length_cm": f["length_cm"],
                                     "filled_cm": sum(ws), "symbols": f["symbols"]})
                    continue
                fwd = tkp.EXTERIOR_SIGN == -1
                yaw = tkp._yaw_for(u if fwd else (-u[0], -u[1]), n)
                door_at = None
                if c == 0 and si == h["door_side"]:
                    cands = [i for i, s in enumerate(ws) if s in tkp.DOORS]
                    door_at = cands[len(cands) // 2] if cands else None
                off = tkp.CORNER_ARM_CM
                for i, (s, sym) in enumerate(zip(ws, f["symbols"])):
                    mesh = tkp.DOORS[s] if i == door_at else SYM_MESH[sym]
                    at = off if fwd else off + s
                    pieces.append({"mesh": mesh, "x": p0[0] + u[0] * at, "y": p0[1] + u[1] * at, "z": z,
                                   "yaw": yaw, "role": "door" if i == door_at else "wall", "w": s})
                    off += s
        houses.append({"index": h["index"], "pieces": pieces})
    return houses, fit_fail


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=("plan", "generate", "place"))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    if a.step == "plan":
        rs = runs()
        json.dump(rs, io.open(os.path.join(OUT, "armb_runs.json"), "w", encoding="utf-8"), indent=1)
        print("%d runs (%d front, %d side); lengths %s" % (len(rs), sum(r["kind"] == "front" for r in rs),
              sum(r["kind"] == "side" for r in rs), sorted(set(r["length_cm"] for r in rs))))
        return 0
    if a.step == "generate":
        g1 = generate("_r1")
        g2 = generate("_r2")
        seq = lambda g: sorted((r["house"], r["course"], r["side"], tuple(r["symbols"])) for k in g for r in g[k])
        same = seq(g1) == seq(g2)
        nsym = sum(len(t[3]) for t in seq(g1))
        json.dump({"run1": g1, "deterministic_over_2": same, "runs_compared": len(seq(g1)), "symbols_compared": nsym},
                  io.open(os.path.join(OUT, "armb_fill.json"), "w", encoding="utf-8"), indent=1)
        print("determinism: %s over %d runs, %d symbols" % (same, len(seq(g1)), nsym))
        if nsym == 0:
            return 4
        return 0 if same else 4
    gen = json.load(io.open(os.path.join(OUT, "armb_fill.json"), encoding="utf-8"))["run1"]
    houses, fails = assemble(gen)
    print("fit failures: %d of %d runs" % (len(fails), sum(len(v) for v in gen.values())))
    for f in fails[:10]:
        print("  ", f)
    import sg_trial_plan as sgp
    m = sgp.facade_metrics([(h["index"], h["pieces"]) for h in houses])
    m["fit_failures"] = len(fails)
    met = json.load(io.open(os.path.join(OUT, "metrics.json"), encoding="utf-8"))
    met["arm_b"] = m
    json.dump(met, io.open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(m, indent=1))
    specs = stp.specs_for("A")
    by = {h["index"]: h["pieces"] for h in houses}
    plans = json.load(io.open(os.path.join(OUT, "plans.json"), encoding="utf-8"))
    for s, r in zip(specs, plans["houses"]):
        s["pieces"] = by[r["index"]]
    if not a.go:
        print("dry run (pass --go)")
        return 0
    import ue_exec
    tpl = io.open(os.path.join(REPO, "scripts", "payloads", "town_kit_build_house.py"), encoding="utf-8").read()
    bad = 0
    for s in specs:
        code, out, raw = ue_exec.run(tpl.replace("__SPEC__", json.dumps(s)), marker="__LL__", timeout=25,
                                     stage_name="sg_armb_place")
        ok = isinstance(out, dict) and out.get("ok")
        bad += 0 if ok else 1
        print("%s %s" % (s["label"], "ok" if ok else "FAIL %s" % ((out or {}).get("error") if isinstance(out, dict) else "")))
        if not isinstance(out, dict):
            break
    return 0 if not bad else 4


if __name__ == "__main__":
    sys.exit(main())
