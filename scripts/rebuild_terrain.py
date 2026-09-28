"""rebuild_terrain.py — the canonical headless rebuild of AlpineLab_v1.

Rebuilds the Gaea project through the CLI into the NEXT incrementing
build folder, normalizes the height exactly the way build 002 was
normalized by hand, and hands the result to `verify_build.py`.

    python scripts/rebuild_terrain.py --go

Without `--go` it does the whole preflight, prints the exact command it
WOULD run, and exits 0 having touched nothing. That is the default
deliberately: a build overwrites nothing but takes real minutes of real
CPU, and this project has been bitten by tools that acted on a bare
invocation.

=====================================================================
WHICH CLI, AND WHY NOT THE OBVIOUS ONE
=====================================================================

`Gaea.BuildManager.exe` is installed and STILL DOES NOT WORK on the
Indie licence — it fails with *"The application to execute does not
exist: 'C:\\Program Files\\QuadSpinner\\Gaea 2\\Gaea.BuildManager.dll'"*.
The `.exe` is an apphost with no assembly behind it. That is the same
absence the old BROKEN entry recorded, and licensing did NOT fix it.

`Gaea.Swarm.exe` DOES work and is the headless path. Verified on this
install by running its own `--help` (Gaea Build Swarm 2.3.0.1). The
flags used here, quoted from that output:

    --Filename <string>     REQUIRED. Relative or absolute path to the
                            terrain file to build.
    --buildpath <string>    Fully qualified path to output files. Will
                            overwrite the path specified in the file.
    --resolution <string>   Override the resolution of the build
    --silent                Disables all interactivity. Useful for
                            automation.

=====================================================================
THE NORMALIZATION IS NOT COSMETIC — IT IS WHERE THE Z SCALE COMES FROM
=====================================================================

Gaea's Snow node exports the height as `Snow_Out.png` occupying only
part of the 16-bit range (build 002: 496-24763 of 65535). Build 002's
heightmap was stretched to full range by hand before import, and this
script reproduces that so future builds match.

The stretch DESTROYS the information that fixes the vertical scale, so
it is recorded before it is applied. `height_normalization.json` beside
the output carries the source min/max, the occupancy ratio, and the
derived UE Z scale — see R-GAEA section 6. Normalizing without recording
the range is how a landscape ends up 2.7x too tall and plausible.

This script does NOT resize 4096 -> 4033. That is `resize_gaea_build.py`
and it stays a separate, separately-verified step (R-GAEA section 4).

PROVEN OFFLINE by `scripts/prove_rebuild_terrain.py` (12/12): the
normalization reproduces build 002's adopted heightmap at 16,777,216 of
16,777,216 samples identical, and every refusal below is driven with
input that should trip it.

One cost worth knowing: `write_png16_grey` emits filter-0 rows, so the
normalized PNG is ~26 MB where Gaea's adaptive-filtered export of the
same samples is ~14 MB. Bigger file, identical pixels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_alpine_terrain as mat   # noqa: E402  -- the 16-bit writer
import verify_build                 # noqa: E402  -- the declared SPEC

# ---------------------------------------------------------------------
# DECLARED ONCE. Everything below reads these.
# ---------------------------------------------------------------------

GAEA_DIR = r"C:\Program Files\QuadSpinner\Gaea 2"
SWARM = os.path.join(GAEA_DIR, "Gaea.Swarm.exe")

DEFAULT_ROOT = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1"
DEFAULT_PROJECT = os.path.join(DEFAULT_ROOT, "AlpineLabe_v1.terrain")

# The un-normalized height Gaea writes, and what build 002 called the
# normalized copy. Both names are in verify_build's SPEC/EXCLUDED, which
# is why they are asserted against it below rather than typed twice.
HEIGHT_SOURCE = "Snow_Out.png"
HEIGHT_OUTPUT = "AlpineLab_v1_Height_normalized.png"

# The SAME BYTES under a name UE 5.8's landscape import dialog will not
# pattern-match as a tiled image. Both are written: the canonical name
# is the provenance record every script and recipe refers to, the alias
# is the file a human hands to the dialog. Declared in verify_build's
# ALIASES and asserted against it in preflight.
HEIGHT_IMPORT_ALIAS = "AlpineLabHeight.png"

# UE's 16-bit landscape height range spans this many metres at Z = 100.
UE_HEIGHT_SPAN_M_AT_Z100 = 512.0

DISK_FLOOR_GB = 5.0
BUILD_TIMEOUT_S = 3600


def _safe(text):
    """Make third-party console output printable on THIS console.

    Fixing the subprocess DECODE was only half of it. Gaea's Swarm emits
    private-use glyphs (measured: U+E055, a Nerd-Font-style icon), and
    Python's stdout here is cp1252, so `print()` itself raised
    UnicodeEncodeError and took the whole run down with a traceback --
    AFTER the build had already failed, replacing Gaea's explanation with
    a Python one.

    The error path has to survive end to end: decode, then encode. A
    diagnostic that cannot render the message it went to the trouble of
    capturing has not reported anything (non-negotiable 6).
    """
    enc = (getattr(sys.stdout, "encoding", None) or "utf-8")
    return text.encode(enc, errors="replace").decode(enc, errors="replace")


def _fail(msg, code=2):
    print("REFUSE: {0}".format(msg))
    raise SystemExit(code)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# =====================================================================
# THE ONE DEFINITION OF THE VERTICAL SCALE
# =====================================================================

def derive_z_scale(vmin, vmax, project_height_m):
    """UE Z scale for a height that occupied vmin..vmax of 65535.

    THE SINGLE DEFINITION (non-negotiable 19 -- a physical fact is
    defined once). R-GAEA section 6 quotes this arithmetic and
    ue5_import_alpinelab.py carries the ADOPTED result for the adopted
    build; neither re-derives it.

    Returns (z_scale, span_m, occupancy) or (None, None, occupancy) when
    the project range is unknown -- an unknown Z is reported as unknown,
    never defaulted to 100.
    """
    occupancy = (vmax - vmin) / 65535.0
    if project_height_m is None:
        return None, None, occupancy
    span_m = project_height_m * occupancy
    return span_m / UE_HEIGHT_SPAN_M_AT_Z100 * 100.0, span_m, occupancy


def read_project_height_m(project):
    """Gaea's declared full elevation range in metres, or None.

    The .terrain file is JSON. The value is a numeric Terrain/Height
    somewhere under the document; this walks the whole tree for it and
    refuses if more than one distinct value is found. Returns None rather
    than a guess
    if the shape is not what this expects -- non-negotiable 6, a failed
    read reports that it failed.
    """
    try:
        with open(project, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception as exc:
        print("  project height : COULD NOT READ ({0}: {1})"
              .format(type(exc).__name__, exc))
        return None

    found = []

    def walk(node):
        if isinstance(node, dict):
            terr = node.get("Terrain")
            if isinstance(terr, dict) and isinstance(
                    terr.get("Height"), (int, float)):
                found.append(float(terr["Height"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    uniq = sorted(set(found))
    if not uniq:
        print("  project height : NOT PRESENT in the .terrain")
        return None
    if len(uniq) > 1:
        print("  project height : AMBIGUOUS -- {0} different values {1}. "
              "Not guessing.".format(len(uniq), uniq))
        return None
    return uniq[0]


# =====================================================================
# PREFLIGHT -- everything that can refuse, refuses BEFORE the build runs
# =====================================================================

def next_build_dir(root):
    """Next 3-digit folder after the highest used, as (number, path)."""
    used = []
    for name in os.listdir(root):
        if len(name) == 3 and name.isdigit() and \
                os.path.isdir(os.path.join(root, name)):
            used.append(int(name))
    nxt = (max(used) + 1) if used else 1
    return nxt, os.path.join(root, "{0:03d}".format(nxt))


def preflight(args):
    print("=" * 66)
    print("REBUILD PREFLIGHT")
    print("=" * 66)

    if not os.path.isfile(SWARM):
        _fail("Gaea Build Swarm not found at {0}. Gaea 2.3 must be "
              "installed on this machine.".format(SWARM))
    print("  swarm          : {0}".format(SWARM))

    bm = os.path.join(GAEA_DIR, "Gaea.BuildManager.dll")
    print("  buildmanager   : {0}  (not used either way)"
          .format("present" if os.path.isfile(bm) else
                  "ABSENT -- as expected on Indie"))

    if not os.path.isfile(args.project):
        print("  project        : MISSING -- {0}".format(args.project))
        _hint_autosaves()
        _fail("no saved .terrain project to build. An autosave is a "
              "DERIVED record Gaea rotates and overwrites; building the "
              "canonical terrain from one is how a rebuild silently "
              "stops matching the project. Save the project in Gaea "
              "(File > Save As) to the path above, or pass --project "
              "explicitly if you accept an autosave.")
    print("  project        : {0}  ({1:,} bytes)"
          .format(args.project, os.path.getsize(args.project)))

    if not os.path.isdir(args.root):
        _fail("build root does not exist: {0}".format(args.root))

    free_gb = shutil.disk_usage(args.root).free / (1024.0 ** 3)
    print("  free disk      : {0:.1f} GB (floor {1:.1f})"
          .format(free_gb, DISK_FLOOR_GB))
    if free_gb < DISK_FLOOR_GB:
        _fail("below the disk floor; a half-written build is worse than "
              "no build", 3)

    number, build_dir = next_build_dir(args.root)
    if os.path.exists(build_dir) and os.listdir(build_dir):
        _fail("{0} already exists and is not empty. This script never "
              "overwrites a build.".format(build_dir))
    print("  next build     : {0:03d}  ->  {1}".format(number, build_dir))

    height_m = read_project_height_m(args.project)
    if height_m is not None:
        print("  project height : {0:.1f} m (full range, NOT this build's "
              "span)".format(height_m))

    # HEIGHT_SOURCE and HEIGHT_OUTPUT are not typed twice. If verify_build's
    # contract moves, this refuses instead of normalizing into a name
    # nothing downstream reads (non-negotiable 24).
    if HEIGHT_SOURCE not in verify_build.EXCLUDED:
        _fail("verify_build.EXCLUDED no longer lists {0}. The contract "
              "moved; fix both together.".format(HEIGHT_SOURCE))
    if HEIGHT_OUTPUT not in verify_build.SPEC:
        _fail("verify_build.SPEC no longer declares {0}. The contract "
              "moved; fix both together.".format(HEIGHT_OUTPUT))
    if verify_build.ALIASES.get(HEIGHT_IMPORT_ALIAS) != HEIGHT_OUTPUT:
        _fail("verify_build.ALIASES does not map {0} -> {1}. The import "
              "alias is the file the editor opens; it is not allowed to "
              "be defined in two places that disagree."
              .format(HEIGHT_IMPORT_ALIAS, HEIGHT_OUTPUT))
    hits = verify_build.tiled_prompt_tokens(HEIGHT_IMPORT_ALIAS)
    if hits:
        _fail("the import alias {0} itself matches UE's tiled-image "
              "tokens {1}. Pick a name with no u/v/x/y followed by "
              "digits.".format(HEIGHT_IMPORT_ALIAS, hits))
    print("  contract       : source/output/alias names agree with "
          "verify_build")

    return build_dir, height_m


def _hint_autosaves():
    auto = os.path.join(os.environ.get("APPDATA", ""), "QuadSpinner",
                        "Gaea", "2.0", "Autosaves")
    if not os.path.isdir(auto):
        return
    cands = sorted(n for n in os.listdir(auto)
                   if n.lower().endswith(".terrain")
                   and n.lower().startswith("alpinelab"))
    if cands:
        print("  newest autosave: {0}".format(
            os.path.join(auto, cands[-1])))


# =====================================================================
# BUILD
# =====================================================================

def run_build(args, build_dir):
    cmd = [SWARM,
           "--Filename", args.project,
           "--buildpath", build_dir,
           "--resolution", str(args.resolution),
           "--silent"]
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    if args.ignore_cache:
        cmd += ["--ignorecache"]

    print("")
    print("COMMAND:")
    print("  " + " ".join('"{0}"'.format(c) if " " in c else c
                          for c in cmd))

    if not args.go:
        print("")
        print("DRY RUN -- nothing was built. Re-run with --go.")
        return None

    os.makedirs(build_dir, exist_ok=True)
    print("")
    print("building at {0}x{0} -- this takes minutes, and Swarm prints "
          "little until it finishes".format(args.resolution))
    # THE TIMEOUT SCALES WITH THE WORK, AND IT FAILS CLEANLY.
    #
    # BUILD_TIMEOUT_S (3600) was chosen for a 4096 build. Pixel count goes
    # as resolution^2, so an 8192 build is FOUR TIMES the work and would
    # very plausibly cross an hour -- on a script whose Gaea subprocess
    # call has NEVER EXECUTED. A backstop that trips on the first real run
    # would kill Gaea mid-build and leave a partial build directory that
    # looks like a finished one.
    #
    # And an uncaught TimeoutExpired exits 1 with a traceback, which this
    # script's own docstring contract does not have a 1 for -- so the
    # failure would arrive as a Python error rather than a refusal that
    # tells the operator what to clean up.
    timeout_s = args.build_timeout
    if timeout_s is None:
        timeout_s = int(BUILD_TIMEOUT_S * (float(args.resolution) / 4096.0) ** 2)
    print("timeout      : {0} s ({1:.1f} h)".format(timeout_s,
                                                    timeout_s / 3600.0))
    # ======================================================================
    # GAEA GETS A REAL CONSOLE, AND CAPTURING ITS OUTPUT IS WHAT BROKE IT.
    # ======================================================================
    #
    # THE MEASURED CAUSE, and it is not what any of the symptoms suggested.
    # Run with `capture_output=True` -- i.e. stdout/stderr on PIPES -- Gaea
    # Swarm dies 1.3 s in, immediately after "Opening ...terrain":
    #
    #   Unhandled exception. System.IO.IOException: The handle is invalid.
    #      at QuadSpinner.Gaea.Swarm.Program...
    #   exit 3762504530  (0xE0434352 = CLR unhandled managed exception)
    #
    # "The handle is invalid" is the .NET signature of a Console.* call
    # against a redirected handle. Swarm manipulates the console when it
    # starts a build; with a pipe there is no console to manipulate.
    #
    # PROVEN, not inferred: the IDENTICAL command launched with its own
    # console window sailed past the crash point and kept building, where
    # the piped version had died at 1.3 s every time.
    #
    # WHY THIS MATTERED SO MUCH: it is why this script's build call had
    # "NEVER RUN" successfully. The failure was in the HARNESS, and it
    # looked exactly like a Gaea or licence limitation -- the temptation
    # was to conclude that 8192 exceeded the Indie cap, which would have
    # been a wrong and expensive conclusion about a feature that works.
    #
    # THE COST OF THE FIX, stated because it is a real loss: with a
    # detached console we CANNOT capture Gaea's output. So the build is
    # verified from the ARTEFACT -- which is what `verify_build.py` does
    # and what this project's doctrine requires anyway -- and this
    # function reports that the output was not captured rather than
    # printing an empty string and letting it read as "Gaea said nothing".
    CREATE_NEW_CONSOLE = 0x00000010
    started = time.time()
    try:
        proc = subprocess.run(cmd, timeout=timeout_s,
                              creationflags=CREATE_NEW_CONSOLE)
    except subprocess.TimeoutExpired:
        elapsed = time.time() - started
        _fail(
            "Gaea did not finish within {0} s ({1:.1f} h) and was KILLED. "
            "The build directory {2} is PARTIAL and must be deleted before "
            "retrying -- a half-written build has the right filenames and "
            "the wrong contents, which verify_build would then be asked to "
            "adjudicate. Re-run with a larger --build-timeout, or check "
            "whether Gaea is actually progressing before assuming it is "
            "slow.".format(timeout_s, elapsed / 3600.0, build_dir), 5)
    elapsed = time.time() - started
    # Gaea ran in its own console, so there is nothing on these pipes.
    # SAY THAT, rather than printing an empty string that reads as
    # "Gaea produced no output" -- the distinction between "it said
    # nothing" and "we did not listen" is the whole of non-negotiable 6.
    out = (proc.stdout or "") + (proc.stderr or "")
    if out.strip():
        print(_safe(out.strip()[-4000:]))
    else:
        print("  (Gaea ran in its own console; its output was NOT captured "
              "-- see the comment above. The build is adjudicated from the "
              "ARTEFACT by verify_build, not from a transcript.)")
    print("swarm exit {0} after {1:.1f} s".format(proc.returncode, elapsed))
    if proc.returncode != 0:
        # NAME THE EXIT CODE. 3762504530 is 0xE0434352, the CLR's
        # "unhandled managed exception" code -- i.e. Gaea itself threw,
        # rather than exiting with a status it chose. A reader who does
        # not know that spends the next hour looking for a Gaea error
        # code that does not exist.
        hexcode = "0x{0:08X}".format(proc.returncode & 0xFFFFFFFF)
        note = ""
        if (proc.returncode & 0xFFFFFFFF) == 0xE0434352:
            note = (" That is the .NET CLR's UNHANDLED MANAGED EXCEPTION "
                    "code, so Gaea crashed rather than refusing: the cause "
                    "is in the output above, or Gaea wrote nothing because "
                    "it died before it could.")
        _fail("Gaea build failed, exit {0} ({1}).{2} Nothing downstream "
              "ran, and the build directory is empty or partial."
              .format(proc.returncode, hexcode, note), 4)
    return build_dir


def locate_outputs(build_dir):
    """Where did Gaea actually put the PNGs?

    NOT assumed. Swarm's layout under --buildpath is its business and it
    is free to nest by project name; this walks the tree and reports the
    directory that holds the height source. An empty result is reported
    as empty, never silently treated as 'somewhere else'.
    """
    hits = []
    for dirpath, _dirnames, filenames in os.walk(build_dir):
        if HEIGHT_SOURCE in filenames:
            hits.append(dirpath)
    if not hits:
        pngs = sum(1 for _d, _n, f in os.walk(build_dir)
                   for x in f if x.lower().endswith(".png"))
        _fail("build produced no {0} anywhere under {1} ({2} PNGs found). "
              "Either the graph's Snow node was renamed or the build did "
              "not write. Look before re-running."
              .format(HEIGHT_SOURCE, build_dir, pngs), 5)
    if len(hits) > 1:
        _fail("{0} appears in {1} directories under {2}: {3}. Ambiguous -- "
              "not guessing which build is the build."
              .format(HEIGHT_SOURCE, len(hits), build_dir, hits), 5)
    return hits[0]


# =====================================================================
# NORMALIZE -- and record what the stretch destroys
# =====================================================================

def normalize_height(out_dir, project_height_m):
    from PIL import Image

    src = os.path.join(out_dir, HEIGHT_SOURCE)
    dst = os.path.join(out_dir, HEIGHT_OUTPUT)

    im = Image.open(src)
    if im.mode != "I;16":
        _fail("{0} is mode {1}, not 16-bit greyscale. Normalizing an 8-bit "
              "height would quantise the terrain to 256 levels."
              .format(HEIGHT_SOURCE, im.mode), 6)
    a = np.asarray(im).astype(np.float64)
    vmin, vmax = float(a.min()), float(a.max())

    print("")
    print("=" * 66)
    print("NORMALIZATION")
    print("=" * 66)
    print("  source         : {0}  {1}x{2}".format(
        HEIGHT_SOURCE, im.size[0], im.size[1]))
    print("  source range   : {0:.0f} - {1:.0f} of 65535".format(vmin, vmax))

    if vmax <= vmin:
        _fail("source height is FLAT ({0:.0f} everywhere). A stretch would "
              "divide by zero and a flat heightmap is not a terrain."
              .format(vmin), 6)

    scaled = (a - vmin) * (65535.0 / (vmax - vmin))
    out = np.clip(np.rint(scaled), 0, 65535).astype(np.uint16)
    mat.write_png16_grey(dst, out)

    # POST-OPERATION ASSERTION on the file, not on the array in hand.
    # A check that reads the value it just computed verifies nothing
    # (non-negotiable 5), so this re-decodes the PNG from disk.
    back = np.asarray(Image.open(dst)).astype(np.float64)
    if back.shape != a.shape:
        _fail("normalized file is {0}, source was {1}".format(
            back.shape, a.shape), 6)
    if back.min() != 0.0 or back.max() != 65535.0:
        _fail("normalized file spans {0:.0f}-{1:.0f}, not 0-65535. The "
              "stretch did not land.".format(back.min(), back.max()), 6)
    print("  written        : {0}".format(HEIGHT_OUTPUT))
    print("  read back      : 0 - 65535 over {0} pixels, {1:,} unique"
          .format(back.size, int(np.unique(back).size)))

    # THE IMPORT ALIAS. Same bytes, a name the landscape dialog will not
    # offer to load as a tiled image. Copied rather than re-encoded, and
    # hashed, because a second write of the same array is a second
    # chance to write it differently (non-negotiable 20).
    alias = os.path.join(out_dir, HEIGHT_IMPORT_ALIAS)
    shutil.copy2(dst, alias)
    a_hash, c_hash = _sha256(alias), _sha256(dst)
    if a_hash != c_hash:
        _fail("the import alias did not copy byte-identically", 6)
    print("  import alias   : {0}  byte-identical, sha256 {1}..."
          .format(HEIGHT_IMPORT_ALIAS, a_hash[:16]))
    print("                   (the canonical name contains {0}, which "
          "makes the editor offer a TILED import that creates no "
          "landscape)".format(
              ", ".join(verify_build.tiled_prompt_tokens(HEIGHT_OUTPUT))
              or "no tiled token"))

    z, span_m, occupancy = derive_z_scale(vmin, vmax, project_height_m)
    print("  occupancy      : {0:.5f} of the 16-bit range".format(occupancy))
    if z is None:
        print("  UE Z SCALE     : UNKNOWN -- the project's elevation range "
              "could not be read. Do NOT default it to 100; see R-GAEA 6.")
    else:
        print("  span           : {0:.2f} m".format(span_m))
        print("  UE Z SCALE     : {0:.2f}   <- set this in the import dialog"
              .format(z))

    sidecar = {
        "generated_by": "scripts/rebuild_terrain.py",
        "import_alias": HEIGHT_IMPORT_ALIAS,
        "import_alias_sha256": a_hash,
        "source_file": HEIGHT_SOURCE,
        "source_sha256": _sha256(src),
        "source_min": vmin,
        "source_max": vmax,
        "output_file": HEIGHT_OUTPUT,
        "output_sha256": _sha256(dst),
        "occupancy": occupancy,
        "project_height_m": project_height_m,
        "span_m": span_m,
        "ue_z_scale": z,
        "z_scale_provenance": (
            "measured -- Gaea Terrain/Height {0} m x occupancy {1:.5f} "
            "= {2} m span, / {3} * 100".format(
                project_height_m, occupancy, span_m,
                UE_HEIGHT_SPAN_M_AT_Z100)
            if z is not None else
            "UNKNOWN -- project elevation range unreadable"),
        "note": ("The stretch to full range destroys the source range. "
                 "It is recorded here because the UE Z scale is derived "
                 "from it and from nothing else."),
    }
    path = os.path.join(out_dir, "height_normalization.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh, indent=2)
    print("  sidecar        : {0}".format(os.path.basename(path)))
    return z


# =====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=DEFAULT_PROJECT,
                    help="the .terrain to build")
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help="parent of the NNN build folders")
    ap.add_argument("--resolution", default=4096, type=int)
    ap.add_argument("--build-timeout", default=None, type=int,
                    help="seconds to allow the Gaea build. Default scales "
                         "as (resolution/4096)^2 from the 3600 s that was "
                         "chosen for a 4096 build, so 8192 gets 4 hours. A "
                         "trip KILLS Gaea and leaves a PARTIAL build "
                         "directory, so this is a backstop, not a schedule.")
    ap.add_argument("--seed", default=None, type=int)
    ap.add_argument("--ignore-cache", action="store_true")
    ap.add_argument("--go", action="store_true",
                    help="actually build. Without it this is a dry run.")
    args = ap.parse_args(argv)

    build_dir, height_m = preflight(args)
    built = run_build(args, build_dir)
    if built is None:
        print("")
        print("Preflight passed. Nothing was written.")
        return 0

    out_dir = locate_outputs(built)
    if os.path.abspath(out_dir) != os.path.abspath(built):
        print("")
        print("NOTE: Gaea nested its output at {0}".format(out_dir))

    z = normalize_height(out_dir, height_m)

    print("")
    print("=" * 66)
    print("VERIFY")
    print("=" * 66)
    rc = subprocess.call(
        [sys.executable,
         os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "verify_build.py"),
         "--build", out_dir,
         "--expect-size", "{0}x{0}".format(args.resolution)])
    print("")
    print("verify_build exit {0}".format(rc))
    if rc != 0:
        print("THE BUILD IS NOT ACCEPTED. Read the refusal above; do not "
              "resize or import it.")
        return rc

    # THE RESIZE TARGET IS DERIVED, NEVER TYPED.
    #
    # This printed "--expect-size 4033x4033" unconditionally, which was
    # correct for the only resolution ever built (4096) and became a TRAP
    # the moment an 8192 build existed: following it verbatim resizes an
    # 8192 build down to 4033, THROWING AWAY THE ENTIRE POINT OF THE
    # BUILD -- and every check downstream passes, because 4033 is a
    # perfectly legitimate landscape size. A wrong instruction that
    # succeeds is worse than one that fails.
    #
    # The rule, from resize_gaea_build's own docstring (4033 = 63 x 64 + 1,
    # "64 components of 63 quads"): quads = resolution/64 - 1, and the
    # vertex target is quads * 64 + 1. That gives 4096 -> 4033 and
    # 8192 -> 8129, and 8129 is also 254 x 32 + 1, which is the
    # 32-component layout the 1 m/vertex migration keeps.
    quads = args.resolution // 64 - 1
    target = quads * 64 + 1
    print("")
    print("BUILD ACCEPTED. Next, by hand:")
    print("  resize target {0} = {1} quads x 64 + 1  (derived from "
          "resolution {2})".format(target, quads, args.resolution))
    print("  python scripts/resize_gaea_build.py --build {0} --size {1} "
          "--archive-excluded".format(out_dir, target))
    print("  python scripts/verify_build.py --build {0}\\UE5_Ready "
          "--expect-size {1}x{1}".format(out_dir, target))
    if z is not None:
        print("  then import with Z scale {0:.2f} -- and if you ADOPT this "
              "build, update Z_SCALE in scripts/ue5_import_alpinelab.py "
              "to match, citing height_normalization.json.".format(z))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
