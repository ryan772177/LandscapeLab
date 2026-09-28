"""temporal_stability.py — the instrument the still frames cannot be:
find LOD pops, cull pops, shadow swimming and flicker in a SEQUENCE of
frames from a slow camera move.

Method
  1. consecutive frames -> linear luma (sRGB decoded)
  2. global motion compensation: estimate the dominant translation
     between frames by phase correlation (a dolly/pan at walking pace
     moves the whole image nearly uniformly at the sub-degree scale a
     frame apart), shift the earlier frame, and take the residual
  3. residual is normalised by local luminance (Weber): r = |dL| / L
  4. a pixel is "changed" when r > jnd (default 0.02) AND it sits in a
     connected blob of at least `min_blob_px` pixels (the eye ignores
     isolated single-pixel noise; TSR/temporal AA also produce it)
  5. per frame: changed fraction, largest blob, its bounding box
  6. pops are frames whose changed fraction exceeds the sequence median
     by more than `spike_sigma` MADs; each is reported with the blob's
     location so the offending object can be identified in the frame

What it is NOT: it does not know WHY a region changed. A pop, a shadow
cascade boundary sweeping, a specular flash and a bird are all spikes.
It finds the frames a human should look at, and it gives a number that
can be compared before/after a change (dither fade on, HLOD on, ...).
That is the instrument's job; the judgement stays with the reader.

Usage
  python temporal_stability.py frames/*.png --out stability.json
  python temporal_stability.py --selftest      (synthetic pop, no files)

Frames must be same size, in order (glob sorts by name; zero-pad).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys

import numpy as np
from PIL import Image


def luma_linear(path_or_array):
    if isinstance(path_or_array, np.ndarray):
        s = path_or_array.astype(np.float64) / 255.0
    else:
        s = np.asarray(Image.open(path_or_array).convert("RGB")).astype(np.float64) / 255.0
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def phase_shift(a, b):
    """Integer (dy, dx) translation that best maps a onto b."""
    A = np.fft.fft2(a - a.mean()); B = np.fft.fft2(b - b.mean())
    R = A * np.conj(B); R /= np.maximum(np.abs(R), 1e-9)
    r = np.fft.ifft2(R).real
    dy, dx = np.unravel_index(np.argmax(r), r.shape)
    h, w = a.shape
    if dy > h // 2: dy -= h
    if dx > w // 2: dx -= w
    return int(dy), int(dx)


def shift(a, dy, dx):
    return np.roll(np.roll(a, -dy, axis=0), -dx, axis=1)


def blobs(mask):
    """Connected components (4-neighbour) without scipy. Returns list of
    (size, y0, y1, x0, x1) sorted by size desc."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True
        n = 0; ymin = ymax = y0; xmin = xmax = x0
        while stack:
            y, x = stack.pop(); n += 1
            ymin = min(ymin, y); ymax = max(ymax, y); xmin = min(xmin, x); xmax = max(xmax, x)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        out.append((n, ymin, ymax, xmin, xmax))
    out.sort(reverse=True)
    return out


def analyse(frames, jnd=0.02, min_blob_px=12, spike_sigma=4.0, downsample=2):
    L = [luma_linear(f)[::downsample, ::downsample] for f in frames]
    per = []
    for i in range(1, len(L)):
        a, b = L[i - 1], L[i]
        dy, dx = phase_shift(a, b)
        a2 = shift(a, dy, dx)
        # crop the wrapped border
        m = 4 + max(abs(dy), abs(dx))
        a2 = a2[m:-m, m:-m]; b2 = b[m:-m, m:-m]
        r = np.abs(b2 - a2) / np.maximum((a2 + b2) / 2.0, 0.005)
        mask = r > jnd
        bl = [x for x in blobs(mask) if x[0] >= min_blob_px]
        changed = sum(x[0] for x in bl) / mask.size
        big = bl[0] if bl else (0, 0, 0, 0, 0)
        per.append({"frame": i, "motion_px": [dy * downsample, dx * downsample],
                    "changed_fraction": round(float(changed), 5),
                    "largest_blob_px": int(big[0] * downsample * downsample),
                    "largest_blob_bbox_xyxy": [int(big[3] * downsample), int(big[1] * downsample),
                                               int(big[4] * downsample), int(big[2] * downsample)]})
    cf = np.array([p["changed_fraction"] for p in per])
    med = float(np.median(cf)); mad = float(np.median(np.abs(cf - med))) or 1e-6
    spikes = [p for p in per if (p["changed_fraction"] - med) / (1.4826 * mad) > spike_sigma]
    return {"frames": len(frames), "jnd": jnd, "min_blob_px": min_blob_px,
            "median_changed_fraction": round(med, 5), "mad": round(mad, 6),
            "spikes": spikes, "per_frame": per,
            "score": round(float(cf.mean()), 5),
            "_read": "score = mean changed fraction (lower is steadier); spikes = frames "
                     "to look at; bbox says where. Compare score before/after a change on "
                     "the SAME dolly path."}


