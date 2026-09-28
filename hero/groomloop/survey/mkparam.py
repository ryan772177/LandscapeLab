"""mkparam.py -- derive a sides variant from a base params file.

    python mkparam.py <base_name> <new_name> key=value [key=value ...]

REFUSES any key that is not a SIDES knob. The brief reserves every other knob
to another agent, and a typo that silently edits a reserved knob would make my
result unattributable and would collide with theirs.
"""

import json
import os
import sys

MINE = {"side_length_scale", "ear_clearance", "temple_wing", "rot_up_deg",
        "rot_side_deg", "gravity_drop", "gravity_ramp"}

HERE = os.path.dirname(os.path.abspath(__file__))
PDIR = os.path.join(HERE, "..", "params")


def main():
    base, new = sys.argv[1], sys.argv[2]
    p = json.load(open(os.path.join(PDIR, base + ".json"), encoding="utf-8"))
    changed = {}
    for kv in sys.argv[3:]:
        if kv.startswith("_label="):
            p["_label"] = kv.split("=", 1)[1]
            continue
        k, v = kv.split("=", 1)
        if k not in MINE:
            raise SystemExit("REFUSE: %r is not a SIDES knob. Mine are %s"
                             % (k, sorted(MINE)))
        old = p.get(k)
        p[k] = float(v)
        changed[k] = (old, p[k])
    p["_sides_delta"] = {k: {"from": a, "to": b} for k, (a, b) in
                         changed.items()}
    json.dump(p, open(os.path.join(PDIR, new + ".json"), "w",
                      encoding="utf-8"), indent=2)
    for k, (a, b) in changed.items():
        print("  %-20s %s -> %s" % (k, a, b))
    print("wrote params/%s.json from %s" % (new, base))


if __name__ == "__main__":
    main()
