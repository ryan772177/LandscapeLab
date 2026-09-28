"""make_asset_manifest.py — inventory Free/ into Free/manifest.json.

READ-ONLY except for the one JSON it writes, and it contacts no editor.
Stage 1 of the asset-pipeline work: know exactly what is on disk, with a
role per file, before anything is imported.

WHAT IT DOES NOT DO, deliberately:

  It does NOT infer real-world footprint from file contents. Footprints
  come from FOOTPRINTS below, a transcription of what Ryan supplied. Per
  Ruling 2, an absent footprint has its size field OMITTED (ABSENT, not
  null), carries a `footprint_absent_reason` string, and is listed in the
  manifest's `blocking` array. A footprint guessed from a texture is a
  number that looks measured and is not, and every tiling decision
  downstream would inherit it.

  It does NOT re-derive normal convention. Ryan established that the
  normal maps this pipeline uses are GL, uniformly. The ambientCG sets
  additionally ship a DX variant of the same map; both are listed, with
  the DX one marked as an unused alternate, because a file that exists
  and is never read should be visible in the inventory rather than
  silently dropped.

Roles are assigned from filename convention only. Where a convention
does not resolve, the role is "unclassified" and the file is reported —
never quietly bucketed, since a mis-roled map is exactly the kind of
error that surfaces later as "the material looks wrong".
"""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREE_DIR = os.path.join(REPO_ROOT, "Free")
OUT_PATH = os.path.join(FREE_DIR, "manifest.json")

# Transcribed from Ryan's brief. Metres across the square tile for a
# surface, or the mesh's real-world extent. NOT measured here, and NOT
# inferred from file contents.
#
# TWO FIELDS, NOT ONE, and this is the point of the whole table. A
# vendor-published dimension and a number picked to start tuning from
# are both floats and are not the same kind of fact. Flattened into one
# field they become indistinguishable the moment anyone reads the
# manifest, and the assumed ones would harden into "measured" by nobody
# doing anything wrong. `footprint_source` keeps them apart all the way
# to the capture where the assumed ones get visually calibrated.
#
# ambientCG does not publish Dimensions for the four rock/snow sets.
# 4.0 m is a starting value chosen for tuning.
ASSUMED_NOTE = ("STARTING VALUE chosen for tuning, not a measurement. "
                "ambientCG publishes no Dimensions for this set. Any "
                "consumer that would behave differently for an assumed "
                "value must branch on the *_source field.")

# RULING 2: ONE FIELD PER QUANTITY, and they are mutually exclusive.
#   surface_tile_m  tiling period of a repeating surface. SURFACES ONLY.
#   mesh_extent_m   world-space width of a mesh bounding box. MESHES ONLY.
# A surface never carries mesh_extent_m and a mesh never carries
# surface_tile_m — the field is ABSENT, not null, so code asking the
# wrong question of an asset gets a KeyError rather than a plausible
# number. The single `footprint_m` this replaces held both quantities at
# once, which is exactly how the grass meshes' vendor WIDTHS ended up
# filed as tiling periods.
#
# Sources: "vendor" published by the asset site, "assumed" a starting
# value for tuning, "measured" read out of the file by this pipeline.
FOOTPRINTS = {
    # id: (field, metres, source)
    "Ground037": ("surface_tile_m", 2.1, "vendor"),
    "Rock026": ("surface_tile_m", 4.0, "assumed"),
    "Rock051": ("surface_tile_m", 4.0, "assumed"),
    "Rock063": ("surface_tile_m", 4.0, "assumed"),
    "Snow006": ("surface_tile_m", 4.0, "assumed"),
    # Vendor-published mesh WIDTHS, not tiling periods.
    # grass_medium_01 / grass_medium_02 are NOT here any more. Their
    # vendor extents (7.3 m and 3.6 m) described the whole laid-out set,
    # not a tuft, and are superseded by MEASURED_OBJECT below. Leaving a
    # vendor entry here would win over the measurement, because FOOTPRINTS
    # is consulted first.
    # A tileable surface that happens to ship as glTF. Typed as a
    # surface, so it takes surface_tile_m and NO mesh_extent_m despite
    # carrying mesh files.
    "leafy_grass": ("surface_tile_m", 2.0, "vendor"),
    # fir_tree_01 is measured, not tabled — see MEASURED_DIR.
}

