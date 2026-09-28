"""texture_16bit.py — the ONE 16-bit-source conversion, used by every importer.

SHARED INFRASTRUCTURE, created under CLAUDE.md non-negotiable 4a.

WHY THIS MODULE EXISTS
----------------------
The 16-bit-single-channel trap has now been paid for three times:

  1. The grass opacity mask. A 16-bit single-channel alpha PNG through
     TC_Alpha: the material's R-pin sample reads zero, the mask clips
     every pixel, and the material RENDERS NOTHING WHILE COMPILING CLEAN.
     Two sessions of invisible grass.
  2. The fir's roughness. Same class through TC_Masks. Quieter symptom —
     a shine defect, nothing looks obviously broken, no error appears.
  3. The landscape surfaces. `import_surface_set.py` imports Normal and
     (from Pass 2) Displacement maps that are 16-bit, and had NO
     conversion of any kind. The fix from (1) and (2) lived in
     `import_static_mesh.py` and did not apply here at all.

Instance (3) is the trigger. Non-negotiable 4a:

    A trap class that recurs across TWO DIFFERENT TOOLS is promoted to
    shared infrastructure, ON THE SPOT, without waiting for a third. One
    implementation, used by every caller, with a mandatory
    post-operation assertion that the result matches spec exactly.
    Individually-patched copies of the same fix then become a REJECTED
    pattern in their own right.

So `import_static_mesh.py` does not keep its own copy. It calls this.
A local re-implementation of this logic is now itself the defect.

THE CONVERSION, AND WHY THE FORMULA IS WHAT IT IS
-------------------------------------------------
    arr8 = clip((arr16 + 128) // 257, 0, 255)

65535 / 255 = 257 exactly, so a full-range 16-bit value maps to a
full-range 8-bit value with NO DATUM SHIFT. The `+ 128` makes it round
rather than truncate. Truncation is what PIL's own `I;16 -> L`
conversion does, and it is how this project once measured three
displacement maps as perfectly flat when they are not.

THE ASSERTION IS THE POINT, NOT THE CONVERSION
----------------------------------------------
The old inline version verified "same coverage above the mask midpoint,
within 1%". That is the right check for a MASK and it is not sufficient
for a HEIGHT FIELD — a displacement map could be badly rescaled and still
keep 50% of its pixels above the midpoint.

`assert_requantised` therefore checks the strictly stronger property:

    max |arr16/65535 - arr8/255|  <=  128/65535

i.e. the derivative is a true requantisation of the original and nothing
else. The bound is DERIVED from the formula (see MAX_REQUANT_ERROR), not
measured and rounded. Measured 2026-08-03 across all five ambientCG
displacement maps, the observed max error is 0.00195315 with correlation
>= 0.99977 — at the bound, as it should be. A datum shift, an inverted
map, a rescale, or a truncating converter all fail it immediately.

The mask-coverage check is KEPT, but with its thresholds CORRECTED and
its status downgraded honestly. The inherited version compared
`src > 128*257` against `dst > 128`, which are not the same threshold —
they differ by a 128-value band — so it refused Ground037's displacement
on arithmetic alone despite a perfect conversion. Aligned, its drift is
exactly 0.0 on all five surfaces, which also means it can no longer fail
unless the residual check fails first. **It is a tripwire that names the
historical symptom in its error message, not a second independent
proof.** Saying otherwise would be the "verified by a read-back it ran
itself" mistake in new clothes.

EVERY RESULT PRINTS. A number that is computed and not printed is not a
check — that lesson cost this project 48 surviving material expressions
nobody knew about.
"""

from __future__ import annotations

import os

# PIL modes that indicate a 16-bit (or 32-bit int) single-channel source.
# These are the defect class. RGB 16-bit is NOT in this list: it is a
# different code path (TC_Normalmap / BC5) and has never been shown to
# fail. Adding it here on suspicion would convert normal maps that may be
# perfectly fine, which is a change nobody has evidence for.
DEFECT_MODES = ("I;16", "I", "I;16B", "I;16L")

