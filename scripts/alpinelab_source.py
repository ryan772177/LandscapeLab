"""alpinelab_source.py — WHERE an AlpineLab recipe's source data lives.

ONE DECLARATION, N PROJECTIONS (non-negotiable 24).

`make_alpinelab_material.py` and `scatter_alpinelab.py` each carried their own
copy of

    PKG = r"C:\\Dev\\LandscapeLab\\TerrainData\\AlpineLab_v1\\002\\UE5_Ready"
    MASK_PNG = {"flow": "Erosion2_Flow.png", ...}

Two copies that must agree, in two files, describing one fact. The test
non-negotiable 24 gives is: *if adding a thing can be done in one place and
forgotten in another, the structure is wrong, not the author.* Pointing this
pipeline at a second Gaea build is exactly that operation, and the failure mode
is the worst kind — the material would be built from build 002's masks while
the scatter read build 006's, both would succeed, and the rocks would sit in
places the surfacing does not describe. Neither tool's verification could see
it, because each would be internally consistent. That is non-negotiable 19's
scree-texture-vs-scree-mesh divergence with a different first cause.

So the build path and the mask filenames move into the RECIPE, and both tools
read them from here.

WHY THIS REFUSES INSTEAD OF DEFAULTING. A default would let a recipe with no
`source` block silently resolve to build 002 — which is precisely the
"plausible field, baked in silently" outcome that `rock_scatter.py`'s exit-2
refusal was praised for avoiding. A tool that fails closed on missing shared
truth is how the shared truth gets noticed at all.
"""

from __future__ import annotations

import os

# The five masks, by ROLE. The role names are the contract every consumer
# uses (recipe mask keys, species mask_window keys); the FILENAMES are
# build-specific Gaea node outputs and live in the recipe.
MASK_ROLES = ("flow", "wear", "deposits", "snow_hard", "snow_depth")


class SourceError(Exception):
    """Raised when a recipe does not declare where its data is."""


def resolve(recipe: dict, recipe_path: str = "<recipe>"):
    """Return (pkg_dir, mask_png, heightmap_name) for an AlpineLab recipe.

    `pkg_dir` is the absolute directory holding the UE5-ready PNGs.
    `mask_png` maps every role in MASK_ROLES to a filename in that directory.

    REFUSES, with the recipe path named, when the block is missing, a role is
    missing, or a declared file is not on disk. Every failure says which
    recipe and which key, because "source not found" without those two sends
    the reader to the wrong file.
    """
    src = recipe.get("source")
    if not isinstance(src, dict):
        raise SourceError(
            "%s declares no `source` block. It must carry build_dir, "
            "masks and heightmap (package_subdir optional, defaults to "
            "UE5_Ready) so that every tool reading this recipe reads the SAME "
            "Gaea build. Refusing rather than "
            "defaulting to a build this recipe never named." % recipe_path)

    build_dir = src.get("build_dir")
    if not build_dir:
        raise SourceError("%s: source.build_dir is missing or empty." % recipe_path)

    pkg_dir = os.path.join(build_dir, src.get("package_subdir") or "UE5_Ready")
    if not os.path.isdir(pkg_dir):
        raise SourceError(
            "%s: source resolves to %s, which is not a directory. This is "
            "'the build is not there', not 'the masks are empty'."
            % (recipe_path, pkg_dir))

    masks = src.get("masks")
    if not isinstance(masks, dict):
        raise SourceError("%s: source.masks is missing." % recipe_path)

    missing_roles = [r for r in MASK_ROLES if not masks.get(r)]
    if missing_roles:
        raise SourceError(
            "%s: source.masks does not declare %s. Every consumer indexes by "
            "role, so an undeclared role is a silent None at sample time."
            % (recipe_path, ", ".join(missing_roles)))

    mask_png = {r: masks[r] for r in MASK_ROLES}

    absent = [("%s -> %s" % (r, f)) for r, f in mask_png.items()
              if not os.path.isfile(os.path.join(pkg_dir, f))]
    if absent:
        raise SourceError(
            "%s: declared mask file(s) not present in %s: %s"
            % (recipe_path, pkg_dir, "; ".join(absent)))

    heightmap = src.get("heightmap")
    if not heightmap:
        raise SourceError("%s: source.heightmap is missing." % recipe_path)
    if not os.path.isfile(os.path.join(pkg_dir, heightmap)):
        raise SourceError(
            "%s: declared heightmap %s is not present in %s"
            % (recipe_path, heightmap, pkg_dir))

    return pkg_dir, mask_png, heightmap