# RULING 3: fir_tree_01's extent is READ FROM THE FBX, not sourced. The
# measurement is cached by scripts/blender/inspect_fbx so the manifest
# does not need a 237 MB Blender import on every run, and the cache
# records which object and which axis produced the number. If the cache
# is absent the field is ABSENT and the asset is BLOCKING — estimating
# is what ruling 3 forbids.
MEASURED_DIR = os.path.join(FREE_DIR, "_measured")
# The object whose bounding box IS the asset's extent. For a set laid
# out side by side in one file, this is one representative tuft, not the
# set — see the note on grass below.
#
# PROMOTION FROM vendor/assumed TO measured (this answers proposal open
# question 6, and the answer turned out to be "the vendor number was
# describing something else entirely").
#
# grass_medium_01 carried mesh_extent_m 7.3 from the vendor page and
# grass_medium_02 carried 3.6. Both are real numbers off the publisher's
# own listing, and both are the width of the WHOLE SET arranged in a row
# for the product shot. The largest single tuft in grass_medium_01 is
# 0.327 m. Used as a footprint, 7.3 m is wrong by a factor of 22 in the
# direction that makes every derived scale invisible — which is exactly
# what happened: the recipe's scale_range of 0.05-0.11 against a 0.147 m
# mesh produced grass 0.7 to 1.6 cm tall.
#
# So a published footprint is not automatically better than a measured
# one; it answers whatever question the publisher was asking. The
# promotion rule is: once normalize_asset.py has measured the object,
# `measured` wins and the vendor value is dropped, not averaged with.
MEASURED_OBJECT = {
    "fir_tree_01": "fir_tree_01_c_LOD0",
    "grass_medium_01": "grass_medium_01_large_a_LOD0",
    "grass_medium_02": "grass_medium_02_e",
}

# Where per-object measurements live. normalized.json is preferred: it
# records dims taken AFTER the pivot bake and verified by a re-read from
# disk, so it describes the file that is actually imported. The older
# per-asset inspect_fbx dumps describe the vendor file.
NORMALIZED_MEASUREMENTS = "normalized.json"

# Assets whose TYPE is not what their file extensions imply.
TYPE_OVERRIDE = {"leafy_grass": "surface"}


def _measured_extent(aid):
    """(metres, note) from the cached Blender read, or (None, why)."""
    want = MEASURED_OBJECT.get(aid)
    if not want:
        return None, "no measurement configured for this asset"

    # Prefer the normalisation report. Both files measure the same
    # object, but normalized.json measures it AFTER the pivot bake and
    # after a re-read from disk, so it describes the file the importer
    # will actually open. Falling back to the per-asset inspect_fbx dump
    # keeps assets that have not been normalised yet working — and the
    # note records WHICH instrument produced the number, because "2.1 m"
    # with no provenance is how the vendor 7.3 survived unchallenged.
    doc = None
    which = None
    norm = os.path.join(MEASURED_DIR, NORMALIZED_MEASUREMENTS)
    if os.path.isfile(norm):
        try:
            with open(norm, "r", encoding="utf-8") as fh:
                report = json.load(fh)
            rows = [r for g in (report or {}).values()
                    if isinstance(g, dict)
                    for r in (g.get("objects") or [])
                    if isinstance(r, dict)]
            for r in rows:
                if r.get("object") == want and r.get("ok"):
                    doc = {"objects": [{"object": want,
                                        "dims_xyz": r.get("dims_m")}],
                           "length_unit": "METERS", "unit_scale_length": 1.0}
                    which = "Free/_measured/normalized.json (post-pivot-bake)"
                    break
        except (OSError, ValueError):
            doc = None

    if doc is None:
        path = os.path.join(MEASURED_DIR, aid + ".json")
        if not os.path.isfile(path):
            return None, (
                "no cached measurement: neither Free/_measured/{0} has a "
                "verified row for {1} nor does Free/_measured/{2}.json "
                "exist — run scripts/blender/normalize_asset.py".format(
                    NORMALIZED_MEASUREMENTS, want, aid))
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            which = "Free/_measured/{0}.json (vendor file, pivot not " \
                    "normalised)".format(aid)
        except (OSError, ValueError) as exc:
            return None, "cached measurement unreadable: {0}".format(
                type(exc).__name__)

    for obj in doc.get("objects") or []:
        if obj.get("object") != want:
            continue
        dims = obj.get("dims_xyz") or []
        if len(dims) != 3:
            return None, "cached measurement has no usable dims"
        # WIDTH, i.e. the larger HORIZONTAL extent. Height (Z) is
        # deliberately not used: ruling 2 says width of the bounding
        # box, and for a tree the two differ by more than a factor of
        # two, so picking the wrong one is not a rounding error.
        width = max(float(dims[0]), float(dims[1]))
        if not (width > 0.0):
            return None, "cached measurement gives no positive width"
        return round(width, 3), (
            "measured from {0}, object {1}: bounding box "
            "{2:.3f} x {3:.3f} x {4:.3f} m. Value is the larger "
            "HORIZONTAL extent; height is {4:.3f} m and is NOT this "
            "field. ONE object, not the set: these files lay their "
            "objects out side by side and a published extent may be "
            "describing the whole row.".format(
                which, want, dims[0], dims[1], dims[2]))
    return None, "object {0!r} not in the cached measurement".format(want)


