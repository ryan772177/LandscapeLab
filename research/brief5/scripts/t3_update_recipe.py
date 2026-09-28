#!/usr/bin/env python3
"""Brief 5 T3 -- write asset-true LOD screen sizes into recipes/alpine_8k.json so
recipe == asset for all four tree species (v3 found ConiferPine recipe != asset;
recipe is source of truth, so fix the recipe to the post-hold asset). Adds
`lod_screen_sizes` per tree species and repairs ConiferPine's stale `lods`
screen sizes. Idempotent. Run once from the host after T3 saved the meshes.
"""
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RECIPE = os.path.join(REPO, "recipes", "alpine_8k.json")
PROBE = os.path.join(REPO, "research", "brief5", "input", "tree_lod_probe_t3.json")


def main():
    probe = json.load(open(PROBE, encoding="utf-8"))
    asset = {m["species"]: [round(float(x), 5) for x in (m.get("screen_sizes") or [])]
             for m in probe["meshes"]}
    # read raw to preserve the BOM/encoding the file uses
    with open(RECIPE, "r", encoding="utf-8-sig") as fh:
        r = json.load(fh)
    changed = []
    for s in r["foliage"]["species"]:
        n = s.get("name")
        if n in asset:
            s["lod_screen_sizes"] = asset[n]
            s["_lod_screen_sizes_note"] = (
                "asset-true per-LOD ScreenSize after Brief 5 T3 (card pushed past "
                "the 512 m cull). recipe == asset; checked by "
                "check_recipe_lods.py against tree_lod_probe_t3.json.")
            changed.append(n)
            # repair the stale ConiferPine `lods` screen sizes (v3 mismatch):
            # its 3 entries are LOD1..LOD3 = asset[1:].
            if n == "ConiferPine" and isinstance(s.get("lods"), list):
                a = asset[n]
                for i, lod in enumerate(s["lods"]):
                    if i + 1 < len(a):
                        lod["screen_size"] = a[i + 1]
    with open(RECIPE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(r, fh, indent=1, ensure_ascii=False)
        fh.write("\n")  # match the original trailing newline
    print("recipe lod_screen_sizes set for:", changed)


if __name__ == "__main__":
    main()
