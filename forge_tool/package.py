"""Assemble the standalone forge distribution.

Produces dist/forge-<version>/ mirroring the sibling layout every script
derives its REPO_ROOT from, so the vendored scripts run UNMODIFIED:

    scripts/       byte-identical copies, each sha256-pinned in
                   forge_tool/vendor_manifest.json (the drift gate)
    forge_tool/    this package
    recipes/       forge stamp catalogue (+ schema doc)
    terrain/       forge_stamps/ + the curated CC0 heightmaps
    textures/      the operator-owned layer textures the recipes name
    examples/      a gated example layout + its concept image
    forge_runs/, captures/  created empty
    README.md, requirements.txt

The emitted UE project is NOT packaged — the user creates it in place
with `python -m forge_tool.cli init --dest <dist-root> --compile`
(compiling requires their UE 5.8 install; shipping engine-patch-locked
binaries would be a lie about their machine).

LICENCE GATE: refuses if ANY packaged file's hash appears in
stampit_catalogue.json (Fab content, UE-projects-only licence). Identity
is the content hash, same rule the compositor enforces.

Usage: python -m forge_tool.package [--version 0.1.0]
Exit: 0 packaged, 2 refusal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# scripts/ subtrees that are NOT part of the landscape path and carry
# hero/character machinery the forge does not ship
_SKIP_SCRIPT_DIRS = {"hero_face", "hero_body", "blender", "__pycache__"}

TEXTURES = ["spike_grass.png", "spike_rock.png", "spike_scree.png",
            "spike_forest.png", "spike_dirt.png", "spike_gravel.png"]

EXAMPLE_IMAGE = os.path.join("Free", "gemini_v2",
                             "concept_highland_dusk.jpg")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return sha256_file(dst)


def package(version):
    dist = os.path.join(REPO, "dist", "forge-%s" % version)
    if os.path.exists(dist):
        print("REFUSE: %s already exists — bump the version or move the "
              "old dist to _trash/" % dist)
        return 2

    fab_hashes = {m["hash"] for m in json.load(open(
        os.path.join(REPO, "terrain", "stampit_catalogue.json"),
        encoding="utf-8"))["maps"]}

    manifest = {}

    def vendor(rel_src, rel_dst=None):
        rel_dst = rel_dst or rel_src
        # audit Q1: a catalogue-supplied relpath must stay relative and
        # inside the tree — never a path escape
        for rp in (rel_src, rel_dst):
            if os.path.isabs(rp) or ".." in rp.replace("\\", "/").split("/"):
                raise RuntimeError("unsafe relpath: %r" % rp)
        src = os.path.join(REPO, rel_src)
        if not os.path.isfile(src):
            raise RuntimeError("missing source: %s (a dist without it "
                               "fails on the END USER'S machine)" % rel_src)
        # audit F1: licence gate on the SOURCE hash, BEFORE the copy —
        # gating the destination would mean the contraband is already in
        # the dist when the refusal fires
        h = sha256_file(src)
        if h in fab_hashes:
            raise RuntimeError("LICENCE: %s is Fab content by hash"
                               % rel_src)
        if _copy(src, os.path.join(dist, rel_dst)) != h:
            raise RuntimeError("copy of %s does not hash-match its source"
                               % rel_src)
        manifest[rel_dst.replace("\\", "/")] = h

    # scripts/: every .py and payload .txt outside the skip set.
    # _compose_iter is excluded: an authoring scratch harness that reads
    # the non-shipped stampit catalogue at module load (audit Q2).
    for entry in sorted(os.listdir(os.path.join(REPO, "scripts"))):
        full = os.path.join(REPO, "scripts", entry)
        if os.path.isdir(full):
            continue  # subdirs are hero/blender tooling — skipped
        if entry == "_compose_iter.py":
            continue
        if not (entry.endswith(".py") or entry.endswith(".txt")
                or entry.endswith(".ps1")):
            continue
        vendor(os.path.join("scripts", entry))

    # forge_tool/ itself
    for entry in sorted(os.listdir(os.path.join(REPO, "forge_tool"))):
        if entry.endswith(".py"):
            vendor(os.path.join("forge_tool", entry))

    # recipes: the shippable catalogue + the schema contract (vendor()
    # itself refuses if missing — no silent skips, audit F3)
    vendor(os.path.join("recipes", "forge_stamps_catalogue.json"))
    vendor(os.path.join("recipes", "schema.md"))
    # pivot-normalization report: the schema validator proves each
    # foliage species' pivot against it (measured on the dist T0 run:
    # absent report = schema refusal). Our own measurement data, 17 KB.
    vendor(os.path.join("Free", "_measured", "normalized.json"))

    # stamps: exactly what the catalogue names (the catalogue IS the
    # inventory — packaging anything else would ship unaudited content)
    cat = json.load(open(os.path.join(
        REPO, "recipes", "forge_stamps_catalogue.json"), encoding="utf-8"))
    for m in cat["maps"]:
        vendor(m["relpath"])
        if sha256_file(os.path.join(dist, m["relpath"])) != m["hash"]:
            raise RuntimeError("catalogue hash mismatch on %s"
                               % m["relpath"])

    # layer textures
    for t in TEXTURES:
        p = os.path.join(REPO, "textures", t)
        if os.path.isfile(p):
            vendor(os.path.join("textures", t))

    # example: concept image (operator-owned Gemini output) + a GATED
    # layout so the keyless path in the README actually works (audit F2:
    # the CLI requires lighting_measured/source_image, which this
    # carries; its source_image points at the vendored image)
    vendor(EXAMPLE_IMAGE, os.path.join("examples",
                                       "concept_highland_dusk.jpg"))
    vendor(os.path.join("examples", "duskhighland_layout.json"))
    # the visual authoring UI (operator-built, three.js, single file)
    # and the digest that fills its stamp list with the REAL catalogue.
    # DRIFT GATE on the SOURCE before the copy: the page carries the
    # catalogue baked in (export_digest --inject); shipping a page
    # missing a stamp would hand the keyless user a stale palette.
    ui_src = os.path.join(REPO, "examples", "forge_layout_author.html")
    html = open(ui_src, encoding="utf-8").read()
    missing = [m["tag"] for m in cat["maps"]
               if json.dumps(m["tag"]) not in html]
    if missing:
        raise RuntimeError(
            "Layout Author page lacks catalogue stamps %s — re-run "
            "python -m forge_tool.export_digest --inject %s"
            % (missing, ui_src))
    vendor(os.path.join("examples", "forge_layout_author.html"))
    # the digest is the page's OTHER stamp door (a user can load it,
    # REPLACING the baked-in list) — gate it against the live catalogue
    # too, or a stale file ships a stale palette (audit F3). Both
    # artefacts regenerate together via export_digest.
    from forge_tool import export_digest
    dig_path = os.path.join(REPO, "examples", "forge_stamp_digest.json")
    shipped = json.load(open(dig_path, encoding="utf-8"))["stamps"]
    if shipped != export_digest.build_digest():
        raise RuntimeError("forge_stamp_digest.json is stale vs the "
                           "catalogue — re-run python -m "
                           "forge_tool.export_digest --inject "
                           "examples/forge_layout_author.html")
    vendor(os.path.join("examples", "forge_stamp_digest.json"))
    # launcher at the dist ROOT
    vendor(os.path.join("forge_tool", "forge.bat"), "forge.bat")

    for d in ("forge_runs", "captures", os.path.join("terrain", "aux")):
        os.makedirs(os.path.join(dist, d), exist_ok=True)

    # PRE-EMIT the UE project skeleton (audit of the first packaged
    # init: the emitter reads the DEV project's sources, which a dist
    # does not carry — so emission happens HERE, where they exist; the
    # user's `init --compile` only compiles). Emitted files join the
    # manifest like everything else.
    from forge_tool import emit_project
    proj = emit_project.emit(dist)
    for root, _dirs, files in os.walk(proj):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, dist)
            h = sha256_file(full)
            if h in fab_hashes:
                raise RuntimeError("LICENCE: emitted %s is Fab content "
                                   "by hash" % rel)
            manifest[rel.replace("\\", "/")] = h

    with open(os.path.join(dist, "forge_tool", "vendor_manifest.json"),
              "w", encoding="utf-8") as f:
        json.dump({"version": version, "files": manifest}, f, indent=1,
                  sort_keys=True)

    with open(os.path.join(dist, "requirements.txt"), "w",
              encoding="utf-8") as f:
        f.write("numpy\nPillow\nscipy\n"
                "# optional - only the experimental auto-read needs it:\n"
                "anthropic\n")

    with open(os.path.join(dist, "README.md"), "w", encoding="utf-8") as f:
        f.write(README % {"v": version})

    print("packaged %s  (%d files, licence gate PASSED)"
          % (dist, len(manifest)))
    return 0


README = """# The Forge %(v)s