SOURCE_BY_ASSET = {
    "Ground037": "ambientCG",
    "Rock026": "ambientCG",
    "Rock051": "ambientCG",
    "Rock063": "ambientCG",
    "Snow006": "ambientCG",
    "grass_medium_01": "Poly Haven",
    "grass_medium_02": "Poly Haven",
    "leafy_grass": "Poly Haven",
    "fir_tree_01": "Poly Haven",
    # 2026-09-12 intake. The SOURCE is a fact and is recorded; the
    # surface_tile_m is NOT, and is deliberately left ABSENT/BLOCKING
    # rather than assumed -- the ruling asked for a STATED size and
    # neither vendor ships one here (ambientCG publishes no Dimensions,
    # per ASSUMED_NOTE above; Megascans states a SCAN AREA, which is the
    # area photographed and not a tiling period).
    "Gravel021": "ambientCG",
    "Snow007A": "ambientCG",
    "rock_shopk_high": "Quixel Megascans via Fab",
    "rock_shopk_raw": "Quixel Megascans via Fab",
    "forest_floor_vktfeilaw_4k": "Quixel Megascans via Fab",
    "nordic_forest_ground_root_moss_coarse_xiekec0_4k":
        "Quixel Megascans via Fab",
    "wild_grass_xbreagf_4k": "Quixel Megascans via Fab",
    "nordic_beach_rocky_ground_ukoncdamw_high": "Quixel Megascans via Fab",
}

MESH_EXT = {".fbx", ".gltf", ".glb", ".obj"}
DCC_EXT = {".blend", ".mtlx", ".tres", ".usdc", ".usda", ".usd"}


def _intake_size(folder):
    """(metres, provenance note) from a pack's own INTAKE.json, or None.

    `fetch_surface.py` writes INTAKE.json at promotion time carrying the
    vendor, the licence and the vendor-PUBLISHED physical size. Poly
    Haven publishes `dimensions` in millimetres; ambientCG returns zero
    and so never lands here.

    Read, not transcribed. A second hand-typed copy in FOOTPRINTS is
    exactly how the `assumed` 4.0 values outlived the vendor numbers
    they were standing in for.
    """
    p = os.path.join(folder, "INTAKE.json")
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None, None
    s = d.get("stated_size_m")
    if not s:
        return None, None
    try:
        v = float(s[0])
    except (TypeError, ValueError, IndexError):
        return None, None
    if not (v > 0.0):
        return None, None
    return v, ("read from INTAKE.json — %s published %s m (R-FETCH)"
               % (d.get("vendor", "the vendor"), s))


