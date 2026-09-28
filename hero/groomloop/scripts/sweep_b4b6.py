"""sweep_b4b6.py -- drive B4 and B6 together instead of trading them.

    python sweep_b4b6.py

I recorded B4 (no scalp through the top) and B6 (tips clump into locks) as
"antagonistic by construction". That is a claim about the MECHANISM, and it was
made without testing the one parameter that decides whether it is true.

The clump gather is ramped along the strand by `t ** clump_taper`. At a LOW
taper the gathering starts near the root, so strand BODIES converge and the
crown they were covering opens -- which is the trade I observed. At a HIGH
taper the gathering is confined to the last part of the strand: tips clump for
B6 while bodies stay spread and keep covering the scalp for B4.

So the two are not antagonistic; they were coupled by a profile shape. This
sweeps the taper and the strength together and reports both benchmarks, so the
claim is settled by measurement either way.

Runs the whole chain per point (p0 -> p3 -> p4 -> p5) because the passes
interact -- measuring p4 alone would answer a question nobody asked.
"""

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
BL = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SC = os.path.join(REPO, "hero", "groomloop", "scripts")
DL = os.path.join(REPO, "hero", "groomloop", "difflocks")

# FIRST SWEEP RESULT, kept because it killed my own hypothesis:
#   taper 1.9 -> 5.5 moved B6 1.0888 -> 1.0274, i.e. the WRONG WAY, and B4
#   passed only when standoff and keep_frac_side moved. Taper cannot touch B6:
#   the gather weight AT THE TIP is `strength` whatever the taper, and B6
#   measures tips. The taper only shapes the body.
#
# B6 is a VARIANCE statistic -- it wants tips concentrated with EMPTY cells
# between them, and more strands on the sides LOWER it by filling cells in. So
# the lever is the NUMBER OF LOCKS: fewer, larger blocks means each lock draws
# from more strands and the gaps between locks stay empty.
# SECOND SWEEP was read through the BROKEN third B6 and is void: it reported
# B6 flat at 0.99-1.04 across a 27-fold change in lock count, which was the
# metric refusing to respond, not the groom refusing to clump.
#
# Re-swept on the corrected (fourth) B6. The extreme point that passed both --
# block 2400, secondary clumping OFF -- is ~19 locks over 45,000 strands, which
# is dreadlocks, and it satisfies B6 by deleting the thing spec 5 asks for
# ("minor secondary clumping pass"). A benchmark passed by abandoning the spec
# it was written to serve is not passed. So: sweep the usable range and keep
# the secondary pass alive.
GRID = [
    # (clump_block, clump_strength, clump2_strength, standoff_deg, keep_frac_side)
    (90, 0.96, 0.22, 58.0, 0.50),      # the previous shipped point, as control
    (180, 0.96, 0.20, 58.0, 0.50),
    (300, 0.97, 0.18, 58.0, 0.50),
    (450, 0.97, 0.15, 58.0, 0.52),
    (700, 0.97, 0.12, 58.0, 0.52),
]


def run(args):
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO)


def marker(txt, tag):
    i = txt.find(tag)
    return json.loads(txt[i + len(tag):].splitlines()[0]) if i >= 0 else None


def main():
    print("%-6s %-7s %-6s %-9s %-6s | %-11s %-11s %s"
          % ("block", "streng", "sec", "standoff", "side", "B4", "B6", "curves"))
    for blk, streng, s2, stand, side in GRID:
        prm = {"clump_block": blk, "clump_strength": streng,
               "clump2_strength": s2,
               "standoff_deg": stand, "keep_frac_side": side}
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
        json.dump(prm, fh)
        fh.close()
        src = os.path.join(DL, "dl_P1.blend")
        for stage in ("p0", "p3", "p4", "p5"):
            dst = os.path.join(DL, "dl_sweep_%s.blend" % stage)
            p = run([BL, "--background", src, "--python",
                     os.path.join(SC, "restyle_p234.py"), "--", dst, stage,
                     fh.name])
            if marker(p.stdout + p.stderr, "__PX__") is None:
                print("  stage %s FAILED: %s" % (stage,
                                                 (p.stdout + p.stderr)[-300:]))
                break
            src = dst
        else:
            p = run([BL, "--background", src, "--python",
                     os.path.join(SC, "benchmarks.py"), "--"])
            b = marker(p.stdout + p.stderr, "__BM__")
            if b is None:
                print("  benchmarks FAILED")
                continue
            v = b["verdict"]
            print("%-6d %-7.2f %-6.2f %-9.0f %-6.2f | %-11s %-11s %d"
                  % (blk, streng, s2, stand, side,
                     "%.4f %s" % (b["B4_scalp_visible_top"],
                                  "OK" if v["B4_scalp_visible_top"] == "PASS"
                                  else "no"),
                     "%.4f %s" % (b["B6_cluster_separation"],
                                  "OK" if v["B6_cluster_separation"] == "PASS"
                                  else "no"),
                     b["curves"]))
        os.unlink(fh.name)


main()
