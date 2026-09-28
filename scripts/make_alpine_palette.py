"""make_alpine_palette.py — resolve the alpine palette into recipes/alpine.json.

OFFLINE. No editor, no `unreal` import. Joins two files that are
deliberately kept apart:

    recipes/alpine_palette_curation.json   JUDGEMENTS  — which asset, what
                                           role, which pass, and why.
                                           Contains NO measurements.
    Free/_measured/fab_registry_*.json     MEASUREMENTS — triangles, bounds,
                                           material and collision counts,
                                           read from the asset registry with
                                           zero assets loaded.

and writes the resolved `palette` block into `recipes/alpine.json`.

WHY THE SPLIT IS THE WHOLE POINT
--------------------------------
A palette is a DERIVED RECORD about project state, and CLAUDE.md
non-negotiable 15 says those verify against the artefact at the moment
they are written. If curation and measurement lived in one hand-edited
file, every triangle count in it would be a number I typed, and a typo
would be indistinguishable from a fact. Here the curation file physically
cannot state a measurement, and this script physically cannot invent one:
every number in the output is looked up, and a curated path that is not in
the registry is a REFUSAL that writes nothing.

WHAT `verified` MEANS, AND WHY IT IS ALWAYS FALSE HERE
------------------------------------------------------
The campaign brief rules: "Verified flags stay NO until render-proved."
Nothing in this palette has been spawned or rendered. Registry tags prove
an asset EXISTS and how big it is; they prove nothing about whether it
loads, looks right, or is the correct biome. So this script writes
`verified: false` on every entry with the specific reason, and offers no
argument to override it. Promotion to true happens in the pass that
renders the asset, not here.

NANITE IS UNKNOWN, NOT OFF
--------------------------
The registry audit requested `NaniteEnabled` on all 940 meshes across the
three packs and the tag came back on NONE of them. That is a failed
measurement, so it is reported as "UNKNOWN — registry tag absent" rather
than as a value (CLAUDE.md non-negotiable 6: a failed measurement reports
that it could not measure, never the number the broken measurement
produced). Pass 3 must confirm Nanite in the editor before placing.

Exit codes:
  0  palette resolved and written (or unchanged)
  2  a curated asset is not in any registry, or an input file is missing
  3  the curation file is structurally invalid
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATION = os.path.join(REPO, "recipes", "alpine_palette_curation.json")
RECIPE = os.path.join(REPO, "recipes", "alpine.json")
MEASURED = os.path.join(REPO, "Free", "_measured")

PACKS = ("KiteDemo", "DragonCave", "Atlantis_Ruins", "StampIt", "Mannequin")

VALID_ADMIT = ("YES", "CONDITIONAL", "HAZARD")

NOT_VERIFIED_REASON = (
    "not spawned and not rendered; registry tags prove existence and size "
    "only"
)
NANITE_UNKNOWN = "UNKNOWN — registry tag absent"


def load_json(path, what):
    if not os.path.isfile(path):
        raise IOError("{0} not found: {1}".format(what, path))
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_index():
    """path -> registry record, across every pack that has been measured.

    A pack with no registry file is SKIPPED with a note rather than
    treated as empty, so "this pack was never measured" cannot silently
    become "this asset does not exist".
    """
    index = {}
    seen, missing = [], []
    for pack in PACKS:
        path = os.path.join(MEASURED, "fab_registry_{0}.json".format(pack))
        if not os.path.isfile(path):
            missing.append(pack)
            continue
        with open(path, "r", encoding="utf-8") as fh:
            reg = json.load(fh)
        for rec in reg.get("assets", []):
            rec = dict(rec)
            rec["_pack"] = pack
            index[rec.get("path")] = rec
        seen.append((pack, len(reg.get("assets", []))))
    return index, seen, missing


def dims_m(rec):
    raw = rec.get("ApproxSize")
    if not raw:
        return None
    try:
        parts = [float(v) for v in str(raw).split("x")]
    except ValueError:
        return None
    if len(parts) != 3:
        return None
    return [round(v / 100.0, 3) for v in parts]


def measure(rec):
    """Everything the registry can say about one mesh. Absences stay absent."""
    out = {
        "pack": rec.get("_pack"),
        "class": rec.get("class"),
        "triangles": None,
        "vertices": None,
        "material_slots": None,
        "collision_prims": None,
        "dims_m": None,
        "bbox_area_m2": None,
        "tri_per_m2": None,
        "shape": None,
        "nanite": NANITE_UNKNOWN,
        "unmeasured": [],
    }

    for key, field in (("Triangles", "triangles"), ("Vertices", "vertices"),
                       ("Materials", "material_slots"),
                       ("CollisionPrims", "collision_prims")):
        raw = rec.get(key)
        try:
            out[field] = int(raw)
        except (TypeError, ValueError):
            out["unmeasured"].append("{0} tag absent".format(key))

    d = dims_m(rec)
    if d is None:
        out["unmeasured"].append("ApproxSize tag absent or unparseable")
        return out

    out["dims_m"] = d
    x, y, z = d
    area = 2.0 * (x * y + y * z + z * x)
    if area > 0.0:
        out["bbox_area_m2"] = round(area, 2)
        if out["triangles"] is not None:
            out["tri_per_m2"] = round(out["triangles"] / area, 1)
        lo, hi = min(d), max(d)
        out["shape"] = "planar" if (lo / hi) < 0.20 else "blob"
    else:
        out["unmeasured"].append("degenerate bounding box")
    return out


def resolve(curation, index):
    """Curated entries joined with measurements. Raises on any unknown path."""
    entries, unknown = [], []

    for c in curation.get("entries", []):
        for required in ("id", "path", "role", "pass", "admit"):
            if required not in c:
                raise ValueError(
                    "curation entry missing {0!r}: {1!r}".format(required, c))
        if c["admit"] not in VALID_ADMIT:
            raise ValueError(
                "entry {0!r} has admit={1!r}; valid: {2}".format(
                    c["id"], c["admit"], list(VALID_ADMIT)))

        rec = index.get(c["path"])
        if rec is None:
            unknown.append((c["id"], c["path"]))
            continue

        entry = {
            "id": c["id"],
            "path": c["path"],
            "role": c["role"],
            "pass": c["pass"],
            "admit": c["admit"],
            "note": c.get("note", ""),
            "measured": measure(rec),
            "verified": False,
            "verified_reason": NOT_VERIFIED_REASON,
        }
        entries.append(entry)

    if unknown:
        raise LookupError(unknown)

    ids = [e["id"] for e in entries]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError("duplicate palette ids: {0}".format(dupes))

    entries.sort(key=lambda e: (e["pass"], e["role"], e["id"]))
    return entries


def budget_note(entries):
    """The one number a reader of this palette most needs and would not compute.

    Talus is the only role in the palette that wants HIGH INSTANCE COUNTS of
    a HIGH-TRIANGLE asset, and this project has already had one GPU device
    hang. Stating the per-instance cost next to the palette is cheaper than
    discovering it during Pass 3.
    """
    talus = [e for e in entries if e["role"].startswith("talus")]
    if not talus:
        return None
    costs = [(e["id"], e["measured"]["triangles"]) for e in talus
             if e["measured"]["triangles"] is not None]
    if not costs:
        return None
    costs.sort(key=lambda kv: -kv[1])
    worst_id, worst = costs[0]
    cheap_id, cheap = costs[-1]
    return {
        "role": "talus_field",
        "most_expensive": {"id": worst_id, "triangles": worst},
        "cheapest": {"id": cheap_id, "triangles": cheap},
        "warning": (
            "At {0} tris, {1:,} instances of {2} alone reach the 39.6M "
            "triangle load the conifer forest already carries. Pass 3 must "
            "state a talus instance ceiling BEFORE scattering, and prefer "
            "{3} ({4} tris) for bulk coverage."
        ).format(worst, max(1, 39_600_000 // max(worst, 1)), worst_id,
                 cheap_id, cheap),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="write the palette into recipes/alpine.json")
    args = ap.parse_args(argv)

    try:
        curation = load_json(CURATION, "curation file")
        recipe = load_json(RECIPE, "recipe")
    except IOError as exc:
        print("REFUSE: {0}".format(exc))
        return 2

    index, seen, missing = build_index()
    print("registries read:")
    for pack, n in seen:
        print("  {0:<16} {1} assets".format(pack, n))
    if missing:
        print("  NOT MEASURED (skipped, not treated as empty): {0}"
              .format(", ".join(missing)))

    try:
        entries = resolve(curation, index)
    except LookupError as exc:
        print("")
        print("REFUSE: curated asset(s) not present in any registry.")
        print("Nothing was written. Either the path is wrong or the pack")
        print("was never measured — both are real problems, and defaulting")
        print("past either one would put a fictional asset in the palette.")
        for pid, path in exc.args[0]:
            print("  {0:<28} {1}".format(pid, path))
        return 2
    except ValueError as exc:
        print("")
        print("REFUSE: curation file is invalid — {0}".format(exc))
        return 3

    palette = {
        "_generated_by": "scripts/make_alpine_palette.py",
        "_curation": "recipes/alpine_palette_curation.json",
        "_measurements": "Free/_measured/fab_registry_*.json (zero assets loaded)",
        "_verified_policy": (
            "Every entry is verified=false. Promotion requires a spawn and a "
            "render, in the pass that places the asset. This file cannot "
            "assert true."
        ),
        "tier_gate": curation.get("tier_gate"),
        # Surface rulings are DECISIONS, not measurements, so they pass
        # through verbatim. They belong in the recipe rather than only in
        # the curation file because a downstream reader asking "why is
        # the scree Rock026?" must find the answer, and the loser's
        # disqualifier, at the point of use.
        "surface_rulings": curation.get("surface_rulings", []),
        "entries": entries,
        "excluded": curation.get("excluded", []),
    }
    note = budget_note(entries)
    if note:
        palette["budget_warning"] = note

    by_admit = {}
    for e in entries:
        by_admit[e["admit"]] = by_admit.get(e["admit"], 0) + 1
    by_pass = {}
    for e in entries:
        by_pass[e["pass"]] = by_pass.get(e["pass"], 0) + 1

    print("")
    print("palette resolved: {0} entries".format(len(entries)))
    print("  by admit: {0}".format(
        ", ".join("{0}={1}".format(k, by_admit[k]) for k in VALID_ADMIT
                  if k in by_admit)))
    print("  by pass : {0}".format(
        ", ".join("P{0}={1}".format(k, by_pass[k]) for k in sorted(by_pass))))
    print("  excluded groups: {0}".format(len(palette["excluded"])))
    print("  verified TRUE: 0 of {0} — {1}".format(
        len(entries), NOT_VERIFIED_REASON))
    print("  Nanite known : 0 of {0} — {1}".format(len(entries),
                                                   NANITE_UNKNOWN))

    missing_tags = [e["id"] for e in entries if e["measured"]["unmeasured"]]
    if missing_tags:
        print("  entries with an ABSENT registry tag: {0}".format(
            ", ".join(missing_tags)))

    if note:
        print("")
        print("BUDGET WARNING ({0}): {1}".format(note["role"], note["warning"]))

    if not args.write:
        print("")
        print("dry run — pass --write to update recipes/alpine.json")
        return 0

    recipe["palette"] = palette
    with open(RECIPE, "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=2)
        fh.write("\n")
    print("")
    print("wrote palette into {0}".format(RECIPE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
