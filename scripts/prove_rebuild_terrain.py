"""prove_rebuild_terrain.py -- offline proof for rebuild_terrain.py.

No Gaea, no editor, no network. Runs in seconds and can gate a commit.

TWO THINGS ARE PROVEN, and the first is the one that matters:

  1. REPRODUCTION. `normalize_height` applied to build 002's archived
     `Snow_Out.png` produces the adopted `AlpineLab_v1_Height_normalized
     .png` EXACTLY -- 16,777,216 of 16,777,216 samples identical. Future
     rebuilds therefore land on the same heightmap the manual process
     produced on 2026-08-09, which is the whole point of automating it.

  2. THE GATES REFUSE. Each failure path is driven with input that
     should trip it (non-negotiable 2 -- a gate that has only seen good
     input has not been tested).

WHY PIXELS AND NOT SHA256, since this project hashes everything else:
the first version of test 1 compared sha256 and FAILED on a
byte-for-byte-different encoding of an identical image. `write_png16_
grey` emits filter-0 rows; the reference PNG uses adaptive filters. Same
samples, 26 MB vs 14 MB. A hash test on a RE-ENCODED image tests the
encoder. The sha inequality is kept below as the positive control for
the pixel test -- if both ever passed, the test would be comparing a
file with itself.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_alpine_terrain as mat   # noqa: E402
import rebuild_terrain as rt        # noqa: E402
import verify_build                 # noqa: E402

BUILD = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\002"
SRC = os.path.join(BUILD, "_archive", "Snow_Out.png")
REF = os.path.join(BUILD, "AlpineLab_v1_Height_normalized.png")

PASSED = []
FAILED = []
TEMPS = []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print("  {0}  {1}{2}".format("PASS" if ok else "FAIL", name,
                                 ("  -- " + detail) if detail else ""))


def refuses(name, fn, want_code=None, want_msg=None):
    # want_msg discriminates a gate that shares an exit code with earlier
    # gates (rule 13): capture the REFUSE output and require it to NAME the
    # gate under test, so an unrelated same-code refusal cannot pass as this
    # one. Output is re-emitted so the prover stays as verbose as before.
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn()
    except SystemExit as exc:
        out = buf.getvalue()
        sys.stdout.write(out)
        ok = exc.code != 0 and (want_code is None or exc.code == want_code)
        detail = "exit {0}".format(exc.code)
        if ok and want_msg is not None and want_msg not in out:
            ok = False
            detail = ("exit {0}, but the REFUSE message did not name this "
                      "gate (missing {1!r}) -- an earlier same-code gate "
                      "fired, so this test proved nothing".format(
                          exc.code, want_msg))
        check(name, ok, detail)
        return
    sys.stdout.write(buf.getvalue())
    check(name, False, "DID NOT REFUSE")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tmp(prefix):
    d = tempfile.mkdtemp(prefix=prefix)
    TEMPS.append(d)
    return d


def prove_reproduction():
    print("=" * 66)
    print("1. NORMALIZATION REPRODUCES THE ADOPTED BUILD 002 HEIGHTMAP")
    print("=" * 66)
    if not (os.path.isfile(SRC) and os.path.isfile(REF)):
        # "I could not look" is not a pass (non-negotiable 6).
        check("build 002 is available to compare against", False,
              "missing {0} or {1}".format(SRC, REF))
        return

    work = _tmp("prove_repro_")
    shutil.copy2(SRC, os.path.join(work, rt.HEIGHT_SOURCE))
    z = rt.normalize_height(work, 2500.0)
    got = os.path.join(work, rt.HEIGHT_OUTPUT)

    a = np.asarray(Image.open(got)).astype(np.int64)
    b = np.asarray(Image.open(REF)).astype(np.int64)
    same_shape = a.shape == b.shape
    check("normalized PIXELS equal the adopted heightmap",
          same_shape and a.size > 0 and not np.any(a - b),
          "{0:,} samples, max |diff| {1}".format(
              a.size, int(np.abs(a - b).max()) if same_shape else -1))
    check("sha256 DIFFERS -- the encoder, not the content",
          _sha(got) != _sha(REF),
          "positive control for the pixel test above")
    check("derived Z equals the adopted 180.81",
          z is not None and abs(z - 180.81) < 0.01, "z={0}".format(z))
    # Not just that the file exists -- that it RECORDS the destroyed range
    # (source_min/source_max), which is the whole reason it is written.
    sidecar_path = os.path.join(work, "height_normalization.json")
    sidecar_ok, sc_detail = False, "file absent"
    if os.path.isfile(sidecar_path):
        try:
            with open(sidecar_path, encoding="utf-8") as fh:
                sc = json.load(fh)
            sidecar_ok = ("source_min" in sc and "source_max" in sc
                          and "occupancy" in sc)
            sc_detail = "min={0} max={1} occ={2}".format(
                sc.get("source_min"), sc.get("source_max"),
                sc.get("occupancy"))
        except (ValueError, OSError) as exc:
            sc_detail = "unreadable: {0}".format(exc)
    check("sidecar RECORDS the destroyed range (source_min/max, occupancy)",
          sidecar_ok, sc_detail)


def prove_refusals():
    print("")
    print("=" * 66)
    print("2. THE GATES REFUSE")
    print("=" * 66)

    flat = _tmp("prove_flat_")
    mat.write_png16_grey(os.path.join(flat, rt.HEIGHT_SOURCE),
                         np.full((64, 64), 4321, dtype=np.uint16))
    refuses("a FLAT height refuses rather than dividing by zero",
            lambda: rt.normalize_height(flat, 2500.0), 6)

    eight = _tmp("prove_8bit_")
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(
        os.path.join(eight, rt.HEIGHT_SOURCE))
    refuses("an 8-BIT height refuses rather than quantising the terrain",
            lambda: rt.normalize_height(eight, 2500.0), 6)

    refuses("a build that wrote NOTHING refuses",
            lambda: rt.locate_outputs(_tmp("prove_empty_")), 5)

    amb = _tmp("prove_amb_")
    for sub in ("a", "b"):
        os.makedirs(os.path.join(amb, sub))
        mat.write_png16_grey(os.path.join(amb, sub, rt.HEIGHT_SOURCE),
                             np.full((8, 8), 1, dtype=np.uint16))
    refuses("TWO candidate output dirs refuses rather than picking one",
            lambda: rt.locate_outputs(amb), 5)

    saved = dict(verify_build.SPEC)
    verify_build.SPEC.pop(rt.HEIGHT_OUTPUT, None)

    class Args(object):
        project = REF          # a real file, so preflight reaches the check
        root = BUILD
    refuses("CONTRACT DRIFT (verify_build.SPEC moved) refuses",
            lambda: rt.preflight(Args()), 2,
            want_msg="verify_build.SPEC no longer declares")
    verify_build.SPEC.clear()
    verify_build.SPEC.update(saved)


def prove_derivation():
    print("")
    print("=" * 66)
    print("3. THE Z DERIVATION")
    print("=" * 66)
    z, span, occ = rt.derive_z_scale(496, 24763, 2500.0)
    check("build 002 arithmetic reproduces from the shared function",
          abs(occ - 0.37029) < 1e-5 and abs(span - 925.73) < 0.01
          and abs(z - 180.81) < 0.01,
          "occ {0:.5f}  span {1:.2f} m  Z {2:.2f}".format(occ, span, z))
    z2, span2, _ = rt.derive_z_scale(496, 24763, None)
    check("an unknown project range yields UNKNOWN, never 100",
          z2 is None and span2 is None)
    zf, _s, _o = rt.derive_z_scale(0, 65535, 2500.0)
    check("a full-range source gives the naive answer, as it should",
          abs(zf - 488.28) < 0.01, "Z {0:.2f}".format(zf))


def main():
    try:
        prove_reproduction()
        prove_refusals()
        prove_derivation()
    finally:
        for d in TEMPS:
            shutil.rmtree(d, ignore_errors=True)

    print("")
    print("-" * 66)
    print("{0} passed, {1} failed".format(len(PASSED), len(FAILED)))
    for name in FAILED:
        print("  FAILED: {0}".format(name))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
