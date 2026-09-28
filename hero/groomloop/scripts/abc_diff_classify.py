"""abc_diff_classify.py -- classify every differing ABC field, and name the leftovers.

    python abc_diff_classify.py <dump.json> <curvesA> <curvesB>

The first pass through this diff reported "16 fields differ and 14 of them are
just 'this groom has more curves'". That was an arithmetic claim made by eye
over a printed table, and it was not checked: the leftovers are what the whole
comparison is for, so the bucketing has to be mechanical.

Count-driven means the pair is EXACTLY (curvesA, curvesB) or (pointsA, pointsB).
Anything else is named with both values, because a field that is neither a count
nor root_uv is the only place a structural difference can still be hiding.
"""

import json
import sys


def flat(o, pre=""):
    out = {}
    for k, v in o.items():
        if isinstance(v, dict) and k != "arb_geom_params":
            out.update(flat(v, pre + k + "."))
        elif k == "arb_geom_params":
            for p in v:
                for kk, vv in p.items():
                    if kk != "name":
                        out["arb." + p["name"] + "." + kk] = vv
        else:
            out[pre + k] = v
    return out


def main():
    path, ca, cb = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    d = json.load(open(path))
    files = list(d.keys())
    A = d[files[0]]["curve_objects"][0]
    B = d[files[1]]["curve_objects"][0]
    fa, fb = flat(A), flat(B)
    pa, pb = fa.get("P_len"), fb.get("P_len")

    diffs = [k for k in sorted(set(fa) | set(fb))
             if str(fa.get(k, "MISSING")) != str(fb.get(k, "MISSING"))]
    print("A = %s  (%d curves, %s points)" % (files[0].split("/")[-1], ca, pa))
    print("B = %s  (%d curves, %s points)" % (files[1].split("/")[-1], cb, pb))
    print("TOTAL DIFFERING FIELDS: %d" % len(diffs))
    print()

    ruv, cnt, other = [], [], []
    for k in diffs:
        va, vb = fa.get(k, "MISSING"), fb.get(k, "MISSING")
        if k.startswith("arb.groom_root_uv."):
            ruv.append(k)
        elif (va, vb) in ((ca, cb), (pa, pb)):
            cnt.append(k)
        else:
            other.append((k, va, vb))

    print("  %2d root_uv rows -- present on A, absent on B" % len(ruv))
    print("  %2d count-driven rows:" % len(cnt))
    for k in cnt:
        print("       %-26s %s -> %s" % (k, fa.get(k), fb.get(k)))
    print("  %2d NEITHER count NOR root_uv:" % len(other))
    for k, va, vb in other:
        print("       %-26s A=%-28r B=%r" % (k, va, vb))
    if not other:
        print("       (none)")


main()
