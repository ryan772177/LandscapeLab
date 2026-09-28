"""Read every layer's ACTUAL tiling back out of the built M_Alpine8K graph.

⭐ WHY, AND WHY IT IS NOT A RECIPE READ. Standing rule 12: a declared
value that is not read back from the ENGINE is prose. `recipes/
alpine_8k.json` says Scree tiles at 2.00 m; Task 3 measured a real local
peak at 2.40 m in the 30-100 m bin, which is 1.2x that. Either the
binding is applying something other than 2.00, or the scan has structure
at 1.2x its own tile. ONLY THE GRAPH CAN SAY WHICH, and the recipe --
the thing under suspicion -- cannot be the witness.

HOW THE TILE IS ENCODED IN THE GRAPH. `make_landscape_material` builds
one shared world-XY source (a ComponentMask of WorldPosition, in
CENTIMETRES) and, per sample, a Divide whose B input is a Constant equal
to `tiling_m * 100`. So the tile in metres is that constant / 100 --
read from the node, not from the JSON that wrote it.

⛔ READ-ONLY. Nothing here creates, wires, deletes or saves. The
connectivity audit's own accessor (`get_inputs_for_material_expression`)
is reused rather than reimplemented.

WHAT IS REPORTED PER TEXTURE SAMPLE: the texture asset, the divisor
found, how many DISTINCT divisors reached it, and the path length. A
sample with two divisors, or none, is reported as such rather than
collapsed to one number -- an ambiguous read must not look like a
measurement.
"""
import json as _json
import traceback as _tb

import unreal as _u

MAT = "/Game/Materials/M_Alpine8K"
_out = {"ok": False, "material": MAT}


def _key(_e):
    try:
        return _e.get_path_name()
    except Exception:
        return str(_e)


try:
    _eal = _u.EditorAssetLibrary
    _mel = _u.MaterialEditingLibrary
    if not _eal.does_asset_exist(MAT):
        # NN6: "I looked and it is absent" is not "I could not look".
        _cands = [p for p in _eal.list_assets("/Game/Materials", False, False)
                  if "M_" in p]
        raise RuntimeError("no material at %s; /Game/Materials holds %r"
                           % (MAT, _cands[:20]))
    _mat = _eal.load_asset(MAT)
    _all = list(_mel.get_material_expressions(_mat))
    _out["expressions"] = len(_all)

    # Index every expression's inputs ONCE; the walk below is then pure
    # dictionary lookup and cannot make a different accessor call for
    # the same node twice.
    _inputs = {}
    _bykey = {}
    _errs = 0
    for _e in _all:
        _bykey[_key(_e)] = _e
        try:
            _inputs[_key(_e)] = [i for i in
                                 (_mel.get_inputs_for_material_expression(
                                     _mat, _e) or []) if i is not None]
        except Exception:
            _inputs[_key(_e)] = []
            _errs += 1
    _out["accessor_errors"] = _errs

    def _const_value(_e):
        """Scalar value of a Constant-like node, or None."""
        for _p in ("r", "constant"):
            try:
                _v = _e.get_editor_property(_p)
                if isinstance(_v, float):
                    return float(_v)
            except Exception:
                pass
        return None

    def _divisors_behind(_start, _max_depth=6):
        """Every (divisor, depth) reachable backwards through Divides.

        Walks the UV side of a sample. A Divide's inputs are the shared
        world-XY source and a Constant; the Constant is the tile. Returns
        ALL of them so a sample fed by two different divisors reads as
        ambiguous instead of as whichever was found first.
        """
        _found = []
        _stack = [(_key(_start), 0)]
        _seen = set()
        while _stack:
            _k, _d = _stack.pop()
            if _k in _seen or _d > _max_depth:
                continue
            _seen.add(_k)
            _e = _bykey.get(_k)
            if _e is None:
                continue
            if isinstance(_e, _u.MaterialExpressionDivide):
                for _i in _inputs.get(_k, []):
                    _v = _const_value(_i)
                    if _v is not None:
                        _found.append((_v, _d))
            for _i in _inputs.get(_k, []):
                _stack.append((_key(_i), _d + 1))
        return _found

    _rows = []
    for _e in _all:
        if not isinstance(_e, _u.MaterialExpressionTextureSample):
            continue
        try:
            _t = _e.get_editor_property("texture")
        except Exception:
            _t = None
        if _t is None:
            continue
        _tn = _t.get_name()
        _divs = _divisors_behind(_e)
        _vals = sorted({round(v, 4) for v, _d in _divs})
        # F3: the docstring promises "the path length" per sample; keep the min
        # depth at which each distinct divisor was reached (it was computed and
        # then discarded).
        _depth = {}
        for _v, _dd in _divs:
            _rv = round(_v, 4)
            _depth[_rv] = min(_dd, _depth.get(_rv, _dd))
        _rows.append({
            "texture": _tn,
            "sampler_type": str(_e.get_editor_property("sampler_type")),
            "divisors_cm": _vals,
            "divisor_path_len": [[_v, _depth[_v]] for _v in _vals],
            "n_distinct_divisors": len(_vals),
            "tiling_m": ([round(v / 100.0, 4) for v in _vals]
                         if _vals else None),
            "editor_xy": [int(_e.get_editor_property(
                              "material_expression_editor_x")),
                          int(_e.get_editor_property(
                              "material_expression_editor_y"))],
        })
    _rows.sort(key=lambda r: (r["texture"], r["editor_xy"]))
    _out["samples"] = _rows
    _out["n_samples"] = len(_rows)

    # Collapse to one row per texture, and SAY when a texture's samples
    # disagree rather than picking one.
    _bytex = {}
    for _r in _rows:
        _bytex.setdefault(_r["texture"], set()).update(_r["divisors_cm"])
    _out["by_texture"] = [
        {"texture": _t,
         "divisors_cm": sorted(_v),
         "tiling_m": sorted(round(x / 100.0, 4) for x in _v),
         "consistent": len(_v) == 1}
        for _t, _v in sorted(_bytex.items())]
    # F1/F2/NN13: a read that found no texture samples, recovered no divisor, or
    # failed the input accessor on every node MEASURED NOTHING -- do not let the
    # unconditional True at the tail report that as a measurement.
    _any_divisor = any(r["divisors_cm"] for r in _rows)
    _all_failed = len(_all) > 0 and _errs >= len(_all)
    _out["ok"] = (_out["n_samples"] > 0) and _any_divisor and not _all_failed
    if not _out["ok"]:
        _out["refused"] = (
            "n_samples=%d, any_divisor=%s, accessor_errors=%d/%d -- nothing "
            "measured, an ambiguous read must not look like one"
            % (_out["n_samples"], _any_divisor, _errs, len(_all)))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