def _intake_vendor(folder):
    """The vendor recorded at fetch time, or None."""
    p = os.path.join(folder, "INTAKE.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh).get("vendor")
    except Exception:
        return None


def _normal_convention(files):
    """(convention, why) from THE FILES THAT EXIST.

    ⛔ THIS WAS DERIVED FROM A SIBLING'S ABSENCE UNTIL 2026-09-12:
    `DX if any(role == "normal-gl") else GL`. That is an inference from
    "a GL alternate ships beside it", and it is correct for exactly the
    two vendors that happened to be on disk — ambientCG ships BOTH
    conventions, Poly Haven meshes ship only `_nor_gl`.

    It is WRONG for anything that ships DX alone, which it calls GL. The
    consumer would then invert the green channel of a DX map, and a
    wrong convention inverts lighting across the whole surface — it
    reads as bad lighting, never as a bug. R-FETCH packs ship exactly
    that: a `*_NormalDX` map and no GL alternate.

    So ask what the PRESENT file says, not what a missing one implies.
    An absent GL map is not evidence about the map that IS there — the
    same "absence is not a measurement" defect as the cvar getter that
    could not tell zero from missing.
    """
    dx = [f for f in files if "DX convention" in (f.get("note") or "")]
    gl = [f for f in files if f["role"] == "normal-gl"
          or "GL convention" in (f.get("note") or "")]
    if dx:
        return "DX", ("derived: ships a *_NormalDX map, consumed directly "
                      "with no flip (ruling 1)"
                      + ("; a GL alternate also ships and is UNUSED"
                         if gl else "; no GL alternate ships"))
    if gl:
        return "GL", ("derived: ships ONLY a GL normal map, whose green "
                      "channel must be inverted for Unreal, which expects "
                      "DX")
    return None, ("UNDETERMINED: no normal map ships, so there is no "
                  "convention to record. Not defaulted — a guessed "
                  "convention inverts lighting silently.")


def _role(fname):
    """(role, note). Filename convention only — never file contents."""
    low = fname.lower()
    stem, ext = os.path.splitext(low)

    if ext == ".bin":
        return "mesh-buffer", "glTF binary payload"
    if ext in MESH_EXT:
        return "mesh", None
    if ext in DCC_EXT:
        return "dcc-variant", "authoring/interchange copy, not imported"

    # ambientCG suffixes
    if stem.endswith("_color"):
        return "color", None
    # RULING 1 (Ryan, 2026-08-02) REVERSED THE EARLIER FACT. ambientCG
    # ships both conventions; DX is the one this pipeline consumes, and
    # there is no green-channel flip anywhere. The GL maps are the
    # unused alternates. See LESSONS.md.
    if stem.endswith("_normaldx"):
        return "normal", "DX convention — consumed directly, no flip"
    if stem.endswith("_normalgl"):
        return "normal-gl", "GL alternate of the DX map; UNUSED"
    if stem.endswith("_roughness"):
        return "roughness", None
    if stem.endswith("_displacement"):
        return "displacement", None
    if stem.endswith("_ambientocclusion"):
        return "ambient-occlusion", None
    if stem.endswith("_metalness"):
        return "metalness", None

    # Poly Haven suffixes (before the _4k tail)
    body = stem[:-3] if stem.endswith("_4k") else stem
    for suffix, role, note in (
            ("_arm", "packed-arm", "AO / Roughness / Metal in R / G / B"),
            ("_diff", "color", None),
            ("_nor_gl", "normal", "GL convention"),
            ("_rough", "roughness", None),
            ("_disp", "displacement", None),
            ("_alpha", "alpha", None)):
        if body.endswith(suffix):
            return role, note

    # ambientCG ships an unsuffixed square preview thumbnail (.png). Anything
    # ELSE that reaches here has no resolvable role -- report it as
    # "unclassified" so the UNCLASSIFIED block below actually fires. Bucketing
    # an unknown file as "preview" is the silent mis-roling the docstring warns
    # of ("the material looks wrong" later). Note the earlier `else None` bug
    # bound only to the note, so EVERY unmatched file became "preview".
    if ext == ".png":
        return "preview", "unsuffixed thumbnail"
    return "unclassified", None


def _asset_id(folder):
    """Folder name -> the id used everywhere else."""
    name = folder
    # Longest tails first: `_4k.fbx` must not be shortened by `_4k`.
    # Plain `_4k` added 2026-09-12 for R-FETCH packs (`forest_floor_4k`),
    # so an id is the VENDOR ID without a resolution tail everywhere --
    # the same rule that already made `Rock051_4K-PNG` into `Rock051`.
    # Without it the recipe would have to name `forest_floor_4k` while
    # every other surface is named without its tier, and the resolution
    # would be baked into a binding that has nothing to do with it.
    for tail in ("_4K-PNG", "_4k.fbx", "_4k.gltf", "_4k"):
        if name.endswith(tail):
            return name[: -len(tail)]
    return name


def _dims(path):
    """(w, h, mode) or None. Header read only; no pixel interpretation."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return [im.size[0], im.size[1], im.mode]
    except Exception:
        # EXR is not readable by this Pillow build. Reported as null
        # rather than as an error: "I could not look" is not "absent"
        # (lesson 2.10), and the EXR question is Stage 3 anyway.
        return None


def build():
    if not os.path.isdir(FREE_DIR):
        raise FileNotFoundError(FREE_DIR)

    assets = []
    for folder in sorted(os.listdir(FREE_DIR)):
        fdir = os.path.join(FREE_DIR, folder)
        if not os.path.isdir(fdir):
            continue
        # Leading underscore marks pipeline working directories, not
        # assets. `_measured/` holds cached Blender reads and was being
        # inventoried as a surface with no size — a self-inflicted
        # blocking entry that would have sat in the report looking like
        # a real gap.
        if folder.startswith("_"):
            continue
        aid = _asset_id(folder)

        files = []
        has_mesh = False
        for root, _dirs, names in os.walk(fdir):
            for n in sorted(names):
                full = os.path.join(root, n)
                rel = os.path.relpath(full, FREE_DIR).replace("\\", "/")
                role, note = _role(n)
                has_mesh = has_mesh or role == "mesh"
                entry = {
                    "path": rel,
                    "role": role,
                    "bytes": os.path.getsize(full),
                }
                if note:
                    entry["note"] = note
                ext = os.path.splitext(n)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".exr"):
                    entry["format"] = ext.lstrip(".")
                    d = _dims(full)
                    entry["resolution"] = d[:2] if d else None
                    entry["pixel_mode"] = d[2] if d else None
                    if d is None:
                        entry["note"] = (entry.get("note", "") +
                                         " header not readable by this "
                                         "Pillow build").strip()
                files.append(entry)

        atype = TYPE_OVERRIDE.get(aid, "mesh" if has_mesh else "surface")
        entry = {
            "id": aid,
            "folder": folder,
            "source": (SOURCE_BY_ASSET.get(aid)
                       or _intake_vendor(os.path.join(FREE_DIR, folder))
                       or "unknown"),
            "type": atype,
            # PER ASSET, from which file actually ships. Ruling 1 said
            # "use _NormalDX for every ambientCG surface" and I applied
            # DX to EVERYTHING, including the Poly Haven meshes, which
            # ship `nor_gl` and no DX variant at all. Recording a
            # convention the files do not have is the same class of
            # error the ruling corrected — an asserted fact overriding
            # the directory — so it is derived here instead.
            "normal_convention": _normal_convention(files)[0],
            "normal_convention_source": _normal_convention(files)[1],
            "files": files,
        }

        field, val, src = FOOTPRINTS.get(aid, (None, None, None))
        note = None
        if field is None and aid in MEASURED_OBJECT:
            val, note = _measured_extent(aid)
            field, src = "mesh_extent_m", "measured"
        if field is None and atype == "surface":
            # R-FETCH (2026-09-12) already recorded the vendor-published
            # size when it fetched the pack. Reading it here rather than
            # transcribing it into FOOTPRINTS keeps ONE copy: a hand-typed
            # second copy is how `assumed` 4.0 values ended up outliving
            # the vendor numbers they stood in for.
            iv, isrc = _intake_size(os.path.join(FREE_DIR, folder))
            if iv is not None:
                val, field, src, note = iv, "surface_tile_m", "vendor", isrc

        if field and val is not None:
            # Mutually exclusive BY CONSTRUCTION: only one key is ever
            # written, and the wrong one for the type raises rather than
            # being accepted as a plausible number.
            if field == "surface_tile_m" and atype != "surface":
                raise ValueError(
                    "{0}: surface_tile_m on a {1}".format(aid, atype))
            if field == "mesh_extent_m" and atype != "mesh":
                raise ValueError(
                    "{0}: mesh_extent_m on a {1}".format(aid, atype))
            entry[field] = val
            entry[field + "_source"] = src
            if src == "assumed":
                entry[field + "_note"] = ASSUMED_NOTE
            elif note:
                entry[field + "_note"] = note
        else:
            entry["footprint_absent_reason"] = (
                note or "no value supplied and none measured")
        assets.append(entry)

    return {
        "generated_by": "scripts/make_asset_manifest",
        "stage": "1 — inventory, read-only, no editor contact",
        "root": "Free/",
        "conventions": {
            "normal": "DX for every ambientCG surface (Ryan ruling 1, "
                      "2026-08-02, reversing an earlier GL assertion). "
                      "Consumed directly — no green-channel flip "
                      "anywhere. The GL maps also ship, role "
                      "'normal-gl', UNUSED.",
            "surface_tile_m": "tiling period in metres. SURFACES ONLY; "
                              "ABSENT (not null) on meshes.",
            "mesh_extent_m": "world-space bounding-box WIDTH in metres, "
                             "i.e. the larger horizontal extent, not "
                             "height. MESHES ONLY; ABSENT (not null) on "
                             "surfaces.",
            "size_source": "vendor = published by the asset site. "
                           "assumed = a starting value for tuning, NOT a "
                           "measurement. measured = read from the file "
                           "by this pipeline. A consumer that would "
                           "behave differently for an assumed value must "
                           "branch on this field.",
            "roles": ["color", "normal", "normal-gl", "roughness",
                      "displacement", "ambient-occlusion", "metalness",
                      "alpha", "packed-arm", "mesh", "mesh-buffer",
                      "dcc-variant", "preview", "unclassified"],
        },
        # DERIVED from the assets themselves, not from FOOTPRINT_PENDING.
        # Listing a hand-written constant here would let the two drift,
        # and the first casualty was real: fir_tree_01 has no supplied
        # footprint and was not on the named-unknowns list either, so a
        # hardcoded blocking list reported 4 gaps while the manifest
        # carried 5 nulls. A blocking list that disagrees with the data
        # it summarises is worse than none.
        # DERIVED from the assets, never a hand-written constant, so the
        # summary cannot disagree with the data it summarises. That is
        # not hypothetical: the first version hardcoded four ids and
        # reported four gaps while the manifest carried five nulls.
        "blocking": [
            {"asset": a["id"],
             "missing": ("surface_tile_m" if a["type"] == "surface"
                         else "mesh_extent_m"),
             "note": a.get("footprint_absent_reason", "")}
            for a in assets
            if "surface_tile_m" not in a and "mesh_extent_m" not in a],
        "assets": assets,
    }


def main(argv=None):
    try:
        doc = build()
    except Exception as exc:                        # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        return 1
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print("wrote {0}".format(os.path.relpath(OUT_PATH, REPO_ROOT)))

    print("")
    print("{0:<17} {1:<8} {2:<11} {3:>5}  {4:<15} {5:>7}  {6}".format(
        "asset", "type", "source", "files", "size field", "metres",
        "provenance"))
    for a in doc["assets"]:
        if "surface_tile_m" in a:
            field, val = "surface_tile_m", a["surface_tile_m"]
        elif "mesh_extent_m" in a:
            field, val = "mesh_extent_m", a["mesh_extent_m"]
        else:
            field, val = "(ABSENT)", None
        print("{0:<17} {1:<8} {2:<11} {3:>5}  {4:<15} {5:>7}  {6}".format(
            a["id"], a["type"], a["source"], len(a["files"]), field,
            "-" if val is None else str(val),
            a.get(field + "_source", "BLOCKING")))

    unclassified = [f["path"] for a in doc["assets"] for f in a["files"]
                    if f["role"] == "unclassified"]
    if unclassified:
        print("")
        print("UNCLASSIFIED files ({0}) — role not resolvable from the "
              "filename:".format(len(unclassified)))
        for p in unclassified:
            print("  {0}".format(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
