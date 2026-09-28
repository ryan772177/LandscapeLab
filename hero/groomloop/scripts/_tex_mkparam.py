"""_tex_mkparam.py -- derive a TEXTURE variant from a base params file.

REFUSES any key that is not a texture knob. Every other knob is reserved to
another round-2 agent; a typo that silently edited one would make this agent's
result unattributable and would collide with theirs.
"""
import json, os, sys

MINE = {"clump_scale", "clump_count", "strand_noise_amp", "strand_noise_freq",
        "flyaway_density", "flyaway_amp", "tip_trim_variance",
        "global_length_scale", "stray_clamp_m"}

HERE = os.path.dirname(os.path.abspath(__file__))
PDIR = os.path.join(HERE, "..", "params")

base, new = sys.argv[1], sys.argv[2]
p = json.load(open(os.path.join(PDIR, base + ".json"), encoding="utf-8"))
changed = {}
for kv in sys.argv[3:]:
    k, v = kv.split("=", 1)
    if k == "_label":
        p["_label"] = v
        continue
    if k not in MINE:
        raise SystemExit("REFUSE: %r is not a texture knob. MINE = %s"
                         % (k, sorted(MINE)))
    val = json.loads(v)
    changed[k] = [p.get(k, "<default>"), val]
    p[k] = val
p["_agent"] = "texture"
p["_delta_from"] = base
p["_delta"] = changed
json.dump(p, open(os.path.join(PDIR, new + ".json"), "w", encoding="utf-8"),
          indent=2)
print("WROTE %s.json  delta=%s" % (new, json.dumps(changed)))