One 2D concept image in, an Unreal Engine 5.8 project with a matching
landscape out — terrain, material, water, lighting and a verification
render, built to the image's own measurements.

## Requirements

- Windows 10/11 with **Unreal Engine 5.8** installed
- **Python 3.11+**, then `pip install -r requirements.txt`
- ~10 GB free disk (engine intermediates)

## Setup — two commands

    forge doctor
    forge init --dest . --compile

`doctor` checks this machine and tells you exactly what to fix if
anything is missing. `init` creates the UE project and compiles the
editor plugin (one-time, a few minutes). Run both from this folder;
`forge` is the launcher next to this README (equivalently:
`python -m forge_tool.cli ...`).

## Building a world

**No account, no API key, nothing to sign up for.**

**Easiest — everything in one page:**

    forge serve

Your browser opens the Layout Author with a Forge panel in the corner:
drop the concept image, place stamps until the preview matches, click
**Forge this world**, watch the build log (~25 min), and finish with
the render on screen and a **Download UE project (.zip)** button. The
zip is a complete UE 5.8 project — unzip anywhere, open the .uproject,
walk the world. (The page only talks to this machine: the server binds
127.0.0.1 and refuses cross-site requests.)

**Or the same thing by hand:**

    forge author

Drop your concept image on the page, place terrain stamps on the 3D
preview until it matches the image (the real stamp catalogue is baked
into the page — nothing to load), and Export. Then:

    forge build my_concept.jpg --layout my.layout.json --name myworld