# The EXACT worst-case residual of the locked formula, DERIVED, not
# guessed and not measured-then-rounded.
#
#   65535 = 257 * 255 exactly.
#   ref = v / 65535,  dst = q / 255  where  q = (v + 128) // 257
#   ref - dst = (v - 257q) / 65535
#   with r = (v + 128) mod 257,  v - 257q = r - 128  in  [-128, +128]
#   so  |ref - dst|  <=  128 / 65535
#
# I first wrote 1/512 here as "half an 8-bit step". That is 0.001953125;
# the true bound is 0.0019531548. The good case FAILED THE SELFTEST by
# 3e-8 and the correct response was to derive the constant, not to widen
# it — a tolerance chosen to make a test pass is not a tolerance.
MAX_REQUANT_RESIDUAL = 128           # the exact integer bound; what is asserted
MAX_REQUANT_ERROR = MAX_REQUANT_RESIDUAL / 65535.0   # the same thing, for reporting

# The mask-coverage tolerance carried over from the original inline fix.
MAX_COVERAGE_DRIFT = 0.01


class TextureConversionError(RuntimeError):
    """Raised when a staged derivative fails its post-operation assertion.

    This is deliberately an exception and not a return code. A caller that
    forgets to check a return code silently imports the unconverted
    source, which is the exact failure mode this module exists to remove.
    """


def _lazy_imports():
    from PIL import Image
    import numpy as np
    return Image, np


def load_float(path):
    """Read ANY depth to float 0..1, without PIL's truncating convert.

    Added 2026-08-30, and it belongs HERE rather than in the caller: this
    module already owns `DEFECT_MODES` and already states, at line 38, that
    truncation "is what PIL's own `I;16 -> L`" does. A second module carrying
    its own copy of that knowledge is the individually-patched-fix pattern
    non-negotiable 4a makes REJECTED in its own right.

    The trap is not theoretical and it fired the day this was written:
    `Image.open(Ground037_Displacement).convert("L")` returns ALL 255 on a map
    whose real range is 18770..59293, so a convention test built on it read
    correlation 0.000 and reported an instrument fault. It was right to.

    Returns a 2-D array for single-channel sources, 3-D for colour.
    """
    Image, np = _lazy_imports()
    with Image.open(path) as im:
        mode = im.mode
        if mode in DEFECT_MODES:
            arr = np.asarray(im).astype(np.float64)
            scale = 65535.0 if arr.max() > 255.0 else 255.0
            return arr / scale
        if mode == "L":
            return np.asarray(im).astype(np.float64) / 255.0
        arr = np.asarray(im.convert("RGB")).astype(np.float64)
    return arr / 255.0


