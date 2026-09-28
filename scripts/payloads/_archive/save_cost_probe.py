"""How long does saving ONE external-actor package actually take?

The number nobody had. On 2026-09-07 a save of 2,796 external actor packages
ran 90 minutes at ~5 cores with no log output, no files written and no DDC
growth, and was killed without ever learning whether it was slow or stuck. That
happened because the operation was launched with no estimate of its cost and no
way to tell progress from a spin.

This saves a BOUNDED number of dirty packages, one at a time, timing each, and
reports the distribution. A per-package cost turns "will 2,796 finish?" from a
gamble into arithmetic.

Saving one at a time is deliberately not the fast path. The point is to get a
per-item number and to keep the game thread returning between items, so a
partial result survives.

Run via:
  python scripts/ue_exec.py scripts/payloads/save_cost_probe.py --set MAX_N=25
"""
import json as _json
import time as _time

import unreal as _u

MAX_N = __MAX_N__

_out = {"error": None, "timings_s": [], "saved": 0, "failed": 0}
try:
    _dirty = list(_u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    _dirty += list(_u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    _seen, _uniq = set(), []
    for _p in _dirty:
        _n = _p.get_name()
        if _n not in _seen:
            _seen.add(_n)
            _uniq.append(_p)
    _out["dirty_total"] = len(_uniq)

    _t0 = _time.time()
    for _p in _uniq[:int(MAX_N)]:
        _s = _time.time()
        try:
            _ok = _u.EditorLoadingAndSavingUtils.save_packages([_p], True)
            _out["saved" if _ok else "failed"] += 1
        except Exception:
            _out["failed"] += 1
        _out["timings_s"].append(round(_time.time() - _s, 3))
    _out["elapsed_s"] = round(_time.time() - _t0, 2)

    _ts = sorted(_out["timings_s"])
    if _ts:
        _out["per_package_s"] = {
            "n": len(_ts), "min": _ts[0], "p50": _ts[len(_ts) // 2],
            "max": _ts[-1], "mean": round(sum(_ts) / len(_ts), 3)}
        _out["projected_all_dirty_s"] = round(
            _out["per_package_s"]["mean"] * _out["dirty_total"], 1)

    _after = [p.get_name() for p in
              _u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    _after += [p.get_name() for p in
               _u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    _out["dirty_after"] = len(set(_after))
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out))
