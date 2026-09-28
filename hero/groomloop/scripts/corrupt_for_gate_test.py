"""corrupt_for_gate_test.py -- manufacture the exact defect checks 5-7 guard.

    blender --background <in.blend> --python this.py -- <out.blend> <mode>

    mode = zeroseg   collapse ONE segment to exactly zero (check 5)
    mode = zerostrand collapse ONE whole strand to a point (check 6)

A gate that has only seen good input has not been tested. Both DiffLocks and the
procedural groom PASS checks 5-7, so on its own that proves nothing -- it is
equally consistent with a gate that returns PASS unconditionally. This makes the
defect on purpose so the refusal can be observed.

Writes a COPY. The source blend is never modified.
"""

import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_blend, mode = tail[0], tail[1]

    d = pick_curves_object(bpy).data
    n = len(d.points)
    pos = np.zeros(n * 3, dtype=np.float32)
    d.attributes["position"].data.foreach_get("vector", pos)
    P = pos.reshape(n, 3)

    s0 = d.curves[0].first_point_index
    k0 = d.curves[0].points_length
    if mode == "zerowidth":
        # the defect that cost a render: a present, correct-length, correctly
        # typed radius array full of zeros
        r = d.attributes.get("radius")
        if r is None:
            raise SystemExit("REFUSE: no radius attribute to zero")
        r.data.foreach_set("value", np.zeros(len(r.data), dtype=np.float32))
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        print("__CORRUPT__ mode=%s wrote=%s" % (mode, out_blend))
        return

    if mode == "zeroseg":
        P[s0 + 1] = P[s0]                       # one coincident pair
    elif mode == "zerostrand":
        P[s0:s0 + k0] = P[s0]                   # the whole strand to a point
    else:
        raise SystemExit("REFUSE: unknown mode " + mode)

    d.attributes["position"].data.foreach_set("vector", P.ravel())
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print("__CORRUPT__ mode=%s wrote=%s" % (mode, out_blend))


if __name__ == "__main__":
    main()