def assert_requantised(src_arr, dst_path, src_size):
    """MANDATORY post-operation assertion. Returns the measured report.

    Raises TextureConversionError unless the staged file is a true
    requantisation of the source. Never returns a soft failure — see the
    docstring on TextureConversionError.
    """
    Image, np = _lazy_imports()

    chk = Image.open(dst_path)
    out = {
        "mode": chk.mode,
        "size_ok": chk.size == src_size,
        "max_error": None,
        "coverage_drift": None,
    }

    if chk.mode != "L":
        raise TextureConversionError(
            "staged {0} has mode {1!r}, expected 'L'".format(
                dst_path, chk.mode))
    if not out["size_ok"]:
        raise TextureConversionError(
            "staged {0} is {1}, source is {2}".format(
                dst_path, chk.size, src_size))

    # THE CHECK IS DONE IN INTEGER SPACE, and that is not a detail.
    #
    #   ref - dst = (v - 257*q) / 65535,  and  |v - 257*q| <= 128
    #
    # so the property is exactly "the integer residual fits in +/-128".
    # Testing it as a float comparison against 128/65535 fails on a
    # single ULP: the correct requantisation of this project's own data
    # produces a max error EQUAL to the bound, and `computed > constant`
    # was True by 1e-19 because the two sides reach the same real number
    # by different operation orders. Integers have no such margin.
    # (First written as a float compare; it refused the good case and
    # would have been "fixed" by widening the tolerance, which is how a
    # gate quietly stops gating.)
    dst_int = np.asarray(chk).astype(np.int64)
    resid = src_arr.astype(np.int64) - 257 * dst_int
    max_resid = int(np.abs(resid).max())
    out["max_residual"] = max_resid
    out["max_error"] = max_resid / 65535.0

    if max_resid > MAX_REQUANT_RESIDUAL:
        raise TextureConversionError(
            "staged {0} is not a requantisation of its source: max "
            "integer residual |v - 257*q| = {1} exceeds {2}, i.e. a "
            "normalised error of {3:.8f} against a bound of {4:.8f}. A "
            "datum shift, rescale, inversion or truncating converter all "
            "fail here.".format(
                dst_path, max_resid, MAX_REQUANT_RESIDUAL,
                max_resid / 65535.0, MAX_REQUANT_ERROR))

    # Mask-coverage tripwire, named for the historical symptom: a
    # conversion that silently EMPTIED a mask is what made the grass
    # invisible for two sessions.
    #
    # THE THRESHOLDS MUST BE ALIGNED, and the inherited version's were
    # not. It compared `src > 128*257` (= 32896) against `dst > 128`, but
    #
    #     dst > 128  <=>  q >= 129  <=>  src >= 129*257 - 128 = 33025
    #
    # leaving a 128-value band [32897, 33024] counted as "above" in the
    # source and "below" in the staged copy. Any texture whose histogram
    # is dense at the midpoint fails on arithmetic alone.
    #
    # It fired on real data the day it was shared: Ground037's
    # displacement has 1.24% of its pixels in exactly that band and was
    # REFUSED despite a perfect requantisation. The inherited inline copy
    # carried the same latent bug and never fired only because alpha and
    # roughness masks are bimodal -- mass at 0 and 255, nothing at the
    # midpoint. Moving the check to a HEIGHT FIELD exposed it.
    #
    # Aligned, the drift is EXACTLY 0.0 on all five surfaces. That also
    # means this check is now implied by the residual bound rather than
    # independent of it: it cannot fail unless the residual check fails
    # first. It is kept as a cheap tripwire that names the historical
    # symptom in its error message, NOT as a second proof.
    src_midpoint = (128 + 1) * 257 - 128        # 33025
    cov_src = float((src_arr >= src_midpoint).mean())
    cov_dst = float((np.asarray(chk) > 128).mean())
    drift = abs(cov_src - cov_dst)
    out["coverage_drift"] = drift
    if drift > MAX_COVERAGE_DRIFT:
        raise TextureConversionError(
            "staged {0} coverage above midpoint drifted {1:.4f} "
            "(source {2:.4f} -> staged {3:.4f}), tolerance {4:.4f}"
            .format(dst_path, drift, cov_src, cov_dst, MAX_COVERAGE_DRIFT))

    return out


