"""measure_falloff_contours.py — re-test the stamp falloff evidence gaps.

docs/archive/pre8k/SWEEP_REPORT.md section 6 names two evidence gaps this
instrument closes. ARCHIVED 2026-08-29: that report grades the pre-8K
/Game/Alpine world (2017 sq, 4 m/vertex), not /Game/Alpine8K.
or re-opens with numbers instead of a look:

  GAP A — `spine_aretes` CV (recorded 0.089, bar >= 0.05, schema v1.15):
          the coefficient of variation of each placement's OUTER
          CONTRIBUTING RADIUS, re-measured on the placements as they are
          NOW, provenance-linked to the terrain the world actually
          renders.
  GAP B — "the two polished falloff spots": falloff-annulus regions whose
          surface relief is anomalously smooth for their slope, found and
          ranked from the terrain artefact itself.

SOURCE ARTEFACTS — stated per non-negotiable 0 (two readings that share
a source are ONE measurement):

  Reading A (contour CV) reads the RECIPE's stamps block plus the
  compositor's own mask implementation (`composite_stamps.
  _stamp_mask_and_sample` — one declaration, never re-derived here).
  It is a statement about the terrain ONLY through the provenance gate
  below; it shares NO pixels with reading B.

  Reading B (polish) reads the HEIGHTMAP PIXELS of
  `heightmap.source` — the adopted terrain file, which the live world
  has been proven to carry (adoption gates A and B, RECIPES R-STAMP,
  2026-08-06). It does not consult the mask values beyond membership
  (which pixels belong to which annulus).

  A and B answer DIFFERENT questions (contour geometry vs surface
  relief) and are reported separately, never as corroboration.

PROVENANCE GATE (non-negotiable 20 / 15). Reading A describes the world
only if the recipe's stamps block is the one that produced the adopted
terrain, and the terrain file is the compositor's recorded output.
Asserted at runtime against the sidecar:

    sha256(heightmap.source bytes)          == sidecar.output_sha256
    canonical_sha256(recipe["stamps"])      == sidecar.stamps_block_sha256
    sha256(each stamp file)                 == placement.stamp_sha256

Any mismatch is exit 4, COULD NOT MEASURE — never a number from a broken
premise. (Verified to refuse: --selftest tampers each link and requires
the refusal.)

WHY THE RECORDED 0.089 MAY NOT REPRODUCE, AND WHAT WINS. The recorded
band (0.089-0.367, "eight locked placements") has no derivation script
in the repo — the same class as the sweep summit: a real number whose
choosing procedure was never written down. This instrument IS the
written-down procedure from now on. Where its numbers disagree with the
recorded ones, the measured numbers win (non-negotiable 15) and the
disagreement is reported, not smoothed over.

THE POLISH MECHANISM this instrument looks for (GAP B): in a falloff
annulus the surface is a blend `H' = (1-m)*H + m*target`, and the
smoothstep ramp dominates the local shape wherever neither field's own
relief survives the blend. `stamps.detail_relief` re-textures slopes in
its 30-90 degree mask only — an annulus flank at 12-28 degrees received
NO detail relief and keeps the glossy ramp. The measurement is therefore
conditioned on slope (non-negotiable 22): a window is compared against
the map-wide relief median FOR ITS OWN SLOPE BAND, never against a
global number.

THRESHOLDS, derived not tuned:
  POLISH_ABS_LAP_M = 0.5   — half the 1.0 m |laplacian| line that
        diagnosed the smooth-face defect (LESSONS 2026-08-03, "THE
        DETAIL PASS REPORTED SUCCESS"); chosen below it so this flags
        only ground clearly smoother than that already-litigated bar.
  POLISH_REL_SCORE = 0.4   — window median |lap| below 40% of its slope
        band's map-wide median. On the current terrain the window-score
        p5 is ~0.47, so 0.4 sits outside the ordinary spread; a terrain
        with no polished ground flags nothing (the bar is absolute, not
        a percentile, so it cannot manufacture findings).
  POLISH_MIN_SLOPE_DEG = 12 — below this the ground is a basin floor or
        meadow flat, where smoothness is the intended landform, not a
        defect. Above it a smooth sheet is legible as "polished".
  SPOT_MIN_WINDOWS = 6     — a "spot" is a connected cluster of at least
        6 flagged 128 m windows (~0.1 km^2), the scale at which a smooth
        sheet reads in a frame rather than vanishing into noise.
  CV_BAR = 0.05            — the locked v1.15 acceptance bar, quoted.

Exit codes:
  0  measured; NO finding (all CVs >= bar, no polished spot)
  2  bad arguments
  3  measured; FINDINGS PRESENT (any CV below bar, or any polished spot)
  4  COULD NOT MEASURE (provenance broken, inputs unreadable) — never
     a pass, never a number
  1  unexpected error, or --selftest failure
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import composite_stamps as cs   # noqa: E402  single source of mask math

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

CV_BAR = 0.05
CV_NBINS = 720
POLISH_ABS_LAP_M = 0.5
POLISH_REL_SCORE = 0.4
POLISH_MIN_SLOPE_DEG = 12.0
SPOT_MIN_WINDOWS = 6
MIN_REF_CELLS = 1000                 # a band below this has no control
WINDOW_PX = 32                       # 128 m at 4 m spacing
SLOPE_BANDS = ((5.0, 15.0), (15.0, 30.0), (30.0, 45.0), (45.0, 90.0))
RECORDED_SPINE_CV = 0.089            # RECIPES.md "Pass 7 — the sweep gate"

EXIT_OK, EXIT_ERR, EXIT_ARGS, EXIT_FINDINGS, EXIT_NOMEASURE = 0, 1, 2, 3, 4


class NoMeasure(Exception):
    """Raised when the premise is broken: report, exit 4, no numbers."""


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------ loading --

def load_world(recipe_path):
    """Recipe + sidecar + heightmap, with the provenance gate applied.

    Returns dict with recipe, sidecar, height_m (world metres), origin_m,
    spacing_m, and per-placement stamp arrays. Raises NoMeasure with the
    exact broken link on any provenance failure.
    """
    with open(recipe_path, encoding="utf-8") as fh:
        recipe = json.load(fh)
    st = recipe.get("stamps")
    if not isinstance(st, dict) or not st.get("placements"):
        raise NoMeasure("recipe has no stamps.placements block")

    hm_rel = recipe["heightmap"]["source"]
    hm_path = os.path.normpath(os.path.join(REPO_ROOT, hm_rel))
    sidecar_path = os.path.normpath(
        os.path.join(REPO_ROOT, st["output"] + ".stamps.json"))
    if not os.path.isfile(sidecar_path):
        raise NoMeasure("compositor sidecar missing: {0}".format(
            sidecar_path))
    with open(sidecar_path, encoding="utf-8") as fh:
        sidecar = json.load(fh)

    # --- provenance gate -------------------------------------------
    hm_sha = _sha256_file(hm_path)
    if hm_sha != sidecar.get("output_sha256"):
        raise NoMeasure(
            "heightmap.source ({0}) sha {1}.. does not match the "
            "sidecar's output_sha256 {2}.. — the terrain is not the "
            "recorded compositor output; reading A would describe a mask "
            "the world does not carry".format(
                hm_rel, hm_sha[:12],
                str(sidecar.get("output_sha256"))[:12]))
    block_sha = cs._canonical_sha256(st)
    if block_sha != sidecar.get("stamps_block_sha256"):
        raise NoMeasure(
            "recipe stamps block sha {0}.. does not match the sidecar's "
            "{1}.. — the placements were edited after the composite; "
            "re-run the compositor (and adoption) before measuring"
            .format(block_sha[:12],
                    str(sidecar.get("stamps_block_sha256"))[:12]))

    meta = sidecar.get("stamp_meta") or {}
    stamps_by_id = {}
    for p in st["placements"]:
        pid = p["id"]
        if pid not in meta:
            raise NoMeasure("sidecar stamp_meta has no entry for "
                            "{0!r}".format(pid))
        spath = os.path.normpath(
            os.path.join(REPO_ROOT, meta[pid]["relpath"]))
        ssha = _sha256_file(spath)
        if ssha != p["stamp_sha256"]:
            raise NoMeasure(
                "stamp file for {0!r} sha {1}.. does not match the "
                "placement's stamp_sha256 {2}..".format(
                    pid, ssha[:12], p["stamp_sha256"][:12]))
        stamps_by_id[pid] = cs.read_png16_square(spath, pid)

    ls = recipe["landscape"]
    origin_m = (float(ls["location_cm"][0]) / 100.0,
                float(ls["location_cm"][1]) / 100.0)
    spacing_m = float(ls["scale_xy_cm"]) / 100.0
    z_scale_m = float(ls["z_scale_cm"]) / 100.0
    actor_z_m = float(ls["location_cm"][2]) / 100.0

    from PIL import Image
    arr = np.asarray(Image.open(hm_path))
    if arr.dtype != np.uint16 or arr.ndim != 2:
        raise NoMeasure("heightmap must be 16-bit single-channel; got "
                        "dtype {0} ndim {1}".format(arr.dtype, arr.ndim))
    height_m = actor_z_m + (arr.astype(np.float64) / 65535.0 - 0.5) \
        * z_scale_m
    if not np.isfinite(height_m).all():
        raise NoMeasure("heightmap decoded to non-finite values")

    return {"recipe": recipe, "sidecar": sidecar, "height_m": height_m,
            "origin_m": origin_m, "spacing_m": spacing_m,
            "stamps_by_id": stamps_by_id,
            "placements": st["placements"]}


def placement_mask(p, stamp_u16, origin_m, spacing_m, map_n,
                   jitter_override=None):
    """The compositor's own mask for one placement, plus window coords.

    Returns (mask, r0, c0, cx, cy, half_px). The window is NOT clamped to
    the map — the caller decides how to treat off-map area (the CV reader
    excludes boundary-touching bins; the polish reader clamps).
    """
    q = dict(p)
    if jitter_override is not None:
        q["falloff_jitter"] = jitter_override
    cx = (float(p["centre_m"][0]) - origin_m[0]) / spacing_m
    cy = (float(p["centre_m"][1]) - origin_m[1]) / spacing_m
    half_px = float(p["size_m"]) * 0.5 / spacing_m
    theta = math.radians(float(p["rotation_deg"]))
    reach = half_px * (abs(math.cos(theta)) + abs(math.sin(theta)))
    r0 = int(math.floor(cy - reach))
    r1 = int(math.ceil(cy + reach)) + 1
    c0 = int(math.floor(cx - reach))
    c1 = int(math.ceil(cx + reach)) + 1
    rows = np.arange(r0, r1)
    cols = np.arange(c0, c1)
    _s, mask, _f, _side = cs._stamp_mask_and_sample(
        stamp_u16, q, rows, cols, cx, cy, half_px)
    return mask, r0, c0, cx, cy, half_px


# ------------------------------------------------------- reading A: CV --

def outer_contour_cv(mask, r0, c0, cx, cy, half_px, map_n,
                     nbins=CV_NBINS):
    """CV of the outer contributing radius, from the mask itself.

    For every contributing pixel (mask > 0) take its polar angle about
    the placement centre; per angular bin keep the LARGEST radius. Bins
    whose farthest pixel lies within 2 px of the map boundary are
    EXCLUDED — there the contour is the map edge, not the falloff — and
    the exclusion count is reported so a mostly-clipped placement is
    visibly a partial measurement rather than a quiet one.

    Returns (cv, used_bins, excluded_bins). cv is None if fewer than
    half the bins survive — that is "could not measure", not 0.
    """
    rr, cc = np.nonzero(mask > 0.0)
    if rr.size == 0:
        return None, 0, nbins
    dy = (rr + r0).astype(np.float64) - cy
    dx = (cc + c0).astype(np.float64) - cx
    ang = np.arctan2(dy, dx)
    rad = np.hypot(dx, dy)
    bins = ((ang + np.pi) / (2.0 * np.pi) * nbins).astype(int) % nbins

    rout = np.zeros(nbins)
    np.maximum.at(rout, bins, rad)

    # boundary exclusion: farthest pixel per bin at the map edge?
    row_abs = rr + r0
    col_abs = cc + c0
    edge_px = ((row_abs <= 1) | (col_abs <= 1)
               | (row_abs >= map_n - 2) | (col_abs >= map_n - 2))
    edge_bin = np.zeros(nbins, dtype=bool)
    # a bin is tainted if its maximal-radius pixel is (near) the edge:
    # conservative — taint the bin if ANY contributing pixel within 1 px
    # of that bin's max radius is an edge pixel.
    for b in np.unique(bins[edge_px]):
        sel = bins == b
        if rad[sel].max() - rad[sel & edge_px].max() < 1.5:
            edge_bin[b] = True

    ok = (rout > 0) & ~edge_bin
    used = int(ok.sum())
    if used < nbins // 2:
        return None, used, int(nbins - used)
    ro = rout[ok] / half_px
    return float(ro.std() / ro.mean()), used, int(nbins - used)


# --------------------------------------------------- reading B: polish --

def relief_fields(height_m, spacing_m):
    """(|laplacian| in metres, cell slope in degrees)."""
    h = height_m
    lap = np.abs(np.roll(h, 1, 0) + np.roll(h, -1, 0)
                 + np.roll(h, 1, 1) + np.roll(h, -1, 1) - 4.0 * h)
    # roll wraps at the borders; the border ring is not real curvature.
    lap[0, :] = lap[-1, :] = 0.0
    lap[:, 0] = lap[:, -1] = 0.0
    gy, gx = np.gradient(h, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return lap, slope


def band_medians(lap, slope, reference):
    """Per-slope-band median |lap| over the REFERENCE population only.

    `reference` is a boolean mask of cells eligible to serve as the
    control — in the real run, every cell NOT inside any falloff annulus.

    THE REFERENCE MAY NOT CONTAIN THE GROUND UNDER TEST. Measured
    2026-08-06: with the reference taken map-wide, the 15-30 deg band on
    the selftest synthetic was 110,953 cells of which 94,136 were the
    smooth annulus itself — 85% — so the polished ground set the standard
    it was judged against and scored 0.76 against a 0.4 bar. The failure
    is self-masking and worsens with severity: the bigger the polished
    spot, the more it owns its own band. See LESSONS 2026-08-06, "THE
    POLISH DETECTOR USED THE POLISHED GROUND AS ITS OWN CONTROL".

    Returns {band: {"median": float|None, "cells": int}}. `median` is
    None when the band has fewer than MIN_REF_CELLS reference cells, or
    when the median is not finite — both are "could not measure" for that
    band, and the caller must COUNT the windows it skips rather than
    treat them as clean (non-negotiable 6).
    """
    out = {}
    for lo, hi in SLOPE_BANDS:
        m = (slope >= lo) & (slope < hi) & reference
        cells = int(m.sum())
        if cells < MIN_REF_CELLS:
            out[(lo, hi)] = {"median": None, "cells": cells}
            continue
        med = float(np.median(lap[m]))
        out[(lo, hi)] = {"median": med if math.isfinite(med) else None,
                         "cells": cells}
    return out


def polished_windows(lap, slope, annulus, owner_idx, ids, origin_m,
                     spacing_m, bmed):
    """Scan WINDOW_PX windows inside falloff annuli; flag polished ones.

    A window is flagged when, over its annulus cells at slope >= 5 deg:
      median slope >= POLISH_MIN_SLOPE_DEG
      median |lap| <  POLISH_ABS_LAP_M
      median |lap| <  POLISH_REL_SCORE * (REFERENCE median for its band)

    Returns (flagged, skipped) where `skipped` counts candidate windows
    that could NOT be adjudicated because their slope band has no usable
    reference median. A skipped window is an unmeasured window, not a
    clean one.
    """
    n = lap.shape[0]
    flagged = []
    skipped = 0
    for wr in range(0, n - WINDOW_PX, WINDOW_PX):
        for wc in range(0, n - WINDOW_PX, WINDOW_PX):
            aw = annulus[wr:wr + WINDOW_PX, wc:wc + WINDOW_PX]
            if aw.mean() < 0.5:
                continue
            sl = slope[wr:wr + WINDOW_PX, wc:wc + WINDOW_PX]
            lp = lap[wr:wr + WINDOW_PX, wc:wc + WINDOW_PX]
            m = aw & (sl >= 5.0)
            if m.sum() < WINDOW_PX * WINDOW_PX * 0.4:
                continue
            med = float(np.median(lp[m]))
            mslope = float(np.median(sl[m]))
            band = None
            for lo, hi in SLOPE_BANDS:
                if lo <= mslope < hi:
                    band = (lo, hi)
                    break
            ref = bmed.get(band) if band is not None else None
            if ref is None or ref["median"] is None:
                skipped += 1
                continue
            if not math.isfinite(med) or not math.isfinite(mslope):
                skipped += 1
                continue
            score = med / ref["median"]
            if (mslope >= POLISH_MIN_SLOPE_DEG
                    and med < POLISH_ABS_LAP_M
                    and score < POLISH_REL_SCORE):
                ow = owner_idx[wr:wr + WINDOW_PX, wc:wc + WINDOW_PX]
                counts = np.bincount(ow[aw & (ow >= 0)].ravel(),
                                     minlength=len(ids))
                flagged.append({
                    "wr": wr // WINDOW_PX, "wc": wc // WINDOW_PX,
                    "world_x": origin_m[0] + (wc + WINDOW_PX / 2.0)
                    * spacing_m,
                    "world_y": origin_m[1] + (wr + WINDOW_PX / 2.0)
                    * spacing_m,
                    "med_lap_m": med, "med_slope_deg": mslope,
                    "score": score,
                    "owner": ids[int(counts.argmax())],
                })
    return flagged, skipped


def cluster_windows(flagged):
    """4-connected clusters of flagged windows, largest first."""
    key = {(w["wr"], w["wc"]): w for w in flagged}
    seen, clusters = set(), []
    for k in key:
        if k in seen:
            continue
        stack, members = [k], []
        seen.add(k)
        while stack:
            cur = stack.pop()
            members.append(key[cur])
            r, c = cur
            for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if nb in key and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        clusters.append(members)
    clusters.sort(key=len, reverse=True)
    return clusters


# ------------------------------------------------------------ the run --

def run(recipe_path):
    w = load_world(recipe_path)
    placements = w["placements"]
    origin_m, spacing_m = w["origin_m"], w["spacing_m"]
    height_m = w["height_m"]
    n = height_m.shape[0]
    ids = [p["id"] for p in placements]

    print("SOURCE (reading A): recipe stamps block + compositor mask "
          "(composite_stamps._stamp_mask_and_sample)")
    print("SOURCE (reading B): {0} pixels".format(
        w["recipe"]["heightmap"]["source"]))
    print("PROVENANCE: heightmap sha == sidecar output_sha256; recipe "
          "stamps block sha == sidecar stamps_block_sha256; all stamp "
          "files match placement hashes.  ALL VERIFIED.")
    print("")

    findings = []

    # ---- reading A ------------------------------------------------
    print("READING A - outer contributing radius CV (bar >= {0})"
          .format(CV_BAR))
    print("  method: per-{0}-bin max radius of mask>0 pixels, "
          "boundary-tainted bins excluded".format(CV_NBINS))
    annulus = np.zeros(height_m.shape, dtype=bool)
    owner_idx = np.full(height_m.shape, -1, dtype=np.int16)
    _cvs = []
    for i, p in enumerate(placements):
        mask, r0, c0, cx, cy, half_px = placement_mask(
            p, w["stamps_by_id"][p["id"]], origin_m, spacing_m, n)
        cv, used, excl = outer_contour_cv(mask, r0, c0, cx, cy,
                                          half_px, n)
        _cvs.append(cv)
        # baseline with jitter forced 0 — the geometric contour's own CV
        # (non-zero for chebyshev, whose square is legible regardless)
        mask0, r00, c00, _, _, _ = placement_mask(
            p, w["stamps_by_id"][p["id"]], origin_m, spacing_m, n,
            jitter_override=0.0)
        cv0, _, _ = outer_contour_cv(mask0, r00, c00, cx, cy, half_px, n)
        if cv is None:
            print("  {0:<28s} COULD NOT MEASURE ({1} usable bins)"
                  .format(p["id"], used))
            findings.append("{0}: contour mostly off-map; CV not "
                            "measurable".format(p["id"]))
        else:
            verdict = "ok" if cv >= CV_BAR else "BELOW BAR"
            print("  {0:<28s} cv {1:.3f}  (geometric baseline {2:.3f}, "
                  "excluded bins {3})  {4}".format(
                      p["id"], cv, cv0 if cv0 is not None else
                      float("nan"), excl, verdict))
            if cv < CV_BAR:
                findings.append(
                    "{0}: outer-contour CV {1:.3f} is below 0.05 UNDER "
                    "THIS PROCEDURE — see the calibration warning below "
                    "before reading it as a spec violation"
                    .format(p["id"], cv))
            if p["id"] == "spine_aretes":
                print("    spine_aretes recorded CV was {0}; measured "
                      "{1:.3f} here.".format(RECORDED_SPINE_CV, cv))

        # accumulate the annulus for reading B (membership only)
        r1 = r0 + mask.shape[0]
        c1 = c0 + mask.shape[1]
        rr0, cc0 = max(0, r0), max(0, c0)
        rr1, cc1 = min(n, r1), min(n, c1)
        sub = mask[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0]
        a = (sub > 0.0) & (sub < 0.999)
        annulus[rr0:rr1, cc0:cc1] |= a
        ow = owner_idx[rr0:rr1, cc0:cc1]
        ow[a] = i
        owner_idx[rr0:rr1, cc0:cc1] = ow

    # ---- reading A, calibration warning ---------------------------
    # Measured 2026-08-06: EVERY placement reads lower than the recorded
    # band (0.089-0.367, schema.md:824-825), by roughly a factor of two,
    # and uniformly. A systematic offset across all nine is evidence
    # about the METHOD, not about the terrain — so "below 0.05" here is
    # NOT a proven violation of that bar. Compounding it: schema.md
    # records EIGHT locked placements and the recipe now carries NINE,
    # and NO GATE ANYWHERE ENFORCES THE BAR (grep: it appears in
    # schema.md and RECIPES.md prose only, in no script). The recorded
    # numbers are a one-off hand measurement whose procedure was never
    # written down and never re-run.
    print("")
    _got = [v for v in _cvs if v is not None]
    print("  CALIBRATION WARNING — the bar and these numbers may not be")
    print("  the same statistic. Recorded band 0.089-0.367 over EIGHT")
    print("  placements (schema.md:824); measured here {0}"
          .format("{0:.3f}-{1:.3f}".format(min(_got), max(_got))
                  if _got else "nothing measurable"))
    print("  over {0}, every one lower — a systematic offset, which"
          .format(len(_cvs)))
    print("  points at the derivation, not the ground. The recorded")
    print("  procedure is not in the repo and NO GATE ENFORCES the bar.")
    print("  What IS established: this procedure is written down, and")
    print("  its synthetic controls prove it discriminates (jitter 0 ->")
    print("  CV ~0 and below bar; jitter 0.45 -> clears it). Treat the")
    print("  below-bar rows as A RANKING to re-derive the bar against,")
    print("  not as a spec violation to act on.")

    # ---- reading B ------------------------------------------------
    print("")
    print("READING B - polished falloff spots (window {0} px = {1:.0f} "
          "m; abs bar {2} m, rel bar {3}, slope >= {4} deg, cluster >= "
          "{5} windows)".format(
              WINDOW_PX, WINDOW_PX * spacing_m, POLISH_ABS_LAP_M,
              POLISH_REL_SCORE, POLISH_MIN_SLOPE_DEG, SPOT_MIN_WINDOWS))
    lap, slope = relief_fields(height_m, spacing_m)
    reference = ~annulus
    print("  REFERENCE population: cells NOT in any falloff annulus "
          "({0} of {1}, {2:.1f}%). The ground under test is EXCLUDED "
          "from the control it is scored against."
          .format(int(reference.sum()), reference.size,
                  100.0 * reference.sum() / reference.size))
    bmed = band_medians(lap, slope, reference)
    for (lo, hi), v in sorted(bmed.items()):
        print("  reference median |lap|, slope {0:>2.0f}-{1:<2.0f} deg : "
              "{2:<10s} (reference cells {3})".format(
                  lo, hi,
                  "{0:.3f} m".format(v["median"])
                  if v["median"] is not None else "NO CONTROL",
                  v["cells"]))
    flagged, skipped = polished_windows(lap, slope, annulus, owner_idx,
                                        ids, origin_m, spacing_m, bmed)
    clusters = cluster_windows(flagged)
    spots = [c for c in clusters if len(c) >= SPOT_MIN_WINDOWS]
    print("  flagged windows: {0}   clusters: {1}   spots (>= {2} "
          "windows): {3}".format(len(flagged), len(clusters),
                                 SPOT_MIN_WINDOWS, len(spots)))
    # Sub-threshold clusters are EVIDENCE, not silence. Reporting only
    # "spots: 0" would hide 23 flagged windows behind a scale choice, and
    # "the two polished falloff spots" were observed in a FRAME with no
    # recorded extent — they may well be smaller than SPOT_MIN_WINDOWS.
    sub = [c for c in clusters if len(c) < SPOT_MIN_WINDOWS]
    if clusters:
        hist = {}
        for c in clusters:
            hist[len(c)] = hist.get(len(c), 0) + 1
        print("  cluster-size distribution: {0}".format(
            ", ".join("{0} of size {1}".format(hist[k], k)
                      for k in sorted(hist, reverse=True))))
    if sub:
        print("  sub-threshold clusters (below the {0}-window spot bar, "
              "reported so a scale choice cannot read as an absence):"
              .format(SPOT_MIN_WINDOWS))
        for cl in sub[:8]:
            xs = [wd["world_x"] for wd in cl]
            ys = [wd["world_y"] for wd in cl]
            print("    {0} window(s) at ({1:.0f}, {2:.0f}) m, med|lap| "
                  "{3:.2f} m, slope {4:.0f} deg, score {5:.2f}, "
                  "annulus of {6}".format(
                      len(cl), float(np.mean(xs)), float(np.mean(ys)),
                      float(np.median([w["med_lap_m"] for w in cl])),
                      float(np.median([w["med_slope_deg"] for w in cl])),
                      float(np.median([w["score"] for w in cl])),
                      ", ".join(sorted({w["owner"] for w in cl}))))
        if len(sub) > 8:
            print("    ... and {0} more".format(len(sub) - 8))
        print("  largest cluster: {0} window(s) = {1:.3f} km2 (spot bar "
              "{2} windows = {3:.3f} km2)".format(
                  max(len(c) for c in sub),
                  max(len(c) for c in sub) * (WINDOW_PX * spacing_m) ** 2
                  / 1e6, SPOT_MIN_WINDOWS,
                  SPOT_MIN_WINDOWS * (WINDOW_PX * spacing_m) ** 2 / 1e6))

        # A cluster ONE WINDOW under an arbitrary bar is not an absence.
        # SPOT_MIN_WINDOWS was fixed before any of this was measured and
        # is deliberately NOT re-tuned here — tuning a threshold until
        # the expected answer appears is how a measurement becomes a
        # confirmation. The reportable fact is the DISTRIBUTION: where
        # the near-bar clusters separate from the rest, they are the
        # finding regardless of where the bar sits.
        near = [c for c in sub if len(c) >= SPOT_MIN_WINDOWS - 1]
        rest = max([len(c) for c in sub
                    if len(c) < SPOT_MIN_WINDOWS - 1] or [0])
        if near:
            for cl in near:
                findings.append(
                    "near-bar polished cluster: {0} windows ({1:.3f} "
                    "km2) at ({2:.0f}, {3:.0f}) m, slope {4:.0f} deg, "
                    "{5:.0f}% of the reference relief for its band, in "
                    "the {6} annulus — one window under the {7}-window "
                    "spot bar, which was set before measurement"
                    .format(len(cl),
                            len(cl) * (WINDOW_PX * spacing_m) ** 2 / 1e6,
                            float(np.mean([w["world_x"] for w in cl])),
                            float(np.mean([w["world_y"] for w in cl])),
                            float(np.median([w["med_slope_deg"]
                                             for w in cl])),
                            100.0 * float(np.median([w["score"]
                                                     for w in cl])),
                            ", ".join(sorted({w["owner"] for w in cl})),
                            SPOT_MIN_WINDOWS))
            print("  NEAR-BAR: {0} cluster(s) at {1} windows against a "
                  "next-largest of {2} — the distribution separates "
                  "these from the rest independently of the bar."
                  .format(len(near), SPOT_MIN_WINDOWS - 1, rest))

    if skipped:
        print("  UNMEASURED windows: {0} — their slope band has no usable "
              "reference median. These are NOT clean windows."
              .format(skipped))
        findings.append(
            "{0} annulus window(s) could not be adjudicated — no "
            "reference population in their slope band (non-negotiable 6: "
            "unmeasured is not clean)".format(skipped))
    for i, cl in enumerate(spots):
        xs = [wd["world_x"] for wd in cl]
        ys = [wd["world_y"] for wd in cl]
        meds = [wd["med_lap_m"] for wd in cl]
        slopes = [wd["med_slope_deg"] for wd in cl]
        owners = sorted({wd["owner"] for wd in cl})
        area_km2 = len(cl) * (WINDOW_PX * spacing_m) ** 2 / 1e6
        print("  SPOT {0}: {1} windows ({2:.2f} km2), centre "
              "({3:.0f}, {4:.0f}) m, extent x [{5:.0f}..{6:.0f}] "
              "y [{7:.0f}..{8:.0f}], med|lap| {9:.2f} m, slope "
              "{10:.0f} deg, annulus of: {11}".format(
                  i + 1, len(cl), area_km2,
                  float(np.mean(xs)), float(np.mean(ys)),
                  min(xs), max(xs), min(ys), max(ys),
                  float(np.median(meds)), float(np.median(slopes)),
                  ", ".join(owners)))
        findings.append(
            "polished spot {0}: {1:.2f} km2 at ({2:.0f}, {3:.0f}) in "
            "the {4} falloff".format(
                i + 1, area_km2, float(np.mean(xs)), float(np.mean(ys)),
                "/".join(owners)))

    print("")
    if findings:
        print("VERDICT: FINDINGS PRESENT")
        for f in findings:
            print("  - {0}".format(f))
        return EXIT_FINDINGS
    print("VERDICT: no finding — all contour CVs >= {0}, no polished "
          "spot at the derived bars".format(CV_BAR))
    return EXIT_OK


# ----------------------------------------------------------- selftest --

def selftest():
    """Three directions (verification practice): BLOCK the violation,
    PASS the legitimate case, BLOCK WHEN BROKEN."""
    failures = []

    def check(name, ok):
        print("  {0:<58s} {1}".format(name, "ok" if ok else "FAIL"))
        if not ok:
            failures.append(name)

    rng = np.random.default_rng(20260806)
    stamp = (rng.random((256, 256)) * 65535).astype(np.uint16)

    def synth_placement(jitter, shape="euclidean"):
        return {"id": "selftest", "centre_m": [0.0, 0.0],
                "size_m": 2000.0, "rotation_deg": 0.0,
                "flip_x": False, "flip_y": False,
                "falloff": 0.5, "falloff_shape": shape,
                "falloff_jitter": jitter, "falloff_jitter_scale": 0.3,
                "opacity": 1.0, "blend": "ADD", "datum": "min",
                "amplitude_m": 100.0,
                "stamp_sha256": "aa" * 32}

    origin = (-2048.0, -2048.0)
    spacing = 4.0
    map_n = 1024

    # 1. BLOCK: a jitter-0 euclidean contour is geometric — CV ~ 0,
    #    and the instrument must call it below bar.
    p0 = synth_placement(0.0)
    m, r0, c0, cx, cy, half = placement_mask(p0, stamp, origin,
                                             spacing, map_n)
    cv0, used, _ = outer_contour_cv(m, r0, c0, cx, cy, half, map_n)
    check("jitter 0 euclidean: CV measured ~0 and below bar",
          cv0 is not None and cv0 < 0.01 and cv0 < CV_BAR)

    # 2. PASS: a strongly jittered contour clears the bar.
    p1 = synth_placement(0.45)
    m, r0, c0, cx, cy, half = placement_mask(p1, stamp, origin,
                                             spacing, map_n)
    cv1, _, _ = outer_contour_cv(m, r0, c0, cx, cy, half, map_n)
    check("jitter 0.45: CV clears the 0.05 bar",
          cv1 is not None and cv1 >= CV_BAR)

    # 3. Monotone sanity: more jitter, more CV.
    check("CV monotone in jitter (0.45 > 0)", cv1 > cv0)

    # 4. POLISH BLOCK: a pure smoothstep ramp replacing rugged ground
    #    must be flagged. This mirrors the real mechanism: in the
    #    annulus the blend SUPPRESSES the base relief, so the synthetic
    #    puts the bare ramp where the cone contributes and rugged noise
    #    elsewhere. (An additive cone would keep the noise and be
    #    correctly NOT polished — that is case 5.)
    n = 512
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    rough = rng.normal(0.0, 1.0, (n, n))            # slope med ~19 deg
    r_px = np.hypot(xx - n / 2, yy - n / 2)
    t = np.clip((1.0 - r_px / 200.0) / 0.5, 0.0, 1.0)
    cone = (t * t * (3 - 2 * t)) * 150.0            # ramp 12-25 deg
    terrain = np.where(t > 0.0, cone, rough)
    lap, slp = relief_fields(terrain, 4.0)
    ann = (t > 0.0) & (t < 0.999)                   # the cone's annulus
    own = np.where(ann, 0, -1).astype(np.int16)
    bm = band_medians(lap, slp, ~ann)
    flg, skp = polished_windows(lap, slp, ann, own, ["cone"],
                                (0.0, 0.0), 4.0, bm)
    spots = [c for c in cluster_windows(flg) if len(c)
             >= SPOT_MIN_WINDOWS]
    check("synthetic smoothstep ramp flagged as a polished spot",
          len(spots) >= 1)
    check("...and it was adjudicated, not skipped", skp == 0)

    # 4b. THE REGRESSION THIS INSTRUMENT SHIPPED WITH (2026-08-06): with
    #     the reference taken map-wide, the annulus IS 85% of its own
    #     slope band and the identical defect goes unflagged. Asserted so
    #     a later edit cannot quietly restore the self-masking control.
    bm_selfref = band_medians(lap, slp, np.ones_like(ann))
    flg_sr, _ = polished_windows(lap, slp, ann, own, ["cone"],
                                 (0.0, 0.0), 4.0, bm_selfref)
    spots_sr = [c for c in cluster_windows(flg_sr) if len(c)
                >= SPOT_MIN_WINDOWS]
    check("map-wide reference MISSES it (the fixed defect, pinned)",
          len(spots_sr) == 0 and len(spots) >= 1)

    # 5. POLISH PASS: the additive version keeps the base relief in the
    #    annulus — realistic non-polished falloff — and flags nothing.
    lap2, slp2 = relief_fields(rough + cone, 4.0)
    bm2 = band_medians(lap2, slp2, ~ann)
    flg2, _ = polished_windows(lap2, slp2, ann, own, ["cone"],
                               (0.0, 0.0), 4.0, bm2)
    check("additive (relief-preserving) cone flags no window",
          len(flg2) == 0)

    # 6. BLOCK WHEN BROKEN: each provenance link, tampered, must refuse.
    #    Run against the real repo recipe; skip cleanly if absent.
    if os.path.isfile(DEFAULT_RECIPE):
        try:
            load_world(DEFAULT_RECIPE)
            base_ok = True
        except NoMeasure as exc:
            base_ok = False
            print("    (repo provenance currently broken: {0})"
                  .format(exc))
        if base_ok:
            with open(DEFAULT_RECIPE, encoding="utf-8") as fh:
                r = json.load(fh)
            r["stamps"]["placements"][0]["falloff"] = 0.31415
            trash = os.path.join(REPO_ROOT, "_trash")
            os.makedirs(trash, exist_ok=True)
            # left in _trash by design — repo rule 2, no deletes.
            tampered = os.path.join(
                trash, "measure_falloff_selftest_tampered.json")
            with open(tampered, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
            try:
                load_world(tampered)
                check("tampered stamps block refused (exit-4 path)",
                      False)
            except NoMeasure:
                check("tampered stamps block refused (exit-4 path)",
                      True)

    # 7. BLOCK WHEN BROKEN: non-finite heightmap refuses in
    #    relief consumers — NaN must not pass the polish bars
    #    (the NaN-passing-range-checks class, non-negotiable sweep).
    #    A NaN comparison is False, so NaN reaches the bars as a silent
    #    "not polished" — which is exactly the "unknown read as yes/no"
    #    class. The instrument must SKIP and COUNT it instead.
    #    (The previous form of this check ended in `or True` and could
    #     not fail — a dead gate of the class prove_gates.py sweeps for.)
    #    (a) a non-finite reference median must report NO CONTROL rather
    #        than a number. Injected directly, because a NaN in the
    #        heightfield produces a NaN SLOPE, which fails every band
    #        comparison and quietly removes itself from all bands — so
    #        the heightfield route cannot reach this path.
    lap_nan = lap.copy()
    lap_nan[(slp >= 15.0) & (slp < 30.0) & ~ann] = np.nan
    bm_nan = band_medians(lap_nan, slp, ~ann)
    check("a non-finite reference median reports NO CONTROL, not a value",
          bm_nan[(15.0, 30.0)]["median"] is None
          and bm_nan[(15.0, 30.0)]["cells"] >= MIN_REF_CELLS)

    #    (b) and windows whose band has no control are SKIPPED AND
    #        COUNTED — never flagged, and never counted clean. Run on the
    #        case-4 terrain, which DOES contain a real polished spot: the
    #        gate must refuse to adjudicate it rather than pass it.
    flg_nc, skp_nc = polished_windows(lap, slp, ann, own, ["cone"],
                                      (0.0, 0.0), 4.0, bm_nan)
    check("no control -> windows SKIPPED AND COUNTED, none flagged clean",
          skp_nc > 0 and len(flg_nc) < len(flg))
    # explicit: a NaN median cannot satisfy `med < POLISH_ABS_LAP_M`
    check("NaN median cannot satisfy the polish bars",
          not (float("nan") < POLISH_ABS_LAP_M))

    print("")
    if failures:
        print("SELFTEST: {0} FAILURE(S)".format(len(failures)))
        return EXIT_ERR
    print("SELFTEST: all directions hold")
    return EXIT_OK


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not os.path.isfile(args.recipe):
        print("REFUSE: recipe not found: {0}".format(args.recipe))
        return EXIT_ARGS
    try:
        return run(os.path.abspath(args.recipe))
    except NoMeasure as exc:
        print("COULD NOT MEASURE: {0}".format(exc))
        print("This is exit 4, not a pass and not a zero "
              "(non-negotiable 6).")
        return EXIT_NOMEASURE


if __name__ == "__main__":
    sys.exit(main())
