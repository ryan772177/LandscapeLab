"""check_weightmap_fresh.py — is the ENGINE's weightmap older than its source?

    python scripts/check_weightmap_fresh.py
    python scripts/check_weightmap_fresh.py --selftest

RULED 2026-09-12b, hygiene (b). A PRE-CAPTURE gate: REFUSE if the
imported texture asset is older than the source PNG on disk.

⛔ WHY. On 2026-09-12 the engine was found sampling `T_Alpine_8k_Weights`
DATED 14 AUGUST while `textures/alpine_8k_weights.png` had been
regenerated the same day. A month-stale weightmap fed every render and
every acceptance in between -- including the shadow_tint baseline of
1.1243 that a ruled band was built on.

**NO AUDIT COULD SEE IT.** `audit_material_samplers` proves the graph
samples the right ASSET; `audit_material_connectivity` proves the node is
reachable. Both are properties of the GRAPH, not of the PIXELS, and both
passed. It took a render, an eye, and a file timestamp.

That is standing rule 12's other half: a parameter read back from the
graph proves the SETTER ran, not that the DATA is current.

WHAT IT COMPARES. The `.uasset` file's mtime against the source PNG's
mtime. Not import metadata -- the uasset IS the artefact the engine
loads, and its mtime is the last time an import actually wrote it.

FAIL DIRECTION. Refuses CLOSED: a stale weightmap produces a plausible
frame that passes every tonal check, so the expensive failure is running
with it, not stopping.

Exit codes:
  0  every declared map is at least as new as its source
  1  bad arguments / recipe unreadable
  3  a map is STALE, or its asset is missing
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import landscape_spec  # noqa: E402

UE_CONTENT = os.path.join(REPO, "LandscapeLab", "Content")


def _uasset_path(game_path):
    """/Game/Textures/T_X -> LandscapeLab/Content/Textures/T_X.uasset"""
    if not game_path.startswith("/Game/"):
        return None
    return os.path.join(UE_CONTENT, *game_path[len("/Game/"):].split("/")) \
        + ".uasset"


def rows_for(recipe, recipe_path):
    """[(label, source_abs, asset_abs)] for every global map declared."""
    biome = recipe["biome_id"]
    mat = recipe.get("material") or {}
    out = []

    # weightmap and variant_map name their source PATH in the recipe.
    for key, fn in (("weightmap", landscape_spec.weightmap_asset_path),
                    ("variant_map", landscape_spec.variant_map_asset_path)):
        rel = mat.get(key)
        if rel:
            out.append((key, os.path.join(REPO, rel),
                        _uasset_path(fn(biome))))

    # MACRO IS DIFFERENT and the first draft missed it: `macro_variation`
    # declares PARAMETERS (seed, resolution, feature_scale_m, strength,
    # chroma_ratio) and no path -- the source is CONVENTIONAL, the same
    # name import_layer_textures reports as `_macromap
    # textures/<biome>_macro.png`. A gate that silently covers one map of
    # two is worse than none, because it reports "fresh" over an
    # unchecked asset.
    if mat.get("macro_variation"):
        out.append(("macro",
                    os.path.join(REPO, "textures", "%s_macro.png" % biome),
                    _uasset_path(landscape_spec.macro_map_asset_path(biome))))
    return out


def check(recipe_path):
    with open(recipe_path, encoding="utf-8") as fh:
        recipe = json.load(fh)
    bad = []
    print("%-12s %-22s %-22s %s"
          % ("map", "source mtime", "asset mtime", "verdict"))
    for label, src, asset in rows_for(recipe, recipe_path):
        if not os.path.exists(src):
            print("%-12s %-22s %-22s %s"
                  % (label, "MISSING", "-", "REFUSE"))
            bad.append("%s: source missing at %s" % (label, src))
            continue
        if asset is None or not os.path.exists(asset):
            print("%-12s %-22s %-22s %s"
                  % (label, "ok", "NOT IMPORTED", "REFUSE"))
            bad.append("%s: no imported asset at %s" % (label, asset))
            continue
        s, a = os.path.getmtime(src), os.path.getmtime(asset)
        stale = a < s
        print("%-12s %-22s %-22s %s"
              % (label,
                 _fmt(s), _fmt(a),
                 "STALE by %.1f h" % ((s - a) / 3600.0) if stale else "fresh"))
        if stale:
            bad.append("%s: asset is %.1f h older than its source"
                       % (label, (s - a) / 3600.0))
    return bad


def _fmt(t):
    import datetime
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def selftest():
    """THREE DIRECTIONS on the comparison itself, with no editor."""
    import tempfile
    import time
    fails = []
    d = tempfile.mkdtemp()
    src = os.path.join(d, "src.png")
    ast = os.path.join(d, "a.uasset")

    open(ast, "w").close()
    time.sleep(0.05)
    open(src, "w").close()           # source NEWER -> stale asset
    stale = os.path.getmtime(ast) < os.path.getmtime(src)
    print("  source newer than asset      -> stale=%s %s"
          % (stale, "OK" if stale else "WRONG"))
    if not stale:
        fails.append("a newer source did not read as stale")

    time.sleep(0.05)
    open(ast, "w").close()           # asset now NEWER -> fresh
    fresh = os.path.getmtime(ast) >= os.path.getmtime(src)
    print("  asset newer than source      -> fresh=%s %s"
          % (fresh, "OK" if fresh else "WRONG"))
    if not fresh:
        fails.append("a newer asset did not read as fresh")

    missing = not os.path.exists(os.path.join(d, "nope.uasset"))
    print("  missing asset                -> refuse=%s %s"
          % (missing, "OK" if missing else "WRONG"))
    if not missing:
        fails.append("a missing asset was not detected")

    for p in (src, ast):
        os.unlink(p)
    os.rmdir(d)
    if fails:
        print("\nSELFTEST FAIL")
        for f in fails:
            print("  - %s" % f)
        return 1
    print("\nSELFTEST PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=os.path.join(
        REPO, "recipes", "alpine_8k.json"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    bad = check(a.recipe)
    if bad:
        print("")
        print("⛔ REFUSE -- a capture against a stale map measures a world")
        print("nobody declared, and it looks completely plausible:")
        for b in bad:
            print("   %s" % b)
        print("Re-run import_layer_textures before capturing.")
        return 3
    print("\nevery declared map is at least as new as its source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