Prefer text? `examples/duskhighland_layout.json` is a complete,
working example of the layout schema — copy it, edit values, build the
same way.

Try it right now with the shipped example:

    forge build examples/concept_highland_dusk.jpg --layout examples/duskhighland_layout.json --name myworld

*Experimental extra (off by default, honestly untested in this build):
with an Anthropic API key set (`ANTHROPIC_API_KEY`), `forge build
my_concept.jpg --name myworld` asks a vision model to author the
layout for you. Its output goes through exactly the same validation
gate as yours. Without a key the command tells you the standard path
and stops before doing any work.*

## What a build does

terrain synthesis from the plan's stamps -> iterative repair until the
plan's own acceptance criteria measure true on the actual heightfield
-> sightline check that the camera can really see its subjects (pure
height problems are fixed automatically from the gate's prescription)
-> landscape + material + water + lighting in the editor -> a render at
the plan's camera -> a fidelity report comparing the render to the
concept (`forge_runs/<name>/fidelity.json`).

The result: `forge_runs/<name>/renders/<name>.png`, and the
`LandscapeLab/` project opens in UE 5.8 with the world loaded and
walkable.

## Polish — closing the lighting gap

    forge polish --name myworld

re-measures render vs concept and converges exposure automatically
(measured slope, up to 3 iterations). Run it whenever the fidelity
report says the render is brighter/darker than the concept.

## When the forge says no

The forge REFUSES rather than shipping a wrong world, and every refusal
prints what to change:

- **"acceptance cannot converge"** — the plan asks for geometry the
  stamps cannot make (e.g. a 20 m flat harbor on a 300 m ridge). Move
  the placement or widen the acceptance band.
- **"camera cannot see its subjects"** — aiming problem (height
  problems are auto-fixed). Move or re-aim the camera in your layout.
- **"no API key set"** — you ran `forge build` with only an image.
  That mode is the experimental extra; the standard path is
  `forge author` then `forge build ... --layout ...`, no key needed.
- **editor already running** — close Unreal first; the build launches
  and closes its own editor.
- Anything environmental — run `forge doctor` again.

## Licences

Stamps and textures are CC0 or operator-owned; the packaging gate
refuses any Fab-licensed content by content hash. Every vendored file
is pinned in `forge_tool/vendor_manifest.json`. Your concept images and
worlds are yours.
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.1.0")
    a = ap.parse_args(argv)
    dist = os.path.join(REPO, "dist", "forge-%s" % a.version)
    try:
        return package(a.version)
    except (RuntimeError, OSError) as e:
        # OSError included so a vanished file mid-copy is a refusal, not
        # a traceback with the wrong exit code (audit F4)
        print("REFUSE: %s" % e)
        # a partial dist must not block the retry NOR sit there looking
        # finished: rename it as refuse debris (audit F1 second half)
        if os.path.isdir(dist) and not os.path.isfile(
                os.path.join(dist, "forge_tool", "vendor_manifest.json")):
            debris = dist + "_REFUSED"
            if not os.path.exists(debris):
                os.rename(dist, debris)
                print("partial dist moved to %s" % debris)
        return 2


if __name__ == "__main__":
    sys.exit(main())
