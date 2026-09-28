"""fetch_surface.py — search and fetch CC0 ground surfaces, GATED.

    python scripts/fetch_surface.py --search rock terrain
    python scripts/fetch_surface.py --fetch polyhaven:rock_boulder_dry --dry-run
    python scripts/fetch_surface.py --fetch polyhaven:rock_boulder_dry
    python scripts/fetch_surface.py --selftest

RULED 2026-09-12 by Ryan: the agent sources its own materials, because a
human picking packs by eye keeps landing on ones that are subtly wrong --
8-bit height, a missing map, a decal wearing a surface's name. All three
have happened on this project.

⛔ THE POINT IS NOT THE DOWNLOAD. IT IS THAT A DOWNLOAD IS NOT FINISHED
UNTIL IT HAS PASSED THE GATE. Everything lands in `Free/_staging/` and is
PROMOTED to `Free/` only after it passes. A refused pack stays in staging
beside a `REFUSED.json` saying why, so it can never be mistaken for an
intaken asset -- which is exactly how `Ground037` came to be downloaded
twice and `Dry_Fallen_Leaves` sat on disk for a month with no height map.

NOTHING IS DELETED (standing rule 2). A refusal is a file that stays put
with a verdict next to it.

THREE REFUSALS, each bought with a real defect:

  NO HEIGHT MAP    the layer blend IS a height blend. `Dry_Fallen_Leaves`
                   ships B/N/ORM and no _H at all (2026-09-12)
  8-BIT HEIGHT     Megascans ships Displacement as JPEG. Six packs
                   refused on this in one session (2026-09-12)
  A DECAL          `PineNeedles001` passed the height gate at 96.7%
                   TRANSPARENT. A height gate does not test coverage,
                   so coverage is tested separately (2026-09-12)

WHY THESE TWO VENDORS AND NOT FAB. Fab/Megascans requires an
authenticated Epic session; `Bridge`, `Fab` and `MegascansPlugin` ship
ZERO Python and are C++ around an embedded browser, so there is no
scriptable download surface and no permission grant creates one. Poly
Haven and ambientCG both publish open, unauthenticated APIs.

POLY HAVEN IS PREFERRED, and the reason is measurable: it publishes
`dimensions` in millimetres, so the STRETCH check (derived tile against
the scan's real size) is available. ambientCG returns
`dimensionX/Y/Z = 0` for every asset we have tried -- the size is not
withheld from the zip, the vendor does not hold it -- so stretch is
permanently unmeasurable there.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

FREE = os.path.join(REPO, "Free")
STAGING = os.path.join(FREE, "_staging")
UA = {"User-Agent": "UE5LandscapePipeline/intake (CC0 asset fetch)"}

# A surface needs all four to be usable as a landscape layer. Missing any
# is a REFUSAL, not a warning -- this is the "missing files" case.
REQUIRED_ROLES = ("color", "height", "normal", "roughness")

# Poly Haven map name -> our role. `nor_dx` because UE expects DirectX
# normals; the convention is VERIFIED after download, never assumed.
PH_MAPS = {"Diffuse": "color", "Displacement": "height",
           "nor_dx": "normal", "Rough": "roughness", "AO": "ao"}
# PNG THROUGHOUT. For height it is the gate's requirement -- 16-bit and
# readable with no extra dependency (EXR is smaller and 32-bit but needs
# OpenEXR installed, and a gate that cannot read its own input is not a
# gate). For the rest it is because these are SHIPPING material inputs
# that are also MEASURED: JPEG is lossy, and a lossy albedo feeds the
# albedo-band table that rulings are made from.
PH_FORMAT = {"height": "png", "color": "png", "normal": "png",
             "roughness": "png", "ao": "png"}

# ⛔ CANONICAL MAP NAMES -- the ambientCG convention, which every tool in
# scripts/ already reads. MEASURED 2026-09-12: the first fetch named
# files by role (`forest_floor_color_4k.jpg`), the pack passed the gate,
# and `scan_surface_stats` then reported "no colour map found" and both
# normals "absent" on an asset that was completely fine. A second naming
# convention is a second list that must agree with the first (NN24), so
# there is only one, and the fetcher conforms to it rather than teaching
# every downstream tool a new dialect.
CANON = {"color": "Color", "height": "Displacement", "normal": "NormalDX",
         "roughness": "Roughness", "ao": "AmbientOcclusion"}

OPAQUE_AT = 0.98
DECAL_BELOW = 0.98


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _download(url, dest, log=True):
    req = urllib.request.Request(url, headers=UA)
    h = hashlib.sha256()
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            h.update(chunk)
    os.replace(tmp, dest)
    if log:
        print("    %-44s %8.1f MB" % (os.path.basename(dest),
                                      os.path.getsize(dest) / 1e6))
    return h.hexdigest()


# ---------------------------------------------------------------- search

def search_polyhaven(terms):
    assets = _get_json("https://api.polyhaven.com/assets?type=textures")
    out = []
    for aid, a in assets.items():
        hay = " ".join([aid] + (a.get("categories") or [])
                       + (a.get("tags") or [])).lower()
        if all(t.lower() in hay for t in terms):
            d = a.get("dimensions")
            out.append({"vendor": "polyhaven", "id": aid,
                        "name": a.get("name"),
                        "categories": a.get("categories"),
                        "size_m": [round(x / 1000.0, 2) for x in d] if d else None})
    return sorted(out, key=lambda r: r["id"])


def search_ambientcg(terms):
    q = urllib.parse.urlencode({"q": " ".join(terms), "type": "Material",
                                "limit": 60, "include": "dimensionsData"})
    d = _get_json("https://ambientcg.com/api/v2/full_json?" + q)
    out = []
    for a in d.get("foundAssets", []):
        out.append({"vendor": "ambientcg", "id": a.get("assetId"),
                    "name": a.get("displayName"),
                    "categories": [a.get("displayCategory")],
                    "size_m": None})  # vendor publishes 0; see docstring
    return out


# ----------------------------------------------------------------- plan

def plan_polyhaven(asset_id, res):
    files = _get_json("https://api.polyhaven.com/files/%s" % asset_id)
    info = _get_json("https://api.polyhaven.com/info/%s" % asset_id)
    items, missing = [], []
    for ph_name, role in PH_MAPS.items():
        entry = files.get(ph_name)
        fmts = (entry or {}).get(res) or {}
        ext = PH_FORMAT[role]
        if ext not in fmts:
            ext = next(iter(fmts), None)
        if not ext:
            if role in REQUIRED_ROLES:
                missing.append(role)
            continue
        d = fmts[ext]
        items.append({"role": role, "url": d["url"], "bytes": d.get("size"),
                      "name": "%s_%s_%s.%s" % (asset_id, res.upper(),
                                               CANON[role], ext)})
    dim = info.get("dimensions")
    return {"vendor": "polyhaven", "id": asset_id, "res": res,
            "licence": "CC0", "items": items, "missing_roles": missing,
            "stated_size_m": [round(x / 1000.0, 3) for x in dim] if dim else None,
            "authors": info.get("authors")}


def plan_ambientcg(asset_id, res):
    d = _get_json("https://ambientcg.com/api/v2/full_json?"
                  + urllib.parse.urlencode({"id": asset_id,
                                            "include": "downloadData"}))
    found = d.get("foundAssets") or []
    if not found:
        raise SystemExit("ambientCG: no asset '%s'" % asset_id)
    want = "%s-PNG" % res.upper()
    for folder in (found[0].get("downloadFolders") or {}).values():
        cats = folder.get("downloadFiletypeCategories") or {}
        for cat in cats.values():
            for f in cat.get("downloads") or []:
                if str(f.get("attribute")) == want:
                    return {"vendor": "ambientcg", "id": asset_id, "res": res,
                            "licence": "CC0", "zip": f.get("downloadLink"),
                            "bytes": f.get("size"), "items": [],
                            "missing_roles": [],
                            "stated_size_m": None, "authors": None}
    raise SystemExit("ambientCG: '%s' has no %s download" % (asset_id, want))


# ----------------------------------------------------------------- gate

def gate(folder):
    """Refuse on a missing map, an 8-bit height, or a decal."""
    from scan_intake_probe import probe
    p = probe(folder)
    reasons = []

    present = set(p.get("maps", {}).keys())
    missing = [r for r in REQUIRED_ROLES if r not in present]
    if missing:
        reasons.append("MISSING MAPS: %s" % ", ".join(missing))

    hv = p.get("height_verdict", "")
    if not str(hv).startswith("OK"):
        reasons.append(str(hv))

    opaque = None
    try:
        from scan_surface_stats import opacity_stats
        o = opacity_stats(folder)
        if o.get("has_opacity_map"):
            opaque = o.get("opaque_fraction")
            if opaque is not None and opaque < DECAL_BELOW:
                reasons.append(
                    "A DECAL, NOT A SURFACE: opaque fraction %.3f "
                    "(%.1f%% transparent)" % (opaque, 100 * (1 - opaque)))
    except Exception as e:
        reasons.append("coverage NOT MEASURED (%s: %s) -- refusing rather "
                       "than assuming" % (type(e).__name__, e))

    return {"passed": not reasons, "reasons": reasons,
            "height_verdict": hv, "maps_present": sorted(present),
            "opaque_fraction": opaque,
            "height_bit_depth": p.get("height_bit_depth")}


# ---------------------------------------------------------------- fetch

def fetch(spec, res, dry_run=False):
    vendor, _, asset_id = spec.partition(":")
    if vendor not in ("polyhaven", "ambientcg"):
        raise SystemExit("vendor must be polyhaven or ambientcg, got %r" % vendor)
    plan = (plan_polyhaven if vendor == "polyhaven"
            else plan_ambientcg)(asset_id, res)

    print("%s:%s  licence %s" % (vendor, asset_id, plan["licence"]))
    if plan.get("stated_size_m"):
        print("  stated physical size: %s m" % plan["stated_size_m"])
    else:
        print("  stated physical size: NOT PUBLISHED by this vendor")
    if plan["missing_roles"]:
        print("  ⛔ REFUSED BEFORE DOWNLOADING -- vendor has no %s map"
              % ", ".join(plan["missing_roles"]))
        return {"ok": False, "stage": "plan",
                "reasons": ["MISSING MAPS: %s" % ", ".join(plan["missing_roles"])]}
    if plan.get("zip"):
        print("  zip  %.1f MB" % ((plan.get("bytes") or 0) / 1e6))
    for it in plan["items"]:
        print("  %-10s %8.1f MB  %s"
              % (it["role"], (it.get("bytes") or 0) / 1e6, it["name"]))
    if dry_run:
        print("  DRY RUN -- nothing downloaded")
        return {"ok": None, "stage": "dry-run", "plan": plan}

    folder = os.path.join(STAGING, "%s_%s" % (asset_id, res))
    os.makedirs(folder, exist_ok=True)
    hashes = {}
    print("  downloading into %s" % os.path.relpath(folder, REPO))
    if plan.get("zip"):
        z = os.path.join(folder, "%s_%s.zip" % (asset_id, res))
        hashes["zip"] = _download(plan["zip"], z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(folder)
        os.remove(z)  # the extracted files ARE the asset; the zip is a courier
    else:
        for it in plan["items"]:
            hashes[it["role"]] = _download(it["url"],
                                           os.path.join(folder, it["name"]))

    v = gate(folder)
    v.update({"vendor": vendor, "id": asset_id, "res": res,
              "licence": plan["licence"], "sha256": hashes,
              "stated_size_m": plan.get("stated_size_m"),
              "authors": plan.get("authors")})

    if v["passed"]:
        dest = os.path.join(FREE, "%s_%s" % (asset_id, res))
        if os.path.exists(dest):
            print("  ⚠ ALREADY IN Free/ -- left in staging, nothing overwritten")
            v["note"] = "destination exists; not promoted"
        else:
            shutil.move(folder, dest)
            print("  ✓ PASSED -> promoted to Free/%s"
                  % os.path.basename(dest))
        with open(os.path.join(dest if os.path.exists(dest) else folder,
                               "INTAKE.json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, indent=1)
    else:
        print("  ⛔ REFUSED, left in staging:")
        for r in v["reasons"]:
            print("      - %s" % r)
        with open(os.path.join(folder, "REFUSED.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(v, fh, indent=1)
    return v


# -------------------------------------------------------------- selftest

def selftest():
    """THREE DIRECTIONS on the decision logic, with no network."""
    import numpy as np
    from PIL import Image
    import tempfile

    fails = []

    def build(tmp, depth=16, roles=REQUIRED_ROLES, opacity=None):
        os.makedirs(tmp, exist_ok=True)
        for role in roles:
            a = (np.random.rand(64, 64) * (65535 if depth == 16 else 255))
            if role == "height":
                im = Image.fromarray(
                    a.astype(np.uint16 if depth == 16 else np.uint8))
            else:
                im = Image.fromarray(
                    np.dstack([a, a, a]).astype(np.uint8))
            im.save(os.path.join(tmp, "x_%s.png" % (
                {"color": "Color", "height": "Displacement",
                 "normal": "NormalDX", "roughness": "Roughness"}[role])))
        if opacity is not None:
            m = np.full((64, 64), 255 if opacity >= 1 else 0, dtype=np.uint8)
            n_op = int(round(opacity * m.size))
            flat = m.ravel()
            flat[:] = 0
            flat[:n_op] = 255
            Image.fromarray(flat.reshape(64, 64)).save(
                os.path.join(tmp, "x_Opacity.png"))

    with tempfile.TemporaryDirectory() as td:
        # 1. PASS the legitimate case
        d = os.path.join(td, "good"); build(d)
        g = gate(d)
        print("  complete 16-bit surface -> %s"
              % ("PASS" if g["passed"] else "REFUSED %s" % g["reasons"]))
        if not g["passed"]:
            fails.append("a complete 16-bit surface was refused: %s" % g["reasons"])

        # 2. BLOCK each violation
        d = os.path.join(td, "eight"); build(d, depth=8)
        g = gate(d)
        print("  8-bit height              -> %s"
              % ("PASS" if g["passed"] else "REFUSED"))
        if g["passed"]:
            fails.append("an 8-bit height was accepted")

        d = os.path.join(td, "noheight")
        build(d, roles=tuple(r for r in REQUIRED_ROLES if r != "height"))
        g = gate(d)
        print("  no height map             -> %s"
              % ("PASS" if g["passed"] else "REFUSED"))
        if g["passed"]:
            fails.append("a surface with no height map was accepted")

        d = os.path.join(td, "decal"); build(d, opacity=0.03)
        g = gate(d)
        print("  96.7%% transparent decal   -> %s"
              % ("PASS" if g["passed"] else "REFUSED"))
        if g["passed"]:
            fails.append("a decal was accepted as a surface")

        # 3. BLOCK WHEN BROKEN -- empty dir must refuse, not crash through
        d = os.path.join(td, "empty"); os.makedirs(d)
        g = gate(d)
        print("  empty folder              -> %s"
              % ("PASS" if g["passed"] else "REFUSED"))
        if g["passed"]:
            fails.append("an empty folder was accepted")

    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", nargs="+")
    ap.add_argument("--vendor", default="both",
                    choices=("both", "polyhaven", "ambientcg"))
    ap.add_argument("--fetch", help="vendor:asset_id")
    ap.add_argument("--res", default="4k")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    if a.search:
        rows = []
        if a.vendor in ("both", "polyhaven"):
            rows += search_polyhaven(a.search)
        if a.vendor in ("both", "ambientcg"):
            try:
                rows += search_ambientcg(a.search)
            except Exception as e:
                print("ambientCG search failed: %s" % e)
        print("%-11s %-34s %-10s %s"
              % ("vendor", "id", "size m", "categories"))
        for r in rows:
            print("%-11s %-34s %-10s %s"
                  % (r["vendor"], r["id"],
                     ("%.2f" % r["size_m"][0]) if r.get("size_m") else "--",
                     ",".join(r.get("categories") or [])[:46]))
        print("\n%d candidate(s). Poly Haven rows carry a real size; "
              "ambientCG publishes none." % len(rows))
        return 0

    if a.fetch:
        os.makedirs(STAGING, exist_ok=True)
        v = fetch(a.fetch, a.res, dry_run=a.dry_run)
        return 0 if v.get("ok") is not False and v.get("passed", True) else 3

    ap.error("one of --search, --fetch or --selftest")


if __name__ == "__main__":
    raise SystemExit(main())
