"""Refuse an AUTHORED cull that should have been derived (E1, 2026-09-09).

WHY THIS EXISTS. `cull_distance_m` used to be the source of truth, and BRIEF 1
measured that every one of its values deleted an object while it was still
15-63 px tall -- four of them deleting trees inside the DETAIL band, where
internal structure is still resolvable. The fix was to derive culls from a
declared camera and pixel thresholds (`recipe.perception`).

A fix like that decays silently. Someone adds a species, types a
`cull_distance_m`, and nothing complains: the plan builds, the placement runs,
every existing gate passes, and the world quietly goes back to authored
metres. This check is what notices.

WHAT IT REFUSES
  1. a `perception` block that is missing or incomplete
  2. a NON-ground-cover species with no measured height, so its cull cannot be
     derived and silently falls back to the authored value
  3. a placed plan whose `cull_cm` disagrees with what the recipe would derive
     for it today -- i.e. a plan that is stale with respect to the perception
     block

WHAT IT DELIBERATELY ALLOWS. Ground cover (Meadow, Blueberry) keeps its
authored cull, because the band below its derived cull is UNOCCUPIED: HLOD
proxies only take over beyond the 256 m streaming range, so culling grass at
its 18.6 m detail boundary would leave it absent from 18.6 m to 256 m with
nothing standing in for it. RULED 2026-09-09 by Ryan: ground cover KEEPS its
authored cull. This check asserts the exclusion is EXPLICIT -- a ground-cover
species must be in place_foliage's GROUND_COVER set, not merely happen to lack
a height. The ruling settles WHICH cull applies; it does not license a silent
exclusion, so the explicitness assertion stands unchanged.

FAIL DIRECTION. Exits non-zero when a cull is authored that should be derived.
It does NOT fail when a derived value is large: the UNCLAMPED 1148.6 m a
conifer's 40 px detail threshold implies on a 23.9 m tree is the correct
consequence, and a check that refused it would be re-imposing the authored
ceiling it exists to remove. (Since the 2026-09-11 R-RANGE ruling the APPLIED
conifer cull is clamped to streaming.main_loading_range_cm = 512 m by
place_foliage._cull_cm_for; 1148.6 is the pre-clamp figure.)

Run: python scripts/check_derived_culls.py
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from place_foliage import (GROUND_COVER, _cull_cm_for,  # noqa: E402
                           _species_heights)

RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
FOLIAGE = os.path.join(REPO, "foliage")
REQUIRED_PERCEPTION = ("declared_camera", "thresholds_px", "fade_seconds",
                       "cull_threshold")
REQUIRED_THRESHOLDS = ("vanish", "silhouette", "detail")


def main():
    fails, notes = [], []
    recipe = json.load(open(RECIPE, encoding="utf-8"))

    p = recipe.get("perception")
    if not p:
        print("FAIL: recipes/alpine_8k.json has no `perception` block. Culls "
              "would fall back to authored metres, which BRIEF 1 measured as "
              "deleting objects at 15-63 px.")
        return 1
    for k in REQUIRED_PERCEPTION:
        if k not in p:
            fails.append("perception is missing `%s`" % k)
    for k in REQUIRED_THRESHOLDS:
        if k not in (p.get("thresholds_px") or {}):
            fails.append("perception.thresholds_px is missing `%s`" % k)

    heights = _species_heights()
    if not heights:
        fails.append("no measured heights: _verify/bench/2026-09-05/"
                     "species_heights.json is absent, so NOTHING can be "
                     "derived and every species would silently fall back")

    rng_cm = int((recipe.get("streaming") or {}).get(
        "main_loading_range_cm") or 0)
    species = (recipe.get("foliage") or {}).get("species") or []
    if not species:
        # NN13: the loop below simply does not run on an empty set, so with a
        # present perception block the check would fall through to the PASS
        # ("0 species ... No authored cull is standing in") -- a green verdict
        # over zero comparisons. A world with no foliage species is not a
        # world whose culls are all derived; it is one with nothing to check.
        fails.append("recipes/alpine_8k.json foliage.species is EMPTY -- a "
                     "PASS over zero species is not 'every cull is derived', "
                     "it is 'I looked at nothing' (non-negotiable 13)")
    for sp in species:
        name = sp["name"]
        cull_cm, d = _cull_cm_for(sp, p, heights, rng_cm)

        # The plan-staleness check runs for EVERY species with a plan.
        # FIXED 2026-09-11: it used to sit after a `continue` for derived
        # species, so the one class it was written for was never checked
        # -- the docstring's promise (3) was dead code (direction 3: the
        # least-exercised path is the broken one).
        plan = os.path.join(FOLIAGE, "%s_%s.json" % (recipe["biome_id"], name))
        if os.path.isfile(plan):
            got = int(json.load(open(plan, encoding="utf-8")).get("cull_cm")
                      or 0)
            if got != cull_cm:
                fails.append("%s: plan cull_cm %d != recipe-derived %d — the "
                             "plan is stale with respect to perception"
                             % (name, got, cull_cm))

        if str(d["applied"]).startswith("derived"):
            continue
        if name in GROUND_COVER:
            notes.append("%s keeps its authored %.0f m by explicit exclusion "
                         "(derived would be %s m) — RULED 2026-09-09"
                         % (name, d["authored_cull_m"],
                            d.get("derived_cull_m")))
            continue
        fails.append("%s falls back to an AUTHORED cull (%s) and is not in "
                     "GROUND_COVER: %s"
                     % (name, d["authored_cull_m"], d.get("reason")))

    for n in notes:
        print("  note  %s" % n)
    if fails:
        print()
        for f in fails:
            print("FAIL: %s" % f)
        return 1
    print("check_derived_culls — %d species, %d derived, %d excluded ground "
          "cover. No authored cull is standing in for a derivable one."
          % (len(species), len(species) - len(notes), len(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
