"""integrate.py -- compose accepted regional param deltas into one groom.

    python integrate.py <out_name> <region.json> [<region.json> ...]

WHAT IT ENFORCES, and why each one is a real failure mode:

1. OWNERSHIP. Each regional agent was given a disjoint knob list. If two deltas
   both set the same knob, the composition is ambiguous and one agent's result
   silently wins -- so this REFUSES and names the knob and the two files. It is
   the boundary check in its cheapest form: caught before a render, not after.

2. FRAME KNOBS ARE NOT DELTAS. frame_up / frame_fwd / length_unit / survey
   describe the FILE, not the style. A delta that carries them is a delta that
   can silently retarget the whole edit, so they are taken from the baseline and
   a delta that tries to change them is refused.

3. THE BASELINE IS DECLARED. Composition is baseline + deltas, and the baseline
   is written into the output so a params file always says what it was composed
   from. A params file that cannot name its parent is not reproducible.

Superposition is NOT assumed to be safe. Regions barely couple, which is why
they were parallelised -- but "barely" is not "not at all", and the composed
groom is re-rendered and re-judged as a whole. A regional change that scores
well alone and breaks a boundary goes back to its agent WITH the evidence.
"""

import json
import os
import sys

BASELINE = "hero/groomloop/params/hero_032.json"
# THE BASELINE IS A PARAMETER because each round has its own. Round 2's agents
# all started from ROUND2_BASE, so composing them against hero_032 would make
# every round-1 knob they inherited look like a delta CLAIMED BY ALL OF THEM --
# a wall of false conflicts that says nothing about what the agents did.
FRAME_KEYS = ("frame_up", "frame_fwd", "length_unit", "survey")


def main():
    args = sys.argv[1:]
    base_path = BASELINE
    if "--baseline" in args:
        i = args.index("--baseline")
        base_path = args[i + 1]
        del args[i:i + 2]
    out_name = args[0]
    deltas = args[1:]
    if not deltas:
        raise SystemExit("REFUSE: no regional deltas given")

    base = json.load(open(base_path, encoding="utf-8"))
    composed = dict(base)
    owner = {}
    report = {"baseline": base_path, "deltas": {}, "conflicts": []}

    for path in deltas:
        d = json.load(open(path, encoding="utf-8"))
        applied = {}
        for k, v in d.items():
            if k.startswith("_"):
                continue
            if k in FRAME_KEYS:
                if v != base.get(k):
                    raise SystemExit(
                        "REFUSE: %s changes the frame key %r (%r -> %r). Frame "
                        "keys describe the FILE, not the style, and a delta "
                        "that moves one silently retargets every region."
                        % (path, k, base.get(k), v))
                continue
            if v == base.get(k):
                continue                      # not a delta, just inherited
            if k in owner:
                report["conflicts"].append(
                    {"knob": k, "claimed_by": [owner[k], path],
                     "values": [composed[k], v]})
                continue
            owner[k] = path
            composed[k] = v
            applied[k] = v
        report["deltas"][path] = applied

    if report["conflicts"]:
        for c in report["conflicts"]:
            print("CONFLICT  %-24s claimed by %s and %s  (%r vs %r)"
                  % (c["knob"], os.path.basename(c["claimed_by"][0]),
                     os.path.basename(c["claimed_by"][1]),
                     c["values"][0], c["values"][1]))
        raise SystemExit(
            "REFUSE: %d knob(s) claimed by more than one region. The knob "
            "lists were disjoint by design, so this is an agent going outside "
            "its brief, not a merge policy question."
            % len(report["conflicts"]))

    composed["_label"] = (
        "INTEGRATED from %s plus %d regional deltas: %s"
        % (os.path.basename(base_path), len(deltas),
           ", ".join(os.path.basename(p) for p in deltas)))
    composed["_composed_from"] = report

    out = "hero/groomloop/params/%s.json" % out_name
    json.dump(composed, open(out, "w", encoding="utf-8"), indent=2)
    print("wrote %s" % out)
    for path, applied in report["deltas"].items():
        print("  %-40s %d knob(s): %s"
              % (os.path.basename(path), len(applied),
                 ", ".join(sorted(applied)) or "(none -- delta was empty)"))


if __name__ == "__main__":
    main()
