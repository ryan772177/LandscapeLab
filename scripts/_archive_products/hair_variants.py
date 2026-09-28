"""Ruling 8: hair colour variants as PARAMETERS off one master.

Colours are the operator's words, converted sRGB -> LINEAR with the exact
piecewise transfer. UE's VectorParameter takes linear; typing sRGB numbers into
it is the standard way to get hair that renders far too bright.
"""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def lin(s):
    c = s / 255.0
    return round(c / 12.92 if c <= 0.04045
                 else ((c + 0.055) / 1.055) ** 2.4, 4)


def rgb(r, g, b):
    return [lin(r), lin(g), lin(b)]


VARIANTS = [
    {"name": "MI_Hair_Hero", "label": "hero: dark walnut root, sun-faded warm "
                                      "chestnut tip",
     "root": rgb(72, 48, 32), "tip": rgb(158, 108, 68)},
    {"name": "MI_Hair_NPC", "label": "NPC: ash grey root, silvered tip",
     "root": rgb(70, 68, 66), "tip": rgb(196, 194, 188)},
]


def main():
    with io.open(os.path.join(REPO, "scripts", "hair_variants_payload.txt"),
                 encoding="utf-8") as fh:
        tmpl = fh.read()
    gen = os.path.join(REPO, "LandscapeLab", "Saved", "hair_variants_gen.txt")
    with io.open(gen, "w", encoding="utf-8") as fh:
        fh.write(tmpl.replace("VARIANTS_JSON", repr(VARIANTS)))

    print("hair variants -- colours in LINEAR, from the ruled sRGB")
    for v in VARIANTS:
        print("  %-14s root %s  tip %s" % (v["name"], v["root"], v["tip"]))
    print("")

    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         gen, "--timeout", "25"], capture_output=True, text=True)
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if i < 0:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1200:])
        return 5
    r = json.loads(t[i:j + 1])
    if r.get("error"):
        print("FAILED: " + str(r["error"])[:400])
    m = r.get("master") or {}
    print("  master  VolumeStrength %s   volume multiply found %s   rewired %s"
          % (m.get("volume_param"), m.get("found_volume_multiply"),
             m.get("rewired")))
    ce = m.get("compile_errors")
    print("  compile %s" % ("clean, 0 errors" if ce == [] else ce))
    for inst in r.get("instances", []):
        print("  %-14s %s" % (inst["name"], inst["label"]))
        for k, v in sorted(inst["readback"].items()):
            print("      %-10s read back %s" % (k, v))
        print("      VolumeStrength %s   on disk %s"
              % (inst.get("volume_strength"), inst.get("on_disk")))
        if inst.get("error"):
            print("      !! %s" % inst["error"])
    print("")
    print("VARIANTS %s" % ("OK" if r.get("ok") else "!! NOT OK"))
    return 0 if r.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
