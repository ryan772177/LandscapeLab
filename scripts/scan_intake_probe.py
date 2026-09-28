"""scan_intake_probe.py — the intake gate for a ground scan.

    python scripts/scan_intake_probe.py [--root Free] [--only DIR ...] [--out J]

Exit codes:
  0  every scan passes the height gate
  2  no scan folders found (--only matched nothing, or the root is empty)
  3  at least one scan is REFUSED (no height map, or an 8-bit one)

RULED 2026-09-12: before anything binds, every scan must state
  * source and licence
  * its PHYSICAL SIZE in metres (the asset page, or the Megascans json)
  * its height map's BIT DEPTH
and **a scan with no height map, or an 8-bit one, is REFUSED** -- not
bound, and not quietly replaced by a stand-in.

WHY HEIGHT DEPTH IS THE GATE. The layer blend is a HEIGHT blend: it
picks a winner per texel by comparing the two surfaces' heights, so the
height map is not decoration, it is the blend's input. 8 bits over a few
centimetres of relief quantises to ~0.4 mm steps and the blend edge
becomes a staircase of ties. R-LAYERS' own acceptance (mushy fraction
0.2131 vs a linear 0.5551) was measured on a blend that had real height
to work with.

PHYSICAL SIZE IS READ, NEVER ASSUMED. ambientCG states it on the asset
page and in the sidecar files it ships; Megascans states it in the
per-asset json as `physicalSize` / `meta[].name == "Scan Area"`. The
tile derivation multiplies straight through it, so a guessed size is a
guessed tile.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEIGHT_HINTS = ("displacement", "height", "_disp", "_h.", "bump")
ROLE_HINTS = {
    "color": ("color", "albedo", "basecolor", "diffuse", "_col", "_alb"),
    "normal": ("normal", "_nrm", "_nor"),
    "roughness": ("roughness", "_rough", "_rgh"),
    "ao": ("ambientocclusion", "occlusion", "_ao"),
    "height": HEIGHT_HINTS,
}


def png_info(path):
    """(width, height, bit_depth, colour_type) from the PNG IHDR."""
    with open(path, "rb") as fh:
        sig = fh.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        fh.read(4)
        if fh.read(4) != b"IHDR":
            return None
        w, h, depth, ctype = struct.unpack(">IIBB", fh.read(10))
        return {"width": w, "height": h, "bit_depth": depth,
                "colour_type": ctype}


def jpeg_info(path):
    """(width, height, precision) from the JPEG SOF marker.

    MEASURED, not inferred from the extension. Baseline JPEG carries a
    `precision` byte in SOFn; it is 8 for every ordinary encoder, and
    12-bit JPEG exists but is rare. Reading it means the intake record
    says what the FILE says rather than what the format usually is.
    """
    with open(path, "rb") as fh:
        data = fh.read(2)
        if data != b"\xff\xd8":
            return None
        while True:
            b = fh.read(1)
            if not b:
                return None
            if b != b"\xff":
                continue
            marker = fh.read(1)
            while marker == b"\xff":
                marker = fh.read(1)
            if not marker:
                return None
            m = marker[0]
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                continue
            ln = fh.read(2)
            if len(ln) < 2:
                return None
            length = struct.unpack(">H", ln)[0]
            body = fh.read(length - 2)
            # SOF0/1/2/3/5/6/7/9/10/11/13/14/15 -- not DHT(C4)/JPG(C8)/DAC(CC)
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                prec, h, w = struct.unpack(">BHH", body[:5])
                return {"width": w, "height": h, "bit_depth": prec,
                        "container": "jpeg",
                        "_measured": "SOF marker 0x%02X precision byte" % m}


def exr_bit_depth(path):
    """EXR pixel type: 1 = half (16-bit float), 2 = float (32-bit)."""
    try:
        import OpenEXR
        with OpenEXR.File(path) as f:
            ch = f.parts[0].channels
            k = sorted(ch)[0]
            return {"container": "exr",
                    "dtype": str(ch[k].pixels.dtype),
                    "bit_depth": 16 if "16" in str(ch[k].pixels.dtype) else 32}
    except Exception as e:
        return {"container": "exr", "error": str(e)[:120]}


def classify(name):
    low = name.lower()
    for role, hints in ROLE_HINTS.items():
        if any(h in low for h in hints):
            return role
    return None


def physical_size(folder, files):
    """Stated size in metres, and where it was read from."""
    # Megascans: a json carrying physicalSize or a "Scan Area" meta row
    for f in files:
        if not f.lower().endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(folder, f), encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            ps = d.get("physicalSize")
            if ps:
                return {"metres": str(ps), "source": f + " physicalSize"}
            for m in (d.get("meta") or []):
                if isinstance(m, dict) and "scan area" in str(
                        m.get("name", "")).lower():
                    return {"metres": str(m.get("value")),
                            "source": f + " meta[Scan Area]"}
            for key in ("dimensions", "size", "scanArea"):
                if d.get(key):
                    return {"metres": str(d[key]), "source": f + " " + key}
    # OUR OWN INTAKE RECORD. `fetch_surface.py` writes INTAKE.json with
    # the size the VENDOR published -- Poly Haven states `dimensions` in
    # millimetres, so for those packs the size is known and the stretch
    # check is available. Read last, so a vendor's own sidecar always
    # wins over our transcription of it.
    p = os.path.join(folder, "INTAKE.json")
    if os.path.isfile(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            s = d.get("stated_size_m")
            if s:
                return {"metres": "%sx%s" % (s[0], s[-1]),
                        "source": "INTAKE.json (%s, vendor-published)"
                                  % d.get("vendor")}
        except Exception:
            pass

    # ambientCG: the .mtlx / .usda sidecars sometimes carry it; the
    # asset id itself does not -- and its API returns 0, so the vendor
    # does not hold one. Report ABSENT rather than invent one.
    return {"metres": None, "source": None}


def probe(folder):
    files = sorted(os.listdir(folder))
    out = {"folder": os.path.basename(folder), "n_files": len(files),
           "maps": {}, "other": []}
    for f in files:
        p = os.path.join(folder, f)
        if not os.path.isfile(p):
            continue
        role = classify(f)
        ext = os.path.splitext(f)[1].lower()
        # Only formats with a real bit-depth handler below are admitted as a
        # map. .tif/.tiff have NO handler (they landed with no bit_depth and
        # were then mislabelled "depth unreadable"), so route them to "other".
        # .jpeg was missing here though the handler existed -- added.
        if role is None or ext not in (".png", ".exr", ".jpg", ".jpeg"):
            out["other"].append(f)
            continue
        info = {"file": f, "bytes": os.path.getsize(p)}
        if ext == ".png":
            info.update(png_info(p) or {"error": "not a PNG"})
        elif ext == ".exr":
            info.update(exr_bit_depth(p))
        elif ext in (".jpg", ".jpeg"):
            info.update(jpeg_info(p) or {"error": "not a JPEG"})
        out["maps"].setdefault(role, []).append(info)
    out["physical_size"] = physical_size(folder, files)

    h = out["maps"].get("height") or []
    if not h:
        out["height_verdict"] = "REFUSE -- NO HEIGHT MAP"
    else:
        depths = [m.get("bit_depth") for m in h if m.get("bit_depth")]
        best = max(depths) if depths else None
        out["height_bit_depth"] = best
        if best is None:
            out["height_verdict"] = "REFUSE -- height map depth unreadable"
        elif best <= 8:
            out["height_verdict"] = "REFUSE -- 8-bit height"
        else:
            out["height_verdict"] = "OK -- %d-bit height" % best
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(REPO, "Free"))
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    names = a.only or sorted(
        d for d in os.listdir(a.root)
        if os.path.isdir(os.path.join(a.root, d)))
    rows = []
    for n in names:
        p = os.path.join(a.root, n)
        if not os.path.isdir(p):
            continue
        rows.append(probe(p))

    if not rows:
        # NN13: a probe over zero folders is not a clean pass.
        print("REFUSE: no scan folders found under %s (--only matched nothing, "
              "or the root has no subdirectories). 'Could not look', not OK."
              % a.root)
        return 2

    print("%-48s %-7s %-22s %s" % ("folder", "roles", "height", "size m"))
    for r in rows:
        h = r.get("height_verdict", "?")
        sz = (r["physical_size"]["metres"] or "NOT STATED")
        print("%-48s %-7d %-22s %s"
              % (r["folder"], len(r["maps"]), h, sz))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"_what": "ground-scan intake probe", "scans": rows},
                      fh, indent=1)
        print("wrote %s" % a.out)
    # This IS a gate (the docstring calls it "the intake gate"): a REFUSE
    # verdict must reach the exit CODE, not live only in the printed table.
    refused = [r["folder"] for r in rows
               if str(r.get("height_verdict", "")).startswith("REFUSE")]
    if refused:
        print("REFUSED: %d scan(s) fail the height gate: %s"
              % (len(refused), ", ".join(refused)))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
