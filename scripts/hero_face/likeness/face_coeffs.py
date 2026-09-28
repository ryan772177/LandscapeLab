"""THE PARAMETRIC CONTROLS. Read and write the face model's own coefficients.

WHY THIS EXISTS
---------------
The geometry route works but fights the model: an edit is pushed into vertex
positions and `FitToFaceDna` then solves for the nearest state it can
express, so the response is non-linear, region-coupled, and needed a measured
gain per region that drifted between iterations.
`get/set_face_model_coefficients` moves the model in ITS OWN BASIS, which is
what Ryan ruled for after the geometry loop plateaued at 0.747 cm with a
render that read wider rather than more like the reference.

THE LAYOUT, DECODED FROM THE VECTOR ITSELF (2026-08-18)
-------------------------------------------------------
1397 floats, and the arithmetic closes exactly:

    [0]        region count = 22
    [1..8]     global transform
    per region, 22 of them:
        [count]                  PCA coefficient count for this region
        [count floats]           the region's PCA coefficients
        [8 floats]               the region's transform
                                 -- EXCEPT THE LAST REGION, which has no
                                 transform block; the vector ends.

    check: 9 + sum(1 + count_i) + 21*8 = 9 + 1220 + 168 = 1397

The 8-float transform reads [1, a, b, c, 1, X, Y, Z] and the last three are a
CENTRE in the same space the DNA declares -- X=Left, Y=Up, Z=Front, cm. The X
values come in symmetric pairs (+/-5.75, +/-3.07, +/-7.39, ...), which is
what makes a width a single paired edit rather than a search.

NOTHING HERE IS DOCUMENTED BY EPIC. The layout above is inferred from the
numbers and confirmed only by the arithmetic closing and by the symmetry of
the X pairs. It is a HYPOTHESIS until a write moves the render, which is what
`--probe` is for. Treat a layout that has not been rendered as unproven.

EXIT CODES
    0  ran
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  payload error
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (REPO_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import ue_exec                       # noqa: E402
import capture_shot as CS                         # noqa: E402


PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

CHARACTER = "__CHARACTER__"
EDITS     = __EDITS__
RESET     = __RESET__

_out = {"ok": False, "error": None, "applied": []}
try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _ch = _eal.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        if not _sub.try_add_object_to_edit(_ch):
            raise RuntimeError("try_add_object_to_edit refused")

    _c = [float(v) for v in _sub.get_face_model_coefficients(_ch)]
    _out["count"] = len(_c)

    if RESET:
        _base = _json.load(open(RESET, "r"))
        # The dump written by the probe is {"working": [...], "master": [...]}
        # while a plain vector dump is a bare list. Accept both, because the
        # refusal for the wrong one ("reset vector is 2 long") is correct but
        # was reached by feeding the tool its own sibling's format.
        if isinstance(_base, dict):
            _base = _base.get("working") or _base.get("master")
        if _base is None or len(_base) != len(_c):
            raise RuntimeError("reset vector is %d long, live is %d"
                               % (len(_base), len(_c)))
        _c = [float(v) for v in _base]
        _out["applied"].append({"reset_from": RESET})

    for _e in EDITS:
        _i = int(_e[0])
        _d = float(_e[1])
        if _i < 0 or _i >= len(_c):
            raise RuntimeError("index %d outside [0, %d)" % (_i, len(_c)))
        _before = _c[_i]
        _c[_i] = _before + _d
        _out["applied"].append({"index": _i, "before": round(_before, 6),
                                "after": round(_c[_i], 6), "delta": _d})

    _sub.set_face_model_coefficients(_ch, _c)

    # READ BACK. A setter that silently clamps or ignores would otherwise
    # report a move that never happened -- the class this project keeps
    # finding.
    _back = [float(v) for v in _sub.get_face_model_coefficients(_ch)]
    _bad = []
    for _e in EDITS:
        _i = int(_e[0])
        _want = _c[_i]
        if abs(_back[_i] - _want) > 1e-4:
            _bad.append({"index": _i, "wanted": round(_want, 6),
                         "read_back": round(_back[_i], 6)})
    _out["readback_mismatches"] = _bad
    _out["changed_after_set"] = sum(
        1 for _k in range(len(_c)) if abs(_back[_k] - _c[_k]) > 1e-5)

    _sub.commit_face_state(_ch, _sub.get_face_state(_ch)) if hasattr(
        _sub, "get_face_state") else None
    _sub.assemble_for_preview(_ch)
    _out["assembled"] = True
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:500]

print("__LL__" + _json.dumps(_out, default=str))
'''


def layout(coeffs):
    """-> [{region, count, pca_start, transform_start or None}], decoded."""
    n = int(coeffs[0])
    out = []
    i = 9
    for r in range(n):
        c = int(coeffs[i])
        pca = i + 1
        tr = pca + c
        out.append({"region": r, "count": c, "pca_start": pca,
                    "transform_start": tr if tr + 8 <= len(coeffs) else None})
        i = tr + 8
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--dump", default=None,
                    help="write the live coefficient vector to this JSON")
    ap.add_argument("--reset-from", default=None,
                    help="restore the vector from a JSON dump before editing")
    ap.add_argument("--set", action="append", default=[], metavar="INDEX=DELTA",
                    help="add DELTA to the coefficient at INDEX; repeatable")
    ap.add_argument("--widen", action="append", default=[],
                    metavar="REGION_PAIR=CM",
                    help="move a symmetric region pair APART by CM, e.g. "
                         "10,11=0.5 -- resolves each side's transform X and "
                         "pushes it outward")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args(argv)

    edits = []
    for s in args.set:
        k, _, v = s.partition("=")
        edits.append([int(k), float(v)])

    if args.widen:
        if not args.reset_from and not os.path.isfile(
                os.path.join(REPO_ROOT, "_verify", "hero_likeness",
                             "coeffs.json")):
            print("--widen needs a coefficient dump to resolve the layout; "
                  "run --dump first")
            return 2
        src = args.reset_from or os.path.join(
            REPO_ROOT, "_verify", "hero_likeness", "coeffs.json")
        with open(src, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        vec = data["working"] if isinstance(data, dict) else data
        lay = layout(vec)
        for w in args.widen:
            pair, _, cm = w.partition("=")
            a, b = [int(x) for x in pair.split(",")]
            cm = float(cm)
            for reg, sign in ((a, 1.0), (b, -1.0)):
                ts = lay[reg]["transform_start"]
                if ts is None:
                    print("region %d has no transform block" % reg)
                    return 2
                xi = ts + 5
                # Outward means AWAY FROM ZERO, and the pair's signs are read
                # from the live vector rather than assumed from the order the
                # regions were listed in.
                out = 1.0 if vec[xi] >= 0 else -1.0
                edits.append([xi, out * cm])
                print("  region %-2d transform X at %d = %+.3f  ->  %+.3f"
                      % (reg, xi, vec[xi], vec[xi] + out * cm))

    reset = args.reset_from
    if reset:
        reset = reset if os.path.isabs(reset) else os.path.join(REPO_ROOT,
                                                                reset)

    rc, d, _ = ue_exec.run(
        CS._fill(PAYLOAD, CHARACTER=args.character, EDITS=edits,
                 RESET=(repr(reset) if reset else "None")),
        timeout=args.timeout, stage_name="hero_coeffs")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        return 5

    print("coefficients: %d" % d["count"])
    for a in d["applied"]:
        print("  %s" % a)
    if d.get("readback_mismatches"):
        print("*** READ-BACK MISMATCH — the setter did not take ***")
        for m in d["readback_mismatches"]:
            print("  %s" % m)
        return 5
    print("changed after set: %d coefficients differ from what was sent"
          % d.get("changed_after_set", -1))
    print("assembled for preview: %s" % d.get("assembled"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
