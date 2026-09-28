"""restamp_consumed.py — execute the R5/R6 ruled routing for the
CANNOT-REPRODUCE shipped plans (E-4).

For each configured plan:
  * CONSUMED RE-STAMP (R6-Q3): locate the ADOPTION-TIME bytes of each
    JSON input — the committed version whose sha256 (raw, or CRLF->LF
    normalised) equals the plan's recorded `_input_sha256` value — and
    write `_consumed_sha256` computed from THOSE bytes, never from the
    current file (NN20: re-basing to today would launder every
    post-adoption consumed change into MATCHES). REFUSES when no
    committed version matches.
  * WAIVER (R5/R6): write the ruled `_stamp_waiver` — consumed-pair
    entries bound to the live (recorded -> actual) consumed hashes,
    ruled-kind entries for script inputs of EXPECTED-UNREPRODUCIBLE
    plans, whole-file pairs where adoption bytes are unfindable.
  * CONTAINMENT (R6-Q2, `_verified` only): every verified row confirmed
    present in the current `_all` encounter set, count printed, ZERO
    comparisons REFUSES (rule 13).

Deliberately a DRIVER with the routing declared in-code: the per-plan
decisions are deputy rulings (DESK_LOG R5/R6), not parameters a caller
may vary. Run with --dry-run first; idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import plan_stamp  # noqa: E402

# Consumed-field declarations, line-cited (R6-Q4 granularity floor):
#   place_foliage.py: landscape/heightmap :366, material :378/:677,
#     biome_id :522, foliage :529+, perception :1080, streaming :1146
#   plan_city.py: site :168, plan :169, buildings :170, gates :171,
#     landmark :449/:509, roofs :482, city_id :530/:662, level_path :530;
#     biome landscape/heightmap :59-:60/:525
#   city_reachable_region_payload.txt reads the town PLAN (streets :143,
#     buildings :146), not city.json — city.json shapes the town it
#     measured, so its declaration is plan_city's city.json list
#     (at-or-above the reads).
PF_FIELDS = ["landscape", "heightmap", "material", "biome_id", "foliage",
             "perception", "streaming"]
# What the settlement exclusion reads of the TOWN PLAN
# (town_exclusion.py: streets :86, plaza_radius_cm :89/:96,
# site_centre_cm :112, buildings iteration): metadata edits to the town
# plan (notes, waivers, stamps) must not stale the foliage plans.
CITYPLAN_FIELDS = ["buildings", "streets", "plaza_radius_cm",
                   "site_centre_cm"]
CITY_FIELDS = ["site", "plan", "buildings", "gates", "landmark", "roofs",
               "city_id", "level_path"]
BIOME_FIELDS = ["landscape", "heightmap"]

FOLIAGE = ["foliage/alpine_8k_%s.json" % s
           for s in ("Conifer", "ConiferPine", "SpruceSapling",
                     "SpruceSub")]

RULED_PF = {"kind": "ruled",
            "ruling": "R-TOWNEXCL / D-4 (EXPECTED-UNREPRODUCIBLE: no "
                      "producer edit alters committed rows; plain re-run "
                      "re-samples 48% low and is BLOCKED)",
            "retires_when": "foliage regeneration un-gates "
                            "(planting-field contract + carve, D-4/X-1)"}
RULED_PLAN_CITY = {"kind": "ruled",
                   "ruling": "town divergence ruled DIVERGENT-BY-RULING "
                             "(R6-Q1 2026-09-16); re-placement GATED",
                   "retires_when": "the town rebuild un-gates (kit "
                                   "re-plan; shared retirement with the "
                                   "reachable waiver)"}
# Brief-4 water carve moved terrain/alpine_8k.png (T3). The town plans stamp
# it whole-file as _terrain_source, but the carve is the NORTH CASCADE only:
# T3 changed 47 px at pool lips (8129 col 2528-2900, row 4804-5864); the town
# footprint (plaza px ~1956,6852) is byte-identical, verified by diffing the
# changed-pixel bbox against the town extent 2026-09-19b. A PNG has no
# consumed-field instrument, so the ruling lives in the whole-file waiver's
# `why` (the sanctioned override, same class as the _verified _all pair).
CARVE_TERRAIN_WHY = (
    "terrain/alpine_8k.png hash moved by the Brief-4 water carve (T3), which "
    "is the NORTH CASCADE ONLY: 47 changed px at pool lips (8129 col "
    "2528-2900, row 4804-5864); the town footprint (plaza px ~1956,6852) is "
    "byte-identical (changed-px bbox vs town extent, 2026-09-19b). The town's "
    "terrain-dependence is unchanged; the whole-file hash move is the carve, "
    "not the town.")
CARVE_TERRAIN_RETIRES = ("the town is re-planned on carved terrain (not "
                         "required — the town does not touch the cascade)")


def whole_pair(stamp, rel):
    """Whole-file {from: recorded_full_sha, to: actual_full_sha} for `rel`."""
    return {"from": stamp.get(rel),
            "to": plan_stamp.sha256_file(os.path.join(REPO, rel))}


def sha12(b):
    return hashlib.sha256(b).hexdigest()[:12]


def find_adoption_bytes(rel, want_sha256):
    """Committed bytes of `rel` whose sha256 (raw or CRLF->LF) equals
    want_sha256, or None."""
    revs = subprocess.run(["git", "log", "--format=%H", "--", rel],
                          capture_output=True, text=True,
                          cwd=REPO).stdout.split()
    for r in revs:
        blob = subprocess.run(["git", "show", "%s:%s" % (r, rel)],
                              capture_output=True, cwd=REPO).stdout
        for cand in (blob, blob.replace(b"\r\n", b"\n")):
            if hashlib.sha256(cand).hexdigest() == want_sha256:
                return cand
    return None


def consumed_from_adoption(doc, rel, fields):
    """-> (entry, changed_fields, err). entry is the _consumed_sha256
    record computed from ADOPTION bytes; changed_fields names the
    consumed top-level fields whose value differs today (for the waiver
    why); err is a refusal string when adoption bytes are unfindable."""
    recorded = (doc.get(plan_stamp.STAMP_KEY) or {}).get(rel)
    if not recorded:
        return None, None, "%s not in the whole-file stamp" % rel
    blob = find_adoption_bytes(rel, recorded)
    if blob is None:
        return None, None, ("no committed version of %s hashes to the "
                            "adopted %s..." % (rel, recorded[:12]))
    adopted = json.loads(blob.decode("utf-8"))
    entry = {"fields": sorted(set(fields)),
             "sha256": plan_stamp.consumed_subset_hash(adopted, fields)}
    current = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
    changed = []
    for f in sorted(set(fields)):
        pa, va = plan_stamp._dotpath(adopted, f)
        pb, vb = plan_stamp._dotpath(current, f)
        if (pa, va) != (pb, vb):
            changed.append(f)
    return entry, changed, None


def containment_verified(repo):
    """R6-Q2: every verified row present in current _all. -> (n_ok, n)."""
    ver = json.load(io.open(os.path.join(repo, "encounters",
                                         "alpine_8k_verified.json"),
                            encoding="utf-8"))
    allp = json.load(io.open(os.path.join(repo, "encounters",
                                          "alpine_8k_all.json"),
                             encoding="utf-8"))
    def key(e):
        return (e.get("archetype"), tuple(e.get("loc_cm") or ()))
    have = {key(e) for e in allp.get("encounters") or []}
    rows = ver.get("encounters") or []
    if not rows:
        raise SystemExit("REFUSE: zero verified rows to compare "
                         "(rule 13: a zero count refuses)")
    ok = sum(1 for e in rows if key(e) in have)
    return ok, len(rows)


def process(rel, consumed_specs, waiver, dry):
    ap = os.path.join(REPO, rel)
    with io.open(ap, encoding="utf-8") as _fh:
        _raw = _fh.read()
    doc = json.loads(_raw)
    # PRESERVE the artefact's existing formatting (T10 2026-09-19b): the
    # plans are stored in three styles by their producers -- indent=2
    # (plan_city roofbias, plan_encounters _all), indent=1 (adopt_verified
    # _verified), or compact one-line (place_foliage, town_plan) -- all with
    # the json default ensure_ascii=True. A fixed compact dump reflowed the
    # pretty ones into 25k-line whitespace-only diffs. Sniff the second
    # line's leading-space count for the indent width, and preserve the
    # trailing newline, so a restamp writes a minimal diff (the waiver).
    if _raw[:2] == "{\n":
        _l2 = _raw.split("\n", 2)[1]
        _indent = len(_l2) - len(_l2.lstrip(" "))
    else:
        _indent = None
    _trail = "\n" if _raw.endswith("\n") else ""
    print("=" * 70)
    print(rel)
    consumed_map = dict(doc.get(plan_stamp.CONSUMED_KEY) or {})
    notes = []
    for input_rel, fields in consumed_specs:
        entry, changed, err = consumed_from_adoption(doc, input_rel, fields)
        if err:
            print("  CONSUMED RE-STAMP REFUSED for %s: %s" % (input_rel, err))
            notes.append((input_rel, None, err))
            continue
        consumed_map[input_rel] = entry
        cur = json.load(io.open(os.path.join(REPO, input_rel),
                                encoding="utf-8"))
        actual = plan_stamp.consumed_subset_hash(cur, entry["fields"])
        verdict = ("MATCHES_CONSUMED" if actual == entry["sha256"]
                   else "DIFFERS")
        print("  consumed %-28s %s  (%d fields%s)"
              % (input_rel, verdict, len(entry["fields"]),
                 "; changed: " + ", ".join(changed) if changed else ""))
        notes.append((input_rel, (entry["sha256"][:12], actual[:12],
                                  verdict, changed), None))
    doc[plan_stamp.CONSUMED_KEY] = consumed_map

    if waiver is not None:
        # fill live consumed pairs into granted_for entries marked
        # {"kind": "consumed", "pair": "live"}
        for path, g in waiver.get("granted_for", {}).items():
            if g.get("kind") == "consumed" and g.get("pair") == "live":
                row = next((n for n in notes if n[0] == path and n[1]), None)
                if row is None:
                    raise SystemExit("REFUSE: no consumed measurement for "
                                     "%s to bind the waiver to" % path)
                g["from"], g["to"] = row[1][0], row[1][1]
                del g["pair"]
        doc["_stamp_waiver"] = waiver
        print("  waiver written: inputs=%s" % waiver["inputs"])

    if dry:
        print("  DRY RUN -- nothing written")
        return
    with io.open(ap, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=_indent) + _trail)
    print("  written")


def main(argv=None):
    apar = argparse.ArgumentParser()
    apar.add_argument("--dry-run", action="store_true")
    a = apar.parse_args(argv)
    dry = a.dry_run

    # ---- 4 foliage plans (R6 routing row 3) --------------------------
    for rel in FOLIAGE:
        doc = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
        st = doc.get(plan_stamp.STAMP_KEY) or {}
        pf_pair = {"from": (st.get("scripts/place_foliage.py") or "")[:12],
                   "to": plan_stamp.sha256_file(
                       os.path.join(REPO, "scripts/place_foliage.py"))[:12]}
        waiver = {
            "inputs": ["recipes/alpine_8k.json",
                       "city/alpine_basin_town_plan.json",
                       "scripts/place_foliage.py"],
            "recorded": "2026-09-16 (R5/R6; replaces the expired 09-09 "
                        "waiver whose pairs had been merged forward)",
            "why": ("EXPECTED-UNREPRODUCIBLE by ruling. The recipe's "
                    "CONSUMED subset moved in exactly two places since "
                    "adoption, both RULED: foliage.species (Unit-6 "
                    "collision declarations + species override_materials"
                    ", D-3 lane) and material.layers (R-TILE tiling "
                    "rulings 2026-09-12b/2026-09-13: gray_rocks 1.8 m, "
                    "scree 2.00 m + blend fields). The plan's rows are "
                    "the committed 2026-09-08 placement a plain re-run "
                    "cannot reproduce (R-TOWNEXCL: stratified re-sample "
                    "48% low). place_foliage.py edits (Pass 3 2026-09-16 "
                    "fixes) do not alter committed rows."),
            "granted_for": {
                "recipes/alpine_8k.json": {"kind": "consumed",
                                           "pair": "live"},
                "city/alpine_basin_town_plan.json": {"kind": "consumed",
                                                     "pair": "live"},
                "scripts/place_foliage.py": dict(RULED_PF, **pf_pair),
            },
        }
        process(rel, [("recipes/alpine_8k.json", PF_FIELDS),
                      ("city/alpine_basin_town_plan.json",
                       CITYPLAN_FIELDS)], waiver, dry)

    # ---- town plan (R6 routing row 1: stamp side) --------------------
    rel = "city/alpine_basin_town_plan.json"
    doc = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
    st = doc.get(plan_stamp.STAMP_KEY) or {}
    pc_pair = {"from": (st.get("scripts/plan_city.py") or "")[:12],
               "to": plan_stamp.sha256_file(
                   os.path.join(REPO, "scripts/plan_city.py"))[:12]}
    waiver = {
        "inputs": ["recipes/alpine_8k.json", "recipes/city.json",
                   "scripts/plan_city.py", "terrain/alpine_8k.png"],
        "recorded": "2026-09-16 (R5/R6); terrain pair added 2026-09-19b (T10)",
        "why": ("The town's divergence is DIVERGENT-BY-RULING (R6-Q1; "
                "storey_m 3.2 -> 2.0 ruled, re-placement GATED). city."
                "json's consumed subset moved through that ruling plus "
                "later additions; alpine_8k's consumed subset (landscape/"
                "heightmap) is expected unchanged. Shared retirement "
                "with the reachable waiver: the town rebuild. " +
                CARVE_TERRAIN_WHY),
        "granted_for": {
            "recipes/alpine_8k.json": {"kind": "consumed", "pair": "live"},
            "recipes/city.json": {"kind": "consumed", "pair": "live"},
            "scripts/plan_city.py": dict(RULED_PLAN_CITY, **pc_pair),
            "terrain/alpine_8k.png": whole_pair(st, "terrain/alpine_8k.png"),
        },
    }
    process(rel, [("recipes/city.json", CITY_FIELDS),
                  ("recipes/alpine_8k.json", BIOME_FIELDS)], waiver, dry)

    # ---- town roofbias variant (same terrain ruling; T10 2026-09-19b) ----
    rel = "city/alpine_basin_town_plan_roofbias.json"
    doc = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
    st = doc.get(plan_stamp.STAMP_KEY) or {}
    pc_pair = {"from": (st.get("scripts/plan_city.py") or "")[:12],
               "to": plan_stamp.sha256_file(
                   os.path.join(REPO, "scripts/plan_city.py"))[:12]}
    waiver = {
        "inputs": ["recipes/alpine_8k.json", "recipes/city.json",
                   "scripts/plan_city.py", "terrain/alpine_8k.png"],
        "recorded": "2026-09-19b (T10)",
        "why": ("A roof-bias variant of the town plan, same producer and "
                "same DIVERGENT-BY-RULING town. " + CARVE_TERRAIN_WHY),
        "granted_for": {
            "recipes/alpine_8k.json": {"kind": "consumed", "pair": "live"},
            "recipes/city.json": {"kind": "consumed", "pair": "live"},
            "scripts/plan_city.py": dict(RULED_PLAN_CITY, **pc_pair),
            "terrain/alpine_8k.png": whole_pair(st, "terrain/alpine_8k.png"),
        },
    }
    process(rel, [("recipes/city.json", CITY_FIELDS),
                  ("recipes/alpine_8k.json", BIOME_FIELDS)], waiver, dry)

    # ---- reachable (R6 routing row 2) --------------------------------
    rel = "city/alpine_basin_town_reachable.json"
    waiver = {
        "inputs": ["recipes/city.json"],
        "recorded": "2026-09-16 (R5/R6; replaces the expired waiver)",
        "why": ("Measured against the BUILT navmesh and the committed "
                "town plan; the payload reads the town PLAN (streets/"
                "buildings), not city.json — city.json shaped the town "
                "it measured. Its consumed subset moved through the "
                "ruled storey_m change (same ruling as the town's "
                "DIVERGENT-BY-RULING note). Retires when the town "
                "rebuild un-gates (shared retirement, R6 rows 1-2)."),
        "granted_for": {
            "recipes/city.json": {"kind": "consumed", "pair": "live"},
        },
    }
    process(rel, [("recipes/city.json", CITY_FIELDS)], waiver, dry)

    # ---- _all (Brief-4 T8 moved encounters.json + plan_encounters.py;
    #      T10 2026-09-19b). _all is the PRE-WATER candidate pool (320
    #      rows). T8 ruled it FROZEN: the water exclusion applies FORWARD
    #      (to the shipped verified 305 via removal of the 12 drowned, and
    #      to future regens via exclusions.water + the WaterMask in the
    #      placer). _all is NOT regenerated — a regen re-samples placement
    #      and needs the POST-CARVE navmesh lattice (T6-owned). encounters.
    #      json's CONSUMED subset genuinely moved (exclusions.water is read
    #      by plan_encounters), so it is waived WHOLE-FILE (the ruled
    #      override), and plan_encounters.py by the ruled/script class. The
    #      consumed subsets of town_plan/alpine_8k/character are unchanged
    #      (MATCHES_CONSUMED) and drop out of the stale set on their own.
    #      ⭐ ORDERED BEFORE _verified (audit F-1, 2026-09-19b): _verified's
    #      whole-file pair for _all must bind to _all's FINAL bytes, so _all
    #      is rewritten here FIRST — a `to` computed from a file the same run
    #      later rewrites is dead on arrival (verified reads STALE on run 1,
    #      converges only on run 2). See LESSONS 2026-09-19.
    rel = "encounters/alpine_8k_all.json"
    doc = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
    st = doc.get(plan_stamp.STAMP_KEY) or {}
    pe_pair = {"from": (st.get("scripts/plan_encounters.py") or "")[:12],
               "to": plan_stamp.sha256_file(
                   os.path.join(REPO, "scripts/plan_encounters.py"))[:12]}
    RULED_PLAN_ENC = {
        "kind": "ruled",
        "ruling": "Brief-4 T8 (2026-09-19): _all is the FROZEN pre-water "
                  "candidate pool; the water exclusion is FORWARD-only "
                  "(applied to the shipped verified set + future regens). "
                  "The plan_encounters.py WaterMask edit does not alter "
                  "the committed pool.",
        "retires_when": "encounters are re-placed on the post-carve navmesh "
                        "lattice (a future session; shared with the T6 "
                        "reachable-lattice regeneration)"}
    waiver = {
        "inputs": ["recipes/encounters.json", "scripts/plan_encounters.py"],
        "recorded": "2026-09-19b (T10; Brief-4 T8 moves)",
        "why": ("_all is the PRE-WATER candidate pool (320 rows). Brief-4 "
                "T8 added exclusions.water to encounters.json (a field the "
                "PLACER reads, so its consumed subset genuinely moved) and "
                "the WaterMask rejection to plan_encounters.py, then "
                "re-froze the SHIPPED verified set 317->305 by removing the "
                "12 Lake-A drowned. By T8's ruling _all is FROZEN, not "
                "regenerated: a regen re-samples placement and needs the "
                "post-carve navmesh lattice (T6-owned). The 12 drowned "
                "remain in _all as the historical record of what was "
                "removed. town_plan/alpine_8k/character consumed subsets "
                "are unchanged (MATCHES_CONSUMED)."),
        "granted_for": {
            "recipes/encounters.json": whole_pair(st,
                                                  "recipes/encounters.json"),
            "scripts/plan_encounters.py": dict(RULED_PLAN_ENC, **pe_pair),
        },
    }
    process(rel, [], waiver, dry)

    # ---- _verified (R6 routing row 4 + Q2 containment) ----------------
    ok, n = containment_verified(REPO)
    print("=" * 70)
    print("containment: %d/%d verified rows present in current _all" % (ok, n))
    if ok != n:
        raise SystemExit("REFUSE: containment failed (%d/%d) -- the "
                         "verified plan claims rows _all no longer "
                         "carries; a waiver may not be granted over that."
                         % (ok, n))
    rel = "encounters/alpine_8k_verified.json"
    doc = json.load(io.open(os.path.join(REPO, rel), encoding="utf-8"))
    st = doc.get(plan_stamp.STAMP_KEY) or {}
    # whole-file pairs carry FULL sha256 values — waiver_covers compares
    # them against the full recorded/actual hashes (12-char pairs are
    # the CONSUMED kind's convention only)
    all_pair = {"from": st.get("encounters/alpine_8k_all.json"),
                "to": plan_stamp.sha256_file(
                    os.path.join(REPO, "encounters",
                                 "alpine_8k_all.json"))}
    rec_pair = {"from": st.get("recipes/alpine_8k.json"),
                "to": plan_stamp.sha256_file(
                    os.path.join(REPO, "recipes", "alpine_8k.json"))}
    enc_pair = {"from": st.get("recipes/encounters.json"),
                "to": plan_stamp.sha256_file(
                    os.path.join(REPO, "recipes", "encounters.json"))}
    waiver = {
        "inputs": ["encounters/alpine_8k_all.json",
                   "recipes/alpine_8k.json",
                   "recipes/encounters.json"],
        "recorded": "2026-09-16 (R5/R6-Q2); encounters.json pair added "
                    "2026-09-19b (T10, Brief-4 T8 move)",
        "why": ("(1) _all: the adoption-time bytes are UNFINDABLE in "
                "history (7 revisions checked, CRLF-normalised too) — "
                "adopted while uncommitted; Q2's refuse-to-waiver route. "
                "CONTAINMENT re-measured this run: %d/%d verified rows "
                "present in current _all (archetype+loc_cm identity; a "
                "zero count would have REFUSED, rule 13). _all is bound by "
                "its own T10 waiver (whole-file, this commit). (2) the "
                "recipe(s): adopt_verified_encounters "
                "consumes --plan and --rows ONLY (adopt_verified_"
                "encounters.py:58-74); recipes/alpine_8k.json and "
                "recipes/encounters.json are inherited metadata the "
                "ADOPTER never reads. Brief-4 T8 added exclusions.water to "
                "encounters.json (read by the PLACER, not the adopter) and "
                "re-froze verified 317->305 by removing the 12 Lake-A "
                "drowned; the verified rows a re-adopt would produce are "
                "unchanged by that field. All pairs expire mechanically on "
                "the next movement — no rebuild condition." % (ok, n)),
        "granted_for": {
            "encounters/alpine_8k_all.json": all_pair,
            "recipes/alpine_8k.json": rec_pair,
            "recipes/encounters.json": enc_pair,
        },
    }
    process(rel, [], waiver, dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
