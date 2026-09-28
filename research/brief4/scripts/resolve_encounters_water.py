"""resolve_encounters_water.py -- Brief-4 CARVE_PLAN T8 RESOLUTION.

T8 detection (encounters_in_water.py) found 12 of 317 verified encounters
inside Lake A's §7 footprint, all scavenger (11 below 180 m; #308 a
borderline shoal at 180.7 m, inside the footprint by flood-fill though
0.7 m above the surface). This REMOVES them from
encounters/alpine_8k_verified.json and re-freezes the set with a
provenance block + a new evidence stamp -- it does NOT relocate (RULING
§4.3 resolves drowned rows by removal per encounters.json density, which
is a MAX not a floor; removing 12 of 317 stays well inside every gate).

Idempotent: re-running after the removal is a no-op (the drowned indices
are already gone; it asserts they are absent and rewrites nothing new).

Read-back (rule 12/13): asserts exactly `drowned_total` rows are dropped,
by INDEX matched to loc_cm (not by count alone), and the surviving count
equals total - drowned. REFUSES on any mismatch.

Usage:
  python resolve_encounters_water.py --detection <encounters_in_water.json>
      --verified encounters/alpine_8k_verified.json [--write]
"""
import argparse
import datetime as _dt
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detection", required=True)
    ap.add_argument("--verified", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    det = _load(a.detection)
    ver = _load(a.verified)
    rows = ver["encounters"]
    drowned = det["drowned"]
    dcount = det["drowned_total"]
    if len(drowned) != dcount:
        sys.exit("REFUSE: detection drowned_total %d != len(drowned) %d"
                 % (dcount, len(drowned)))

    # Match each drowned row to the verified row by INDEX and confirm the
    # loc_cm agrees -- indices alone could drift if the file were re-sorted.
    already = 0
    to_drop = []
    for d in drowned:
        i = d["index"]
        if i >= len(rows):
            # already removed in a prior run; verify by absence of loc
            already += 1
            continue
        r = rows[i]
        if [round(c, 1) for c in r["loc_cm"]] != \
                [round(c, 1) for c in d["loc_cm"]]:
            # index no longer maps to the same row -> the set already
            # changed shape; fall back to loc match below
            already = -1
            break
        to_drop.append(i)

    if already == -1 or (already and not to_drop):
        # loc-based idempotent path: drop any row whose loc matches a
        # drowned loc; if none match, the removal already happened.
        dlocs = {tuple(round(c, 1) for c in d["loc_cm"]) for d in drowned}
        keep = [r for r in rows
                if tuple(round(c, 1) for c in r["loc_cm"]) not in dlocs]
        removed = len(rows) - len(keep)
        if removed == 0:
            print("idempotent: 0 drowned rows present; set already resolved "
                  "(%d encounters)" % len(rows))
            return 0
    else:
        if len(to_drop) != dcount:
            sys.exit("REFUSE: matched %d drowned rows by index, detection "
                     "says %d" % (len(to_drop), dcount))
        dropset = set(to_drop)
        keep = [r for i, r in enumerate(rows) if i not in dropset]
        removed = len(rows) - len(keep)

    if removed != dcount:
        sys.exit("REFUSE: would remove %d rows, detection drowned_total %d"
                 % (removed, dcount))

    # rebuild counts by archetype from the surviving rows
    by_arche = {}
    for r in keep:
        by_arche[r["archetype"]] = by_arche.get(r["archetype"], 0) + 1
    new_total = len(keep)

    date = _dt.date.today().isoformat()
    ver["encounters"] = keep
    ver["counts"] = {"encounters": new_total, "by_archetype": by_arche}
    ver["_water_removal"] = {
        "date": date,
        "removed": dcount,
        "from_total": len(rows),
        "to_total": new_total,
        "all_archetype": "scavenger",
        "body": "A_east_basin (id 4893 @ 180 m)",
        "detection": os.path.relpath(a.detection, REPO),
        "removed_indices": [d["index"] for d in drowned],
        "_why": "CARVE_PLAN T8: these sat inside Lake A's §7 connected-"
                "component footprint (placed on the pre-water surface). "
                "Resolved by REMOVAL per RULING §4.3 -- density is a MAX, "
                "so -12 of 317 stays inside every gate; separation and "
                "settlement exclusion are unaffected. Re-frozen this stamp.",
        "_re_freeze": "the verified set is re-frozen at this removal; the "
                      "plan (encounters/alpine_8k_all.json) is unchanged and "
                      "the placer now carries a `water` exclusion so a "
                      "regeneration will not re-introduce drowned rows."}

    if not a.write:
        print("DRY RUN: would remove %d rows (%s), %d -> %d"
              % (dcount, ", ".join(str(d["index"]) for d in drowned),
                 len(rows), new_total))
        print("  new counts by archetype: %s" % by_arche)
        return 0

    with io.open(a.verified, "w", encoding="utf-8") as fh:
        json.dump(ver, fh, indent=1, ensure_ascii=False)
    # read-back
    rb = _load(a.verified)
    if len(rb["encounters"]) != new_total:
        sys.exit("REFUSE (read-back): wrote %d, re-read %d"
                 % (new_total, len(rb["encounters"])))
    print("WROTE %s: %d -> %d encounters (removed %d drowned scavengers)"
          % (a.verified, len(rows), new_total, dcount))
    print("  counts by archetype: %s" % by_arche)


if __name__ == "__main__":
    main()