def stage_8bit(src, stem, stage_dir, role="texture", verbose=True):
    """Convert `src` to an 8-bit staged copy IF it is a 16-bit source.

    Returns a dict, always — never None, and never a bare boolean:

        {"converted": bool,
         "src":       path the caller should import (staged copy, or the
                      ORIGINAL untouched when no conversion applied),
         "reason":    why it was or was not converted,
         "mode":      the source's PIL mode, or None if not inspected,
         "assertion": the measured report, or None}

    The vendor file is never modified. The derivative lands in
    `stage_dir`, the same pattern as pivot normalisation.

    A source PIL cannot read (the grass roughness ships as EXR) passes
    through UNINSPECTED with a stated reason. "I could not look" is
    reported, never silent, and never escalated into refusing a
    legitimate source the engine imports natively (non-negotiable 6).
    """
    result = {"converted": False, "src": src, "reason": None,
              "mode": None, "assertion": None}

    if not src.lower().endswith(".png"):
        result["reason"] = ("not a PNG; 16-bit inspection skipped "
                            "(I could not look, not 'it is fine')")
        if verbose:
            print("  NOTE: {0} source {1} is {2}".format(
                role, os.path.basename(src), result["reason"]))
        return result

    Image, np = _lazy_imports()

    try:
        im = Image.open(src)
    except OSError as exc:
        raise TextureConversionError(
            "cannot inspect {0}: {1}".format(src, exc))

    result["mode"] = im.mode
    if im.mode not in DEFECT_MODES:
        result["reason"] = "mode {0!r} is not the 16-bit single-channel " \
                           "defect class".format(im.mode)
        return result

    arr = np.asarray(im).astype(np.uint32)
    arr8 = np.clip((arr + 128) // 257, 0, 255).astype(np.uint8)

    os.makedirs(stage_dir, exist_ok=True)
    dst = os.path.join(stage_dir, stem + "_8bit.png")
    Image.fromarray(arr8, "L").save(dst)

    # MANDATORY. Raises rather than returning a code the caller may skip.
    report = assert_requantised(arr, dst, im.size)

    result.update({
        "converted": True,
        "src": dst.replace("\\", "/"),
        "reason": "16-bit single-channel source converted to 8-bit",
        "assertion": report,
    })

    if verbose:
        print("  16-bit {0} {1} ({2}) -> 8-bit staged copy  "
              "[max requant error {3:.6f} of {4:.6f}; coverage drift "
              "{5:.4f}]".format(role, stem, im.mode,
                                report["max_error"], MAX_REQUANT_ERROR,
                                report["coverage_drift"]))
    return result


def selftest():
    """Prove the assertion REFUSES, not just that it accepts.

    A gate that has only seen good input has not been tested
    (non-negotiable 2). Every case below is a way the conversion could go
    wrong that the OLD coverage-only check would have MISSED.
    """
    import tempfile
    Image, np = _lazy_imports()
    rng = np.random.default_rng(20260803)
    ok = True

    with tempfile.TemporaryDirectory() as tmp:
        # A source with real structure, spanning most of the 16-bit range.
        base = (rng.random((256, 256)) * 55000 + 5000).astype(np.uint32)
        src_path = os.path.join(tmp, "src.png")
        Image.fromarray(base.astype(np.uint16), "I;16").save(src_path)

        def stage(arr8, name):
            p = os.path.join(tmp, name)
            Image.fromarray(arr8.astype(np.uint8), "L").save(p)
            return p

        good = np.clip((base + 128) // 257, 0, 255)
        cases = [
            ("correct requantisation ACCEPTED", good, True),
            ("truncating converter (no +128)", base // 257, False),
            ("datum shift of +8 levels", np.clip(good + 8, 0, 255), False),
            ("inverted map", 255 - good, False),
            ("rescaled to half range", good // 2, False),
            ("flat mid-grey", np.full(good.shape, 128), False),
        ]
        for label, arr8, should_pass in cases:
            p = stage(arr8, label.replace(" ", "_") + ".png")
            try:
                assert_requantised(base, p, (256, 256))
                passed = True
                detail = ""
            except TextureConversionError as exc:
                passed = False
                detail = str(exc).split("source: ", 1)[-1].strip()[:78]
            good_result = (passed == should_pass)
            ok = ok and good_result
            verdict = "ACCEPTED" if passed else "REFUSED "
            print("  {0} {1:<38} {2}".format(
                verdict, label, "" if good_result else "*** WRONG ***"))
            if not passed and detail:
                print("           -> {0}".format(detail))

        # A truncating converter is the specific failure that made this
        # project measure three real displacement maps as flat.
        trunc = base // 257
        drift = abs(float((base >= (128 + 1) * 257 - 128).mean())
                    - float((trunc > 128).mean()))
        print("")
        print("  NOTE: the truncating converter's mask-coverage drift is "
              "{0:.4f},".format(drift))
        print("        {0} the old 1% coverage-only check — which is why "
              "the".format("INSIDE" if drift <= MAX_COVERAGE_DRIFT
                           else "outside"))
        print("        requantisation bound was added.")

        # load_float, proven against the exact failure that motivated it:
        # PIL's own convert("L"). The discriminator is a source whose range
        # sits in the UPPER half of 16-bit, which convert("L") saturates to
        # a constant -- the Ground037 displacement case, reproduced.
        print("")
        hi = (40000 + (base % 20000)).astype(np.uint16)
        hp = os.path.join(tmp, "hi16.png")
        Image.fromarray(hi, "I;16").save(hp)
        ref = hi.astype(np.float64) / 65535.0
        got = load_float(hp)
        bad_pil = np.asarray(Image.open(hp).convert("L")).astype(
            np.float64) / 255.0
        err = float(np.abs(got - ref).max())
        pil_flat = float(bad_pil.std()) < 1e-9
        good = err <= 1e-12 and pil_flat
        ok = ok and good
        print("  {0} load_float on a 16-bit upper-range source        {1}"
              .format("ACCEPTED" if err <= 1e-12 else "REFUSED ",
                      "" if good else "*** WRONG ***"))
        print("           -> max error {0:.3e}; PIL convert('L') std "
              "{1:.4f} ({2})".format(
                  err, float(bad_pil.std()),
                  "FLAT, i.e. destroyed" if pil_flat else "not flat"))

    print("")
    print("SELFTEST {0}".format("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(selftest())
