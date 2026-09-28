"""pick_curves.py -- choose THE groom object in a file, and refuse ambiguity.

WHY THIS EXISTS. Every script in this loop opened its source with

    ob = [o for o in bpy.data.objects if o.type == "CURVES"][0]

which is correct only while a file contains exactly one Curves object. The
hero's authoring blend contains TWO: an empty template `AlpineHero_Hair_v1`
with 0 curves, and the authored `AlpineHero_Hair_v1.001` with 48,000. `[0]`
took the empty one, and the failure surfaced deep inside numpy as
`IndexError: index -1 is out of bounds for axis 0 with size 0` from a
percentile over an empty root array -- a diagnostic that says nothing at all
about the cause.

Worse is the case that does NOT raise. Had the template carried a handful of
curves instead of none, every script in the loop would have run to completion
and measured the wrong groom, and no output would have looked odd.

So the selection is: the Curves object with the MOST curves, refusing outright
if none has any. It returns the object so the caller can log its NAME and
count, because "which object did this measure" has to be answerable from the
artefact rather than from the ordering of bpy.data.objects.
"""


def pick_curves_object(bpy):
    cands = [o for o in bpy.data.objects
             if o.type == "CURVES" and len(o.data.curves) > 0]
    if not cands:
        raise SystemExit(
            "REFUSE: no CURVES object with any curves in this file "
            "(found %d Curves objects, all empty)"
            % len([o for o in bpy.data.objects if o.type == "CURVES"]))
    cands.sort(key=lambda o: len(o.data.curves), reverse=True)
    return cands[0]
