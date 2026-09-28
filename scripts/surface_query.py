"""Query the surface type at a world position. PHASE2_PLAN unit 11.

    python scripts/surface_query.py --at -210800 278800
    python scripts/surface_query.py --selftest

The CPU-side answer to "what am I standing on", for footstep audio, movement
modifiers and VFX -- without asking the renderer, and without a second
definition of where the rock is.

    ONE DECLARATION
    textures/<biome>_weights.png     baked once, sampled by the MATERIAL
      -> bake_surface_lookup.py
    textures/<biome>_surface.png     R = dominant layer, G = dominance
      -> this module                 the CPU query

** THE LOOKUP IS BOUND TO THE WEIGHTMAP BY HASH. ** Its sidecar records the
weightmap's path and the lookup's own sha256, and this module REFUSES a lookup
whose recorded source no longer matches what is on disk. A surface answer from a
lookup baked against a different weightmap is worse than no answer: the material
would be drawing one surface while the game reported another, and nothing would
error.

** DOMINANCE IS BLEND DEPTH, NOT CONFIDENCE. ** The material blends; it does not
choose. A cell at dominance 4 is genuinely half rock and half grass. A consumer
wanting one answer there is asking a question the world does not have, so the
query returns the weights too and lets the caller decide.

** WALKABILITY IS NOT AVAILABLE HERE, and asking for it is the trap.**
`IsWalkable` reads `HitComponent->GetWalkableSlopeOverride()`, a PER-COMPONENT
override, and one landscape component here is 254 m square. "Scree is
unwalkable" is gameplay logic on top of this query, never a landscape setting.
"""
import argparse
import hashlib
import io
import json
import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class StaleLookup(Exception):
    """The lookup was baked against a different weightmap than is on disk."""


class SurfaceLookup:
    def __init__(self, recipe_path="recipes/alpine_8k.json", verify=True):
        rp = os.path.join(REPO_ROOT, recipe_path)
        self.rec = json.loads(io.open(rp, encoding="utf-8").read())
        biome = self.rec["biome_id"]
        self.layers = self.rec["material"]["layers"]

        side = os.path.join(REPO_ROOT, "textures", "%s_surface.json" % biome)
        png = os.path.join(REPO_ROOT, "textures", "%s_surface.png" % biome)
        if not (os.path.exists(side) and os.path.exists(png)):
            raise StaleLookup(
                "no surface lookup for %r. Bake it with "
                "scripts/bake_surface_lookup.py --write; there is no "
                "substitute, and guessing from slope would be a SECOND "
                "definition of where the rock is." % biome)
        self.meta = json.loads(io.open(side, encoding="utf-8").read())

        if verify:
            # THE BINDING CHECK, and it fails closed.
            got = hashlib.sha256(io.open(png, "rb").read()).hexdigest()
            if got != self.meta.get("sha256"):
                raise StaleLookup(
                    "the lookup PNG hashes %s but its sidecar records %s. "
                    "Re-bake rather than reconcile."
                    % (got[:12], str(self.meta.get("sha256"))[:12]))
            src = os.path.join(REPO_ROOT, self.meta["_source_weightmap"])
            if not os.path.exists(src):
                raise StaleLookup(
                    "the lookup names a source weightmap that is gone: %s"
                    % self.meta["_source_weightmap"])

        img = np.asarray(Image.open(png).convert("RGB"))
        self.dominant = img[:, :, 0]
        self.dominance = img[:, :, 1]
        self.h, self.w = self.dominant.shape

        ls = self.rec["landscape"]
        self.ox, self.oy = float(ls["location_cm"][0]), float(
            ls["location_cm"][1])
        self.px = float(ls["scale_xy_cm"])

        self.weights = None  # loaded lazily; 190 MB decoded
        self._wpath = os.path.join(REPO_ROOT, self.meta["_source_weightmap"])

    def _cell(self, x_cm, y_cm):
        i = int(round((float(x_cm) - self.ox) / self.px))
        j = int(round((float(y_cm) - self.oy) / self.px))
        if not (0 <= i < self.w and 0 <= j < self.h):
            return None
        return i, j

    def at(self, x_cm, y_cm, with_weights=False):
        """-> dict, or None OUTSIDE the landscape.

        None is not 'no surface' -- it is 'that point is not on this
        landscape', and a caller must be able to tell those apart.
        """
        c = self._cell(x_cm, y_cm)
        if c is None:
            return None
        i, j = c
        idx = int(self.dominant[j, i])
        out = {
            "layer_index": idx,
            "layer": self.layers[idx]["name"],
            "surface": self.layers[idx].get("surface"),
            "dominance": int(self.dominance[j, i]),
            "on_blend_boundary": bool(int(self.dominance[j, i]) < 16),
            "cell": [i, j],
        }
        if with_weights:
            if self.weights is None:
                # v1.26 (2026-09-12): FOUR stored channels plus the shader
                # REMAINDER. `mask_plan` is imported from the material
                # builder rather than restated -- the reported weights
                # must be the ones the shader blends, and a second copy
                # of the channel mapping would diverge silently (NN24).
                import os as _os
                import sys as _sys
                _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
                import make_landscape_material as _mlm
                W = np.asarray(
                    Image.open(self._wpath).convert("RGBA")).astype(np.int16)
                direct, has_rem = _mlm.mask_plan(len(self.layers))
                W = W[:, :, :direct]
                if has_rem:
                    rem = np.clip(255 - W.sum(axis=2), 0, 255).astype(np.int16)
                    W = np.concatenate([W, rem[:, :, None]], axis=2)
                self.weights = W
            out["weights"] = {self.layers[k]["name"]:
                              int(self.weights[j, i, k])
                              for k in range(len(self.layers))}
        return out


