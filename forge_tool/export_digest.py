"""Export the forge stamp catalogue as a Layout Author digest.

The operator's three.js authoring UI (forge_layout_author.html) loads a
"stamp digest" so its placement dropdown shows REAL stamps instead of
its built-ins. Its reader accepts an array of
{name, description, profile?, default_size_m?, default_amplitude_m?}
and falls back to keyword guessing when profile is absent — so the
profile is stated explicitly here, mapped from each stamp's surveyed
character.

--inject <html> goes one further for the KEYLESS path: it replaces the
UI's built-in generic stamp list (`const BUILTIN_STAMPS = [...]`) with
the real catalogue, so the shipped page is born knowing the true stamps
and nobody has to find and load a digest file by hand. Idempotent — the
injected block matches the same marker on the next run. Re-run it (and
--out) whenever the catalogue changes; package.py refuses to ship an
HTML that is missing a catalogue tag.

Usage: python -m forge_tool.export_digest [--out forge_stamp_digest.json]
                                          [--inject examples/forge_layout_author.html]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(REPO, "recipes", "forge_stamps_catalogue.json")

# tag -> (Layout Author profile, default size m, default amplitude m).
# Profiles are the UI's preview shapes; sizes/amps are sane starting
# points from the two forged worlds.
PROFILE_MAP = {
    "mountain":    ("massif",    2200, 650),
    "hills":       ("foothills", 1800, 180),
    "ridges":      ("ridge",     1800, 500),
    "rise":        ("hill",      1700, 450),
    "dunes":       ("foothills", 1500, 120),
    "craters":     ("basin",     1000, -30),
    "island_peak": ("peak",       900, 500),
    "basin":       ("valley",    1500, -25),
    "terraces":    ("plateau",   1000, 150),
    "flat_pad":    ("basin",     1200, -12),
    "mesa":        ("plateau",    500, 250),
}


MARKER = "const BUILTIN_STAMPS = ["


def build_digest():
    cat = json.load(open(CATALOGUE, encoding="utf-8"))
    digest = []
    for m in cat["maps"]:
        prof, size, amp = PROFILE_MAP.get(m["tag"], ("hill", 1000, 300))
        digest.append({
            "name": m["tag"],
            "description": m["character"],
            "profile": prof,
            "default_size_m": size,
            "default_amplitude_m": amp,
        })
    return digest


def inject(html_path, digest):
    """Replace the UI's BUILTIN_STAMPS literal with the real catalogue.

    Returns the stamp count. Refuses (RuntimeError) if the marker or its
    closing bracket is missing — a partial edit of a 600 KB page would
    be worse than no edit.
    """
    src = open(html_path, encoding="utf-8").read()
    start = src.find(MARKER)
    if start < 0:
        raise RuntimeError("%s has no '%s' marker — not the Layout "
                           "Author page this injector knows"
                           % (html_path, MARKER))
    end = src.find("];", start)
    if end < 0:
        raise RuntimeError("%s: BUILTIN_STAMPS block never closes"
                           % html_path)
    rows = "".join(
        "  {name:%s, profile:%s, size:%d, amp:%d, desc:%s},\n"
        % (json.dumps(d["name"]), json.dumps(d["profile"]),
           d["default_size_m"], d["default_amplitude_m"],
           json.dumps(d["description"]))
        for d in digest)
    # catalogue text is a growing input: '];' inside a row would truncate
    # the NEXT run's splice mid-string, '</' would close the <script>
    # element — both are silent corruption of a 662 KB page (audit F1)
    if "];" in rows or "</" in rows:
        raise RuntimeError("catalogue text would break the injected JS "
                           "block ('];' or '</') — sanitize the "
                           "character field first")
    block = (MARKER
             + "  // injected from recipes/forge_stamps_catalogue.json"
             " by export_digest.py — do not hand-edit\n" + rows + "]")
    src = src[:start] + block + src[end + 1:]
    # the static help line under the button carries a literal count
    src = re.sub(r"in use \(\d+ stamps\)",
                 "in use (%d stamps)" % len(digest), src)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(src)
    return len(digest)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        REPO, "examples", "forge_stamp_digest.json"))
    ap.add_argument("--inject", metavar="HTML",
                    help="bake the catalogue into the Layout Author "
                         "page's built-in stamp list (idempotent)")
    a = ap.parse_args(argv)
    digest = build_digest()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"stamps": digest}, f, indent=1)
        f.write("\n")
    print("digest: %s  (%d stamps)" % (a.out, len(digest)))
    if a.inject:
        try:
            n = inject(a.inject, digest)
        except (RuntimeError, OSError) as e:
            print("REFUSE: %s" % e)
            return 2
        print("injected %d stamps into %s" % (n, a.inject))
    return 0


if __name__ == "__main__":
    sys.exit(main())
