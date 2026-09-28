"""verify_grooms_on_disk.py — are the grooms REALLY in the saved character?

The tool that added them is the tool reporting they were added. This asks a
different representation: the bytes of MHC_AlpineHero.uasset on disk, scanned
for the groom asset names.

POSITIVE-CONTROLLED, because a substring search that finds everything proves
nothing. It also searches for groom names that were deliberately NOT selected
(WI_Hair_L_Straight, WI_Beard_L_Full, ...). Those must be ABSENT. If they are
present, the search is matching something other than a real reference and the
whole result is void.

This is the same technique used to verify the landscape Nanite flags from
package bytes on 2026-08-11, and for the same reason: a read-back that reads
what the setter wrote proves only that the value landed.
"""

from __future__ import annotations

import argparse
import os
import sys

WANT = ["Hair_M_Layered", "Beard_M_Stubble", "Mustache_M_Stubble",
        "Eyebrows_M_Dense"]
CONTROL = ["Hair_L_Straight", "Beard_L_Full", "Mustache_L_Handlebar",
           "Eyebrows_S_FlatThin", "Hair_M_Mohawk"]


def find(blob, needle):
    b = needle.encode("ascii")
    n = 0
    i = blob.find(b)
    while i >= 0:
        n += 1
        i = blob.find(b, i + 1)
    # MetaHuman names also appear UTF-16 encoded in some package tables
    b2 = needle.encode("utf-16-le")
    j = blob.find(b2)
    while j >= 0:
        n += 1
        j = blob.find(b2, j + 1)
    return n


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default=os.path.join(
        root, "LandscapeLab", "Content", "Hero", "MHC_AlpineHero.uasset"))
    args = ap.parse_args(argv)

    size = os.path.getsize(args.asset)
    with open(args.asset, "rb") as fh:
        blob = fh.read()
    print("asset : %s" % os.path.basename(args.asset))
    print("size  : %d B" % size)
    print("")

    print("SELECTED grooms -- each must be PRESENT:")
    ok = True
    for w in WANT:
        n = find(blob, w)
        print("   %-22s %s (%d)" % (w, "PRESENT" if n else "ABSENT", n))
        if not n:
            ok = False

    print("")
    print("CONTROL -- grooms deliberately NOT selected, each must be ABSENT:")
    control_clean = True
    for c in CONTROL:
        n = find(blob, c)
        print("   %-22s %s (%d)" % (c, "ABSENT" if not n else "PRESENT", n))
        if n:
            control_clean = False

    print("")
    if not control_clean:
        print("VERDICT WITHHELD: a groom that was never selected appears in")
        print("the bytes, so the search is matching something other than a")
        print("real reference. This result carries no information.")
        return 3
    if ok:
        print("VERDICT: all four selected grooms are in the saved character,")
        print("and five that were not selected are absent. The search")
        print("discriminates, so the presences are evidence.")
        return 0
    print("VERDICT: at least one selected groom is NOT in the saved bytes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
