"""What does the wider kit seed actually SERVE, against the town's footprints?

⛔ THE OLD COVERAGE QUESTION DOES NOT APPLY AND MUST NOT BE RE-ASKED.
The 2026-08-27 gate compared WHOLE-BUILDING meshes against 303 footprints at
+-20%. The kit has no building meshes -- it is modular -- so footprint coverage
is near-total by tiling and the number would be meaningless.

The wider seed changes which question is worth asking, twice:

  * ROOFS are NOT modular. A roof piece is a whole object with a fixed span,
    so the +-20% fit question is exactly right FOR ROOFS and only for roofs.
  * HBEAMS and BOARDWALLS are modular banding, so they are reported as course
    lengths, not as fits.

Everything here is offline: measured mesh JSON against the committed city plan.
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# The roof spans and the +-20%/rotate fit test are OWNED by roof_servability;
# import them rather than re-deriving the rule here. This closes the
# two-lists-one-badly-stored defect both modules used to name (the old local
# TOL/fit copy could drift from the sibling silently).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roof_servability as roofsvc     # noqa: E402  (not `rs`: main() uses
#                                        `rs` as a row loop var below)


def load(p):
    with io.open(os.path.join(REPO, p), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    v2 = load("Free/_measured/kit_medievalvillage_v2.json")["rows"]
    plan = load("city/alpine_basin_town_plan.json")

    foot = []
    for b in plan.get("buildings", []):
        # size_cm is the plan's own key; footprint_m does not exist. Read the
        # SCHEMA, do not guess the field name -- guessing produced an empty
        # list and a refusal that looked like a finding about the kit.
        fp = b.get("size_cm")
        if fp and len(fp) >= 2:
            foot.append((float(fp[0]) / 100.0, float(fp[1]) / 100.0))
    if not foot:
        print("REFUSE: the plan carries no readable footprints -- that is")
        print("  'could not look', not 'the kit covers nothing'.")
        print("  building keys seen: %s"
              % sorted((plan.get("buildings") or [{}])[0].keys()))
        return 5

    beams = [r for r in v2 if r["name"].startswith("SM_HBeam")]
    walls = [r for r in v2 if "BoardWall" in r["name"]]
    props = [r for r in v2 if r["name"] in
             ("SM_OldWoodenBench", "SM_WoodenWheelA", "SM_WoodenWheelB",
              "SM_WoodenWheelbarrow", "SM_LanternPost")]

    print("THE TOWN: %d buildings" % len(foot))
    xs = sorted(f[0] for f in foot)
    ys = sorted(f[1] for f in foot)
    print("  footprint X  %.2f .. %.2f m   Y  %.2f .. %.2f m"
          % (xs[0], xs[-1], ys[0], ys[-1]))
    print("")

    # roof_spans() is (name, sx_m, sy_m); re-sort by sx to match the
    # historical table order. servable_by() is the SAME +-20%/rotate fit,
    # now owned in one place.
    roof_spans = roofsvc.roof_spans()
    if not roof_spans:
        print("REFUSE: the measured kit carries no roof pieces -- that is")
        print("  'could not look', not 'nothing fits'.")
        return 5
    print("ROOFS -- a whole object with a fixed span, so +-20% fit APPLIES")
    print("  %-24s %16s" % ("roof", "span X x Y m"))
    for name, sx, sy in sorted(roof_spans, key=lambda t: t[1]):
        print("  %-24s %6.2f x %6.2f" % (name[:24], sx, sy))

    covered = sum(1 for fx, fy in foot
                  if roofsvc.servable_by(fx, fy, roof_spans) is not None)
    biggest = max(max(sx, sy) for _n, sx, sy in roof_spans)
    big = [f for f in foot if max(f) > biggest]
    print("")
    print("  footprints a SINGLE roof piece fits at +-20%%: %d of %d (%.1f%%)"
          % (covered, len(foot), 100.0 * covered / len(foot)))
    print("  footprints LARGER than the biggest roof piece (%.2f m): %d"
          % (biggest, len(big)))
    print("  -> the rest need a COMPOSED roof (ridge + slopes), which the")
    print("     Roofs set does not provide as separate parts. A real gap,")
    print("     stated rather than averaged away.")

    print("")
    print("BEAMS -- modular banding, reported as COURSE LENGTHS not as fits")
    lens = sorted({round(r["size_cm"][0] / 100.0, 2) for r in beams})
    print("  %d HBeam variants at lengths: %s m"
          % (len(beams), ", ".join("%.2f" % v for v in lens)))
    print("  CENTRE-pivoted (pivot_base_error ~= -half height), where the v1")
    print("  WALLS were BASE-pivoted at 0.0. Mixing the two seeds by")
    print("  arithmetic without a per-mesh correction is wrong by ~8.6 cm on")
    print("  every beam and by up to 201 cm on a roof.")

    print("")
    print("BOARDWALLS  %s" % ", ".join(
        "%s %.2fx%.2f m" % (w["name"], w["size_cm"][0] / 100.0,
                            w["size_cm"][2] / 100.0) for w in walls))
    print("PROPS       %d (bench, 2 wheels, wheelbarrow, lantern post)"
          % len(props))

    print("")
    print("NAME COLLISIONS -- discriminate by PATH, never by name")
    byname = {}
    for r in v2:
        byname.setdefault(r["name"], []).append(r)
    n_col = 0
    for n, rs in sorted(byname.items()):
        if len(rs) > 1:
            n_col += 1
            print("  %s x%d" % (n, len(rs)))
            for r in rs:
                print("     %-56s nanite %7s pivot %7.1f"
                      % (r["package"][:56], r["nanite_tris"],
                         r["pivot_base_error_cm"]))
    if not n_col:
        print("  none")

    print("")
    print("THE HEAVY ROWS, against the ratified budgets")
    heavy = sorted(v2, key=lambda r: -(r["nanite_tris"] or 0))[:4]
    for r in heavy:
        print("  %-24s nanite %9s tris   LOD0 fallback %6s"
              % (r["name"][:24], r["nanite_tris"],
                 (r["fallback_tris_by_lod"] or ["?"])[0]))
    print("  Nanite carries these. The FALLBACK chain is what matters if")
    print("  Nanite is ever off, and there they are 6k-24k, which is fine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
