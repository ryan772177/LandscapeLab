"""validate_groom_export.py — is this groom something UE can draw?

    blender.exe --background <stack.blend> --python this.py

Blender will happily render a curves object that UE draws as nothing. The
round trip costs four minutes and an editor; these checks cost forty seconds
and they are the properties UE's groom pipeline actually consumes:

    points per curve   GroomBuilder asserts CurveNumVertices >= 2
    root UVs           a groom with no/degenerate surface_uv_coordinate binds
                       cleanly and renders nothing -- measured 2026-08-21
    radius             zero width draws zero pixels
    finite positions   a NaN anywhere can take out a whole group
    5 segment collapse a consecutive-point distance of zero has no tangent
    6 strand collapse  a strand with no length is a point wearing a curve
    7 root collision   many strands sharing one root position

CHECKS 5-7 ARE MEASUREMENTS WITH ONE REFUSAL EACH, AND THE REASON THEY ARE NOT
STRICTER IS THE POINT. They were added 2026-08-22 to catch a generative groom
regenerating the classic DiffLocks vellus/degenerate-strand defect in Blender in
forty seconds rather than in UE in four minutes. They were then CALIBRATED
AGAINST A GROOM THAT DRAWS, and the calibration inverted the expectation:

    metric                       DiffLocks (BALD)   procedural (DRAWS)
    min consecutive-point dist     0.0806 cm          0.0092 cm
    segments under 1e-2 cm         0                  1
    roots sharing a position       10                 166
    min strand length              2.6756 cm          --

The groom that renders is DIRTIER on every one of the three. A bar set where
intuition wants it would REFUSE THE KNOWN-GOOD GROOM -- which is exactly the
defect `verify_export_bounds.py` was retired for. So only an EXACTLY-zero
segment or an exactly-zero strand refuses; everything else is reported as a
number beside its denominator. Bars are scale-free (a fraction of the strand's
own length, or of the median strand length) so they survive a blend authored in
metres.

**AND NONE OF THE THREE WAS THE DIFFLOCKS DEFECT.** They are here because the
class is real and cheap to catch, not because they explain the bald render.

WHY IT EXISTS. v22 rendered a full head in Blender and a bald skull in UE,
through TWO independent bindings, so the groom itself was the suspect and
there was no cheap way to interrogate it.
"""

import json
import math
import sys

import bpy
import mathutils
import numpy as np


