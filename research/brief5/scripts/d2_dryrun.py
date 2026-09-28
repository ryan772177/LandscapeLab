#!/usr/bin/env python3
"""Brief 5 D2 dry-run analyser: trees per species per zone, before vs after.

Offline, read-only. Compares two sets of foliage plan JSONs (the shipped
foliage/ plans = BEFORE, at m=1; and the D2 dry-run plans built under the
density zone map = AFTER) and reports, per tree species and per zone:

  BEFORE count, AFTER count, ratio (the realised density multiplier),

where a tree's ZONE is the station cull-disc it falls inside (forest_floor,
plaza, treeline; the minimum-cap disc wins an overlap, matching zone_map.py's
zone assignment), or "open" outside every disc. Disc centres and radius are
read from the same zone_map.json the placement used, so this analyser and the
placer share ONE definition of the zones (rule 0).

Usage:
  python d2_dryrun.py --before <repo>/foliage --after <dryrun_dir> \
      --zone-map <repo>/research/brief5/derived/zone_map.json --out <json>
"""
import argparse
import json
import os

import numpy as np

SPECIES = ["Conifer", "ConiferPine", "SpruceSub", "SpruceSapling"]
BIOME = "alpine_8k"


def load_xy_cm(plans_dir, sp):
    """Nx2 array of instance world XY in cm, from alpine_8k_<sp>.json."""
    path = os.path.join(plans_dir, "%s_%s.json" % (BIOME, sp))
    d = json.load(open(path, encoding="utf-8"))
    rows = d.get("instances") or []
    if not rows:
        return np.zeros((0, 2)), d
    a = np.array([[r[0], r[1]] for r in rows], dtype=np.float64)
    return a, d


def zone_of(xy_cm, centers_cm, radius_cm, caps):
    """Zone label per instance. Inside a disc -> that station; the lowest-cap
    disc wins an overlap (forest_floor cap < target, so it wins by construction).
    Outside every disc -> 'open'. xy_cm is Nx2 cm; centers_cm {name:(x,y)} cm."""
    n = len(xy_cm)
    labels = np.array(["open"] * n, dtype=object)
    best_cap = np.full(n, np.inf)
    # order does not matter: we keep the minimum-cap disc that contains each point
    for name, (cx, cy) in centers_cm.items():
        d = np.hypot(xy_cm[:, 0] - cx, xy_cm[:, 1] - cy)
        inside = d <= radius_cm
        take = inside & (caps[name] < best_cap)
        labels[take] = name
        best_cap[take] = caps[name]
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True, help="shipped foliage/ dir (m=1)")
    ap.add_argument("--after", required=True, help="D2 dry-run plans dir")
    ap.add_argument("--zone-map", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    zm = json.load(open(a.zone_map, encoding="utf-8"))
    P, caps_j = zm["params"], zm["caps"]
    radius_cm = float(P["disc_radius_cm"])
    centers_cm = {n: (float(c[0]) * 100.0, float(c[1]) * 100.0)
                  for n, c in P["disc_centers_m"].items()}
    caps = {n: float(caps_j[n]["cap"]) for n in centers_cm}
    zones = ["forest_floor", "plaza", "treeline", "open"]

    per_species = {}
    tot_before = {z: 0 for z in zones}
    tot_after = {z: 0 for z in zones}
    grand = {"before": 0, "after": 0}
    for sp in SPECIES:
        bxy, _ = load_xy_cm(a.before, sp)
        axy, adoc = load_xy_cm(a.after, sp)
        bz = zone_of(bxy, centers_cm, radius_cm, caps)
        az = zone_of(axy, centers_cm, radius_cm, caps)
        row = {}
        for z in zones:
            nb = int(np.sum(bz == z))
            na = int(np.sum(az == z))
            tot_before[z] += nb
            tot_after[z] += na
            row[z] = {"before": nb, "after": na,
                      "ratio": (round(na / nb, 3) if nb else None)}
        b_tot, a_tot = int(len(bxy)), int(len(axy))
        grand["before"] += b_tot
        grand["after"] += a_tot
        row["ALL"] = {"before": b_tot, "after": a_tot,
                      "ratio": (round(a_tot / b_tot, 3) if b_tot else None)}
        row["_density_zone_declared"] = adoc.get("density_zone")
        per_species[sp] = row

    zone_tot = {z: {"before": tot_before[z], "after": tot_after[z],
                    "ratio": (round(tot_after[z] / tot_before[z], 3)
                              if tot_before[z] else None),
                    "cap": (caps[z] if z in caps else None)}
                for z in zones}
    zone_tot["ALL"] = {"before": grand["before"], "after": grand["after"],
                       "ratio": (round(grand["after"] / grand["before"], 3)
                                 if grand["before"] else None)}

    out = {
        "_what": "Brief 5 D2 dry-run: trees per species per zone, before(m=1) vs after(zone map).",
        "_before_dir": a.before, "_after_dir": a.after,
        "_zone_map": os.path.relpath(a.zone_map),
        "_zone_rule": ("disc containment (512 m); lowest-cap disc wins overlap; "
                       "outside all = open. Same discs as zone_map.py."),
        "caps": caps,
        "per_species": per_species,
        "per_zone_total": zone_tot,
        "MAX_INSTANCES_note": ("place_foliage MAX_INSTANCES = 250,000; the AFTER "
                               "total below is the count the density upgrade implies."),
    }
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, indent=1) + "\n")

    # human table
    print("Brief 5 D2 dry-run -- trees per zone, before(m=1) -> after(zone map)")
    print("%-14s %12s %12s %12s %12s %10s" %
          ("species", "forest_floor", "plaza", "treeline", "open", "ALL"))
    for sp in SPECIES:
        r = per_species[sp]
        print("%-14s %12s %12s %12s %12s %10s" % (
            sp,
            "%d/%d" % (r["forest_floor"]["before"], r["forest_floor"]["after"]),
            "%d/%d" % (r["plaza"]["before"], r["plaza"]["after"]),
            "%d/%d" % (r["treeline"]["before"], r["treeline"]["after"]),
            "%d/%d" % (r["open"]["before"], r["open"]["after"]),
            "%d/%d" % (r["ALL"]["before"], r["ALL"]["after"])))
    print("-" * 80)
    zt = zone_tot
    print("%-14s %12s %12s %12s %12s %10s" % (
        "TOTAL",
        "%d/%d" % (zt["forest_floor"]["before"], zt["forest_floor"]["after"]),
        "%d/%d" % (zt["plaza"]["before"], zt["plaza"]["after"]),
        "%d/%d" % (zt["treeline"]["before"], zt["treeline"]["after"]),
        "%d/%d" % (zt["open"]["before"], zt["open"]["after"]),
        "%d/%d" % (zt["ALL"]["before"], zt["ALL"]["after"])))
    print("ratio (after/before): " + "  ".join(
        "%s=%s" % (z, zt[z]["ratio"]) for z in zones + ["ALL"]))
    print("caps: " + "  ".join("%s=%.3f" % (z, caps[z]) for z in caps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