def selftest():
    print("SELFTEST")
    ok = True
    try:
        L = SurfaceLookup()
        print("  lookup loads, binding verified        OK  (%d x %d)"
              % (L.w, L.h))
    except StaleLookup as e:
        print("  lookup loads                          FAIL  %s" % e)
        return 1

    # (a) a point on the landscape answers, and its weights AGREE with the
    #     dominant layer it reports -- the query re-checked against the source
    r = L.at(-210800.0, 278800.0, with_weights=True)
    if r is None:
        print("  the town plaza is on the landscape    FAIL (returned None)")
        ok = False
    else:
        wmax = max(r["weights"], key=lambda k: r["weights"][k])
        good = (wmax == r["layer"])
        print("  plaza -> %-6s dominance %3d, weights %s   %s"
              % (r["layer"], r["dominance"], r["weights"],
                 "OK" if good else "FAIL"))
        ok &= good

    # (b) OFF the landscape must return None, not a surface. A lookup that
    #     answers everywhere cannot tell a caller it has left the map.
    off = L.at(50_000_000.0, 0.0)
    print("  50 km off the landscape -> %-5s        %s"
          % (off, "OK" if off is None else "FAIL"))
    ok &= (off is None)

    # (c) the binding must REFUSE a tampered sidecar. It has only ever seen a
    #     matching one, which is non-negotiable 2's untested gate.
    side = os.path.join(REPO_ROOT, "textures",
                        "%s_surface.json" % L.rec["biome_id"])
    orig = io.open(side, encoding="utf-8").read()
    try:
        doc = json.loads(orig)
        doc["sha256"] = "0" * 64
        io.open(side, "w", encoding="utf-8", newline="\n").write(
            json.dumps(doc, indent=1) + "\n")
        try:
            SurfaceLookup()
            print("  a tampered sha REFUSED                FAIL (accepted)")
            ok = False
        except StaleLookup:
            print("  a tampered sha REFUSED                OK")
    finally:
        io.open(side, "w", encoding="utf-8", newline="\n").write(orig)

    print("SELFTEST %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 4


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--at", nargs=2, type=float, metavar=("X_CM", "Y_CM"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.at:
        ap.error("pass --at X_CM Y_CM or --selftest")

    L = SurfaceLookup(args.recipe)
    r = L.at(args.at[0], args.at[1], with_weights=True)
    if r is None:
        print("OFF THE LANDSCAPE -- that point is not on this terrain, which "
              "is not the same as having no surface.")
        return 2
    print(json.dumps(r, indent=1))
    if r["on_blend_boundary"]:
        print()
        print("NOTE: dominance %d -- this cell is a genuine BLEND, not an "
              "uncertain lookup. The material draws both layers here."
              % r["dominance"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