def selftest():
    rng = np.random.default_rng(1)
    h, w = 240, 320
    base = rng.uniform(0.2, 0.8, (h + 40, w + 40))
    # smooth it a bit so phase correlation has structure
    for _ in range(2):
        base = (base + np.roll(base, 1, 0) + np.roll(base, 1, 1) + np.roll(base, -1, 0) + np.roll(base, -1, 1)) / 5
    frames = []
    for i in range(12):
        f = base[i:i + h, 2 * i:2 * i + w].copy()   # dolly: 1 px down, 2 px right per frame
        if i == 7:
            f[100:130, 150:170] *= 1.6              # a pop: a 30x20 region brightens 60%
        rgb = np.clip(f, 0, 1) ** (1 / 2.2) * 255
        frames.append(np.stack([rgb] * 3, -1).astype(np.uint8))
    rep = analyse(frames, downsample=1)
    # the region brightens at frame 7 and reverts at 8: two spikes, both real
    ok = [p["frame"] for p in rep["spikes"]] == [7, 8] and \
        all(140 <= p["largest_blob_bbox_xyxy"][0] <= 152 for p in rep["spikes"])
    ok = ok and _dup_ok()
    print("selftest:", "PASS" if ok else "FAIL", json.dumps(rep["spikes"], indent=1))
    return 0 if ok else 1


# DUPLICATE-TOOL CONTRACT-BEGIN (PASS3 §1, D-2 item 1f). This file exists twice --
# here (the working copy) and as the desk's DELIVERED artefact under
# research/. The delivered copy is read-only; this copy is byte-identical to
# it, or _DIVERGENCE_NOTE states why it is ahead. A silent drift between the
# two is the defect this check exists to catch.
import os as _os  # noqa: E402
_RESEARCH_COPY = "research/brief/brief1_distance_as_angle/brief1/scripts/temporal_stability.py"
_DIVERGENCE_NOTE = None  # None => the ANALYSIS code must match the delivered copy


def _dup_ok():
    return _dup_check(__file__, _RESEARCH_COPY, _DIVERGENCE_NOTE)


def _dup_check(this_file, research_rel, note):
    """Compare the SUBSTANTIVE code (everything before the DUPLICATE-TOOL
    CONTRACT marker) against the desk's delivered copy, so this contract block
    itself is not counted as drift. Identical substance -> OK. Different
    substance -> OK only if a note documents it, else FAIL: a silent drift in
    the analysis is the defect this guards."""
    # tokens assembled from pieces so the FULL marker string never appears
    # verbatim in this code -- otherwise split() would cut at these very
    # assignment lines instead of at the real marker comments.
    begin = "# DUPLICATE-TOOL " + "CONTRACT-BEGIN"
    end = "# DUPLICATE-TOOL " + "CONTRACT-END"
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(this_file)))
    other = _os.path.join(root, research_rel)
    if not _os.path.isfile(other):
        print("  dup-check: research copy MISSING at %s -- FAIL" % research_rel)
        return False
    mine = open(_os.path.abspath(this_file), encoding="utf-8").read()
    theirs = open(other, encoding="utf-8").read()

    def _strip(t):
        # excise the contract region (BEGIN..END, wherever it sits in the
        # file) and the one-line call into it, then compare only substantive
        # non-blank lines. Blank-line drift around the excision does not count.
        if begin in t and end in t:
            t = t.split(begin)[0] + t.split(end, 1)[1]
        return "\n".join(ln.rstrip() for ln in t.split("\n")
                         if ln.strip() and "_dup_ok()" not in ln)
    mine_code = _strip(mine)
    theirs_code = _strip(theirs)
    if mine_code == theirs_code:
        print("  dup-check: analysis code byte-identical to the delivered copy  OK")
        return True
    if note:
        print("  dup-check: analysis DIVERGES (documented): %s  OK" % note)
        return True
    print("  dup-check: analysis DIVERGES from the delivered copy, NO note -- FAIL")
    return False
# DUPLICATE-TOOL CONTRACT-END


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--jnd", type=float, default=0.02)
    ap.add_argument("--min-blob-px", type=int, default=12)
    ap.add_argument("--downsample", type=int, default=2)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    files = sorted(sum([glob.glob(p) for p in a.frames], []))
    if len(files) < 2:
        print("need at least two frames"); return 2
    rep = analyse(files, a.jnd, a.min_blob_px, downsample=a.downsample)
    js = json.dumps(rep, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_frame"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
