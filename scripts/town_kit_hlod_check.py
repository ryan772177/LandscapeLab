"""town_kit_hlod_check.py -- offline acceptance: are the kit houses IN the built HLOD? (2026-10-09)

    python scripts/town_kit_hlod_check.py --since <run dir>/BUILD_START_MARKER

Kit meshes are referenced from the INSTANCED layer's packages -- labels Alpine8K_MainPartition_L0_X<i>_Y<j>, the
MainPartition source grid of 12,800 cm (pilot 2026-10-08j: Merged L0 X-9_Y10 was built from MainPartition
X-18..-17 / Y20..21, so a Merged L0 cell is 2x2 of them) -- not from the Merged layer, whose output is baked and
names no source mesh (audit 2026-10-09 F5). For every house, its MainPartition cell = (floor(x/12800),
floor(y/12800)) must have a package that (a) was written after the marker and (b) references SM_MedievalModular* /
SM_House0*_Roof. Packages come from _verify/hlod/hlod_packages.txt, which must be NEWER than the last -SetupHLODs
log (hlod_gitignore --apply rewrites it). Exit 0 = every house cell passes; 4 = any fails or nothing counted.
LIMIT (re-audit 2026-10-09 F2): every house uses the same meshes, so a cell passes when its fresh package names ANY
kit mesh -- it proves each house CELL was rebuilt with kit content, NOT that every individual house is in it.
"""
import argparse
import glob
import io
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = re.compile(rb"SM_MedievalModular\w+|SM_House0\d_Roof\w*")
LABEL = re.compile(rb"Alpine8K_MainPartition_L0_X(-?\d+)_Y(-?\d+)")
CELL = 12800.0
PKGS = os.path.join(REPO, "_verify", "hlod", "hlod_packages.txt")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True, help="the build's BUILD_START_MARKER file")
    a = ap.parse_args(argv)
    t0 = os.path.getmtime(a.since)
    setups = glob.glob(os.path.join(REPO, "_verify", "hlod", "*_setup", "setup.log"))
    if not setups or os.path.getmtime(PKGS) <= max(os.path.getmtime(s) for s in setups):
        print("REFUSE: %s is not newer than the last -SetupHLODs log -- run hlod_gitignore.py --apply" % PKGS)
        return 4
    man = json.load(io.open(os.path.join(REPO, "city", "alpine_basin_town_kit_manifest.json"), encoding="utf-8"))
    want = sorted(set((int(math.floor(h["loc_cm"][0] / CELL)), int(math.floor(h["loc_cm"][1] / CELL)))
                      for h in man["houses"]))
    rels = [l.strip() for l in io.open(PKGS, encoding="utf-8") if l.strip() and not l.startswith("#")]
    cells, n_kit = {}, 0
    for rel in rels:
        f = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(f):
            continue
        b = io.open(f, "rb").read()
        m = LABEL.search(b)
        if not m:
            continue
        k = len(KIT.findall(b))
        n_kit += k > 0
        key = (int(m.group(1)), int(m.group(2)))
        fresh = os.path.getmtime(f) > t0
        prev = cells.get(key)
        if prev is None or (k, fresh) > (prev[0], prev[1]):
            cells[key] = (k, fresh, rel)
    print("house MainPartition cells: %d; HLOD packages listed %d; packages referencing kit meshes %d"
          % (len(want), len(rels), n_kit))
    bad = []
    for c in want:
        k, fresh, rel = cells.get(c, (0, False, None))
        print("  MP L0 X%d_Y%d  kit refs %4d  built after marker %s" % (c[0], c[1], k, fresh))
        if rel is None or k == 0 or not fresh:
            bad.append(c)
    if not want or n_kit == 0 or bad:
        print("VERDICT: FAIL -- %d of %d house cells lack a fresh package with kit meshes: %s" % (len(bad), len(want), bad))
        return 4
    print("VERDICT: OK -- every house cell rebuilt and referencing kit meshes; per-house inclusion NOT proven")
    return 0


if __name__ == "__main__":
    sys.exit(main())