def main():
    rep = {"blend": bpy.data.filepath}
    curves = [o for o in bpy.data.objects if o.type == "CURVES"
              and len(o.data.curves) > 0]
    if not curves:
        rep["error"] = "no curves object"
        print("__VALID__" + json.dumps(rep))
        return
    ob = max(curves, key=lambda o: len(o.data.curves))
    d = ob.data
    rep["object"] = ob.name
    rep["curves"] = len(d.curves)
    rep["points"] = len(d.points)

    sizes = [c.points_length for c in d.curves]
    rep["points_per_curve"] = {"min": min(sizes), "max": max(sizes),
                               "mean": round(sum(sizes) / len(sizes), 3)}
    rep["curves_under_2_points"] = sum(1 for s in sizes if s < 2)

    # positions
    bad = 0
    zero_len = 0
    starts = [c.first_point_index for c in d.curves]
    for i, s in enumerate(starts):
        n = sizes[i]
        p0 = mathutils.Vector(d.points[s].position)
        p1 = mathutils.Vector(d.points[s + n - 1].position)
        for v in (p0.x, p0.y, p0.z, p1.x, p1.y, p1.z):
            if not math.isfinite(v):
                bad += 1
                break
        if (p1 - p0).length < 1e-4:
            zero_len += 1
    rep["curves_with_nonfinite_ends"] = bad
    rep["curves_zero_length"] = zero_len

    # radius
    rad_attr = d.attributes.get("radius")
    if rad_attr is None:
        rep["radius"] = "MISSING"
    else:
        vals = [rad_attr.data[i].value for i in range(len(rad_attr.data))]
        vals_s = sorted(vals)
        rep["radius"] = {"min": round(vals_s[0], 6),
                         "max": round(vals_s[-1], 6),
                         "zero_or_less": sum(1 for v in vals if v <= 0.0)}

    # root UVs -- the one that binds cleanly and renders nothing
    uv = None
    for nm in ("surface_uv_coordinate", "groom_root_uv"):
        if nm in d.attributes:
            uv = d.attributes[nm]
            rep["root_uv_attr"] = nm
            break
    if uv is None:
        rep["root_uv"] = "MISSING"
    else:
        pts = []
        for i in range(len(uv.data)):
            v = uv.data[i]
            val = getattr(v, "vector", None)
            if val is None:
                val = getattr(v, "value", None)
            if val is None:
                continue
            pts.append((round(float(val[0]), 6), round(float(val[1]), 6)))
        uniq = len(set(pts))
        rep["root_uv"] = {
            "n": len(pts), "unique": uniq,
            "unique_frac": round(uniq / max(1, len(pts)), 4),
            "outside_0_1": sum(1 for a, b in pts
                               if not (0.0 <= a <= 1.0 and 0.0 <= b <= 1.0)),
            "nonfinite": sum(1 for a, b in pts
                             if not (math.isfinite(a) and math.isfinite(b)))}
    # ---- CHECKS 5-7: degeneracy. Read the docstring before tightening a bar.
    npts = len(d.points)
    pos = np.zeros(npts * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", pos)
    P = pos.reshape(npts, 3).astype(np.float64)
    S = np.asarray(sizes, dtype=np.int64)
    starts_a = np.asarray(starts, dtype=np.int64)

    # Segment lengths, computed WITHOUT crossing a curve boundary: the last
    # point of curve i and the first of curve i+1 are adjacent in the flat
    # buffer and are NOT a segment. Getting this wrong invents a large bogus
    # segment at every boundary, and the histogram it produces would hide every
    # real short one underneath it.
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    keep = np.ones(len(seg), dtype=bool)
    if len(starts_a) > 1:
        keep[starts_a[1:] - 1] = False
    seg_in = seg[keep]
    cidx = np.repeat(np.arange(len(S)), S)      # point index -> curve index
    seg_curve = cidx[1:][keep]                  # segment index -> curve index
    total = np.bincount(seg_curve, weights=seg_in, minlength=len(S))

    med = float(np.median(total)) if len(total) else 0.0
    denom = total[seg_curve]
    ratio = seg_in / np.where(denom > 0, denom, np.inf)

    rep["check5_segment_collapse"] = {
        "unit": "raw blender units; mean_strand_length is the scale cue",
        "mean_strand_length": round(float(total.mean()), 6) if len(total) else 0.0,
        "min_segment": round(float(seg_in.min()), 8) if len(seg_in) else 0.0,
        "segments_exactly_zero": int((seg_in == 0.0).sum()),
        "min_segment_over_strand_len": round(float(ratio.min()), 10)
                                       if len(ratio) else 0.0,
        "segments_under_1e-6_of_strand": int((ratio < 1e-6).sum()),
        "control": "the procedural groom that DRAWS reads min_segment 0.0092 cm"}

    rep["check6_strand_collapse"] = {
        "median_strand_length": round(med, 6),
        "min_strand_length": round(float(total.min()), 6) if len(total) else 0.0,
        "strands_exactly_zero": int((total == 0.0).sum()),
        "strands_under_5pct_of_median": int((total < 0.05 * med).sum())
                                        if med > 0 else 0,
        "note": "DiffLocks writes a vellus layer; short is not by itself wrong"}

    # Root dedup, quantised to 1e-4 of the median strand length so the bucket is
    # scale-free. A fixed decimal place would call every metre-unit groom
    # degenerate and every centimetre-unit groom clean, which is a statement
    # about the file's units and not about the groom.
    q = (med * 1e-4) if med > 0 else 1e-6
    roots = P[starts_a]
    _, counts = np.unique(np.round(roots / q).astype(np.int64), axis=0,
                          return_counts=True)
    rep["check7_root_collision"] = {
        "quantum": round(float(q), 9),
        "roots": int(len(roots)),
        "distinct_positions": int(len(counts)),
        "roots_sharing_a_position": int(len(roots)) - int(len(counts)),
        "largest_cluster": int(counts.max()) if len(counts) else 0,
        "control": "the procedural groom that DRAWS has 166 roots sharing a spot"}

    # THE ONLY REFUSALS. Both are exactly-zero conditions, which are UNDEFINED
    # rather than merely ugly: a zero segment has no tangent and a zero strand
    # has no direction. Anything softer refuses the known-good groom -- measured,
    # see the docstring table.
    refuse = []
    if rep["check5_segment_collapse"]["segments_exactly_zero"] > 0:
        refuse.append("check5: %d segments of length exactly 0 -- no tangent"
                      % rep["check5_segment_collapse"]["segments_exactly_zero"])
    if rep["check6_strand_collapse"]["strands_exactly_zero"] > 0:
        refuse.append("check6: %d strands of length exactly 0"
                      % rep["check6_strand_collapse"]["strands_exactly_zero"])
    # ---- CHECK 8: VALUE VARIANCE ON EVERY RESOLVED ATTRIBUTE.
    #
    # Checks 1-4 ask whether a thing is PRESENT. Three times in two days a
    # present, correct-length, correctly-typed array shipped full of zeros and
    # every presence check passed:
    #
    #     groom_root_uv   absent entirely, then present and all-zero
    #     widths          present, right length, ALL ZERO -- and that one cost
    #                     a render. It defeats the builder's absent-width 1 cm
    #                     fallback: an EMPTY width is substituted, a ZERO width
    #                     is obeyed.
    #
    # CALIBRATED AGAINST CLAY, the groom the owner watched render:
    #     widths   min 0.012  mean 0.0235  max 0.035  12 distinct
    # so "distinct > 1" is not the bar either -- a legitimately uniform groom
    # exists. The bar is the pair that is UNUSABLE: min <= 0, or every value
    # identical AND that value zero.
    rep["check8_value_variance"] = {}
    zero_refusals = []
    for nm, attr in (("radius", d.attributes.get("radius")),
                     ("groom_root_uv", d.attributes.get("groom_root_uv"))):
        if attr is None:
            rep["check8_value_variance"][nm] = "ABSENT"
            continue
        comp = {"FLOAT": 1, "FLOAT2": 2, "FLOAT_VECTOR": 3}.get(
            attr.data_type)
        if comp is None:
            rep["check8_value_variance"][nm] = "UNHANDLED TYPE " + attr.data_type
            continue
        n_el = len(attr.data)
        buf = np.zeros(n_el * comp, dtype=np.float32)
        attr.data.foreach_get("value" if comp == 1 else "vector", buf)
        V = buf.reshape(n_el, comp)
        row = {"type": attr.data_type, "n": n_el,
               "min": round(float(V.min()), 8),
               "mean": round(float(V.mean()), 8),
               "max": round(float(V.max()), 8),
               "distinct": int(len(np.unique(np.round(V, 8), axis=0))),
               "all_zero": bool((V == 0.0).all())}
        rep["check8_value_variance"][nm] = row
        if nm == "radius" and (row["min"] <= 0.0 or row["all_zero"]):
            zero_refusals.append(
                "check8: 'radius' min %g, all_zero %s -- a groom with zero "
                "width draws zero pixels (control: clay min 0.012, 12 distinct)"
                % (row["min"], row["all_zero"]))
        if nm == "groom_root_uv" and row["all_zero"]:
            zero_refusals.append(
                "check8: 'groom_root_uv' is all zero")

    refuse.extend(zero_refusals)
    rep["refusals"] = refuse
    rep["verdict"] = "REFUSE" if refuse else "PASS"

    print("__VALID__" + json.dumps(rep))
    if refuse:
        raise SystemExit(7)


main()
