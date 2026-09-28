"""make_landscape_material.py — build the auto-material from the recipe.

The real deliverable, as opposed to make_layer_debug_material.py which
paints diagnostic false colours. Same proven node graph; every value
comes from the recipe instead of an instrument palette.

Builds `material.parent_material` (find-or-create, hard rule 3) with one
slope/height band per recipe layer, composited first-match-wins, driving
BaseColor and Roughness from each layer's `base_color` and `roughness`.

Asset creation goes through unreal.AssetTools / MaterialEditingLibrary —
the editor API — which conduct rule 4 permits; rule 4 forbids direct
on-disk .uasset edits.

TEXTURES (schema v1.2). Each layer may declare a `texture`, which
MULTIPLIES its `base_color` rather than replacing it:

    final_albedo = base_color * 4 * detail_sample.rgb * macro_sample.rgb

The textures are linear variation maps with a per-channel mean of exactly
0.5, so the product has mean 1.0 and a fully-mipped layer renders exactly
its recipe base_color. Colour therefore stays in the recipe (hard rule 2)
and a fading texture cannot tint the terrain. A layer with `texture` but
no `macro_tiling_m` takes a single sample and a gain of 2.0, for the same
reason: one mean-0.5 sample times 2 is also mean 1.0.

Every texture asset is loaded and checked BEFORE the existing graph is
cleared. delete_all_material_expressions() is destructive to live state,
so nothing that can fail may run after it: a missing texture discovered
mid-build would leave the material blank in memory and dirty, with the
terrain rendering untextured and a later "Save All" able to persist the
blank over the good copy on disk. Missing textures refuse at exit 4 with
the material untouched.

TWO SCALES, and why one is not enough. UVs are world-space:
`WorldPosition.xy / (tiling_m * 100)`. At this recipe's cameras the
nearest terrain is ~1.1 km and most of frame is 3-14 km; one pixel
subtends 1.5 m at 3 km. A 4 m repeat spans well under 3 px and mips to
its mean, contributing nothing. `macro_tiling_m` (~300 m) spans 41-200 px
and is what actually reads. Both scales sample the SAME texture asset.

Samplers use SSM_Wrap_WorldGroupSettings (shared samplers) so doubling
the sample count costs no sampler slots, and wrapping does not depend on
the texture asset's own address settings.

FEATHER WIDTHS — the schema gap, now closed with a normative formula.
`blend_sharpness` is 0..1 with no defined width in metres or degrees
(audit finding R2, ruled 2026-08-01). This script uses, and
recipes/schema.md now records normatively:

    slope feather (deg) = (1 - blend_sharpness) * 12
    height feather (m)  = (1 - blend_sharpness) * 0.06 * z_scale_m

So sharpness 1.0 is a hard edge, 0.0 is a 12-degree / 6%-of-range
feather, and everything between interpolates linearly. Chosen because
12 degrees is roughly the width over which real snow and rock
interfinger on a mountainside, and 6% of vertical range is a plausible
snowline transition band. They are defensible defaults, not physics.

Slope masks avoid an inverse-trig node entirely: the vertex normal's
world Z equals cos(slope), and cos is monotonically decreasing over
0..90, so `slope <= S` is exactly `normal.z >= cos(S)`. Thresholds are
converted to cosines on the CPU.

Heights use the schema's datum: world_z_cm = actor_z + height_m*100 -
z_scale_cm/2, because Unreal maps heightmap value 32768 — not 0 — to the
actor's Z.

Exit codes:
  8  another heavy operation holds the lock (scripts/resource_guard.py)
  0  material built (and assigned, if --assign)
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  material build failed in the editor
  5  --assign requested but the landscape was not found or not unique,
     or World Partition residency could not be established
  6  level gate refused — the editor has a different level open than
     `landscape.level_path` (schema v1.2)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import resource_guard   # noqa: E402 — RAM check + heavy-op lock
import capture            # noqa: E402 — shared World Partition residency gate
import import_heightmap   # noqa: E402 — shared recipe validation
import landscape_spec     # noqa: E402
import material_graph     # noqa: E402 — shared clear/assert, rule 4a
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_MATERIAL__"

# Feather CAPS = the widest feather (softest blend, blend_sharpness=0):
# slope band feathers up to +-12 deg, height band up to +-6% of z-range.
# Defensible AESTHETIC defaults, NOT physics: 12 deg is roughly how far snow
# and rock interfinger on a real mountainside, 6% a plausible snowline
# transition band. Normative since schema v1.2; ruled LESSONS 2026-08-01
# (R2 feather widths), introduced 3570cb51. Revisit only if a biome needs a
# feather this (1-sharpness) formula cannot express. (NOT Brief 3 Task 2 --
# PASS3 sec2 mis-attributed it; corrected there 2026-09-16, ruling R3.)
SLOPE_FEATHER_MAX_DEG = 12.0
HEIGHT_FEATHER_MAX_FRAC = 0.06


# =====================================================================
# THE ONE DECLARATION (CLAUDE.md non-negotiable 24)
#
# Adding a sampled texture to this material is a ONE-ROW edit here. The
# preflight set, the sampler type, the import-settings contract and the
# post-build assertion's expected set are all PROJECTIONS of this. None
# of them is written down a second time anywhere.
#
# Written 2026-08-03 after the third divergence in one session: the
# assertion demanded textures the builder never sampled, and the failure
# landed AFTER the destructive graph clear instead of before it.
# =====================================================================

# class -> (reflected MaterialSamplerType member,
#           compression_settings the asset MUST read back as,
#           srgb the asset MUST read back as)
#
# The compression/srgb columns are NOT decoration. They are the IMPORT
# CONTRACT restated where the sampler decision is made, and the preflight
# CHECKS THEM — which is what makes the sampler type provable before the
# clear rather than discovered at node-build time.
#
# They also carry the only distinction between two classes that share a
# sampler member: `selector` (uncompressed, so a block compressor cannot
# bleed one layer's weights into another) and `variation` (TC_BC7, where
# banding matters more than bleed). Without these columns those two would
# be the same row, which is the inert-field trap in a table meant to
# eliminate it.
#
# Sources: import_surface_set.ROLE_SETTINGS, import_layer_textures.EXPECTED.
SAMPLER_CLASS = {
    "colour":    ("SAMPLERTYPE_COLOR",            "TC_DEFAULT",               True),
    "normal":    ("SAMPLERTYPE_NORMAL",           "TC_NORMALMAP",             False),
    "mask":      ("SAMPLERTYPE_MASKS",            "TC_MASKS",                 False),
    "grayscale": ("SAMPLERTYPE_LINEAR_GRAYSCALE", "TC_GRAYSCALE",             False),
    "variation": ("SAMPLERTYPE_LINEAR_COLOR",     "TC_BC7",                  False),
    "selector":  ("SAMPLERTYPE_LINEAR_COLOR",     "TC_VECTOR_DISPLACEMENTMAP", False),
}

_WRAP = "SSM_WRAP_WORLD_GROUP_SETTINGS"
_CLAMP = "SSM_CLAMP_WORLD_GROUP_SETTINGS"

# (band key, class, REQUIRES all truthy, FORBIDS any truthy, sampler source)
#
# `sub_active` is the ONE sub-surface predicate (computed in layer_bands
# where the recipe is visible). Every sub row requires it, so the build
# gate and the assertion cannot disagree about whether a sub-surface is
# on — they no longer each spell the condition out.
#
# sub_n / sub_r additionally require the PRIMARY's normal / roughness:
# the blend needs a pair, so the declaration refuses to express "sub
# only". That was a real latent bug before this table existed.
SAMPLED_TEXTURES = (
    # FORBIDS surface_c: schema v1.8 says a `surface` SUPERSEDES a
    # `texture` entirely, and the builder branches accordingly
    # (_surface_albedo vs _albedo). Without this column the plan demands
    # BOTH and the assertion fails on three textures the graph never
    # samples. R2 REJECTED already records the mirror of this mistake:
    # declaring a band's legacy texture when it has a surface.
    ("texture_asset", "variation", ("texture_asset",),    ("surface_c",), _WRAP),
    ("surface_c",     "colour",    ("surface_c",),                    (), _WRAP),
    ("surface_n",     "normal",    ("surface_c", "surface_n"),        (), _WRAP),
    ("surface_r",     "mask",      ("surface_c", "surface_r"),        (), _WRAP),
    # `d_active`, NOT `sub_active`. The primary's height map is needed by
    # TWO features now — the sub-surface HeightLerp (which compares two
    # heights) and Nanite DISPLACEMENT (which needs one for every surfaced
    # layer, sub-surface or not). Adding a second row beside this one
    # would be two lists that must agree (NN24); instead the PREDICATE
    # widened, in the one place layer_bands computes it, and `d_active` is
    # asserted to be implied by `sub_active` in _assert_band_invariant so
    # the two features cannot disagree about whether the map is present.
    ("surface_d",     "grayscale", ("d_active",),                     (), _WRAP),
    ("sub_c",         "colour",    ("sub_active",),                   (), _WRAP),
    ("sub_n",         "normal",    ("sub_active", "surface_n", "sub_n"), (), _WRAP),
    ("sub_r",         "mask",      ("sub_active", "surface_r", "sub_r"), (), _WRAP),
    ("sub_d",         "grayscale", ("sub_active",),                   (), _WRAP),
)

# Whole-material, one each, clamped 1:1 onto the terrain (never tiled).
GLOBAL_TEXTURES = (
    ("weightmap",  "selector",  _CLAMP),
    ("variantmap", "selector",  _CLAMP),
    # v1.19. CLAMPED 1:1 like the others: a WRAPPED macro map would
    # repeat ~3x across 8064 m and reintroduce the tiling it exists to
    # break up. TC_BC7 rather than uncompressed — this is a smooth
    # low-frequency signal where banding matters and channel bleed does
    # not, which is the whole distinction between the two selector-ish
    # classes.
    ("macromap",   "variation", _CLAMP),
)


class TexturePlanError(ValueError):
    """The declaration cannot be reduced to a buildable plan."""


# ⛔ THE WEIGHTMAP CHANNEL CONTRACT — ONE DECLARATION, TWO CONSUMERS.
# The landscape material samples these channels; `bake_surface_lookup`
# answers "what am I standing on?" from the SAME texture and must agree
# about which channel is which layer and which layer is the remainder.
# Two copies of that mapping would be two lists that must agree (NN24),
# and they would disagree silently — the shader would paint scree where
# the footstep audio played grass, with nothing to compare. So the
# payload's `_chan` is INTERPOLATED from here and the lookup IMPORTS
# `mask_plan`; neither spells it out again.
WEIGHTMAP_CHANNELS = ("R", "G", "B", "A")

# The VARIANT map is a SEPARATE texture with its own width: RGB, one
# channel per layer in recipe order, baked by `make_variant_map`. It is
# NOT the weightmap and must never be indexed with WEIGHTMAP_CHANNELS --
# doing so raised IndexError after the graph had been cleared on
# 2026-09-12, and was invisible for as long as the layer count happened
# to equal the weightmap's channel count.
VARIANTMAP_CHANNELS = ("R", "G", "B")


def mask_plan(n_layers, channels=WEIGHTMAP_CHANNELS):
    """(direct, has_remainder) for `n_layers` against a stored contract.

    Layers 0..direct-1 read a stored channel. When there are more layers
    than channels the LAST layer is the shader remainder
    1-(sum of the stored channels) — never a stored fifth number, which
    8-bit quantisation would let disagree with the other four.

    Raises when a second weightmap texture would be needed, because that
    is a build the material does not do and must not be widened into
    silently.
    """
    n = int(n_layers)
    direct = min(n, len(channels))
    if n > len(channels) + 1:
        raise TexturePlanError(
            "the weightmap has {0} channels, so at most {1} layers are "
            "addressable (the last being the remainder); {2} were "
            "declared. A further layer needs a SECOND weightmap texture, "
            "which this builder does not create.".format(
                len(channels), len(channels) + 1, n))
    return direct, n > direct


def texture_plan(bands, weightmap=None, variantmap=None,
                 macromap=None):
    """Reduce THE ONE DECLARATION against these bands into the plan.

    One row per TextureSample the builder will create:

        [band_index, band_key, class, sampler_member, sampler_source, path,
         compression_settings, srgb]

    `band_index` is -1 for whole-material rows. LISTS, not dicts: this is
    JSON-serialised into the largest payload in the repo and field names
    would be paid for on every run.

    The CLASS travels in the row so the preflight can check the asset's
    import settings against it. Carrying only the sampler member would
    make the compression/srgb columns unreadable — inert by construction.

    PURE. No editor, no filesystem. Feed it a synthetic band and assert
    it REFUSES (non-negotiable 2).
    """
    rows = []
    for i, b in enumerate(bands):
        for key, klass, needs, forbids, source in SAMPLED_TEXTURES:
            if any(not b.get(k) for k in needs):
                continue
            if any(b.get(k) for k in forbids):
                continue
            path = b.get(key)
            if not path:
                raise TexturePlanError(
                    "band {0!r} satisfies the REQUIRES gate for {1!r} but "
                    "carries no path for it. The declaration's REQUIRES "
                    "column is wrong, not the recipe.".format(
                        b.get("name"), key))
            _sm, _comp, _srgb = SAMPLER_CLASS[klass]
            rows.append([i, key, klass, _sm, source, path, _comp, _srgb])
    for key, klass, source in GLOBAL_TEXTURES:
        path = {"weightmap": weightmap, "variantmap": variantmap,
                "macromap": macromap}[key]
        if path:
            _sm, _comp, _srgb = SAMPLER_CLASS[klass]
            rows.append([-1, key, klass, _sm, source, path, _comp, _srgb])
    _plan_conflicts(rows)
    return rows


def _plan_conflicts(rows):
    """Refuse a plan the ASSERTION could not adjudicate.

    1. ONE PATH, TWO CLASSES — the same asset sampled as `colour` in one
       band and `mask` in another cannot both be right, and the compiler
       would only ever name one of them.
    2. TWO PATHS, ONE SHORT NAME — `_ll_assert_graph` normalises to the
       last path segment, so `/Game/A/T_X` and `/Game/B/T_X` are
       INDISTINGUISHABLE to it: one could be missing and the other extra
       and it would report an exact match. A check that cannot tell its
       own inputs apart verifies nothing (non-negotiable 5).
    """
    by_path, by_short = {}, {}
    for _, key, klass, sampler, _src, path, _c, _g in rows:
        if by_path.setdefault(path, klass) != klass:
            raise TexturePlanError(
                "{0} is declared as two different classes ({1} and {2}); "
                "one of the band keys names the wrong CLASS".format(
                    path, by_path[path], klass))
        short = path.split("/")[-1].split(".")[0]
        if by_short.setdefault(short, path) != path:
            raise TexturePlanError(
                "{0} and {1} share the short name {2!r}; the graph "
                "assertion compares short names, so it could not tell a "
                "missing one from an extra one".format(
                    by_short[short], path, short))


def assert_texture_plan_gates():
    """Prove the reducer REFUSES bad declarations (non-negotiable 2).

    Pure, host-side, no editor. Each case is a way the declaration could
    be wrong while still producing a plausible-looking plan.
    """
    fails = []

    def expect_refuse(label, bands, wm=None, vm=None):
        try:
            texture_plan(bands, weightmap=wm, variantmap=vm)
        except TexturePlanError:
            return
        fails.append(label)

    base = {"name": "X", "surface_c": "/Game/S/T_A_C"}

    # REQUIRES satisfied but no path: the declaration's gate is wrong.
    b = dict(base, sub_active=True, sub_c=None, sub_d="/Game/S/T_B_D",
             surface_d="/Game/S/T_A_D")
    expect_refuse("REQUIRES satisfied with no path", [b])

    # One asset, two classes.
    b1 = {"name": "P", "surface_c": "/Game/S/T_SAME"}
    b2 = {"name": "Q", "surface_c": "/Game/S/T_OK",
          "surface_r": "/Game/S/T_SAME"}
    expect_refuse("same path declared colour and mask", [b1, b2])

    # Two paths, one short name — invisible to the graph assertion.
    b3 = {"name": "P", "surface_c": "/Game/A/T_DUP"}
    b4 = {"name": "Q", "surface_c": "/Game/B/T_DUP"}
    expect_refuse("two paths sharing a short name", [b3, b4])

    # v1.21. DISPLACEMENT ON, but the layer's height map is missing. This
    # is the sub-surface bug's exact shape one feature later: the
    # predicate says the map is needed, so a plan without a path must be
    # a REFUSAL here rather than a KeyError after the destructive clear.
    b5 = {"name": "S", "surface_c": "/Game/S/T_A_C", "d_active": True,
          "surface_d": None}
    expect_refuse("d_active with no surface_d path", [b5])

    # And it must ACCEPT the shipping shape.
    try:
        rows = texture_plan(
            [{"name": "R", "surface_c": "/Game/S/T_A_C",
              "surface_n": "/Game/S/T_A_N", "surface_r": "/Game/S/T_A_R",
              "sub_active": True, "d_active": True,
              "sub_c": "/Game/S/T_B_C",
              "sub_n": "/Game/S/T_B_N", "sub_r": "/Game/S/T_B_R",
              "sub_d": "/Game/S/T_B_D", "surface_d": "/Game/S/T_A_D"}],
            weightmap="/Game/T/T_W", variantmap="/Game/T/T_V")
        if len(rows) != 10:
            fails.append("a full sub-surface band + 2 globals should be "
                         "10 rows, got {0}".format(len(rows)))
    except TexturePlanError as exc:
        fails.append("refused a valid plan: {0}".format(exc))

    # v1.21. DISPLACEMENT ON A LAYER WITH NO SUB-SURFACE — the Snow case,
    # and the only shape that adds a NEW texture to the shipping plan.
    # It must produce exactly one height sample and no sub-surface rows.
    try:
        rows = texture_plan(
            [{"name": "Snow", "surface_c": "/Game/S/T_A_C",
              "surface_n": "/Game/S/T_A_N", "surface_r": "/Game/S/T_A_R",
              "d_active": True, "surface_d": "/Game/S/T_A_D"}],
            weightmap="/Game/T/T_W")
        keys = sorted(r[1] for r in rows)
        want = ["surface_c", "surface_d", "surface_n", "surface_r",
                "weightmap"]
        if keys != want:
            fails.append(
                "a surfaced band with displacement and NO sub-surface "
                "should plan {0}, got {1}".format(want, keys))
        # The class carries the sampler decision, and grayscale is the one
        # the engine picks for a single-channel non-sRGB map
        # (MaterialExpressionUtils.cpp:37-38). A _D planned as `mask`
        # would be refused by the preflight, after the point where a
        # wrong class is cheap to fix.
        dcls = [r[2] for r in rows if r[1] == "surface_d"]
        if dcls != ["grayscale"]:
            fails.append("surface_d must be class 'grayscale', got "
                         "{0}".format(dcls))
    except TexturePlanError as exc:
        fails.append("refused a valid displacement-only plan: {0}".format(
            exc))

    return fails


def _cpu_triplanar(sx, sy, sz, nx, ny, nz, m, sharpness):
    """CPU mirror of the payload's triplanar blend. Must stay identical.

        wx = |nx|^s * m ; wy = |ny|^s * m ; wz = |nz|^s
        out = (sx*wx + sy*wy + sz*wz) / (wx + wy + wz)

    The slope mask `m` multiplies the two SIDE weights only. That is what
    makes m=0 collapse to exactly sz, and it is why the mask has one
    entry point and cannot be applied twice.
    """
    wx = (abs(nx) ** sharpness) * m
    wy = (abs(ny) ** sharpness) * m
    wz = abs(nz) ** sharpness
    den = wx + wy + wz
    if den <= 0.0:
        raise ValueError(
            "triplanar denominator collapsed (n={0},{1},{2} m={3})".format(
                nx, ny, nz, m))
    return (sx * wx + sy * wy + sz * wz) / den


def _assert_triplanar_invariants():
    """Properties the FORMULA CANNOT RESTATE (non-negotiable 2).

    The reviewer's point about the reviewed design was that its invariant
    suite re-derived the same arithmetic and therefore proved nothing.
    Each property below is stated in terms of EXPECTED PHYSICAL BEHAVIOUR
    and would fail on a plausible mis-wiring.
    """
    fails = []
    S = 2.0

    # 1. THE REGRESSION GUARANTEE. Below the slope band the mask is 0 and
    #    the result must be EXACTLY the top-down sample -- not
    #    approximately, exactly -- for ANY normal and ANY side samples.
    #    This is what makes triplanar safe to ship: flat ground renders
    #    bit-for-bit as it did before.
    for n in ((0.0, 0.0, 1.0), (0.3, 0.2, 0.93), (0.7, 0.0, 0.71)):
        got = _cpu_triplanar(9.0, -4.0, 0.25, n[0], n[1], n[2], 0.0, S)
        if abs(got - 0.25) > 1e-12:
            fails.append(
                "m=0 must collapse to the Z sample exactly; normal {0} "
                "gave {1!r}".format(n, got))

    # 2. A WALL MUST NOT USE ITS TOP-DOWN SAMPLE. On a perfectly vertical
    #    +X face the Z weight is 0, so the smeared top-down texel must
    #    contribute NOTHING. If this fails the feature does not remove
    #    the artefact it exists to remove.
    got = _cpu_triplanar(1.0, 0.0, 999.0, 1.0, 0.0, 0.0, 1.0, S)
    if abs(got - 1.0) > 1e-9:
        fails.append("vertical +X face still admits the top-down sample: "
                     "{0!r}".format(got))

    # 3. AXIS ROUTING. A face pointing along +X must take its colour from
    #    the X projection, +Y from the Y projection. Swapping the two
    #    weight assignments -- a real and easy mis-wiring -- is invisible
    #    to any test that feeds symmetric inputs, so these are asymmetric.
    if abs(_cpu_triplanar(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, S) - 1.0) > 1e-9:
        fails.append("+X face did not read the X projection")
    if abs(_cpu_triplanar(0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, S) - 1.0) > 1e-9:
        fails.append("+Y face did not read the Y projection")

    # 4. SIGN INDEPENDENCE. -X and +X are the same plane; a normal's SIGN
    #    must not change which projection is used. A missing Abs passes
    #    every positive-normal test and fails here.
    #
    #    SWEPT OVER THE ADMISSIBLE DOMAIN, NOT THE SHIPPED VALUE. This
    #    property was written against `S = 2.0` alone -- the number in
    #    `recipes/alpine.json` today -- and at an EVEN exponent
    #    `nx ** s == abs(nx) ** s` identically, so deleting the Abs
    #    changed nothing and the check could not fail. The validator
    #    admits any sharpness in [1, 8]; at 3.0 the same deletion yields
    #    a NEGATIVE weight and a blend that leaves the convex hull.
    #    A suite pinned to the current recipe value tests the recipe,
    #    not the code -- and the recipe is the thing free to change.
    for s in (1.0, 2.0, 3.0, 4.5, 8.0):
        a = _cpu_triplanar(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, s)
        b = _cpu_triplanar(1.0, 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, s)
        if abs(a - b) > 1e-12:
            fails.append("projection depends on the SIGN of the normal at "
                         "sharpness {0} ({1!r} vs {2!r}); Abs is missing"
                         .format(s, a, b))

    # 5. BOUNDEDNESS. The output is a convex combination, so it can never
    #    leave the range of its inputs. An unnormalised blend (forgetting
    #    the divide) brightens every steep face and would read as a
    #    lighting bug, not a projection bug.
    for mm in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = _cpu_triplanar(0.2, 0.8, 0.5, 0.5, 0.5, 0.707, mm, S)
        if v < 0.2 - 1e-9 or v > 0.8 + 1e-9:
            fails.append("not a convex combination at m={0}: {1!r}".format(
                mm, v))

    # 6. THE DENOMINATOR CANNOT COLLAPSE — swept over REACHABLE states.
    #
    #    `m` and the normal are NOT independent: m is DERIVED from n.z by
    #    the same ramp the layer bands use. Sweeping them separately
    #    reaches (vertical normal, m=0), which the shader cannot produce,
    #    and reports a denominator of 1e-33 that no pixel will ever see.
    #    The first version of this test did exactly that and failed — the
    #    TEST was wrong, not the graph. A sweep that ignores a coupling
    #    between its variables is testing a different system.
    import math as _mh
    cos_lo = _mh.cos(_mh.radians(45.0))
    cos_hi = _mh.cos(_mh.radians(50.0))
    worst = None
    for i in range(0, 181):
        for j in range(0, 361, 5):
            th, ph = _mh.radians(i), _mh.radians(j)
            n = (_mh.sin(th) * _mh.cos(ph), _mh.sin(th) * _mh.sin(ph),
                 _mh.cos(th))
            # m from |n.z|. The payload ramps on RAW n.z with no Abs —
            # equivalent here because a heightmap landscape's normals
            # never point down (n.z >= 0); the abs() keeps this CPU
            # model total over the whole sphere for the sweep.
            t = (abs(n[2]) - cos_lo) / (cos_hi - cos_lo)
            mm = min(1.0, max(0.0, t))
            d = ((abs(n[0]) ** S) * mm + (abs(n[1]) ** S) * mm
                 + abs(n[2]) ** S)
            if worst is None or d < worst[0]:
                worst = (d, n, mm)
    # For sharpness 2 and a unit normal the bound is ~0.41: either the
    # mask is 0 and n.z^2 >= cos(45)^2 = 0.5, or the mask is 1 and the
    # three squares sum to exactly 1.
    if worst[0] < 0.3:
        fails.append("denominator reaches {0:.4f} at reachable normal {1} "
                     "m={2:.3f}".format(*worst))

    # 7. AT FULL MASK THIS IS CANONICAL TRIPLANAR — the mask's ONLY job is
    #    to fade the two SIDE planes in. It must never touch the Z weight.
    #
    #    Properties 1-6 all survive a mis-wiring that ALSO multiplies the
    #    Z weight by the mask (`wz = |nz|^s * (1-m)`): m=0 still collapses
    #    to sZ, a vertical wall still excludes the top-down sample, axis
    #    routing is unchanged, it stays convex, and the extra factor never
    #    reaches zero at any COUPLED (n, m). Yet it is wrong everywhere in
    #    the 45-50 degree transition band, which is the entire region the
    #    feature was built for.
    #
    #    The reference below is the TEXTBOOK form, written independently
    #    of `_cpu_triplanar`. That is what makes this a check rather than
    #    a restatement: the claim under test is not "the arithmetic is the
    #    arithmetic" but "the masked blend RELAXES TO the standard one",
    #    which is a design statement and can be false.
    def _canonical(sx, sy, sz, nx, ny, nz, sharpness):
        wx, wy, wz = (abs(nx) ** sharpness, abs(ny) ** sharpness,
                      abs(nz) ** sharpness)
        return (sx * wx + sy * wy + sz * wz) / (wx + wy + wz)

    for n in ((0.577, 0.577, 0.577), (0.8, 0.1, 0.59), (0.1, 0.9, 0.42),
              (0.6, 0.6, 0.53)):
        got = _cpu_triplanar(0.9, 0.3, 0.1, n[0], n[1], n[2], 1.0, S)
        want = _canonical(0.9, 0.3, 0.1, n[0], n[1], n[2], S)
        if abs(got - want) > 1e-12:
            fails.append(
                "at m=1 the blend is not canonical triplanar for normal "
                "{0}: got {1!r}, canonical {2!r}. The slope mask is "
                "reaching a weight it must not touch.".format(n, got, want))
    return fails


def _tri_spec(recipe):
    """material.triplanar with its cosines resolved host-side, or {}.

    The payload compares the world normal's Z against a cosine; turning
    the recipe's DEGREES into that cosine is a derivation and belongs
    where every other band threshold is derived (layer_bands), not in a
    shader that has no math module.
    """
    tp = (recipe.get("material") or {}).get("triplanar")
    if not tp:
        return {}
    lo, hi = [float(v) for v in tp["slope_deg"]]
    return {
        "layers": list(tp["layers"]),
        "slope_deg": [lo, hi],
        # QUANTISED HERE, once (2026-09-16, Pass 3): the payload builds
        # |n|^s by repeated multiply, so it can only realise INTEGER
        # exponents — it rounds. Rounding host-side means the CPU model,
        # the invariant sweep and the graph all see the SAME value, and
        # "must stay identical" is true for every value that can reach
        # the graph. (Shipping recipe declares 2.0; unchanged by this.)
        "sharpness": float(int(round(float(tp["sharpness"])))),
        # cos DECREASES as slope increases, so cos(hi) < cos(lo).
        "cos_lo": math.cos(math.radians(lo)),
        "cos_hi": math.cos(math.radians(hi)),
    }


def _surface_asset(layer, role):
    """`/Game/Surfaces/T_<id>_<role>` for a layer's SUB-surface, or None.

    Returns None both when no `sub_surface` block exists and when it
    exists with `surface: null` (the deferred case) — in either case
    there is no texture to sample. The two states are distinguished for
    REPORTING by `sub_declared`, not here.
    """
    ss = layer.get("sub_surface") or {}
    sid = ss.get("surface")
    return "/Game/Surfaces/T_{0}_{1}".format(sid, role) if sid else None


def displacement_spec(recipe):
    """schema v1.27 — the displacement block, reduced to ENGINE units. Once.

    Returns None when displacement is absent or disabled, else
    {"per_layer", "amplitude_ref", "magnitude", "center", "scale_z"}.
    `per_layer` is {layer_name: metres}; `amplitude_ref` is its MAX (the
    layer the engine `magnitude` carries); the payload scales every other
    layer's centred height down by amplitude_layer / amplitude_ref. (Before
    v1.27 this was a single global `amplitude_m` and the return carried
    that key -- retired by the Brief 7 Phase 1 per-layer bump; a stale
    reader of the old shape is exactly the rule-9 seed contamination.)

    THE CONVERSION LIVES HERE AND NOWHERE ELSE. The recipe declares a
    PHYSICAL amplitude in metres; the engine wants a unitless magnitude in
    the landscape's LOCAL space. Those differ by a factor of 500 on this
    world, which is precisely the kind of gap that produces a number that
    is arithmetically right and means something else.

    THE ARITHMETIC, derived from the shader rather than from a docs page:

        NaniteRasterizationCommon.ush:568
            D_local = (v - Center) * Magnitude,  v in [0, 1]
        so with Center 0.5 the local swing is +/- Magnitude/2.

        :578  PointPostDeform += Normal * D_local     (LOCAL space)
        :588  PointWorld = mul(PointPostDeform, LocalToTranslatedWorld)

        The landscape's Nanite mesh is exported RelativeToProxy
        (LandscapeNaniteComponent.cpp:337 ->
         LandscapeEdit.cpp:4215-4216, ComponentTransform *
         ProxyTransform.Inverse()), so the proxy scale is divided out of
        the mesh and re-applied by the component. Vertical scale is
        scale_z = z_scale_cm / 512 (landscape_spec.py:35), which is 500
        here and matches the live editor's [400, 400, 500].

        peak_cm = (Magnitude / 2) * scale_z
        =>  Magnitude = 2 * amplitude_m * 100 / scale_z

    A SANITY CHECK ON THE MAGNITUDE THIS REPLACES: the engine default is
    4.0 (EngineTypes.h:3456), which by the line above is +/-10 m on this
    landscape. The handoff's instinct that 4.0 was "far too strong" was
    right; this is the mechanism and the number behind it.

    CENTER IS 0.5, AND THE OBVIOUS JUSTIFICATION FOR IT IS FALSE. This
    docstring previously read "it is the value the height maps are neutral
    at, so a fully-mipped or missing sample displaces by zero". That is a
    claim about PIXELS and it was never checked. Measured 2026-08-11 over
    the five surface height maps actually in this material:

        Ground037  mean 0.5257   ->   +2.06 cm at magnitude 0.16
        Rock051    mean 0.6005   ->   +8.04 cm
        Snow006    mean 0.6490   ->  +11.92 cm
        Rock026    mean 0.7602   ->  +20.82 cm
        Rock063    mean 0.7311   ->  +18.49 cm   (not in this material)

    NOT ONE IS CENTRED ON 0.5. So center 0.5 lifts every surface by a
    constant — up to +21 cm against a +/-40 cm amplitude, i.e. half the
    signal — and because the lift DIFFERS PER SURFACE it also puts a step
    of up to ~19 cm at layer boundaries that is not real relief. A
    fully-mipped sample returns the map's MEAN, not 0.5, so the
    degraded-state guarantee does not hold either.

    0.5 IS NOW CORRECT, BUT ONLY BECAUSE THE GRAPH MAKES IT SO. Fixed the
    same day: `_centred_height` in the payload re-centres every height
    sample on ITS OWN fully-mipped value before the displacement
    composite —

        centred = raw - mipped + center

    — so the value reaching the Displacement pin is centred on `center`
    by construction, whatever the map's own mean happens to be. The
    neutral is READ FROM THE TEXTURE rather than declared, so there is no
    derived record to drift when a map is reimported or recompressed
    (these maps have been recompressed before).

    The re-centring applies ONLY to the displacement path. The sub-surface
    HeightLerp keeps the UNCENTRED samples, because that blend compares
    two heights against each other and shifting them by different
    constants would change which surface wins.

    `center` therefore stays 0.5 and is genuinely a free choice now; it is
    kept at 0.5 so the usable range is symmetric (+/- magnitude/2).
    """
    d = (recipe.get("material") or {}).get("displacement")
    if not d or not d.get("enabled"):
        return None
    # schema v1.27 (Brief 7 Phase 1). PER-LAYER amplitude in metres,
    # replacing the single global `amplitude_m`. `_validate_displacement`
    # has already refused the retired key and proven `per_layer` is a
    # dict of {layer_name: float} keyed EXACTLY by the material's layers,
    # so this reducer trusts the shape and only does the metres ->
    # engine-magnitude conversion (NN24: one owner for the conversion).
    per_layer = {str(k): float(v) for k, v in dict(d["per_layer"]).items()}
    center = float(d.get("center", 0.5))
    scale_z = float(recipe["landscape"]["z_scale_cm"]) / 512.0
    if not scale_z > 0.0:
        raise ValueError(
            "landscape.z_scale_cm reduces to a non-positive vertical scale "
            "({0!r}); the displacement magnitude would be undefined".format(
                scale_z))
    # THE ENGINE MAGNITUDE IS ONE SCALAR, so it carries the LARGEST layer
    # amplitude and the graph scales every other layer DOWN from it by
    # amplitude_layer / amplitude_ref (see the payload's per-band scale).
    # This keeps every baked graph value inside [center +/- 0.5] -- no
    # layer's centred height is amplified past the reference -- so the
    # engine's uniform (v - Center) * Magnitude reproduces each layer's
    # own peak amplitude exactly. amplitude_ref is the MAX, not the mean,
    # for that reason.
    amplitude_ref = max(per_layer.values())
    magnitude = 2.0 * amplitude_ref * 100.0 / scale_z
    return {"per_layer": per_layer,
            "amplitude_ref": amplitude_ref,
            "magnitude": magnitude,
            "center": center,
            "scale_z": scale_z}


# schema v1.28 (Brief 7 Phase 1 addendum). The height-blend divide-by-zero
# guard is RELATIVE to the smallest possible weighted sum, not an absolute
# constant. The renormalisation is norm = S / (S' + eps_norm), where
# S' = sum(base_i * (h_i + eps)**k). The worst-case partition drift is
# eps_norm / eps**k (the smallest S'/S is eps**k, at h==0), so a FIXED
# eps_norm is only safe for one (k, eps) pair -- at the validator's ceiling
# k=16 / eps=0.02, eps**k = 6.5e-28 and any fixed 1e-15 floor would dominate
# the real sum and collapse a stored texel to the remainder (cloud review,
# 2026-09-23). Making the floor eps_norm = (eps**k) * REL caps the drift at
# REL for EVERY validated (k, eps): drift <= (eps**k * REL) / eps**k = REL.
# REL = 1e-7 keeps that an order of magnitude under the 1e-6 partition gate
# and far below the 1/255 weightmap quantum. eps_norm is still strictly
# positive (eps > 0), so it fires at S'==0 (a pure-remainder texel -> norm
# 0), and it stays << any real S' (>= base_min * eps**k = eps_norm / REL *
# base_min), so norm == S/S' to precision when S' > 0.
# PORTABILITY: for very large k, eps_norm can fall below the float32
# subnormal floor (~1.4e-45); the target is desktop SM5/SM6 float32 and the
# shipped k=4/eps=0.02 gives eps_norm = 1.6e-14, well inside range. A
# half-precision path (fp16 min ~6e-5) would flush it to 0 -> 0/0 NaN at a
# pure-remainder texel; revisit if this material is ever compiled for fp16.
HEIGHT_BLEND_NORM_REL = 1e-7


def _height_blend_eps_norm(k, eps):
    """The relative divide-by-zero floor for the renormalisation (v1.28).

    eps_norm = (eps ** k) * HEIGHT_BLEND_NORM_REL -- see HEIGHT_BLEND_NORM_REL.
    One owner for the formula (NN24): the reducer, the CPU mirror and the
    graph all take it from here / from the reducer's output.
    """
    return (float(eps) ** float(k)) * HEIGHT_BLEND_NORM_REL


def height_blend_spec(recipe):
    """schema v1.28 — the height-weighted-blend block, or None when absent.

    Returns None when `material.height_blend` is absent OR k == 0 (both mean
    "no reweighting"; k==0 makes (h+eps)**0 == 1, a mathematical identity,
    so collapsing it to None keeps the graph free of dead nodes). Else
    {"k", "eps"}. `_validate_height_blend` has already bounded both.
    """
    hb = (recipe.get("material") or {}).get("height_blend")
    if not hb:
        return None
    k = float(hb["k"])
    if k == 0.0:
        return None
    eps = float(hb["eps"])
    return {"k": k, "eps": eps, "eps_norm": _height_blend_eps_norm(k, eps)}


def _cpu_height_blend(base_weights, heights, k, eps, eps_norm=None):
    """CPU mirror of the stored-layer height reweighting (schema v1.28).

        w_i' = base_i * (h_i + eps) ** k
        norm = sum(base) / (sum(w') + eps_norm)
        return [w_i' * norm]

    `base_weights` are the STORED layers' weightmap channel values (>= 0);
    `heights` are their RAW height samples in [0, 1]. The normalisation
    preserves sum(base) (so the meadow REMAINDER, 1 - sum(base), is
    unchanged), redistributing weight toward the higher-elevation surfaces.
    At a pure-remainder texel (all base 0) sum(w')==0 and the guard returns
    0 rather than 0/0 -- the remainder is 1 there, so nothing is all-zero.
    """
    if eps_norm is None:
        eps_norm = _height_blend_eps_norm(k, eps)
    hk = [(h + eps) ** k for h in heights]
    wp = [b * f for b, f in zip(base_weights, hk)]
    s = sum(base_weights)
    sp = sum(wp)
    norm = s / (sp + eps_norm)
    return [w * norm for w in wp]


STOCHASTIC_DEFAULTS = {
    # ⛔ NOT ENGINE DEFAULTS -- the engine's are Vector4f previews whose
    # components Python cannot read, so relying on them would put a value
    # in the graph that nobody can read back. These are OUR declared
    # values and every one is written into the graph explicitly.
    #
    # variation_scale is the MEASURED lever and has no default on
    # purpose: it must be declared, because its semantics are not
    # readable from the function (get_inputs_for_material_expression
    # returns EMPTY on a MaterialFunction) and were established by a
    # capture sweep instead.
    "variation_levels": 3.0,
    "heightmap_influence": 1.0,
    "random_rotation_and_scale": False,
    "use_dither": False,
    "hq_edge_comparison": True,
}


def _stochastic_spec(layer):
    """Validated stochastic-tiling block for one layer, or None.

    REFUSES an unknown key rather than ignoring it: a misspelled
    parameter that is silently dropped is a setting that reads as applied
    and is not.
    """
    spec = layer.get("stochastic_tiling")
    if not spec:
        return None
    if "variation_scale" not in spec:
        # ValueError, not SystemExit: these are RECIPE faults, and main()
        # catches ValueError from layer_bands() to honour the documented
        # exit-2 contract. SystemExit here exited 1 as "unexpected error".
        raise ValueError(
            "layer %r declares stochastic_tiling with no variation_scale. "
            "It has no default: the function's own input semantics are "
            "unreadable from Python, so this value is MEASURED (R-STOCH) "
            "and must be declared." % layer.get("name"))
    allowed = set(STOCHASTIC_DEFAULTS) | {"variation_scale"}
    unknown = sorted(k for k in spec if not k.startswith("_")
                     and k not in allowed)
    if unknown:
        raise ValueError(
            "layer %r: unknown stochastic_tiling key(s) %r. Allowed: %r"
            % (layer.get("name"), unknown, sorted(allowed)))
    out = dict(STOCHASTIC_DEFAULTS)
    out.update({k: v for k, v in spec.items() if not k.startswith("_")})
    out["variation_scale"] = float(out["variation_scale"])
    if not (0.0 < out["variation_scale"] <= 64.0):
        raise ValueError(
            "layer %r: variation_scale %r is outside the swept range "
            "(0, 64]." % (layer.get("name"), out["variation_scale"]))
    return out


def layer_bands(recipe):
    """Recipe layers -> shader-comparable thresholds and appearance."""
    biome = recipe["biome_id"]
    ls = recipe["landscape"]
    actor_z = float(ls["location_cm"][2])
    z_scale = float(ls["z_scale_cm"])
    z_scale_m = z_scale / 100.0
    # v1.21. Read ONCE from the same reducer the payload uses, so "is
    # displacement on" cannot be spelled two ways (NN24). Truthiness of
    # the raw block is NOT the test — `enabled: false` must read as off.
    _dspec = displacement_spec(recipe)
    disp_on = _dspec is not None

    def world_z(h_m):
        return actor_z + h_m * 100.0 - z_scale / 2.0

    out = []
    for layer in recipe["material"]["layers"]:
        # schema v1.27. `_validate_material` proves per_layer is keyed
        # EXACTLY by the layer names, but `layer_bands` is also reachable
        # WITHOUT that preflight (make_layer_weightmap.py, an ad-hoc
        # load_recipe), so a missing key must raise the CLASSIFIED
        # recipe-fault (ValueError -> exit 2) rather than a bare KeyError
        # from the band-dict index below.
        if _dspec is not None and layer["name"] not in _dspec["per_layer"]:
            raise ValueError(
                "material.displacement.per_layer has no entry for layer "
                "{0!r}; it must be keyed exactly by the material.layers "
                "names (run _validate_material, which refuses this "
                "recipe)".format(layer["name"]))
        s_lo, s_hi = [float(v) for v in layer["slope_deg"]]
        h_lo, h_hi = [float(v) for v in layer["height_m"]]
        sharp = float(layer["blend_sharpness"])

        f_deg = (1.0 - sharp) * SLOPE_FEATHER_MAX_DEG
        f_m = (1.0 - sharp) * HEIGHT_FEATHER_MAX_FRAC * z_scale_m

        # Feather OUTWARD: the mask is 1 across the whole inclusive band
        # and ramps to 0 outside it. Ramping inward would leave a seam of
        # "no layer" along every shared boundary.
        #
        # A band reaching 0 or 90 degrees is OPEN at that end, and the
        # outward feather has nowhere to go: NO ANGLE HAS A COSINE OUTSIDE
        # [0, 1]. Clamping the ANGLE at 0/90 therefore collapses the outer
        # bound onto the inner one and hands _ramp a zero span. That is
        # what made Snow's and Grass's slope masks identically ZERO over
        # the entire terrain - both bands start at 0 degrees - so only Rock
        # ever rendered and the "green" in every capture was the flat
        # background constant, texture-less, which is exactly how it read.
        #
        # Push the outer bound just PAST the closed cosine range instead:
        # the span stays nonzero and correctly signed, and the ramp reads 1
        # across the whole open end.
        #
        # Do NOT simply drop the clamp. cos is even about 0 and symmetric
        # about 90, so cos(radians(-9)) == cos(radians(+9)) folds the outer
        # bound back INSIDE the band and inverts the ramp - masking out
        # everything except near-flat ground.
        OPEN = 1e-3
        cos_lo = (math.cos(math.radians(s_hi + f_deg))
                  if s_hi + f_deg < 90.0 else -OPEN)
        cos_hi = (math.cos(math.radians(s_lo - f_deg))
                  if s_lo - f_deg > 0.0 else 1.0 + OPEN)
        out.append({
            "name": layer["name"],
            "cos_lo": cos_lo,
            "cos_hi": cos_hi,
            "cos_lo_in": math.cos(math.radians(s_hi)),
            "cos_hi_in": math.cos(math.radians(s_lo)),
            "z_lo": world_z(h_lo - f_m),
            "z_hi": world_z(h_hi + f_m),
            "z_lo_in": world_z(h_lo),
            "z_hi_in": world_z(h_hi),
            "color": [float(c) for c in layer["base_color"]],
            "roughness": float(layer["roughness"]),
            "slope_deg": [s_lo, s_hi],
            "height_m": [h_lo, h_hi],
            "feather_deg": f_deg,
            "feather_m": f_m,
            # schema v1.2. `texture_asset` is None when the layer declares
            # no texture, and the graph falls back to a flat Constant3.
            # UV divisors are in CENTIMETRES because WorldPosition is.
            "texture_asset": (
                landscape_spec.texture_asset_path(biome, layer["name"])
                if layer.get("texture") else None),
            # schema v1.8 — a real photogrammetry SURFACE, imported by
            # import_surface_set. When present it supersedes `texture`
            # entirely: colour comes from the surface's own albedo
            # rather than from base_color, and the layer gains a normal
            # and a roughness MAP where it previously had a flat normal
            # and a single scalar.
            #
            # THIS INVERTS WHAT base_color MEANS, deliberately. The
            # generated textures were pinned to per-channel mean 0.5 so
            # they could only MODULATE a recipe colour; real albedo IS
            # the colour, and the measured means run 0.19 to 0.79, so
            # normalising them to 0.5 would delete the thing worth
            # having. With a surface set, base_color becomes an optional
            # TINT (1,1,1 = untinted). Hard rule 2 still holds — the
            # recipe owns every scene parameter — but for a surfaced
            # layer it owns SELECTION and TILING rather than colour.
            "surface_c": ("/Game/Surfaces/T_{0}_C".format(layer["surface"])
                          if layer.get("surface") else None),
            "surface_n": ("/Game/Surfaces/T_{0}_N".format(layer["surface"])
                          if layer.get("surface") else None),
            "surface_r": ("/Game/Surfaces/T_{0}_R".format(layer["surface"])
                          if layer.get("surface") else None),
            "tint": [float(c) for c in layer["base_color"]],
            "uv_detail_cm": float(layer["tiling_m"]) * 100.0,
            # schema v1.26 — STOCHASTIC TILING, per layer. Present only
            # when the layer declares it; every input is carried
            # explicitly because the engine function's own defaults are
            # `Vector4f` previews that expose no components to Python and
            # so could never be read back (standing rule 12).
            "stochastic": _stochastic_spec(layer),
            "uv_macro_cm": (float(layer["macro_tiling_m"]) * 100.0
                            if layer.get("macro_tiling_m") else None),
            # schema v1.11 — see _forest_floor_band below.
            "forest": None,
            # schema v1.14 — the SUB-SURFACE. A layer keeps ONE weightmap
            # channel and may declare a second surface, selected by that
            # layer's channel of `material.variant_map` and blended by
            # HEIGHT rather than by a linear alpha.
            #
            # `sub_c/n/r/d` are None in two distinct cases and the
            # difference matters:
            #   * no `sub_surface` block at all  -> the layer has no
            #     second surface and the graph builds none.
            #   * `sub_surface.surface: null`    -> the path is declared
            #     and DELIBERATELY UNBOUND (the deferred Grass case).
            #     The selector channel is still baked and the recipe
            #     still records the contrast, so binding a surface later
            #     is a one-word edit rather than a re-design.
            # `sub_declared` distinguishes them so the builder can report
            # "deferred" instead of silently looking identical to
            # "absent" — non-negotiable 6 applied to a config state.
            "sub_declared": layer.get("sub_surface") is not None,
            "sub_surface_id": (layer.get("sub_surface") or {}).get("surface"),
            "sub_c": _surface_asset(layer, "C"),
            "sub_n": _surface_asset(layer, "N"),
            "sub_r": _surface_asset(layer, "R"),
            "sub_d": _surface_asset(layer, "D"),
            # The PRIMARY's displacement map. TWO features want it and
            # they want it under different conditions:
            #   * the sub-surface HeightLerp compares TWO heights, so the
            #     primary's map is meaningless without the sub's;
            #   * Nanite DISPLACEMENT (v1.21) needs one for every surfaced
            #     layer, whether or not that layer has a sub-surface.
            # The union is expressed HERE, once, and `d_active` below is
            # the predicate every consumer tests.
            #   * STOCHASTIC TILING (v1.26) needs it too: the engine's
            #     TextureVariation blends its cells BY HEIGHT, so a
            #     stochastic layer's _D is sampled whether or not
            #     displacement is on for the material. Today `disp_on` is
            #     true here so this changes nothing -- which is exactly
            #     why it is written down: a later recipe with
            #     displacement OFF and stochastic ON would otherwise
            #     preflight no _D and die on a KeyError AFTER the
            #     destructive clear, on an asset that was present all
            #     along.
            "surface_d": ("/Game/Surfaces/T_{0}_D".format(layer["surface"])
                          if (layer.get("surface")
                              and ((layer.get("sub_surface") or {}).get(
                                  "surface") or disp_on
                                   or layer.get("stochastic_tiling")))
                          else None),
            "sub_contrast": float((layer.get("sub_surface")
                                   or {}).get("height_contrast", 0.35)),
            # THE SUB-SURFACE PREDICATE, COMPUTED ONCE (NN24).
            #
            # Every consumer -- the graph builder, the preflight and the
            # post-build assertion -- tests THIS and nothing else. Three
            # separate spellings of "is the sub-surface active" is how
            # the assertion came to demand five textures the builder
            # never sampled, which fails AFTER the destructive clear.
            #
            # `variant_map` belongs in the predicate because the blend
            # cannot run without a selector to blend by: a bound
            # sub-surface with no selector map is not active, it is
            # misconfigured. Only layer_bands can see it, which is
            # exactly why the predicate belongs here and not in the
            # payload.
            "tri_active": bool(
                layer["name"] in set(
                    ((recipe.get("material") or {}).get("triplanar")
                     or {}).get("layers") or [])
                and layer.get("surface")),
            # `weightmap` is in the predicate too (2026-09-16, Pass 3):
            # the variant sampler is built INSIDE the weightmap branch
            # (it rides the weightmap's UV chain), so without weightmap
            # the plan would emit sub rows the graph never samples and
            # die at the post-clear assertion. main() also refuses that
            # recipe shape host-side; this keeps plan and graph derived
            # from ONE condition either way.
            "sub_active": bool(
                layer.get("surface")
                and (layer.get("sub_surface") or {}).get("surface")
                and (recipe.get("material") or {}).get("variant_map")
                and (recipe.get("material") or {}).get("weightmap")),
            # THE HEIGHT-MAP PREDICATE (v1.21). "This layer needs its
            # primary _D sampled", for EITHER reason. Deliberately a
            # superset of `sub_active`: the HeightLerp cannot run on one
            # height, so a band that is sub_active and not d_active is a
            # contradiction, and _assert_band_invariant refuses it rather
            # than letting the plan drop a sampler the graph then asks for.
            "d_active": bool(
                (layer.get("surface")
                 and (layer.get("sub_surface") or {}).get("surface")
                 and (recipe.get("material") or {}).get("variant_map")
                 and (recipe.get("material") or {}).get("weightmap"))
                or (disp_on and layer.get("surface"))
                # v1.26 — the third reason the primary _D is needed:
                # TextureVariation cuts its cell edges on height.
                or (layer.get("stochastic_tiling") and layer.get("surface"))),
            # Displacement is a WHOLE-MATERIAL feature, but the graph
            # builds its chain per band, so each band carries the flag.
            "disp_on": bool(disp_on),
            # schema v1.27 (Brief 7 Phase 1). PER-LAYER displacement.
            # `disp_amplitude_m` is this layer's peak amplitude in metres;
            # `disp_k` is the scale its centred height gets in the graph
            # relative to the engine's single Magnitude (which carries
            # amplitude_ref = the MAX layer). The payload multiplies each
            # surfaced band's (centred_height - center) by disp_k, so the
            # engine's uniform (v - Center) * Magnitude reproduces THIS
            # layer's own peak amplitude. Both None when displacement is
            # off. A band with no height map contributes `center` and is
            # never scaled, so its disp_k is inert -- the neutral is
            # preserved exactly as before (NN24: one source for "is
            # displacement on", `disp_on`).
            "disp_amplitude_m": (
                _dspec["per_layer"][layer["name"]] if _dspec else None),
            "disp_k": (
                _dspec["per_layer"][layer["name"]] / _dspec["amplitude_ref"]
                if _dspec and _dspec["amplitude_ref"] > 0.0 else None),
        })

    _attach_forest_floor(recipe, out, world_z)
    _assert_band_invariant(out)
    return out


def _attach_forest_floor(recipe, bands, world_z):
    """schema v1.11 — darken one layer across the tree elevation band.

    WHY THIS EXISTS. Beyond the conifer cull the terrain is the ONLY
    thing conveying that a forest is there, and it was rendering plain
    meadow: the 2 km verification frame measured 0.00% vegetation
    pixels. Trees at 24.7/ha with a ~4 m canopy cover 12.4% of the
    ground, so a forest at this density genuinely IS a partial tint from
    altitude rather than a solid canopy — terrain colour can carry it
    honestly.

    WHY HEIGHT ONLY, NO SLOPE TERM. The obvious mask is the conifer's
    own slope+height rule, but a slope term here would be read from the
    VERTEX NORMAL, and the comment at the weightmap branch below records
    why that is wrong: the shader normal is the DECIMATED mesh's normal,
    so it flattens with distance and every slope band drifts. A
    slope-masked tint would therefore fail at exactly the range it
    exists to serve. The host layer's own mask comes from the BAKED
    weightmap, computed once on the CPU at full heightmap resolution,
    and already carries the slope limit — so riding on that mask and
    adding only a height band keeps the tint stable at every LOD.

    This changes NO weightmap channel and NO layer count. The weightmap
    is RGB(A) with one channel per layer (place_foliage.py:308/:325
    indexes it by layer position; line ref corrected 2026-09-11), so a fourth "Forest" layer is not representable
    — and foliage placement reads that same baked weightmap, so a tint
    applied purely in the shader provably cannot move a single tree.
    """
    spec = recipe["material"].get("forest_floor")
    if not spec:
        return
    name = spec["layer"]
    target = [b for b in bands if b["name"] == name]
    if not target:
        raise ValueError(
            "forest_floor.layer is {0!r} but the material declares no such "
            "layer; layers are {1}. Refusing rather than tinting an "
            "arbitrary band.".format(name, [b["name"] for b in bands]))

    # schema v1.25 (Brief 3 Task 2, 2026-09-11): driver "weightmap_alpha"
    # -- the tint mask is the baked weightmap's ALPHA channel, which
    # derive_layer_weights fills with the CANOPY-derived forest_floor
    # weight (crown-splatted instance cover), replacing the height-band
    # proxy: the band said "trees live at these altitudes", the alpha
    # says "a tree stands here". Height fields are refused alongside the
    # driver -- two masks for one tint is the two-lists defect.
    driver = str(spec.get("driver", "height_band"))
    if driver not in ("height_band", "weightmap_alpha"):
        raise ValueError("forest_floor.driver must be height_band or "
                         "weightmap_alpha, got {0!r}".format(driver))
    if driver == "weightmap_alpha":
        if "height_m" in spec:
            raise ValueError(
                "forest_floor: driver weightmap_alpha AND height_m are "
                "both declared -- which mask is in effect cannot be read "
                "from the recipe. Delete one.")
        if not (recipe.get("material") or {}).get("weightmap"):
            raise ValueError("forest_floor.driver weightmap_alpha needs "
                             "material.weightmap")
        strength = float(spec["strength"])
        if not 0.0 <= strength <= 1.0:
            raise ValueError("forest_floor.strength must be in [0, 1], "
                             "got {0}".format(strength))
        target[0]["forest"] = {
            "driver": "weightmap_alpha",
            "tint": [float(c) for c in spec["tint"]],
            "strength": strength,
        }
        return

    h_lo, h_hi = [float(v) for v in spec["height_m"]]
    if h_hi <= h_lo:
        raise ValueError(
            "forest_floor.height_m must be increasing, got [{0}, {1}]"
            .format(h_lo, h_hi))
    f_m = float(spec.get("feather_m", 0.0))
    strength = float(spec["strength"])
    if not 0.0 <= strength <= 1.0:
        raise ValueError(
            "forest_floor.strength must be in [0, 1], got {0}".format(
                strength))
    target[0]["forest"] = {
        "z_lo": world_z(h_lo - f_m),
        "z_lo_in": world_z(h_lo),
        "z_hi_in": world_z(h_hi),
        "z_hi": world_z(h_hi + f_m),
        "tint": [float(c) for c in spec["tint"]],
        "strength": strength,
        "height_m": [h_lo, h_hi],
        "feather_m": f_m,
    }


def weightmap_uv_params(recipe):
    """Return (weightmap, variant_map, macro_map, org_x, org_y, span_cm).

    The UV mapping that turns a world XY into a weightmap texel:
    (world_xy - origin_xy) / span_cm, where span is the terrain's full
    footprint so the texture maps 1:1 onto it and never tiles.

    EXTRACTED SO THE DIAGNOSTIC CANNOT DRIFT FROM THE SHIPPING MATERIAL.
    `make_layer_debug_material.py` visualises which layer the shader picks;
    if it derived these three numbers separately and either copy changed,
    the instrument would keep working and start reporting a decision the
    shipping material never made — a confident wrong answer about exactly
    the thing it exists to check. One function decides (lesson 1.9), the
    same reason `landscape_spec` owns `derive_spec` for both ends of the
    import bracket.

    `weightmap` absent from the recipe returns None for the asset, which
    is the callers' signal to fall back to vertex-normal bands.
    """
    asset = (landscape_spec.weightmap_asset_path(recipe["biome_id"])
             if (recipe.get("material") or {}).get("weightmap") else None)
    # The selector map rides the SAME UV. Resolved here, in the one
    # function that decides the mapping, for the reason in the docstring:
    # a second copy of these numbers is a second decision that can drift.
    variant = (landscape_spec.variant_map_asset_path(recipe["biome_id"])
               if (recipe.get("material") or {}).get("variant_map")
               else None)
    macro = (landscape_spec.macro_map_asset_path(recipe["biome_id"])
             if (recipe.get("material") or {}).get("macro_variation")
             else None)
    span_cm = ((int(recipe["heightmap"]["resolution"]) - 1)
               * float(recipe["landscape"]["scale_xy_cm"]))
    org = recipe["landscape"]["location_cm"]
    return asset, variant, macro, float(org[0]), float(org[1]), span_cm


class BandInvariantError(ValueError):
    """A layer band could not produce a usable mask. Raised, never logged."""


class PayloadTransportError(ValueError):
    """The payload cannot survive UE's remote-execution transport."""


def _guard_payload(src):
    """Refuse a payload UE would silently mistake for a FILENAME.

    ENGINE BEHAVIOUR, read at the source rather than inferred
    (PythonScriptPlugin.cpp:813-830, UE 5.8):

        // The EPythonCommandExecutionMode::ExecuteFile name is misleading
        // as it is used to run literal code or a .py file.
        const TCHAR* PyFileExtension = TEXT(".py");
        int32 Pos = UE::String::FindFirst(Command, PyFileExtension);
        if (Pos == INDEX_NONE) { return false; }

    `FindFirst` scans the WHOLE command — code, comments and string
    literals alike. So a single occurrence of ".py" anywhere turns the
    entire script into a path, and the engine logs

        Could not load Python file '<engine dir>/<the whole script>'

    This actually happened on 2026-08-01. An error message added to help
    the operator —

        " -- run scripts/import_layer_textures.py first. "

    — made every run of this script fail, while every sibling script kept
    working because none of them names a .py file. Two hours went into
    payload SIZE (a real correlation: this is the largest payload in the
    repo, so it was the only one carrying such a message) before anyone
    read the engine source.

    The rule: NEVER name a .py file inside a remote-exec payload, in any
    context. Say "the import_layer_textures script", not its filename.
    """
    pos = src.find(".py")
    if pos != -1:
        start = src.rfind("\n", 0, pos) + 1
        end = src.find("\n", pos)
        line_no = src.count("\n", 0, pos) + 1
        raise PayloadTransportError(
            "payload contains '.py' at line {0}, which makes UE treat the "
            "ENTIRE script as a filename instead of running it "
            "(PythonScriptPlugin.cpp:813-830). Offending line:\n    {1}\n"
            "Remove the file extension — name the script without '.py'."
            .format(line_no, src[start:end if end != -1 else None].strip()))
    return src


def _cpu_ramp(v, edge, outer, rising):
    """CPU mirror of the payload's `_ramp`. Must stay identical to it.

    THE DEGENERATE-SPAN RULE (both copies implement this):
    a zero-width span means "no feather at this edge", so the ramp must
    become a STEP reading 1 on the INSIDE of the band. Which side is
    inside cannot be recovered from the numbers — both bounds are equal —
    so it comes from the caller via `rising`, which the shader-side
    `_ramp` accepted and then never referenced. Choosing the sign from
    `span >= 0` instead turned every degenerate FALLING edge into a
    rising step: 0 across the whole band rather than 1. Together with the
    cosine-range collapse in layer_bands() that zeroed Snow and Grass
    outright, and it made the module's "sharpness 1.0 is a hard edge"
    claim false — at sharpness 1.0 every feather is zero-width, so EVERY
    band degenerated and the material rendered 100% background.

    KEEP THIS EXPLANATION HOST-SIDE. It used to live in the payload's own
    docstring, which pushed the rendered payload from ~12.7 KB to
    ~13.6 KB and made the engine refuse it outright — UE fell back to
    treating the whole script as a FILENAME and logged "Could not load
    Python file '<engine path>/<the entire script>'". Prose inside a
    remote-exec payload is shipped over the wire on every run; comments
    are free here and expensive there.
    """
    span = edge - outer
    if abs(span) < 1e-9:
        eps = max(1e-6, abs(edge) * 1e-6)
        outer = edge - eps if rising else edge + eps
        span = edge - outer
    return min(1.0, max(0.0, (v - outer) / span))


def _cpu_band(v, lo_out, lo_in, hi_in, hi_out):
    """CPU mirror of the payload's `_band`."""
    return (_cpu_ramp(v, lo_in, lo_out, True)
            * _cpu_ramp(v, hi_in, hi_out, False))


def _cpu_heightlerp(a, b, t, ha, hb, contrast):
    """CPU mirror of the payload's `_heightlerp`. Must stay identical.

    Height-aware blend of surface A (primary) and B (sub-surface):

        wa = ha + (1 - t)
        wb = hb + t
        ma = max(wa, wb) - contrast
        b1 = max(wa - ma, 0)
        b2 = max(wb - ma, 0)
        out = (a*b1 + b*b2) / (b1 + b2)

    WHY THIS AND NOT A LINEAR LERP. Pass 2a mandates height blending, and
    the reason is that a linear alpha dissolves one surface into the
    other uniformly: at t=0.5 every pixel is 50/50 mud. A height blend
    lets the surface whose HEIGHT MAP is locally higher win, so scree
    fills the hollows between rocks and the rock's own crests stay
    exposed. The transition follows the geometry instead of ignoring it.

    WHY NOT /Engine/.../HeightLerp. It exists in 5.8 (verified on disk)
    but `MaterialEditingLibrary` exposes no accessor for a material
    function's input pins — probed against the live editor,
    `get_inputs_for_material_function` does not exist. Wiring it would
    mean GUESSING pin names, which the UE 5.8 resolution protocol
    forbids. Six arithmetic nodes I can verify beat one call I cannot.

    `contrast` > 0 always. At contrast -> 0 the blend becomes a hard
    height-ordered cut; large contrast degenerates toward a linear lerp.
    Zero is refused by the validator because `b1 + b2` collapses to 0
    wherever the two weighted heights are equal, and the divide is then
    0/0 — a NaN that propagates through base colour with no error.
    """
    # THE HEIGHT WINDOW, and it is not optional.
    #
    # The naive form (wa = ha + (1-t), wb = hb + t) FAILS AT THE
    # ENDPOINTS whenever the height maps differ strongly: at t=0 with
    # ha=0, hb=1 both weighted heights equal 1, so the blend returns
    # 0.5 — half sub-surface where the selector said NONE. The heights
    # and the alpha live on the same 0..1 scale, so height can cancel
    # alpha outright. Caught by invariant 1 before any editor contact.
    #
    # `hw` is zero at both endpoints and 1 at t=0.5, so height biases the
    # TRANSITION and can never override the decision. At t=0 the selector
    # gets the primary, always; at t=1 the sub-surface, always.
    hw = 4.0 * t * (1.0 - t)
    wa = (1.0 - t) + ha * hw
    wb = t + hb * hw
    ma = max(wa, wb) - contrast
    b1 = max(wa - ma, 0.0)
    b2 = max(wb - ma, 0.0)
    denom = b1 + b2
    if denom <= 0.0:
        # Unreachable while contrast > 0: ma is strictly below max(wa,wb),
        # so at least one of b1/b2 is positive. Asserted, not assumed.
        raise ValueError(
            "height blend denominator collapsed to 0 (wa={0}, wb={1}, "
            "contrast={2}); contrast must be > 0".format(wa, wb, contrast))
    return (a * b1 + b * b2) / denom


def _assert_heightlerp_invariants():
    """Prove the blend does what Pass 2a needs, BEFORE any editor contact.

    Four properties, each a way the blend could be wrong while still
    producing plausible-looking numbers:
    """
    fails = []

    # 1. LOAD-BEARING: HEIGHT MUST DRIVE THE BLEND. With equal alpha, the
    #    surface whose height map is locally higher must dominate. If this
    #    fails, the whole feature is a LINEAR LERP WEARING A COSTUME —
    #    which is exactly what Pass 2a rejects, and which would look
    #    entirely reasonable in any still frame. This property is why the
    #    feature exists, so it is asserted first.
    mid_flat = _cpu_heightlerp(0.0, 1.0, 0.5, 0.5, 0.5, 0.35)
    mid_b_high = _cpu_heightlerp(0.0, 1.0, 0.5, 0.1, 0.9, 0.35)
    mid_a_high = _cpu_heightlerp(0.0, 1.0, 0.5, 0.9, 0.1, 0.35)
    if not (mid_a_high < mid_flat < mid_b_high):
        fails.append("height does not drive the blend at t=0.5: "
                     "a_high={0:.4f} flat={1:.4f} b_high={2:.4f}"
                     .format(mid_a_high, mid_flat, mid_b_high))

    # 2. Endpoints resolve fully, for EVERY height configuration. A blend
    #    that never fully resolves leaves both surfaces permanently mixed.
    #
    #    THIS IS THE ASSERTION THAT FIRED on the standard formulation
    #    (wa = ha + (1-t), wb = hb + t): at t=0 with ha=0, hb=1 it
    #    returned 0.5 — half sub-surface where the selector said NONE.
    #    Height cancelled alpha outright at the decision boundary. See
    #    the `hw` window above and R2 REJECTED.
    for ha, hb in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.7, 0.3)):
        lo = _cpu_heightlerp(0.0, 1.0, 0.0, ha, hb, 0.35)
        hi = _cpu_heightlerp(0.0, 1.0, 1.0, ha, hb, 0.35)
        if lo > 0.02:
            fails.append("t=0 did not resolve to the primary "
                         "(ha={0}, hb={1}) -> {2:.4f}".format(ha, hb, lo))
        if hi < 0.98:
            fails.append("t=1 did not resolve to the sub-surface "
                         "(ha={0}, hb={1}) -> {2:.4f}".format(ha, hb, hi))

    # 3. MONOTONIC in t. A non-monotonic blend flickers as the selector
    #    ramps, which reads as shimmer along every transition.
    prev = None
    for i in range(51):
        t = i / 50.0
        v = _cpu_heightlerp(0.0, 1.0, t, 0.3, 0.6, 0.35)
        if prev is not None and v < prev - 1e-9:
            fails.append("not monotonic in t at t={0:.2f}".format(t))
            break
        prev = v

    # 4. BOUNDED. The output must never leave [A, B]; an overshoot shows
    #    as a bright or black fringe along transitions.
    for i in range(21):
        t = i / 20.0
        v = _cpu_heightlerp(0.0, 1.0, t, 0.85, 0.15, 0.05)
        if v < -1e-6 or v > 1.0 + 1e-6:
            fails.append("out of bounds at t={0:.2f}: {1:.6f}".format(t, v))
            break

    return fails


def _cpu_disp_band(centred, k, center):
    """CPU mirror of the per-layer displacement scale (schema v1.27).

    The graph applies, per surfaced band, to its centred height sample:

        val = center + (centred - center) * k

    where k = amplitude_layer / amplitude_ref and the engine's single
    displacement_scaling.magnitude carries amplitude_ref (the MAX layer,
    `displacement_spec`). Because the scale acts on the DEVIATION from
    `center`, a pixel that supplies no height (or the fully-mipped value,
    which `_centred_height` maps to `center`) reads `center` and moves by
    nothing whatever k is — the degraded state stays the identity.
    """
    return center + (centred - center) * k


def _assert_displacement_invariants():
    """Prove the per-layer displacement scale, BEFORE any editor contact.

    Five properties, each a way the scale could be wrong while still
    compiling and rendering a plausible surface. The engine realises
    Displacement = (v - Center) * Magnitude
    (NaniteRasterizationCommon.ush:568), so an error here is a per-layer
    relief that is silently too strong or too weak — exactly the class the
    stills gate would only catch after a full world rebuild.
    """
    fails = []
    c = 0.5

    # 1. THE REFERENCE LAYER IS UNTOUCHED. k == 1 must be the identity, or
    #    the layer that sets the engine Magnitude would itself be re-scaled
    #    and NOTHING would carry amplitude_ref. Asserted first because it
    #    is the property the whole "MAX carries the magnitude" scheme rests
    #    on.
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        if abs(_cpu_disp_band(v, 1.0, c) - v) > 1e-12:
            fails.append("k=1 is not the identity at centred={0}".format(v))

    # 2. NEUTRAL PRESERVED FOR EVERY k. A sample at `center` (no height /
    #    fully-mipped) must stay at `center` — this is why the scale acts
    #    on the deviation and not on the raw value. If it failed, a
    #    map-less layer would take a constant Z step that reads as a seam.
    for k in (0.0, 0.1, 0.15, 0.5, 1.0):
        if abs(_cpu_disp_band(c, k, c) - c) > 1e-12:
            fails.append("center did not stay center at k={0}".format(k))

    # 3. SAME SIDE, SCALED TOWARD center. For a peak above center and
    #    0 < k < 1 the result must lie strictly between center and the
    #    unscaled value: a sign flip or an overshoot is a relief that
    #    inverts or exceeds the layer's own amplitude.
    for k in (0.1, 0.15, 0.3):
        up = _cpu_disp_band(1.0, k, c)
        dn = _cpu_disp_band(0.0, k, c)
        if not (c < up < 1.0):
            fails.append("above-center peak not scaled toward center at "
                         "k={0}: {1:.4f}".format(k, up))
        if not (0.0 < dn < c):
            fails.append("below-center peak not scaled toward center at "
                         "k={0}: {1:.4f}".format(k, dn))

    # 4. LINEAR IN k. Doubling k must double the deviation, or the metres
    #    the recipe declares would not map linearly onto engine amplitude.
    dev_k = _cpu_disp_band(1.0, 0.15, c) - c
    dev_2k = _cpu_disp_band(1.0, 0.30, c) - c
    if abs(dev_2k - 2.0 * dev_k) > 1e-12:
        fails.append("deviation is not linear in k")

    # 5. INDEPENDENT: END-TO-END METRES. Reference implementation, NOT the
    #    scale function — push the layer's peak deviation through the FULL
    #    chain (this scale, then the engine's (v-Center)*Magnitude, then the
    #    proxy vertical scale) and demand it comes out equal to the layer's
    #    own declared amplitude in metres. Magnitude is recomputed here from
    #    amplitude_ref rather than read from `displacement_spec`, so a bug
    #    shared between the scale and the reducer cannot pass both (NN8 /
    #    the material-builder "property 7" rule).
    for amp, amp_ref, scale_z in ((0.02, 0.20, 500.0),
                                  (0.06, 0.20, 500.0),
                                  (0.20, 0.20, 500.0),
                                  (0.03, 0.20, 400.0)):
        k = amp / amp_ref
        magnitude_ref = 2.0 * amp_ref * 100.0 / scale_z   # engine units
        v_peak = _cpu_disp_band(center=c, k=k, centred=c + 0.5)  # full up
        local = (v_peak - c) * magnitude_ref                 # engine local
        metres = local * scale_z / 100.0                     # proxy re-scale
        if abs(metres - amp) > 1e-9:
            fails.append(
                "end-to-end metres != declared amplitude "
                "(amp={0}, ref={1}, scale_z={2}): got {3:.6f}".format(
                    amp, amp_ref, scale_z, metres))

    return fails


def _assert_height_blend_invariants():
    """Prove the height-weighted blend, BEFORE any editor contact.

    The reweighting redistributes weight among the STORED layers by height
    and MUST leave the partition intact -- if it did not, the meadow
    remainder (1 - sum(stored)) would move and the world would repaint, or
    a texel would go all-zero and render the flat background constant (the
    same class the 92%-background-constant defect fell into).
    """
    fails = []
    k, eps = 4.0, 0.02
    cases = [
        [0.4, 0.3, 0.2, 0.1],
        [0.25, 0.25, 0.25, 0.25],
        [0.7, 0.1, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],   # pure remainder
        [0.5, 0.5, 0.0, 0.0],
    ]
    heights = [0.2, 0.8, 0.5, 0.1]

    # 1. SUM (and therefore the meadow remainder) PRESERVED. This is the
    #    load-bearing property: the reweighting may move weight BETWEEN
    #    stored layers but may not change how much the stored layers hold
    #    in total, or meadow's 1 - sum(stored) shifts under it.
    for base in cases:
        out = _cpu_height_blend(base, heights, k, eps)
        if abs(sum(out) - sum(base)) > 1e-6:
            fails.append("sum not preserved for base=%s: %.8f vs %.8f"
                         % (base, sum(out), sum(base)))
        # remainder preserved is the same statement, asserted explicitly
        if abs((1.0 - sum(out)) - (1.0 - sum(base))) > 1e-6:
            fails.append("meadow remainder moved for base=%s" % (base,))

    # 2. NO NaN / all-zero at a pure-remainder texel (all stored 0). The
    #    guard must return 0, not 0/0 -> NaN which would propagate through
    #    every downstream lerp.
    out0 = _cpu_height_blend([0.0, 0.0, 0.0, 0.0], heights, k, eps)
    if any(o != 0.0 for o in out0):
        fails.append("pure-remainder texel did not resolve to 0: %s" % out0)

    # 3. HEIGHT DRIVES THE BLEND (independent reference: the ORDERING, not
    #    the code's own output). Equal weights, unequal heights -> the
    #    higher surface takes strictly more, and they still sum to the
    #    original total. If this fails the feature is inert.
    out = _cpu_height_blend([0.5, 0.5], [0.2, 0.8], k, eps)
    if not (out[1] > out[0]):
        fails.append("height does not drive the blend: %s" % out)
    if abs(sum(out) - 1.0) > 1e-6:
        fails.append("equal-weight pair did not preserve sum: %s" % out)

    # 4. EPS FLOOR: a zero-height stored layer with positive weight keeps a
    #    positive (non-vanishing) share -- eps is what stops a low surface
    #    from being deleted rather than merely de-emphasised.
    out = _cpu_height_blend([0.5, 0.5], [0.0, 1.0], k, eps)
    if not (out[0] > 0.0):
        fails.append("eps floor failed: zero-height layer vanished: %s" % out)

    # 5. k -> LARGER is MORE height-selective (monotone in k): the
    #    higher-height layer's share must not DECREASE as k rises.
    lo = _cpu_height_blend([0.5, 0.5], [0.3, 0.7], 2.0, eps)
    hi = _cpu_height_blend([0.5, 0.5], [0.3, 0.7], 8.0, eps)
    if hi[1] < lo[1] - 1e-9:
        fails.append("blend not monotone in k: k2=%s k8=%s" % (lo, hi))

    return fails


class CpuModelInvariantError(AssertionError):
    """The CPU model of a shader construct violates a physical property."""


def _assert_cpu_model_invariants():
    """RUN both invariant suites and RAISE. Fires at import, below.

    THE SUITES EXISTED AND NEVER RAN. `_assert_triplanar_invariants` and
    `_assert_heightlerp_invariants` were both written, both correct, and
    both dead — each RETURNS a failure list, and no caller ever asked for
    it. RECIPES.md R2 meanwhile stated the heightlerp properties were
    "proven by `_assert_heightlerp_invariants()` before" the build. The
    prose was the only thing holding the claim up.

    That is constitution rule (e) in its exact form: a lesson that exists
    and does not fire is a defect in the lesson. A gate that exists and
    does not RUN is not a weaker gate — it is zero gate wearing the
    documentation of one, and it is worse than none, because RECIPES.md
    cited it.

    Import time is the right moment: both suites are pure arithmetic over
    ~13k sampled normals and a 21-step sweep, they touch no editor and no
    file, and they must hold before ANY caller — builder, validator, or
    an interactive import — gets to use the module.
    """
    fails = []
    fails.extend(_assert_triplanar_invariants() or [])
    fails.extend(_assert_heightlerp_invariants() or [])
    # Found by the NN4 sweep for this same defect class: a THIRD suite in
    # this file, reporting by return value, with no call site anywhere in
    # `scripts/`. It proves the plan reducer refuses three bad
    # declarations AND accepts the shipping shape — both directions, and
    # neither had ever been exercised outside its author's terminal.
    fails.extend(assert_texture_plan_gates() or [])
    # schema v1.27 (Brief 7 Phase 1). The per-layer displacement scale is
    # pure arithmetic baked into the graph per band; its five properties
    # (reference-layer identity, neutral preservation, same-side scaling,
    # linearity in k, and an INDEPENDENT end-to-end metres check) hold
    # before any editor contact, same as the other suites.
    fails.extend(_assert_displacement_invariants() or [])
    # schema v1.28 (Brief 7 Phase 1 addendum). The height-weighted blend is
    # pure arithmetic over the stored masks; its properties (sum/remainder
    # preserved, no NaN at a pure-remainder texel, height drives the blend,
    # eps floor, monotone in k) hold before any editor contact.
    fails.extend(_assert_height_blend_invariants() or [])
    if fails:
        raise CpuModelInvariantError(
            "{0} CPU-model invariant(s) violated; the shader these model "
            "would be wrong in a way that COMPILES AND RENDERS:\n  - {1}"
            .format(len(fails), "\n  - ".join(fails)))


_assert_cpu_model_invariants()


def _assert_band_invariant(bands):
    """Refuse bands that cannot produce a usable mask, before ANY editor
    contact.

    This evaluates the SAME arithmetic the shader will, on the CPU, and
    asserts the only property that actually matters:

        the mask reads ~1 in the middle of the band, and ~0 far outside it.

    An earlier version of this check tested the ORDERING of the bounds
    instead. That is a proxy, and it was wrong twice over: it rejected a
    legitimate `blend_sharpness: 1.0` (a hard edge is a zero-width span,
    which `_ramp` handles correctly), while a non-strict version would
    have passed the very bug this exists to catch. Test the behaviour, not
    a stand-in for it.

    WHY IT EXISTS. The material shipped, compiled clean, rendered, and was
    wrong: Snow's and Grass's slope masks were identically ZERO over the
    entire terrain, so ~92% of the landscape was painted by the flat
    background constant. Nothing errored - every constant reached the
    shader with the correct magnitude and the graph compiled. It took a
    numpy simulation of the node graph to see it at all. This check is
    pure arithmetic on values already in hand: no editor, no shader
    compile, no capture (lesson 2.1 - a correct number from a wrong
    premise produces confident, wrong output).
    """
    for b in bands:
        # v1.21. `d_active` is a SUPERSET of `sub_active` by construction
        # in layer_bands. Assert it rather than trust it: if the two ever
        # part, the plan omits the primary's height map while still
        # emitting the sub's, and the HeightLerp is handed one height
        # instead of two — which is a silent linear lerp, not an error
        # (see _ll_wire's note on unconnected inputs keeping defaults).
        if b.get("sub_active") and not b.get("d_active"):
            raise BandInvariantError(
                "layer {0!r} is sub_active but not d_active. The "
                "sub-surface HeightLerp compares the PRIMARY's height map "
                "against the SUB's, so dropping the primary's would turn a "
                "height blend into a linear lerp with no error anywhere. "
                "These two predicates are computed together in "
                "layer_bands and must not be edited apart.".format(
                    b["name"]))
        # A layer that needs a height map must carry its path. The plan
        # reducer refuses this too, but it refuses at plan time and this
        # refuses at band time — the earlier the better, and this one
        # names the layer.
        if b.get("d_active") and not b.get("surface_d"):
            raise BandInvariantError(
                "layer {0!r} is d_active but carries no surface_d path. "
                "Either the predicate is wrong or the layer declares no "
                "`surface`; both are recipe faults, refused before any "
                "editor contact.".format(b["name"]))
        for axis, lo_out, lo_in, hi_in, hi_out in (
                ("slope (cos of normal.z)", b["cos_lo"], b["cos_lo_in"],
                 b["cos_hi_in"], b["cos_hi"]),
                ("height (world cm)", b["z_lo"], b["z_lo_in"],
                 b["z_hi_in"], b["z_hi"])):
            inside = _cpu_band(0.5 * (lo_in + hi_in),
                               lo_out, lo_in, hi_in, hi_out)
            if inside < 0.999:
                raise BandInvariantError(
                    "layer {0!r} {1}: the mask reads {2:.6f} at the CENTRE "
                    "of its own band, not 1. Bounds were outer_lo={3!r} "
                    "inner_lo={4!r} inner_hi={5!r} outer_hi={6!r}. A band "
                    "that does not read 1 inside itself never renders - "
                    "the background shows through instead, with a clean "
                    "compile and no error anywhere. That is exactly how "
                    "Snow and Grass vanished on 2026-08-01.".format(
                        b["name"], axis, inside,
                        lo_out, lo_in, hi_in, hi_out))
            width = abs(hi_out - lo_out)
            outside = max(
                _cpu_band(lo_out - 0.5 * width - 1.0,
                          lo_out, lo_in, hi_in, hi_out),
                _cpu_band(hi_out + 0.5 * width + 1.0,
                          lo_out, lo_in, hi_in, hi_out))
            if outside > 0.001:
                raise BandInvariantError(
                    "layer {0!r} {1}: the mask reads {2:.6f} well OUTSIDE "
                    "its band, not 0 - the ramp is inverted, so this layer "
                    "would paint everywhere it should not.".format(
                        b["name"], axis, outside))


def _payload(asset_path, bands, assign, actor_name,
             weightmap=None, variantmap=None, macromap=None,
             plan=None, tri=None, macro=None, disp=None, hblend=None,
             org_x=0.0, org_y=0.0,
             span_cm=1.0, grass=None,
             max_pivot=landscape_spec.MAX_PIVOT_OFFSET_M,
             max_base_z=landscape_spec.MAX_BASE_OFFSET_M):
    # `max_pivot` defaults to the SHARED constant (ruling c, one copy
    # decides) so a call site that forgets to thread it still gets the
    # same limit as place_foliage, never a divergent one.
    rendered = '''
import json as _json
import unreal as _unreal
import os as _os
import sys as _sys
# ⭐ ll_must IS IMPORTED, NOT PASTED. ue_exec stages it beside this
# payload; MODE_EXEC_FILE gives us __file__, so the stage dir is on the
# path below. Placed HERE, at the top, so a staging failure raises
# before any graph is touched rather than half way through a build.
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ll_must as _ll_must

_asset_path = {asset!r}
_bands = _json.loads({bands!r})
# schema v1.7 grass-system species, already resolved host-side by
# grass_entries(): asset path, mesh, layer index, engine-unit density.
_grass = _json.loads({grass!r})
_MAX_PIVOT_M = float({max_pivot})
_MAX_BASE_Z_M = float({max_base_z})
_weightmap = {weightmap!r}
# the weightmap channel contract, injected from WEIGHTMAP_CHANNELS so
# the shader and the CPU surface lookup read ONE declaration (NN24)
_CHAN = {chan!r}
# The VARIANT map's channels -- a DIFFERENT texture from the weightmap,
# baked one channel per layer in recipe order by make_variant_map (RGB).
# Kept separate from _CHAN because sharing the list is what raised
# IndexError mid-clear on 2026-09-12.
_VCHAN = {vchan!r}
_variantmap = {variantmap!r}
_macromap = {macromap!r}
_plan = _json.loads({plan!r})
_tri = _json.loads({tri!r})
_macro = _json.loads({macro!r})
# v1.21. None when displacement is off. The reducer that produced this
# (displacement_spec) owns the metres -> engine-magnitude conversion; the
# payload never does unit arithmetic of its own.
_disp = _json.loads({disp!r})
# schema v1.28 (Brief 7 Phase 1 addendum). None when height-blend is off
# (absent or k==0). {{"k","eps"}}. The stored-layer masks are scaled by
# (raw_height + eps)**k and renormalised to preserve their sum, so the
# meadow remainder is unchanged; the CPU mirror is _cpu_height_blend.
_hblend = _json.loads({hblend!r})
_org_x = {org_x!r}
_org_y = {org_y!r}
_span_cm = {span_cm!r}
_assign = {assign!r}
_actor_name = {actor!r}

_out = {{"ok": False, "created": False, "assigned": False}}
_pkg, _name = _asset_path.rsplit("/", 1)

if _unreal.EditorAssetLibrary.does_asset_exist(_asset_path):
    _mat = _unreal.EditorAssetLibrary.load_asset(_asset_path)
else:
    _mat = _unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        _name, _pkg, _unreal.Material, _unreal.MaterialFactoryNew())
    _out["created"] = True

# TEXTURE PRE-FLIGHT, before anything destructive.
# delete_all_material_expressions() empties the LIVE graph. If a texture
# turned out to be missing after that point, the payload would die with
# the material left blank in memory and dirty: the terrain renders
# untextured immediately, and any later "Save All" (or an editor-close
# save prompt) persists the blank material over a good one on disk.
# So every texture asset is resolved FIRST and the run refuses without
# touching the asset at all.
_textures = {{}}
_fatal = None
if _mat is None:
    _fatal = "could not find or create material"
else:
    _missing = []
    # PROJECTION 1 OF THE DECLARATION — the preflight.
    #
    # Iterates THE PLAN. There is no second list of band keys here: a
    # texture reaches the graph only if it is in the plan, and the plan
    # is the same object the assertion projects from. This is what makes
    # "assertion updated, preflight forgotten" unrepresentable rather
    # than merely discouraged (non-negotiable 24).
    #
    # It ALSO checks the asset's import settings against the class the
    # declaration assigned. That is what makes the compression/srgb
    # columns live rather than decorative, and it moves sampler-type
    # enforcement to BEFORE the destructive clear: a class mismatch is
    # now a refusal, not a crash mid-rebuild.
    _badclass = []
    for _r in _plan:
        _p = _r[5]
        if _p in _textures or _p in _missing:
            continue
        _t = _unreal.EditorAssetLibrary.load_asset(_p)
        if _t is None:
            _missing.append(_p)
            continue
        _want_comp, _want_srgb = _r[6], _r[7]
        _got_comp = str(_t.get_editor_property("compression_settings"))
        _got_srgb = bool(_t.get_editor_property("srgb"))
        # CASE-INSENSITIVE, deliberately. The two importers in this repo
        # spell the same enum differently -- import_surface_set uses the
        # C++ form ("TC_Default"), import_layer_textures the reflected
        # Python form ("TC_VECTOR_DISPLACEMENTMAP") -- and the engine
        # reflects it as <TextureCompressionSettings.TC_DEFAULT: 0>.
        # Comparing raw strings makes this gate fire on every texture in
        # the material, which is exactly what it did on first run.
        # Normalising is honest here: the enum IDENTITY is the fact, its
        # spelling is not.
        def _norm_enum(_v):
            return str(_v).split(".")[-1].split(":")[0].strip().upper(
                ).replace("_", "")
        _comp_ok = _norm_enum(_got_comp) == _norm_enum(_want_comp)
        if not _comp_ok or _got_srgb != _want_srgb:
            _badclass.append(
                _p + " is declared class '" + _r[2] + "' (expects "
                + _want_comp + ", srgb=" + str(_want_srgb)
                + ") but the asset reads back " + _got_comp
                + ", srgb=" + str(_got_srgb))
        else:
            _textures[_p] = _t

    if _badclass:
        _fatal = ("sampler CLASS mismatch, refused BEFORE the graph clear: "
                  + " | ".join(_badclass)
                  + ". Either the declaration names the wrong class for "
                    "this texture, or the asset was imported with the "
                    "wrong compression/sRGB. The material was NOT "
                    "modified.")
    elif _missing:
        _fatal = ("texture asset(s) not found: " + ", ".join(_missing)
                  + " -- run the import_layer_textures script first. "
                    "The material was NOT modified.")

if _fatal is not None:
    _out["error"] = _fatal
else:
    _mel = _unreal.MaterialEditingLibrary
    # SHARED UTILITY (the material_graph module). This clear used to be
    # implemented inline here, correctly -- and the identical trap then
    # recurred in the foliage builder, which had never been swept. As of
    # 2026-08-03 a per-script copy of this logic is itself a REJECTED
    # pattern; there is one implementation and every builder calls it.
    #
    # The original reasoning, preserved because it names the mechanism:
    # delete_all_material_expressions does NOT delete all material
    # expressions. Custom-output nodes (MaterialExpressionCustomOutput
    # subclasses, of which LandscapeGrassOutput is one) survive it, so
    # each rebuild was adding a SECOND grass node beside the first until
    # the material stopped compiling with "The material can contain only
    # one Landscape Grass node". A clear-then-rebuild is only idempotent
    # if the clear is total, and "delete_all_X" is a name, not a
    # guarantee.
    _out["clear"] = _ll_clear_graph(_mel, _mat)
    _residual = _out["clear"]["remaining"]
    _out["expressions_after_clear"] = _residual
    if _residual:
        _out["error"] = ("material graph still holds expressions after an "
                         "explicit total clear -- refusing to rebuild on "
                         "top of debris")
        raise RuntimeError(_out["error"])

    def _n(_cls, _x, _y):
        return _mel.create_material_expression(_mat, _cls, _x, _y)

    def _c(_v, _x, _y):
        _e = _n(_unreal.MaterialExpressionConstant, _x, _y)
        _e.set_editor_property("r", float(_v))
        return _e

    # DEFINED HERE, BESIDE ITS DEPENDENCIES, BECAUSE THE PAYLOAD RUNS
    # TOP-TO-BOTTOM. This was defined ~400 lines below its first use
    # (the triplanar slope mask), so every build raised NameError
    # before touching the graph -- and because the clear runs first,
    # it left the material EMPTY IN MEMORY while the disk copy stayed
    # good. A function used at line 202 and defined at line 599 is a
    # forward reference that Python only forgives inside another def.
    def _ramp(_src, _edge, _outer, _x, _y, _rising):
        # 0 at outer, 1 at edge. Degenerate span => step, side from
        # _rising. See _cpu_ramp host-side for the full reasoning.
        _span = _edge - _outer
        if abs(_span) < 1e-9:
            _eps = max(1e-6, abs(_edge) * 1e-6)
            _outer = _edge - _eps if _rising else _edge + _eps
            _span = _edge - _outer
        _sub = _n(_unreal.MaterialExpressionSubtract, _x, _y)
        _ll_wire(_mel, _src, "", _sub, "A")
        _ll_wire(_mel, _c(_outer, _x - 200, _y + 70),
                                          "", _sub, "B")
        _div = _n(_unreal.MaterialExpressionDivide, _x + 200, _y)
        _ll_wire(_mel, _sub, "", _div, "A")
        _ll_wire(_mel, _c(_span, _x, _y + 140),
                                          "", _div, "B")
        _sat = _n(_unreal.MaterialExpressionSaturate, _x + 400, _y)
        _ll_wire(_mel, _div, "", _sat, "")
        return _sat

    def _c3(_rgb, _x, _y):
        _e = _n(_unreal.MaterialExpressionConstant3Vector, _x, _y)
        _e.set_editor_property("constant", _unreal.LinearColor(
            float(_rgb[0]), float(_rgb[1]), float(_rgb[2]), 1.0))
        return _e

    _normal = _n(_unreal.MaterialExpressionVertexNormalWS, -2200, -400)
    _nz = _n(_unreal.MaterialExpressionComponentMask, -1950, -400)
    _nz.set_editor_property("r", False)
    _nz.set_editor_property("g", False)
    _nz.set_editor_property("b", True)
    _nz.set_editor_property("a", False)
    _ll_wire(_mel, _normal, "", _nz, "")

    _wp = _n(_unreal.MaterialExpressionWorldPosition, -2200, 200)
    # ⛔ WORLD-Z IS BUILT ONLY WHERE IT IS READ. It feeds exactly two
    # paths: the height-band masks (taken only when there is NO baked
    # weightmap) and a forest_floor tint driven by a height band. With a
    # weightmap and a `weightmap_alpha` tint, NOTHING reads it -- the
    # node sat in the graph reachable from no output.
    #
    # Caught by audit_material_connectivity on 2026-09-12, and
    # PRE-EXISTING: it dates from forest_floor moving to weightmap_alpha
    # (v1.25, 2026-09-11), which set `_fb = _wsamp` and left this as the
    # last reader. It went unseen because the connectivity audit needs a
    # live editor and was not re-run after that change.
    #
    # A node contributing to nothing is the inert-field class in graph
    # form -- it reads like part of the computation and is not.
    # ⛔ USE dict(), NEVER AN EMPTY BRACE PAIR. This payload is a
    # .format() TEMPLATE, so a literal brace is a replacement field and
    # an empty pair raised "Replacement index 0 out of range" at format
    # time -- twice: once in the code, then again in the COMMENT that
    # explained it, because .format() does not skip Python comments.
    # Doubling the braces also works and is the convention elsewhere in
    # this template, but it is one careless edit away from breaking
    # again. dict() cannot be got wrong, and neither can prose that
    # never types the character.
    _need_wz = (not _weightmap) or any(
        ((_b.get("forest") or dict()).get("driver") or "height_band")
        != "weightmap_alpha"
        for _b in _bands if _b.get("forest"))
    _wz = None
    if _need_wz:
        _wz = _n(_unreal.MaterialExpressionComponentMask, -1950, 200)
        _wz.set_editor_property("r", False)
        _wz.set_editor_property("g", False)
        _wz.set_editor_property("b", True)
        _wz.set_editor_property("a", False)
        _ll_wire(_mel, _wp, "", _wz, "")

    # World-space UV source, shared by every textured layer: the XY of
    # absolute world position, in centimetres. Divided per layer by the
    # tiling distance to get a repeat every N metres.
    _wxy = _n(_unreal.MaterialExpressionComponentMask, -1950, 500)
    _wxy.set_editor_property("r", True)
    _wxy.set_editor_property("g", True)
    _wxy.set_editor_property("b", False)
    _wxy.set_editor_property("a", False)
    _ll_wire(_mel, _wp, "", _wxy, "")

    # ⭐ STOCHASTIC TILING, schema v1.26. One slot, set by the band loop
    # before a band's samples are built and cleared after, so
    # `_sample_typed` needs no new argument at its eight call sites. Do
    # NOT use a brace literal anywhere in this payload -- it is a
    # .format() template and a literal brace is a replacement field.
    _stoch_uv = dict(node=None)
    _STOCH_FN = ("/Engine/Functions/Engine_MaterialFunctions03/Texturing/"
                 "TextureVariation")

    def _build_stochastic(_B, _x, _y):
        """The engine TextureVariation call for one band, or None.

        EVERY input is wired EXPLICITLY from the recipe. The function's
        own preview defaults are NOT relied on: `Vector4f` exposes no
        components to Python, so a default here would be a value nobody
        could read back, which is the inert-field class. Pipeline rule 2
        -- the recipe owns every scene parameter -- applies to an engine
        function's inputs exactly as it does to ours.
        """
        _spec = _B.get("stochastic")
        if not _spec:
            return None
        if _B.get("tri_active"):
            # The side planes carry their own UVs and would bypass the
            # shifted ones, so the layer would tile stochastically on Z
            # and plainly on X/Y. REFUSE rather than ship a half-applied
            # effect that renders and is wrong.
            raise RuntimeError(
                "layer " + str(_B.get("name")) + " declares BOTH "
                "stochastic_tiling and triplanar. The triplanar side "
                "planes build their own UVs and would not receive the "
                "shifted ones. Untested combination -- refusing.")
        if not _unreal.EditorAssetLibrary.does_asset_exist(_STOCH_FN):
            raise RuntimeError(
                "no material function at " + _STOCH_FN + ". 5.8 ships no "
                "hex-tiling function; this is the UV-domain one the "
                "sweep was measured on.")
        _fn = _unreal.EditorAssetLibrary.load_asset(_STOCH_FN)
        _call = _n(_unreal.MaterialExpressionMaterialFunctionCall, _x, _y)
        _call.set_material_function(_fn)
        # the plain world-UV divide this band would otherwise have used
        _uv0 = _n(_unreal.MaterialExpressionDivide, _x - 320, _y)
        _ll_wire(_mel, _wxy, "", _uv0, "A")
        _ll_wire(_mel, _c(_B["uv_detail_cm"], _x - 520, _y + 90), "",
                 _uv0, "B")
        _ll_wire(_mel, _uv0, "", _call, "UVs")
        # The HEIGHTMAP is what the function blends cells by. This layer
        # has a real displacement map; without it the blend has nothing
        # to cut on and falls back to a straight cell boundary.
        _hm = _B.get("surface_d")
        if not _hm:
            raise RuntimeError(
                "layer " + str(_B.get("name")) + " declares "
                "stochastic_tiling but binds no displacement map. "
                "TextureVariation blends cells BY HEIGHT; without one "
                "the cell edges are straight cuts.")
        _to = _n(_unreal.MaterialExpressionTextureObject, _x - 320, _y + 260)
        _to.set_editor_property("texture", _textures[_hm])
        _ll_wire(_mel, _to, "", _call, "Heightmap")
        _ll_wire(_mel, _c(float(_spec["variation_scale"]), _x - 320,
                          _y + 420), "", _call, "Variation Scale")
        _ll_wire(_mel, _c(float(_spec["variation_levels"]), _x - 320,
                          _y + 500), "", _call, "Variation Levels")
        _ll_wire(_mel, _c(float(_spec["heightmap_influence"]), _x - 320,
                          _y + 580), "", _call, "Heightmap Influence")
        # Mask Channel selects which channel of the heightmap to read.
        # Our displacement maps are single-channel grey, so R.
        _mc = _n(_unreal.MaterialExpressionConstant4Vector, _x - 320,
                 _y + 660)
        _mc.set_editor_property("constant", _unreal.LinearColor(
            1.0, 0.0, 0.0, 0.0))
        _ll_wire(_mel, _mc, "", _call, "Mask Channel")
        _bools = (("Random Rotation and Scale",
                   "random_rotation_and_scale"),
                  ("Use Dither", "use_dither"),
                  ("HQ Edge Comparison", "hq_edge_comparison"))
        for _bi in range(len(_bools)):
            _nm, _key = _bools[_bi]
            _sb = _n(_unreal.MaterialExpressionStaticBool, _x - 320,
                     _y + 740 + 60 * _bi)
            _sb.set_editor_property("value", bool(_spec[_key]))
            _ll_wire(_mel, _sb, "", _call, _nm)
        return _call

    # =============================================================
    # TRIPLANAR (schema v1.18). Built ONCE, shared by every layer that
    # declares it — the slope mask enters here and NOWHERE else, so it
    # cannot be applied twice (the reviewed design applied it twice on
    # the normal channel and once on colour; here there is no second
    # entry point to duplicate).
    #
    # RULED: detail ALBEDO only, three planes, the existing top-down
    # sample reused AS the Z plane. +4 fetches, not +12.
    #
    # NN26 permits the vertex normal here: this is SHADING (how to
    # project a surface already selected), not SELECTION. As the normal
    # flattens with distance the projection weighting softens — and it
    # softens exactly where UV stretching is already sub-pixel. The
    # degradation lands where it does not matter.
    # =============================================================
    _tri_w = None
    if _tri:
        # Cosines are computed HOST-SIDE (see _tri_spec) for the same
        # reason layer_bands does it: the payload has no math module, and
        # a trig call is a scene parameter's derivation, not the shader's
        # job. The shader compares the world normal's Z, which IS the
        # cosine of the slope.
        _cos_lo = _tri["cos_lo"]
        _cos_hi = _tri["cos_hi"]
        # m: 0 below lo, 1 above hi. _ramp is the SAME feather the layer
        # bands use, so slope feels identical everywhere in this material.
        _m = _ramp(_nz, _cos_hi, _cos_lo, -1700, -700, False)

        _an = _n(_unreal.MaterialExpressionAbs, -1950, -900)
        _ll_wire(_mel, _normal, "", _an, "")

        def _axis(_pin, _y):
            _c1 = _n(_unreal.MaterialExpressionComponentMask, -1700, _y)
            _c1.set_editor_property("r", _pin == "r")
            _c1.set_editor_property("g", _pin == "g")
            _c1.set_editor_property("b", _pin == "b")
            _c1.set_editor_property("a", False)
            _ll_wire(_mel, _an, "", _c1, "")
            # sharpness as repeated multiply: the exponent is a recipe
            # value in [1, 8] and Power on a possibly-zero base is the
            # kind of edge case that renders as NaN rather than an error.
            _acc = _c1
            for _k in range(int(round(float(_tri["sharpness"]))) - 1):
                _mm = _n(_unreal.MaterialExpressionMultiply,
                         -1500 + _k * 60, _y)
                _ll_wire(_mel, _acc, "", _mm, "A")
                _ll_wire(_mel, _c1, "", _mm, "B")
                _acc = _mm
            return _acc

        _wx = _axis("r", -1100)
        _wy = _axis("g", -900)
        _wz_axis = _axis("b", -700)
        # THE MASK ENTERS ONCE, on the two SIDE weights only. At m=0 the
        # blend collapses to sZ*wz/wz = sZ, i.e. bit-for-bit the current
        # top-down rendering below the threshold. That identity is the
        # regression guarantee and is asserted on the CPU.
        _wxm = _n(_unreal.MaterialExpressionMultiply, -1300, -1100)
        _ll_wire(_mel, _wx, "", _wxm, "A")
        _ll_wire(_mel, _m, "", _wxm, "B")
        _wym = _n(_unreal.MaterialExpressionMultiply, -1300, -900)
        _ll_wire(_mel, _wy, "", _wym, "A")
        _ll_wire(_mel, _m, "", _wym, "B")

        _d1 = _n(_unreal.MaterialExpressionAdd, -1100, -1000)
        _ll_wire(_mel, _wxm, "", _d1, "A")
        _ll_wire(_mel, _wym, "", _d1, "B")
        _den = _n(_unreal.MaterialExpressionAdd, -950, -900)
        _ll_wire(_mel, _d1, "", _den, "A")
        _ll_wire(_mel, _wz_axis, "", _den, "B")
        # _den cannot reach 0: m=0 only where N.z >= cos(lo), so wz > 0;
        # with m=1 a unit normal gives wx+wy+wz >= 1/3 for sharpness 2.
        _tri_w = (_wxm, _wym, _wz_axis, _den, _m)

        # Side-plane UVs. X plane reads (world Y, world Z); Y plane reads
        # (world X, world Z). The Z plane is the existing _wxy.
        _wyz = _n(_unreal.MaterialExpressionComponentMask, -1700, 700)
        _wyz.set_editor_property("r", False)
        _wyz.set_editor_property("g", True)
        _wyz.set_editor_property("b", True)
        _wyz.set_editor_property("a", False)
        _ll_wire(_mel, _wp, "", _wyz, "")
        _wxz = _n(_unreal.MaterialExpressionComponentMask, -1700, 900)
        _wxz.set_editor_property("r", True)
        _wxz.set_editor_property("g", False)
        _wxz.set_editor_property("b", True)
        _wxz.set_editor_property("a", False)
        _ll_wire(_mel, _wp, "", _wxz, "")
        _tri_uv = (_wyz, _wxz)

    _BY_PATH = {{}}
    for _r in _plan:
        _BY_PATH[_r[5]] = _r

    def _bind_global(_node, _tex, _path):
        """Bind a whole-material sampler from the plan (projection 2).

        The weightmap and the selector are plan rows like any other; they
        just are not per-band. Binding them by hand with a literal would
        leave two textures whose sampler type the declaration does not
        govern -- two of the sixteen outside the system built to cover
        all sixteen.
        """
        _row = _BY_PATH.get(_path)
        if _row is None:
            raise RuntimeError(
                "global texture " + str(_path) + " is not in the plan")
        _node.set_editor_property("texture", _tex)
        _auto = _node.get_editor_property("sampler_type")
        _want = getattr(_unreal.MaterialSamplerType, _row[3])
        if _auto != _want:
            raise RuntimeError(
                "declared sampler type disagrees with the asset for "
                + str(_path) + ": declares " + str(_want)
                + ", engine derives " + str(_auto))
        _node.set_editor_property("sampler_type", _want)
        _node.set_editor_property(
            "sampler_source",
            getattr(_unreal.SamplerSourceMode, _row[4]))

    def _sample_uv(_asset, _uv_src, _divisor_cm, _x, _y):
        """Sample `_asset` on a CALLER-SUPPLIED world-plane UV source.

        Same plan-derived sampler type and the same texture-then-type
        assignment order as _sample_typed; only the UV differs. Kept as a
        separate entry point rather than an optional argument on
        _sample_typed, because an optional UV would be a parameter that
        silently changes projection — and this material has already paid
        for one argument that looked like control.
        """
        _uv = _n(_unreal.MaterialExpressionDivide, _x, _y)
        _ll_wire(_mel, _uv_src, "", _uv, "A")
        _ll_wire(_mel, _c(_divisor_cm, _x - 200, _y + 90), "", _uv, "B")
        _ts = _n(_unreal.MaterialExpressionTextureSample, _x + 220, _y)
        _row = _BY_PATH.get(_asset)
        if _row is None:
            raise RuntimeError(
                "texture " + str(_asset) + " is not in the plan")
        _tex = _textures.get(_asset)
        if _tex is None:
            raise RuntimeError(
                "texture " + str(_asset) + " was never preflighted")
        _ts.set_editor_property("texture", _tex)
        _want = getattr(_unreal.MaterialSamplerType, _row[3])
        _auto = _ts.get_editor_property("sampler_type")
        if _auto != _want:
            raise RuntimeError(
                "declared sampler type disagrees with the asset for "
                + str(_asset))
        _ts.set_editor_property("sampler_type", _want)
        _ts.set_editor_property(
            "sampler_source", getattr(_unreal.SamplerSourceMode, _row[4]))
        _ll_wire(_mel, _uv, "", _ts, "UVs")
        return _ts

    def _sample_typed(_asset, _divisor_cm, _x, _y):
        # PROJECTION 2 OF THE DECLARATION — the sampler type.
        #
        # There is NO sampler-type parameter. The declaration decides;
        # call sites cannot. 15 SAMPLERTYPE_ literals scattered through
        # the builder were 15 chances to pick the wrong one, and the
        # compiler only catches some of them.
        #
        # This parameter was briefly kept and ignored. An accepted
        # argument that changes nothing is the inert-field class -- it
        # reads like control and is connected to nothing -- so it is
        # gone rather than defaulted.
        _row = _BY_PATH.get(_asset)
        if _row is None:
            raise RuntimeError(
                "texture " + str(_asset) + " is not in the plan, so no "
                "class was declared for it. Add a row to "
                "SAMPLED_TEXTURES; do not pass a sampler type here.")
        _stype = getattr(_unreal.MaterialSamplerType, _row[3])
        """A world-scaled sample with an EXPLICIT sampler type.

        The sampler type is not cosmetic and there is no safe default:
        a normal map read as LINEAR_COLOR is not decoded as a vector and
        the lighting is wrong everywhere without an error, while a
        colour map read as NORMAL is worse. SAMPLERTYPE_NORMAL is
        REQUIRED for anything imported as TC_Normalmap, because BC5
        stores only X and Y and the sampler is what reconstructs Z.
        """
        # ⭐ STOCHASTIC TILING (schema v1.26). When the band being built
        # declares it, `_stoch_uv` holds an engine TextureVariation call
        # ALREADY fed by this layer's plain world-UV divide, and every
        # sample of the band reads its SHIFTED UVs instead of the divide.
        # One call per band, not one per map, so all four of a layer's
        # textures stay registered with each other -- a per-map call
        # would give the albedo, normal and roughness DIFFERENT random
        # offsets and shred the surface.
        _stoch = _stoch_uv["node"]
        _uv = None
        if _stoch is None:
            _uv = _n(_unreal.MaterialExpressionDivide, _x, _y)
            _ll_wire(_mel, _wxy, "", _uv, "A")
            _ll_wire(_mel,
                _c(_divisor_cm, _x - 200, _y + 90), "", _uv, "B")
        _ts = _n(_unreal.MaterialExpressionTextureSample, _x + 220, _y)
        _tex = _textures.get(_asset)
        if _tex is None:
            # "not in the preflight cache", NOT "does not exist" -- the
            # asset may be perfectly present on disk. Saying "not found"
            # sent the first sub-surface build hunting for a missing
            # T_Rock026_C that was there all along (non-negotiable 6:
            # distinguish "I looked and it is absent" from "I could not
            # look"). If this fires, the PREFLIGHT is missing a key.
            raise RuntimeError(
                "texture " + _asset + " was never preflighted, so it is "
                "not in the cache. This is NOT proof the asset is "
                "missing -- add its band key to the preflight loop.")
        # ORDER IS LOAD-BEARING AND IS NOW ASSERTED.
        #
        # Assigning `texture` fires PostEditChangeProperty, which calls
        # AutoSetSampleType() and OVERWRITES sampler_type from the asset
        # (MaterialExpressions.cpp:2625-2634). So `texture` must be set
        # FIRST and `sampler_type` after it, or the declared type is
        # silently discarded -- and the compile then passes CLEAN,
        # because the auto-set type always matches the asset. A texture
        # imported with the wrong settings would render wrong with no
        # error anywhere.
        #
        # This builder was correct only by accident of ordering; nothing
        # checked it. A READ-BACK IS THE RIGHT INSTRUMENT HERE, which is
        # rare in this project and worth saying why: the usual objection
        # (non-negotiable 8 -- reading the field you just wrote proves
        # only that the value landed) does not apply, because the THREAT
        # IS PRECISELY THAT THE ENGINE REWROTE OUR DECLARATION between
        # the write and the read. We are not confirming our own write;
        # we are checking whether something else overrode it.
        # Assign `texture` FIRST. That fires PostEditChangeProperty ->
        # AutoSetSampleType(), which sets sampler_type from the ASSET's
        # own import settings (MaterialExpressions.cpp:2625-2634).
        _ts.set_editor_property("texture", _tex)
        # READ THE ENGINE'S OPINION BEFORE OVERWRITING IT. This is the
        # whole check, and it is a genuine second instrument: `_auto` is
        # what UE thinks this asset must be sampled as, derived from its
        # compression settings and sRGB flag; `_stype` is what THIS
        # BUILDER declares. A disagreement means the asset was imported
        # with settings inconsistent with the texture class we are
        # treating it as -- which is a real, findable defect.
        _auto = _ts.get_editor_property("sampler_type")
        if _auto != _stype:
            raise RuntimeError(
                "declared sampler type disagrees with the asset for "
                + str(_asset) + ": this builder declares " + str(_stype)
                + " but the engine derives " + str(_auto)
                + " from the asset's own import settings. Either the "
                "declaration is wrong for this texture class, or the "
                "asset was imported with the wrong compression/sRGB.")
        _ts.set_editor_property("sampler_type", _stype)
        # Sampler SOURCE from the declaration too (_row[4]) — it was a
        # hardcoded _WRAP here while the table's source column read as
        # authoritative, the inert-column trap. _sample_uv/_bind_global
        # already read _row[4]; now all projections agree.
        _ts.set_editor_property(
            "sampler_source",
            getattr(_unreal.SamplerSourceMode, _row[4]))
        if _stoch is None:
            _ll_wire(_mel, _uv, "", _ts, "UVs")
        else:
            # ⛔ THE DERIVATIVES ARE NOT OPTIONAL. TextureVariation's own
            # description says so in as many words: "Make sure to set
            # texture samples to MipValueMode: Derivative." The shifted
            # UVs jump at every cell boundary, so the GPU's implicit
            # derivative there is enormous and the sample collapses to
            # the lowest mip -- a dark seam along every cell edge. The
            # function hands back the UNSHIFTED derivatives for exactly
            # this, and they go into DDX(UVs)/DDY(UVs).
            #
            # `mip_value_mode` is ABSENT from dir(MaterialExpression-
            # TextureSample) and IS settable anyway -- tested on a
            # throwaway material 2026-09-13 before this was written. An
            # omission from dir() is not proof of absence, and it nearly
            # got this route declared impossible.
            _ts.set_editor_property(
                "mip_value_mode",
                _unreal.TextureMipValueMode.TMVM_DERIVATIVE)
            _rb_mip = str(_ts.get_editor_property("mip_value_mode"))
            if "DERIVATIVE" not in _rb_mip.upper():
                raise RuntimeError(
                    "mip_value_mode read back as " + _rb_mip + ", not "
                    "DERIVATIVE. Without it the shifted UVs mip-collapse "
                    "at every cell boundary, and the seams are silent.")
            _ll_wire(_mel, _stoch, "Shifted UVs", _ts, "UVs")
            _ll_wire(_mel, _stoch, "DDX", _ts, "DDX(UVs)")
            _ll_wire(_mel, _stoch, "DDY", _ts, "DDY(UVs)")
        return _ts

    def _centred_height(_asset, _raw, _divisor_cm, _x, _y):
        """A height sample re-centred on ITS OWN fully-mipped value.

        WHY THIS EXISTS. `displacement_scaling.center` is ONE scalar for
        the whole material, and the height maps do not agree with it:
        measured means run 0.5257 (Ground037) to 0.7602 (Rock026), so a
        fixed center 0.5 lifts every surface by a constant -- up to
        +21 cm against a +/-40 cm amplitude, HALF THE SIGNAL SPENT AS DC
        -- and lifts each one by a DIFFERENT amount, putting a ~19 cm
        step at layer boundaries that is not relief.

        THE NEUTRAL IS TAKEN FROM THE TEXTURE ITSELF, NOT DECLARED.
        A second TextureSample of the same asset, forced to the smallest
        mip (`TMVM_MIP_LEVEL` with a const mip above the chain, which the
        sampler clamps), returns the texture's fully-mipped value. Then

            centred = raw - mipped + center

        NO DERIVED RECORD ANYWHERE. A recipe-declared mean would be a
        copy of a fact about an asset that can be reimported, resized or
        recompressed underneath it (NN15) -- and these maps HAVE been
        recompressed before. This reads the artefact every frame, so it
        cannot drift and it self-corrects on reimport.

        AND IT IS MORE CORRECT THAN THE ARITHMETIC MEAN WOULD BE. What
        the centring must cancel is *what this texture reads as when it
        degrades*, which is exactly the top mip -- so a fully-mipped
        sample now displaces by ZERO by construction. That is the same
        guarantee the macro-variation map carries, and the one the
        original center-0.5 comment merely claimed.

        The raw sample is passed IN rather than re-created: the height
        value feeding the sub-surface HeightLerp must stay UNCENTRED
        (that blend compares two heights against each other, and shifting
        them by different constants changes the blend), so exactly one
        node is shared and only the displacement path is re-centred.
        """
        _row = _BY_PATH.get(_asset)
        if _row is None:
            raise RuntimeError(
                "height texture " + str(_asset) + " is not in the plan")
        _mip = _n(_unreal.MaterialExpressionTextureSample, _x, _y)
        _t = _textures.get(_asset)
        if _t is None:
            raise RuntimeError(
                "height texture " + str(_asset) + " was not preflighted")
        _mip.set_editor_property("texture", _t)
        _mip.set_editor_property(
            "sampler_type", getattr(_unreal.MaterialSamplerType, _row[3]))
        _mip.set_editor_property(
            "sampler_source", getattr(_unreal.SamplerSourceMode, _row[4]))
        # TMVM_MIP_LEVEL = "explicitly compute the sample's mip level"
        # (EngineTypes.h, reflected as TextureMipValueMode). const_mip_value
        # is used only when the MipValue pin is unconnected, which it is.
        # 15 is above any mip chain a 4K texture can have (4096 -> 13
        # levels); the sampler clamps to the smallest available.
        _mip.set_editor_property(
            "mip_value_mode", _unreal.TextureMipValueMode.TMVM_MIP_LEVEL)
        _mip.set_editor_property("const_mip_value", 15)
        _sub = _n(_unreal.MaterialExpressionSubtract, _x + 300, _y)
        _ll_wire(_mel, _raw, "R", _sub, "A")
        _ll_wire(_mel, _mip, "R", _sub, "B")
        _add = _n(_unreal.MaterialExpressionAdd, _x + 460, _y)
        _ll_wire(_mel, _sub, "", _add, "A")
        _ll_wire(_mel, _c(float(_disp["center"]), _x + 300, _y + 140), "",
                 _add, "B")
        return _add

    def _sample(_asset, _divisor_cm, _x, _y):
        """A world-scaled sample. Delegates; kept for call-site clarity.

        This used to hardcode SAMPLERTYPE_LINEAR_COLOR for the generated
        multiplier textures. It no longer decides anything: the plan
        declares the class (`variation` -> LINEAR_COLOR, TC_BC7) and
        _sample_typed reads it. Two functions that differed ONLY in a
        hardcoded sampler type are one function once the declaration owns
        the type.

        Returns the TextureSample NODE, not a pin, so every caller names
        "RGB" explicitly when connecting from it.
        """
        return _sample_typed(_asset, _divisor_cm, _x, _y)

    def _surface_albedo(_B, _x, _y):
        """Real photogrammetry albedo, used AS the colour (schema v1.8).

        No mean-0.5 gain and no base_color multiply: the vendor albedo
        already IS the surface colour, and the measured means run 0.19
        to 0.79. `tint` multiplies only when it is not white, so an
        untinted layer renders the scan exactly as authored.

        Detail and macro are averaged, not multiplied. The generated
        textures multiplied because each had mean 0.5 and the product
        returned to 1.0; two real albedos multiplied would square the
        colour and halve the brightness. An average keeps the mean and
        still breaks up the detail repeat at distance.
        """
        # SAMPLERTYPE_COLOR, not LINEAR_COLOR. The generated textures
        # were linear multipliers; a photogrammetry albedo is imported
        # sRGB, and the sampler type must MATCH the import settings or
        # the material compiler refuses — which it did, by name, for all
        # three colour maps and all three roughness maps on the first
        # build.
        #
        # CORRECTED 2026-08-03: this used to add "the same mismatch on a
        # normal map compiles fine and is silently wrong". THAT IS FALSE.
        # VerifySamplerType errors on EVERY mismatch and applies an EXTRA
        # sRGB check that fires only for Normal and Masks
        # (MaterialExpressionUtils.cpp:65-76) -- normal maps are checked
        # MORE strictly. The real silent path is assigning `texture`
        # AFTER `sampler_type`: PostEditChangeProperty then calls
        # AutoSetSampleType and overwrites the declared type
        # (MaterialExpressions.cpp:2625-2634). Order is load-bearing.
        _det = _sample_typed(_B["surface_c"], _B["uv_detail_cm"],
                             _x + 260, _y + 160)
        _val = _det
        _pin = "RGB"

        # TRIPLANAR, detail albedo only. The top-down _det IS the Z
        # plane; we add the two side planes and blend by the shared
        # weights. Covers the sub-surface automatically, because the
        # sub-surface is built through this same function with its
        # surface slots repointed.
        if _B.get("tri_active") and _tri_w is not None:
            _wxm, _wym, _wz, _den, _mmask = _tri_w
            _sx = _sample_uv(_B["surface_c"], _tri_uv[0],
                             _B["uv_detail_cm"], _x + 260, _y - 120)
            _sy = _sample_uv(_B["surface_c"], _tri_uv[1],
                             _B["uv_detail_cm"], _x + 260, _y - 380)
            _nx = _n(_unreal.MaterialExpressionMultiply, _x + 560, _y - 120)
            _ll_wire(_mel, _sx, "RGB", _nx, "A")
            _ll_wire(_mel, _wxm, "", _nx, "B")
            _ny = _n(_unreal.MaterialExpressionMultiply, _x + 560, _y - 380)
            _ll_wire(_mel, _sy, "RGB", _ny, "A")
            _ll_wire(_mel, _wym, "", _ny, "B")
            _nzz = _n(_unreal.MaterialExpressionMultiply, _x + 560, _y + 160)
            _ll_wire(_mel, _det, "RGB", _nzz, "A")
            _ll_wire(_mel, _wz, "", _nzz, "B")
            _s1 = _n(_unreal.MaterialExpressionAdd, _x + 720, _y - 250)
            _ll_wire(_mel, _nx, "", _s1, "A")
            _ll_wire(_mel, _ny, "", _s1, "B")
            _s2 = _n(_unreal.MaterialExpressionAdd, _x + 860, _y - 60)
            _ll_wire(_mel, _s1, "", _s2, "A")
            _ll_wire(_mel, _nzz, "", _s2, "B")
            _tv = _n(_unreal.MaterialExpressionDivide, _x + 1000, _y - 60)
            _ll_wire(_mel, _s2, "", _tv, "A")
            _ll_wire(_mel, _den, "", _tv, "B")
            _val = _tv
            _pin = ""
        if _B["uv_macro_cm"]:
            _mac = _sample_typed(
                _B["surface_c"], _B["uv_macro_cm"], _x + 260, _y + 420)
            _sum = _n(_unreal.MaterialExpressionAdd, _x + 700, _y + 290)
            # CONSUME THE PREVIOUS STAGE, never the raw sample. This read
            # `_det, "RGB"` until 2026-08-07, which DISCARDED the
            # triplanar result assigned ~5 lines above whenever a surface
            # had both features -- and `triplanar.layers` is ["Rock"],
            # the one layer that also carries macro variation, so
            # triplanar was inert on 100% of the surfaces it exists for.
            # Found by reachability, not by looking: 41 orphaned
            # expressions in M_AutoLandscape, including both rock albedo
            # side projections. The tint block below is the correct
            # idiom and always was -- it consumes (_val, _pin).
            # LESSONS 2026-08-07; R2 OPEN DEFECT.
            _ll_wire(_mel, _val, _pin, _sum, "A")
            _ll_wire(_mel, _mac, "RGB", _sum, "B")
            _val = _n(_unreal.MaterialExpressionMultiply,
                      _x + 900, _y + 290)
            _ll_wire(_mel, _sum, "", _val, "A")
            _ll_wire(_mel, 
                _c(0.5, _x + 700, _y + 470), "", _val, "B")
            _pin = ""
        _t = _B.get("tint") or [1.0, 1.0, 1.0]
        if abs(_t[0] - 1.0) < 1e-6 and abs(_t[1] - 1.0) < 1e-6 \\
                and abs(_t[2] - 1.0) < 1e-6:
            return _val, _pin
        _mul = _n(_unreal.MaterialExpressionMultiply, _x + 1140, _y + 120)
        _ll_wire(_mel, _val, _pin, _mul, "A")
        _ll_wire(_mel, _c3(_t, _x + 900, _y + 40),
                                          "", _mul, "B")
        return _mul, ""

    def _surface_normal(_B, _x, _y):
        """Tangent-space normal at the detail scale, or None.

        SAMPLERTYPE_NORMAL is mandatory: the maps are imported
        TC_Normalmap, i.e. BC5 storing X and Y only, and the sampler is
        what reconstructs Z. Read as LINEAR_COLOR the vector is garbage
        -- and the compiler DOES refuse it: VerifySamplerType errors on
        every mismatch (MaterialExpressionUtils.cpp:65-76). An earlier
        version of this docstring claimed it was silent; it is not.

        Detail scale only. A macro normal would fight the detail one
        along every shared edge, and the landform is already carried by
        the heightmap — the normal map's job here is the sub-4-metre
        relief the 4 m grid cannot express.
        """
        if not _B.get("surface_n"):
            return None
        return _sample_typed(
            _B["surface_n"], _B["uv_detail_cm"], _x + 260, _y + 700)

    def _surface_roughness(_B, _x, _y):
        """Roughness MAP scaled by the recipe's scalar, or None.

        The recipe's `roughness` stops being the value and becomes a
        MULTIPLIER on the scan's own variation, so the recipe still
        controls the layer (hard rule 2) without flattening the map to
        a constant.
        """
        if not _B.get("surface_r"):
            return None
        # SAMPLERTYPE_MASKS to match the TC_Masks import.
        _rs = _sample_typed(
            _B["surface_r"], _B["uv_detail_cm"], _x + 260, _y + 950)
        _mul = _n(_unreal.MaterialExpressionMultiply, _x + 700, _y + 950)
        _ll_wire(_mel, _rs, "R", _mul, "A")
        _ll_wire(_mel, 
            _c(_B["roughness"] * 2.0, _x + 500, _y + 1040), "", _mul, "B")
        return _mul

    def _albedo(_B, _x, _y):
        """base_color, optionally modulated by its texture at two scales."""
        _base = _c3(_B["color"], _x, _y)
        if not _B["texture_asset"]:
            return _base
        _det = _sample(_B["texture_asset"], _B["uv_detail_cm"],
                       _x + 260, _y + 160)
        _prod = _det
        if _B["uv_macro_cm"]:
            _mac = _sample(_B["texture_asset"], _B["uv_macro_cm"],
                           _x + 260, _y + 420)
            _prod = _n(_unreal.MaterialExpressionMultiply,
                       _x + 700, _y + 290)
            _ll_wire(_mel, _det, "RGB", _prod, "A")
            _ll_wire(_mel, _mac, "RGB", _prod, "B")
            _gain = 4.0
        else:
            _gain = 2.0
        # The gain is the ENCODING constant of the texture format (mean
        # 0.5 per sample), not a scene parameter: 2 samples -> 4, one
        # sample -> 2. Either way the mean product is 1.0, so a mipped-out
        # layer renders exactly base_color.
        _scaled = _n(_unreal.MaterialExpressionMultiply, _x + 920, _y + 290)
        if _prod is _det:
            _ll_wire(_mel, _prod, "RGB", _scaled, "A")
        else:
            _ll_wire(_mel, _prod, "", _scaled, "A")
        _ll_wire(_mel, 
            _c(_gain, _x + 700, _y + 470), "", _scaled, "B")
        _out_mul = _n(_unreal.MaterialExpressionMultiply,
                      _x + 1140, _y + 120)
        _ll_wire(_mel, _base, "", _out_mul, "A")
        _ll_wire(_mel, _scaled, "", _out_mul, "B")
        return _out_mul

    def _band(_src, _lo_out, _lo_in, _hi_in, _hi_out, _x, _y):
        _a = _ramp(_src, _lo_in, _lo_out, _x, _y, True)
        _b = _ramp(_src, _hi_in, _hi_out, _x, _y + 260, False)
        _m = _n(_unreal.MaterialExpressionMultiply, _x + 620, _y + 130)
        _ll_wire(_mel, _a, "", _m, "A")
        _ll_wire(_mel, _b, "", _m, "B")
        return _m

    def _heightlerp_apply(_A, _Apin, _B2, _Bpin, _w, _x, _y):
        """Apply precomputed blend weights to one channel pair.

        `_w` is (b1, b2, den) from _heightlerp_weights. Computed ONCE per
        band and reused for albedo, normal and roughness: the three must
        agree pixel-for-pixel or the surface's colour, its lighting and
        its shine come from different places, which reads as a material
        that shimmers between two identities along every transition.
        """
        _b1, _b2, _den = _w
        _na = _n(_unreal.MaterialExpressionMultiply, _x, _y)
        _ll_wire(_mel, _A, _Apin, _na, "A")
        _ll_wire(_mel, _b1, "", _na, "B")
        _nb = _n(_unreal.MaterialExpressionMultiply, _x, _y + 200)
        _ll_wire(_mel, _B2, _Bpin, _nb, "A")
        _ll_wire(_mel, _b2, "", _nb, "B")
        _num = _n(_unreal.MaterialExpressionAdd, _x + 160, _y + 100)
        _ll_wire(_mel, _na, "", _num, "A")
        _ll_wire(_mel, _nb, "", _num, "B")
        _out2 = _n(_unreal.MaterialExpressionDivide, _x + 320, _y + 100)
        _ll_wire(_mel, _num, "", _out2, "A")
        _ll_wire(_mel, _den, "", _out2, "B")
        return _out2

    def _heightlerp_weights(_t, _ha, _hb, _contrast, _x, _y):
        """Node-for-node mirror of host-side `_cpu_heightlerp`.

        hw = 4t(1-t); wa = (1-t) + ha*hw; wb = t + hb*hw
        ma = max(wa,wb) - contrast; b1 = max(wa-ma,0); b2 = max(wb-ma,0)
        out = (A*b1 + B*b2) / (b1+b2)

        The window `hw` is what keeps the selector authoritative at its
        extremes -- see the host docstring. Contrast is validated (0,1].
        """
        _one = _c(1.0, _x, _y - 120)
        _omt = _n(_unreal.MaterialExpressionSubtract, _x + 160, _y - 60)
        _ll_wire(_mel, _one, "", _omt, "A")
        _ll_wire(_mel, _t, "", _omt, "B")

        _tt = _n(_unreal.MaterialExpressionMultiply, _x + 160, _y + 60)
        _ll_wire(_mel, _t, "", _tt, "A")
        _ll_wire(_mel, _omt, "", _tt, "B")
        _hw = _n(_unreal.MaterialExpressionMultiply, _x + 320, _y + 60)
        _ll_wire(_mel, _tt, "", _hw, "A")
        _ll_wire(_mel, 
            _c(4.0, _x + 160, _y + 180), "", _hw, "B")

        _haw = _n(_unreal.MaterialExpressionMultiply, _x + 480, _y - 200)
        _ll_wire(_mel, _ha, "R", _haw, "A")
        _ll_wire(_mel, _hw, "", _haw, "B")
        _wa = _n(_unreal.MaterialExpressionAdd, _x + 640, _y - 140)
        _ll_wire(_mel, _omt, "", _wa, "A")
        _ll_wire(_mel, _haw, "", _wa, "B")

        _hbw = _n(_unreal.MaterialExpressionMultiply, _x + 480, _y + 260)
        _ll_wire(_mel, _hb, "R", _hbw, "A")
        _ll_wire(_mel, _hw, "", _hbw, "B")
        _wb = _n(_unreal.MaterialExpressionAdd, _x + 640, _y + 200)
        _ll_wire(_mel, _t, "", _wb, "A")
        _ll_wire(_mel, _hbw, "", _wb, "B")

        _mx = _n(_unreal.MaterialExpressionMax, _x + 800, _y + 30)
        _ll_wire(_mel, _wa, "", _mx, "A")
        _ll_wire(_mel, _wb, "", _mx, "B")
        _ma = _n(_unreal.MaterialExpressionSubtract, _x + 960, _y + 30)
        _ll_wire(_mel, _mx, "", _ma, "A")
        _ll_wire(_mel, 
            _c(float(_contrast), _x + 800, _y + 150), "", _ma, "B")

        _d1 = _n(_unreal.MaterialExpressionSubtract, _x + 1120, _y - 140)
        _ll_wire(_mel, _wa, "", _d1, "A")
        _ll_wire(_mel, _ma, "", _d1, "B")
        _b1 = _n(_unreal.MaterialExpressionMax, _x + 1280, _y - 140)
        _ll_wire(_mel, _d1, "", _b1, "A")
        _ll_wire(_mel, 
            _c(0.0, _x + 1120, _y - 20), "", _b1, "B")

        _d2 = _n(_unreal.MaterialExpressionSubtract, _x + 1120, _y + 200)
        _ll_wire(_mel, _wb, "", _d2, "A")
        _ll_wire(_mel, _ma, "", _d2, "B")
        _b2 = _n(_unreal.MaterialExpressionMax, _x + 1280, _y + 200)
        _ll_wire(_mel, _d2, "", _b2, "A")
        _ll_wire(_mel, 
            _c(0.0, _x + 1120, _y + 320), "", _b2, "B")

        _den = _n(_unreal.MaterialExpressionAdd, _x + 1440, _y + 380)
        _ll_wire(_mel, _b1, "", _den, "A")
        _ll_wire(_mel, _b2, "", _den, "B")
        # No epsilon guard. `contrast > 0` is enforced by the recipe
        # validator, and with contrast > 0 `ma` is strictly below
        # max(wa, wb), so at least one of b1/b2 is positive ALWAYS. An
        # epsilon here would hide a validator failure instead of letting
        # it be one -- and a NaN through base colour is exactly the class
        # the bound was promoted into the validator to prevent.
        return _b1, _b2, _den

    # Declared BEFORE the weightmap branch so they exist on every path.
    # Without this a recipe with no weightmap raises NameError deep in
    # the band loop instead of simply building no sub-surfaces.
    _vsamp = None
    _wsamp = None          # audit 2026-09-11 F4: the v1.25 forest-floor
                           # driver reads this inside the band loop
    _chan = list(_CHAN)   # ONE spelling of the channel contract — a
                          # hardcoded 3-channel list here was a stale
                          # copy of the 4-channel _CHAN (dead today,
                          # but a live landmine for the no-weightmap
                          # path; Pass 3 2026-09-16)

    # schema v1.28 (Brief 7 Phase 1 addendum). When height-blend is on, the
    # per-layer height sample is created ONCE here (at mask build) and
    # reused as the band's `_hA` in the composite loop below -- one
    # expression, three consumers (blend weight, HeightLerp, displacement).
    # None per band until populated.
    _hgt = [None] * len(_bands)

    if _weightmap:
        # Masks come from the BAKED weightmap, not from the vertex normal.
        # The shader normal is the normal of the DECIMATED mesh, so it
        # flattens with distance and every slope band drifts toward the
        # flat-favouring layer. Baked weights are computed once, on the
        # CPU, from the full-resolution heightmap, so rendered coverage
        # equals predicted coverage at every LOD.
        _wmt = _unreal.EditorAssetLibrary.load_asset(_weightmap)
        if _wmt is None:
            raise RuntimeError("weightmap asset not found: " + _weightmap)
        _org = _n(_unreal.MaterialExpressionConstant2Vector, -2000, 760)
        _org.set_editor_property("r", float(_org_x))
        _org.set_editor_property("g", float(_org_y))
        _rel = _n(_unreal.MaterialExpressionSubtract, -1700, 700)
        _ll_wire(_mel, _wxy, "", _rel, "A")
        _ll_wire(_mel, _org, "", _rel, "B")
        _uvw = _n(_unreal.MaterialExpressionDivide, -1450, 700)
        _ll_wire(_mel, _rel, "", _uvw, "A")
        _ll_wire(_mel, 
            _c(float(_span_cm), -1700, 830), "", _uvw, "B")
        _wsamp = _n(_unreal.MaterialExpressionTextureSample, -1150, 700)
        _bind_global(_wsamp, _wmt, _weightmap)
        _ll_wire(_mel, _uvw, "", _wsamp, "UVs")

        # The SUB-SURFACE SELECTOR shares the weightmap's UV node
        # EXACTLY -- same origin, same span, same clamp. They are two
        # channels-worth of the same 1:1 terrain projection, and giving
        # each its own UV chain would let a future edit move one and not
        # the other, mis-registering the selector against the mask it
        # modulates by a fraction of a texel with no error anywhere.
        if _variantmap:
            _vmt = _unreal.EditorAssetLibrary.load_asset(_variantmap)
            if _vmt is None:
                raise RuntimeError("variant map asset not found: "
                                   + _variantmap)
            _vsamp = _n(_unreal.MaterialExpressionTextureSample,
                        -1150, 1020)
            _bind_global(_vsamp, _vmt, _variantmap)
            _ll_wire(_mel, _uvw, "", _vsamp, "UVs")

        # v1.26 (2026-09-12): FOUR addressable channels plus a REMAINDER
        # layer. The baked weightmap carries derive_layer_weights' w8a
        # contract -- R=snow G=rock B=scree A=forest_floor -- and the
        # fifth layer (meadow) is 1-(R+G+B+A).
        #
        # ⛔ THE REMAINDER IS NOT STORED, AND THAT IS THE POINT. A fifth
        # channel would be a fifth number obliged to agree with four
        # others, and 8-bit quantisation guarantees it sometimes would
        # not -- two lists that must agree are one list badly stored
        # (NN24). Deriving it in the shader makes the masks sum to 1 BY
        # CONSTRUCTION rather than by assertion.
        #
        # SATURATE, not raw subtract: quantisation can push the sum a
        # few 1/255ths past 1, and a negative mask multiplies a layer's
        # albedo to a negative colour, which reads as a black bruise
        # rather than as an error.
        # INTERPOLATED from WEIGHTMAP_CHANNELS host-side -- not spelled
        # out here, so the shader and bake_surface_lookup cannot drift.
        _chan = list(_CHAN)
        if len(_bands) > len(_chan) + 1:
            raise RuntimeError(
                "the weightmap has %d channels, so at most %d layers are "
                "addressable (the last being the remainder); the recipe "
                "declares %d. A further layer needs a SECOND weightmap "
                "texture, which this builder does not create -- it is not "
                "a limit to widen quietly."
                % (len(_chan), len(_chan) + 1, len(_bands)))
        _masks = []
        _direct = min(len(_bands), len(_chan))
        for _i in range(_direct):
            _mk = _n(_unreal.MaterialExpressionMultiply, -600, _i * 1100)
            _ll_wire(_mel, _wsamp, _chan[_i], _mk, "A")
            _ll_wire(_mel,
                _c(1.0, -800, _i * 1100 + 120), "", _mk, "B")
            _masks.append(_mk)
        if _hblend is not None:
            # HEIGHT-WEIGHTED BLEND (schema v1.28, Brief 7 Phase 1 addendum).
            # LB_HeightBlend has no referent in this material, so its effect
            # is built here: scale each STORED layer's mask by
            # (raw_height + eps)**k, then renormalise so the four sum to
            # what they did. The remainder (computed just below as
            # 1 - sum(stored)) is therefore UNCHANGED -- only the split
            # AMONG the stored layers moves toward the higher surface. The
            # height is the RAW sample (0..1), NOT the displacement-centred
            # value: an even power on a re-centred height would fold a texel
            # far below its own mean onto one far above (see recipe
            # _height_source). The per-layer sample is created ONCE here and
            # reused as `_hA` in the composite loop (one expression, three
            # consumers).
            _hb_k = float(_hblend["k"])
            _hb_eps = float(_hblend["eps"])
            _base = list(_masks)        # the wsamp*1.0 nodes, pre-reweight
            _wp = []
            for _i in range(_direct):
                _B = _bands[_i]
                # Gate on d_active, NOT surface_d: d_active is the plan's
                # own "this layer's _D is sampled" predicate, so the sample
                # is guaranteed preflighted, and it is the SAME condition
                # the composite loop reuses `_hgt[_i]` under. A stored layer
                # without a height map is left at factor 1 (not reweighted).
                if _B.get("d_active"):
                    _hgt[_i] = _sample_typed(
                        _B["surface_d"], _B["uv_detail_cm"],
                        -2050, _i * 1100 + 300)
                    _hpe = _n(_unreal.MaterialExpressionAdd,
                              -1850, _i * 1100 + 300)
                    _ll_wire(_mel, _hgt[_i], "R", _hpe, "A")
                    _ll_wire(_mel, _c(_hb_eps, -2050, _i * 1100 + 460),
                             "", _hpe, "B")
                    _pw = _n(_unreal.MaterialExpressionPower,
                             -1650, _i * 1100 + 300)
                    # const_exponent is used only when the Exponent pin is
                    # unconnected (PythonStub: MaterialExpressionPower), and
                    # it is left unconnected here.
                    _pw.set_editor_property("const_exponent", _hb_k)
                    _ll_wire(_mel, _hpe, "", _pw, "Base")
                    _wpi = _n(_unreal.MaterialExpressionMultiply,
                              -1450, _i * 1100 + 300)
                    _ll_wire(_mel, _base[_i], "", _wpi, "A")
                    _ll_wire(_mel, _pw, "", _wpi, "B")
                    _wp.append(_wpi)
                else:
                    # No height map on this stored layer -> factor 1, i.e.
                    # not reweighted. It still participates in the sums.
                    _wp.append(_base[_i])

            def _sumchain(_nodes, _x):
                _a = _nodes[0]
                for _j in range(1, len(_nodes)):
                    _ad = _n(_unreal.MaterialExpressionAdd, _x, _j * 140)
                    _ll_wire(_mel, _a, "", _ad, "A")
                    _ll_wire(_mel, _nodes[_j], "", _ad, "B")
                    _a = _ad
                return _a

            # norm = sum(base) / (sum(wp) + eps_norm). The eps_norm is a
            # pure divide-by-zero floor: sum(wp) is 0 IFF every stored
            # weight is 0 (a pure-remainder texel), where norm -> 0 and the
            # stored masks resolve to 0 while the remainder is 1. For any
            # real stored weight sum(wp) >> eps_norm, so norm == sum(base) /
            # sum(wp) to full precision and the sum is preserved.
            _S = _sumchain(_base, -1250)
            _Sp = _sumchain(_wp, -1150)
            _Spg = _n(_unreal.MaterialExpressionAdd, -1050, 700)
            _ll_wire(_mel, _Sp, "", _Spg, "A")
            _ll_wire(_mel, _c(float(_hblend["eps_norm"]), -1250, 760), "",
                     _Spg, "B")
            _norm = _n(_unreal.MaterialExpressionDivide, -950, 700)
            _ll_wire(_mel, _S, "", _norm, "A")
            _ll_wire(_mel, _Spg, "", _norm, "B")
            for _i in range(_direct):
                _mkn = _n(_unreal.MaterialExpressionMultiply,
                          -750, _i * 1100 + 300)
                _ll_wire(_mel, _wp[_i], "", _mkn, "A")
                _ll_wire(_mel, _norm, "", _mkn, "B")
                _masks[_i] = _mkn
        if len(_bands) > _direct:
            _y0 = _direct * 1100
            _acc = _masks[0]
            for _i in range(1, _direct):
                _add = _n(_unreal.MaterialExpressionAdd, -900, _y0 + _i * 140)
                _ll_wire(_mel, _acc, "", _add, "A")
                _ll_wire(_mel, _masks[_i], "", _add, "B")
                _acc = _add
            _rsub = _n(_unreal.MaterialExpressionSubtract, -750, _y0)
            _ll_wire(_mel, _c(1.0, -900, _y0 - 140), "", _rsub, "A")
            _ll_wire(_mel, _acc, "", _rsub, "B")
            _rem = _n(_unreal.MaterialExpressionSaturate, -600, _y0)
            _ll_wire(_mel, _rsub, "", _rem, "")
            _masks.append(_rem)
    else:
        _masks = []
        for _i, _B in enumerate(_bands):
            _y = _i * 1100
            _sm = _band(_nz, _B["cos_lo"], _B["cos_lo_in"],
                        _B["cos_hi_in"], _B["cos_hi"], -1400, _y)
            _hm = _band(_wz, _B["z_lo"], _B["z_lo_in"],
                        _B["z_hi_in"], _B["z_hi"], -1400, _y + 540)
            _both = _n(_unreal.MaterialExpressionMultiply, -600, _y + 300)
            _ll_wire(_mel, _sm, "", _both, "A")
            _ll_wire(_mel, _hm, "", _both, "B")
            _masks.append(_both)

    # Composite last-to-first so layer 0 lands on top (first-match-wins).
    # The BACKGROUND stays a flat colour deliberately: it is only visible
    # where no band matches at all, which alpine.json drives to 0.00%.
    # Running it through _albedo would duplicate every texture sample of
    # the last layer to paint pixels that do not exist.
    _col = _c3(_bands[-1]["color"], -200, -900)
    _col_pin = ""
    _rgh = _c(_bands[-1]["roughness"], -200, -400)
    # A flat tangent-space normal. Layers without a surface map keep
    # this, so mixing surfaced and unsurfaced layers is well defined.
    _nrm = _c3([0.0, 0.0, 1.0], -200, -1400)
    _nrm_pin = ""
    _any_normal = False

    # DISPLACEMENT ACCUMULATOR (v1.21).
    #
    # THE NEUTRAL VALUE IS `center`, NOT ZERO, and this is the one place
    # the distinction is easy to get wrong and invisible afterwards. The
    # shader computes (v - Center) * Magnitude
    # (NaniteRasterizationCommon.ush:568), so a pixel that supplies no
    # height must read CENTER to move by nothing. Seeding this at 0.0
    # would sink every such pixel by Center*Magnitude -- a uniform trench
    # under any layer without a _D map, rendered with a clean compile.
    #
    # This mirrors the macro-variation map's guarantee: the degraded
    # state is the identity, by construction.
    _dsp = _c(float(_disp["center"]), -200, -1900) if _disp else None

    for _i in range(len(_bands) - 1, -1, -1):
        _B = _bands[_i]
        # ⭐ Set BEFORE any of this band's samples are built and cleared
        # after, so every sample of the band reads the same shifted UVs
        # and no other band can inherit them.
        _stoch_uv["node"] = _build_stochastic(_B, -2600, _i * 1100 + 200)
        _hw_w = None
        _sb = None
        _hB = None
        if _B.get("surface_c"):
            _lc, _lc_pin = _surface_albedo(_B, -200, _i * 1100 + 200)
        else:
            _lc, _lc_pin = _albedo(_B, -200, _i * 1100 + 200), ""

        # SUB-SURFACE (schema v1.14). Height-blended against the primary
        # using this layer's channel of the selector map. Built only when
        # the layer BINDS a second surface -- a declared-but-unbound
        # sub_surface (the deferred Grass case) adds no nodes at all, so
        # the graph a no-op produces is byte-identical to having no
        # block, and the assertion sees no phantom samplers.
        # THE PRIMARY'S HEIGHT SAMPLE, CREATED ONCE PER BAND (v1.21).
        #
        # Two features read it -- the sub-surface HeightLerp and the
        # Nanite displacement chain -- and they must read the SAME node.
        # A second TextureSample of the same asset would be a second
        # texture fetch for an identical value, and the landscape's graph
        # assertion compares DISTINCT sets (multiplicities here are a
        # function of the recipe), so a duplicate would not be caught.
        # One expression, N consumers.
        #
        # SAMPLERTYPE_LINEAR_GRAYSCALE, not MASKS -- the declaration
        # decides and _sample_typed reads it from the plan. The
        # displacement maps import as TC_Grayscale with srgb=False, and
        # MaterialExpressionUtils.cpp:37-38 selects the sampler from
        # exactly those two facts: single-channel and NOT sRGB ->
        # SAMPLERTYPE_LinearGrayscale. MASKS is for TC_Masks, which is
        # what the ROUGHNESS maps are -- different import, different
        # sampler. The compiler refuses this by name rather than
        # rendering it wrong, which is the good case.
        _hA = None
        if _B.get("d_active"):
            # schema v1.28: reuse the height sample created at mask build
            # for the height-weighted blend, when there is one -- one
            # texture fetch feeds the blend weight, the HeightLerp and the
            # displacement chain. Otherwise sample it here as before.
            if _i < len(_hgt) and _hgt[_i] is not None:
                _hA = _hgt[_i]
            else:
                _hA = _sample_typed(
                    _B["surface_d"], _B["uv_detail_cm"], -1900,
                    _i * 1100 + 400)

        if _B.get("sub_active") and _vsamp is not None:
            # Shallow copy with the surface slots repointed at the
            # sub-surface, so the SAME _surface_albedo path builds it --
            # one albedo implementation, two surfaces. NO DICT LITERAL:
            # this source is a .format() template and a literal brace is
            # a format field.
            _sb = dict(_B)
            _sb["surface_c"] = _B["sub_c"]
            _sb["surface_n"] = _B["sub_n"]
            _sb["surface_r"] = _B["sub_r"]
            _sub_c, _sub_pin = _surface_albedo(
                _sb, -200, _i * 1100 + 200 - 560)
            # `_hA` was created above under `d_active`, which
            # _assert_band_invariant proves is implied by `sub_active`.
            # Assert it anyway rather than let a None reach _ll_wire as a
            # confusing pin error: a HeightLerp missing one of its two
            # heights is a silent linear lerp, which is the exact failure
            # this graph's weights exist to avoid.
            if _hA is None:
                raise RuntimeError(
                    "band " + str(_B.get("name")) + " is sub_active but "
                    "its primary height sample was never created; "
                    "d_active and sub_active have drifted apart")
            _hB = _sample_typed(
                _B["sub_d"], _B["uv_detail_cm"], -1900,
                _i * 1100 + 620)
            _sel = _n(_unreal.MaterialExpressionMultiply,
                      -1500, _i * 1100 + 520)
            # ⛔ THE VARIANT MAP HAS ITS OWN CHANNELS. This read
            # `_chan[_i]` until 2026-09-12 -- the WEIGHTMAP's channel
            # contract, used to index a DIFFERENT texture. With three
            # layers and three weightmap channels the two coincided, so
            # the conflation was invisible; at five layers it raised
            # IndexError AFTER the graph had been cleared.
            # A shared index is not a shared meaning.
            if _i >= len(_VCHAN):
                raise RuntimeError(
                    "band %d (%s) declares a sub_surface, but the variant "
                    "map carries only %d channels (%s) -- there is no "
                    "selector channel for it. The variant map is baked one "
                    "channel per layer by make_variant_map; a layer added "
                    "past its width needs the map rebuilt, not an index "
                    "borrowed from the weightmap."
                    % (_i, _B.get("name"), len(_VCHAN), ",".join(_VCHAN)))
            _ll_wire(_mel, _vsamp, _VCHAN[_i], _sel, "A")
            _ll_wire(_mel, 
                _c(1.0, -1700, _i * 1100 + 640), "", _sel, "B")
            _hw_w = _heightlerp_weights(_sel, _hA, _hB,
                                        _B["sub_contrast"],
                                        -1300, _i * 1100 + 300)
            _lc = _heightlerp_apply(_lc, _lc_pin, _sub_c, _sub_pin,
                                    _hw_w, 700, _i * 1100 + 300)
            _lc_pin = ""

        # FOREST FLOOR (schema v1.11). Applied HERE, at the point where
        # the surfaced and untextured paths converge, rather than inside
        # _albedo: this layer declares a `surface`, so it takes the
        # _surface_albedo branch and a tint written into _albedo alone
        # would never execute — a silent no-op that still reported a
        # successful build. Multiplying the layer albedo by
        # lerp(white, tint, band * strength) darkens the ground across
        # the tree elevation band only, and rides on the layer's own
        # baked-weightmap mask so it inherits the slope limit without
        # reading the (LOD-dependent) vertex normal.
        _F = _B.get("forest")
        if _F:
            if _F.get("driver") == "weightmap_alpha":
                if _wsamp is None:
                    raise RuntimeError(
                        "forest_floor driver is weightmap_alpha but this "
                        "graph has no weightmap sampler")
                # v1.25: the mask is the weightmap's ALPHA -- the canopy-
                # derived forest_floor weight baked by
                # derive_layer_weights. Same sampler, no new texture; the
                # A pin of the global weight sample drives the tint.
                _fb = _wsamp
                _fb_pin = "A"
            else:
                _fb = _band(_wz, _F["z_lo"], _F["z_lo_in"], _F["z_hi_in"],
                            _F["z_hi"], -1050, _i * 1100 + 640)
                _fb_pin = ""
            _fs = _n(_unreal.MaterialExpressionMultiply,
                     -640, _i * 1100 + 700)
            _ll_wire(_mel, _fb, _fb_pin, _fs, "A")
            _ll_wire(_mel, 
                _c(_F["strength"], -820, _i * 1100 + 790), "", _fs, "B")
            _ft = _n(_unreal.MaterialExpressionLinearInterpolate,
                     -440, _i * 1100 + 700)
            _ll_wire(_mel, 
                _c3([1.0, 1.0, 1.0], -640, _i * 1100 + 600), "", _ft, "A")
            _ll_wire(_mel, 
                _c3(_F["tint"], -640, _i * 1100 + 880), "", _ft, "B")
            _ll_wire(_mel, _fs, "", _ft, "Alpha")
            _fm = _n(_unreal.MaterialExpressionMultiply,
                     -60, _i * 1100 + 340)
            _ll_wire(_mel, _lc, _lc_pin, _fm, "A")
            _ll_wire(_mel, _ft, "", _fm, "B")
            _lc, _lc_pin = _fm, ""

        _cl = _n(_unreal.MaterialExpressionLinearInterpolate,
                 200 + (len(_bands) - _i) * 260, _i * 1100)
        _ll_wire(_mel, _col, _col_pin, _cl, "A")
        _ll_wire(_mel, _lc, _lc_pin, _cl, "B")
        _ll_wire(_mel, _masks[_i], "", _cl, "Alpha")
        _col = _cl
        _col_pin = ""

        _lr = _surface_roughness(_B, -200, _i * 1100 + 200)
        _lr_pin = ""
        if _lr is None:
            _lr = _c(_B["roughness"], -200, _i * 1100 + 400)
        elif _hw_w is not None and _sb is not None:
            # Same weights as the albedo. A sub-surface that keeps the
            # primary's ROUGHNESS is half a surface swap: scree would
            # take rock's shine and read as wet stone.
            _sr = _surface_roughness(_sb, -200, _i * 1100 + 200 - 560)
            if _sr is not None:
                _lr = _heightlerp_apply(_lr, _lr_pin, _sr, "",
                                        _hw_w, 700, _i * 1100 + 760)
                _lr_pin = ""
        _rl = _n(_unreal.MaterialExpressionLinearInterpolate,
                 200 + (len(_bands) - _i) * 260, _i * 1100 + 500)
        _ll_wire(_mel, _rgh, "", _rl, "A")
        _ll_wire(_mel, _lr, _lr_pin, _rl, "B")
        _ll_wire(_mel, _masks[_i], "", _rl, "Alpha")
        _rgh = _rl

        # NORMALS BLEND WITH THE SAME MASK as colour and roughness. A
        # linear blend of tangent-space normals is not strictly correct
        # — the result is not unit length — but it is what landscape
        # layer blending does, the error is small at these weights, and
        # the alternative (reoriented blending) costs nodes for a
        # difference invisible against a 4 m grid. Stated because it IS
        # an approximation, not because it is free.
        _ln = _surface_normal(_B, -200, _i * 1100 + 200)
        _ln_pin = "RGB"
        if _ln is not None and _hw_w is not None and _sb is not None:
            _sn = _surface_normal(_sb, -200, _i * 1100 + 200 - 560)
            if _sn is not None:
                # Tangent-space normals blended by the same weights.
                # Approximate for large angle differences, exact enough
                # at the sub-4-metre relief these maps carry, and far
                # better than the sub-surface silently wearing the
                # primary's lighting.
                _ln = _heightlerp_apply(_ln, "RGB", _sn, "RGB",
                                        _hw_w, 700, _i * 1100 + 1180)
                _ln_pin = ""
        if _ln is not None:
            _any_normal = True
            _nl = _n(_unreal.MaterialExpressionLinearInterpolate,
                     200 + (len(_bands) - _i) * 260, _i * 1100 + 900)
            _ll_wire(_mel, _nrm, _nrm_pin, _nl, "A")
            _ll_wire(_mel, _ln, _ln_pin, _nl, "B")
            _ll_wire(_mel, _masks[_i], "", _nl, "Alpha")
            _nrm = _nl
            _nrm_pin = ""

        # ==============================================================
        # DISPLACEMENT (schema v1.21). Composited with the SAME per-layer
        # weightmap mask as colour, roughness and normal, and -- where a
        # sub-surface exists -- with the SAME HeightLerp weights.
        #
        # WHY IT MUST SHARE BOTH. The height a pixel is pushed to and the
        # albedo it is painted with have to come from the same surface,
        # or the terrain's shape and its appearance describe different
        # rock. Sharing `_masks[_i]` and `_hw_w` makes that agreement
        # structural rather than a thing to keep in step (NN19: when two
        # passes render the same physical fact, the fact is defined once
        # and both read it).
        #
        # A layer with no height map contributes CENTER -- neutral --
        # rather than being skipped. Skipping would leave the accumulator
        # showing the PREVIOUS layer's height through this layer's
        # pixels, which is a blend seam that only appears once the
        # geometry moves.
        # ==============================================================
        if _disp is not None:
            if _hA is None:
                _ld, _ld_pin = _c(float(_disp["center"]), -200,
                                  _i * 1100 + 900), ""
            else:
                # RE-CENTRED ON EACH MAP'S OWN FULLY-MIPPED VALUE. The
                # UNCENTRED _hA/_hB still feed _heightlerp_weights above:
                # that blend compares the two heights AGAINST EACH OTHER,
                # so shifting them by different constants would change
                # which surface wins. Only the displacement path moves.
                _hAc = _centred_height(_B["surface_d"], _hA,
                                       _B["uv_detail_cm"],
                                       -2500, _i * 1100 + 400)
                if _hw_w is not None and _hB is not None:
                    _hBc = _centred_height(_B["sub_d"], _hB,
                                           _B["uv_detail_cm"],
                                           -2500, _i * 1100 + 620)
                    _ld = _heightlerp_apply(_hAc, "", _hBc, "", _hw_w,
                                            700, _i * 1100 + 1400)
                    _ld_pin = ""
                else:
                    _ld, _ld_pin = _hAc, ""
                # PER-LAYER AMPLITUDE (schema v1.27, Brief 7 Phase 1). The
                # engine's single displacement_scaling.magnitude carries
                # amplitude_ref (the MAX layer, displacement_spec); every
                # other layer is scaled DOWN here by disp_k =
                # amplitude_layer / amplitude_ref, applied to the DEVIATION
                # from center so the neutral is preserved:
                #     val = center + (centred - center) * k
                # A map-less / fully-mipped sample reads `center`, so its
                # deviation is 0 and it still moves by nothing whatever k
                # is -- which is why the scale lives HERE, inside the
                # has-a-height branch, and the `_hA is None` branch is left
                # at raw `center`. `_cpu_disp_band` mirrors this and is
                # proven at import. Skipped for the reference layer
                # (k == 1) so it adds no dead nodes there.
                _k = _B.get("disp_k")
                if _k is not None and abs(_k - 1.0) > 1e-9:
                    _cC = float(_disp["center"])
                    _dev = _n(_unreal.MaterialExpressionSubtract,
                              300, _i * 1100 + 700)
                    _ll_wire(_mel, _ld, _ld_pin, _dev, "A")
                    _ll_wire(_mel, _c(_cC, 150, _i * 1100 + 760), "",
                             _dev, "B")
                    _sc = _n(_unreal.MaterialExpressionMultiply,
                             460, _i * 1100 + 700)
                    _ll_wire(_mel, _dev, "", _sc, "A")
                    _ll_wire(_mel, _c(float(_k), 300, _i * 1100 + 800), "",
                             _sc, "B")
                    _re = _n(_unreal.MaterialExpressionAdd,
                             620, _i * 1100 + 700)
                    _ll_wire(_mel, _sc, "", _re, "A")
                    _ll_wire(_mel, _c(_cC, 460, _i * 1100 + 800), "",
                             _re, "B")
                    _ld, _ld_pin = _re, ""
            _dl = _n(_unreal.MaterialExpressionLinearInterpolate,
                     200 + (len(_bands) - _i) * 260, _i * 1100 + 900)
            _ll_wire(_mel, _dsp, "", _dl, "A")
            _ll_wire(_mel, _ld, _ld_pin, _dl, "B")
            _ll_wire(_mel, _masks[_i], "", _dl, "Alpha")
            _dsp = _dl
        # ⛔ CLEARED AT THE END OF EVERY ITERATION. Left set, the NEXT
        # band would silently sample through this band's shifted UVs --
        # a layer tiling stochastically that never asked to, with no
        # error anywhere.
        _stoch_uv["node"] = None

    # ==================================================================
    # MACRO VARIATION (schema v1.19). ONCE, on the COMPOSITED colour,
    # after every layer has blended and after the forest-floor tint.
    #
    # WHY POST-COMPOSITE and not per-layer: km-scale variation is
    # moisture, weathering, lichen and airborne deposition — processes
    # that cross the snow/rock/grass boundary. Per-layer strengths would
    # create visible discontinuities exactly AT the layer boundaries,
    # DRAWING the lines this feature exists to erase. It is also one
    # fetch and one multiply chain instead of three.
    #
    #     out = colour * (1 + strength * (2*tex - 1))
    #
    # The map's per-channel mean is EXACTLY 0.5 (asserted at bake and
    # again at import), so a fully-mipped or missing sample gives
    # (1 + s*0) = 1.0 and the composite renders UNTOUCHED. The degraded
    # state is the identity, by construction — the same guarantee the
    # per-layer variation textures carry.
    #
    # It rides the weightmap's UV chain, so it is clamped 1:1 over the
    # terrain and cannot repeat.
    # ==================================================================
    if _macro and _macromap and _weightmap:
        _mmt = _unreal.EditorAssetLibrary.load_asset(_macromap)
        if _mmt is None:
            raise RuntimeError("macro map asset not found: " + _macromap)
        _msamp = _n(_unreal.MaterialExpressionTextureSample, -1150, 1340)
        _bind_global(_msamp, _mmt, _macromap)
        _ll_wire(_mel, _uvw, "", _msamp, "UVs")

        _m2 = _n(_unreal.MaterialExpressionMultiply, -850, 1340)
        _ll_wire(_mel, _msamp, "RGB", _m2, "A")
        _ll_wire(_mel, _c(2.0, -1000, 1460), "", _m2, "B")
        _mc = _n(_unreal.MaterialExpressionSubtract, -700, 1340)
        _ll_wire(_mel, _m2, "", _mc, "A")
        _ll_wire(_mel, _c(1.0, -850, 1460), "", _mc, "B")
        _ms = _n(_unreal.MaterialExpressionMultiply, -550, 1340)
        _ll_wire(_mel, _mc, "", _ms, "A")
        _ll_wire(_mel, _c(float(_macro["strength"]), -700, 1460), "",
                 _ms, "B")
        _m1 = _n(_unreal.MaterialExpressionAdd, -400, 1340)
        _ll_wire(_mel, _ms, "", _m1, "A")
        _ll_wire(_mel, _c(1.0, -550, 1460), "", _m1, "B")
        _mv = _n(_unreal.MaterialExpressionMultiply, -200, 1340)
        _ll_wire(_mel, _col, _col_pin, _mv, "A")
        _ll_wire(_mel, _m1, "", _mv, "B")
        _col, _col_pin = _mv, ""

    # ==================================================================
    # OUTPUTS. Two routes, and which one is used is decided by the recipe.
    #
    # WHY THERE ARE TWO. MP_Displacement EXISTS at value 32
    # (SceneTypes.h:181) but is marked UMETA(Hidden), so UHT never
    # emitted it into the reflected Python MaterialProperty enum -- which
    # runs ... MP_FRONT_MATERIAL 30, MP_MATERIAL_ATTRIBUTES 33, MP_MAX 35,
    # with 31 and 32 simply absent. Proven unreachable with a positive
    # control rather than assumed: MaterialProperty(32) raises "Cannot
    # create instances of enum types", MaterialProperty.cast(32) raises
    # "Cannot cast type 'int' to 'MaterialProperty'", and
    # MaterialProperty.MP_MAX reads 35 in the same payload.
    #
    # So connect_material_property CANNOT wire Displacement, and the only
    # route is the material-attributes pin: MakeMaterialAttributes carries
    # `FExpressionInput Displacement`
    # (MaterialExpressionMakeMaterialAttributes.h:77) and
    # MP_MATERIAL_ATTRIBUTES (33) IS exposed.
    #
    # THE OLD PATH STAYS REACHABLE. It is the shipped configuration and
    # this is the main world's material; a recipe flag that can turn the
    # restructure off is what makes the change revertible without a git
    # checkout of a 129 KB binary asset.
    if _disp is None:
        _mat.set_editor_property("use_material_attributes", False)
        _mel.connect_material_property(
            _col, _col_pin, _unreal.MaterialProperty.MP_BASE_COLOR)
        _mel.connect_material_property(
            _rgh, "", _unreal.MaterialProperty.MP_ROUGHNESS)
        if _any_normal:
            # Only wire Normal when at least one layer supplies a map.
            # Connecting a constant (0,0,1) would be a no-op that still
            # forces the tangent-space path on for the whole material.
            _mel.connect_material_property(
                _nrm, _nrm_pin, _unreal.MaterialProperty.MP_NORMAL)
    else:
        # UNCONNECTED PINS TAKE THE ATTRIBUTE DEFAULT, NOT ZERO -- checked
        # at the source because the whole landscape's shading rides on it.
        # FMaterialAttributesInput::CompileWithDefault
        # (MaterialShared.cpp:767-770) falls back to
        # CompileDefaultExpression when the input compiles to INDEX_NONE,
        # and MaterialAttributeDefinitionMap.cpp:394-396 registers
        # Specular .5 / Metallic 0 / Roughness .5. So leaving Metallic and
        # Specular unwired here is the SAME shading the three-pin route
        # produced, not a black metal landscape.
        _mma = _n(_unreal.MaterialExpressionMakeMaterialAttributes,
                  600, -1900)
        _ll_wire(_mel, _col, _col_pin, _mma, "BaseColor")
        _ll_wire(_mel, _rgh, "", _mma, "Roughness")
        if _any_normal:
            _ll_wire(_mel, _nrm, _nrm_pin, _mma, "Normal")
        _ll_wire(_mel, _dsp, "", _mma, "Displacement")
        # Every one of those wires is CHECKED -- _ll_wire raises on a
        # failed connect. That matters more here than anywhere else in
        # this builder: these four pin names are exactly the class of
        # thing non-negotiable 23 says not to trust from memory, and
        # ConnectMaterialExpressions returns false and connects NOTHING
        # for an unresolvable pin name, leaving a material that compiles
        # clean and renders the default.
        _mat.set_editor_property("use_material_attributes", True)
        _mel.connect_material_property(
            _mma, "", _unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)

        # THE MATERIAL-LEVEL GATE. enable_tessellation is documented in
        # the reflected stub as "Whether or not tessellation is enabled.
        # Required for displacement to work." (PythonStub :81519). Without
        # it the Displacement pin is wired, compiles, and does nothing --
        # the silent-no-op shape this project keeps paying for.
        _mat.set_editor_property("enable_tessellation", True)
        _scaling = _mat.get_editor_property("displacement_scaling")
        _scaling.set_editor_property("magnitude", float(_disp["magnitude"]))
        _scaling.set_editor_property("center", float(_disp["center"]))
        _mat.set_editor_property("displacement_scaling", _scaling)

        # READ BACK, from the object rather than from the value we just
        # sent. A struct property assigned by value can fail to stick, and
        # "the call returned" has meant nothing on this project before
        # (three landscape mutations returned ok and moved nothing).
        _rb = _mat.get_editor_property("displacement_scaling")
        _out["displacement"] = {{
            "amplitude_ref_m": _disp["amplitude_ref"],
            "per_layer_m": _disp["per_layer"],
            "magnitude_wanted": float(_disp["magnitude"]),
            "magnitude_readback": float(
                _rb.get_editor_property("magnitude")),
            "center_readback": float(_rb.get_editor_property("center")),
            "enable_tessellation_readback": bool(
                _mat.get_editor_property("enable_tessellation")),
            "use_material_attributes_readback": bool(
                _mat.get_editor_property("use_material_attributes")),
        }}
        if abs(_out["displacement"]["magnitude_readback"]
               - float(_disp["magnitude"])) > 1e-6:
            raise RuntimeError(
                "displacement_scaling.magnitude did not stick: wanted "
                + str(_disp["magnitude"]) + ", reads "
                + str(_out["displacement"]["magnitude_readback"]))
        if not _out["displacement"]["enable_tessellation_readback"]:
            raise RuntimeError(
                "enable_tessellation did not stick; displacement would be "
                "wired and inert")
    _out["normal_maps_wired"] = bool(_any_normal)
    _out["material_attributes"] = _disp is not None

    # ---- landscape grass output (schema v1.7) -----------------------
    # Ground cover comes from the MATERIAL, not from placed instances.
    # The engine spawns and discards grass on the GPU near the camera,
    # so the count is bounded by view distance rather than by map area —
    # which is the only way to get dense cover over 65 km2 on this
    # hardware. 34/ha of persistent instances was 86k and read as bare
    # ground; grass at 8 per 10 m2 is denser by three orders of
    # magnitude and stores nothing.
    #
    # The density mask is `_masks[i]`, the SAME per-layer weight the
    # albedo blend uses, taken from the baked weightmap. Grass therefore
    # cannot disagree with what the ground looks like: one expression,
    # two consumers (lesson 1.9).
    _out["grass"] = []
    if _grass:
        _tools = _unreal.AssetToolsHelpers.get_asset_tools()
        _inputs = []
        _wire = []
        for _g in _grass:
            _gp = _g["asset"]
            if _unreal.EditorAssetLibrary.does_asset_exist(_gp):
                _gt = _unreal.EditorAssetLibrary.load_asset(_gp)
            else:
                _gt = _tools.create_asset(
                    _gp.rsplit("/", 1)[1], _gp.rsplit("/", 1)[0],
                    _unreal.LandscapeGrassType,
                    _unreal.LandscapeGrassTypeFactory())
            if _gt is None:
                _out["grass"].append({{"name": _g["name"], "ok": False,
                                      "why": "grass type could not be "
                                             "created or loaded"}})
                continue
            _vars = []
            _missing = []
            _bad_pivot = []
            for _v in _g["varieties"]:
                _gm = _unreal.EditorAssetLibrary.load_asset(_v["mesh"])
                if _gm is None:
                    # A missing variety is NOT skipped quietly. Skipping
                    # would silently redistribute its share to nothing
                    # and thin the whole species, which reads as "the
                    # density parameter does not work".
                    _missing.append(_v["mesh"])
                    continue
                # RULING (c): measure the pivot of the thing itself.
                # GrassVariety has NO pivot-offset field, so an
                # offset mesh cannot be corrected at any level --
                # the density mask and the visible grass just
                # disagree, forever. Name checks upstream cannot
                # see this; get_bounds() can.
                try:
                    _bb = _gm.get_bounds()
                    _bbo, _bbe = _bb.origin, _bb.box_extent
                    _poff = ((_bbo.x * _bbo.x +
                              _bbo.y * _bbo.y) ** 0.5) / 100.0
                    _sz = [_bbe.x * 2 / 100.0, _bbe.y * 2 / 100.0,
                           _bbe.z * 2 / 100.0]
                    _bz = (_bbo.z - _bbe.z) / 100.0
                except Exception as _pe:
                    _poff, _sz, _bz = None, None, None
                # Degenerate bounds report origin 0,0,0 -- a PASS --
                # exactly when there is no geometry to measure, so
                # they fail first. `not (x <= lim)` because NaN is
                # False for `x > lim` (section 2.8).
                if (_sz is None or any((_q != _q) or (_q <= 0.0)
                                       for _q in _sz)
                        or not isinstance(_poff, float)
                        or _poff != _poff):
                    _bad_pivot.append([_v["mesh"], None])
                    continue
                if not (_poff <= _MAX_PIVOT_M):
                    _bad_pivot.append([_v["mesh"], round(_poff, 4)])
                    continue
                # Vertical half: a base-centre pivot reads 0 here. GPU
                # grass aligns to the surface at the pivot, so a centre
                # pivot buries every blade to half its height.
                if (not isinstance(_bz, float) or _bz != _bz
                        or not (abs(_bz) <= _MAX_BASE_Z_M)):
                    _bad_pivot.append(
                        [_v["mesh"] + " (vertical)",
                         None if _bz is None or _bz != _bz
                         else round(_bz, 4)])
                    continue
                _vars.append((_v, _gm))
            if _missing:
                _out["grass"].append({{"name": _g["name"], "ok": False,
                                      "why": "meshes missing",
                                      "missing": _missing}})
                continue
            if _bad_pivot:
                _out["grass"].append({{
                    "name": _g["name"], "ok": False,
                    "why": "ruling (c): pivot offset unmeasurable or "
                           "over " + str(_MAX_PIVOT_M) + " m; GrassVariety "
                           "has no pivot correction, so the density mask "
                           "and the visible grass would disagree",
                    "bad_pivot": _bad_pivot}})
                continue
            # grass_density is INSTANCES PER 10 SQUARE METRES
            # (LandscapeGrassType.h, via the generated stub). A hectare
            # is 1000 of those, so per-hectare / 1000 converts.
            # CONSTRUCT EMPTY, THEN SET. Probed live rather than taken
            # from the stub, which shows a full keyword constructor for
            # GrassVariety and `def __init__(self) -> None` for
            # GrassInput — and the binding accepts NO arguments for the
            # latter ("call() takes at most 0 arguments (2 given)").
            # Section 6.1: the reflected surface is the contract.
            #
            # grass_density and the cull distances also refuse plain
            # numbers: they are PerPlatformFloat / PerPlatformInt, whose
            # constructors DO take one positional value. scale_x accepts
            # a FloatInterval or a two-element list.
            _built = []
            for _v, _gm in _vars:
                _var = _unreal.GrassVariety()
                _var.set_editor_property("grass_mesh", _gm)
                _var.set_editor_property(
                    "grass_density",
                    _unreal.PerPlatformFloat(_v["density"]))
                _var.set_editor_property(
                    "start_cull_distance",
                    _unreal.PerPlatformInt(int(_g["cull_cm"] * 0.75)))
                _var.set_editor_property(
                    "end_cull_distance",
                    _unreal.PerPlatformInt(int(_g["cull_cm"])))
                _var.set_editor_property("scaling",
                                         _unreal.GrassScaling.UNIFORM)
                _var.set_editor_property(
                    "scale_x",
                    _unreal.FloatInterval(_v["smin"], _v["smax"]))
                _var.set_editor_property("random_rotation", True)
                _var.set_editor_property("align_to_surface", True)
                _var.set_editor_property("cast_dynamic_shadow", False)
                # MATERIAL OVERRIDES on the variety. `GrassVariety` really
                # does carry `override_materials` in 5.8 (PythonStub
                # :121628, "Material Overrides"), which is what lets a
                # vendor grass mesh be rendered with OUR material without
                # editing the vendor asset.
                #
                # Needed by the blueberry understory: its master carries
                # the same `Level 1/2/3 Wind` static switches the PN trees
                # do, an animating understory makes every frame A/B
                # non-deterministic, and the pack is gitignored with 0
                # tracked files so the vendor MI must not be rewritten.
                #
                # FAILS CLOSED. A declared override that will not load is a
                # REFUSAL, never a silent fallback to the vendor material —
                # falling back would render wind-on grass under an asset
                # whose name says otherwise.
                _ovr = _v.get("override_materials") or []
                if _ovr:
                    _mats = []
                    _badmat = []
                    for _mp in _ovr:
                        _mi = _unreal.EditorAssetLibrary.load_asset(_mp)
                        if _mi is None:
                            _badmat.append(_mp)
                        else:
                            _mats.append(_mi)
                    if _badmat:
                        _out["grass"].append({{
                            "name": _g["name"], "ok": False,
                            "why": "declared override_materials failed to "
                                   "load: " + ", ".join(_badmat)}})
                        _built = None
                        break
                    _var.set_editor_property("override_materials", _mats)
                _built.append(_var)
            if _built is None:
                continue
            _gt.set_editor_property("grass_varieties", _built)
            # Placed deliberately, so exempt from the Engine scalability
            # thinning that exists for decorative grass. This machine runs
            # MEDIUM (CLAUDE.md), where that setting would quietly cut it.
            _gt.set_editor_property("enable_density_scaling", False)
            _unreal.EditorAssetLibrary.save_asset(_gp,
                                                  only_if_is_dirty=False)
            # READ BACK the varieties and re-derive the total density
            # from what actually landed on the asset. Setting a list and
            # counting the list you set proves nothing; summing the
            # densities the engine kept and comparing against the
            # species total is a different instrument (lesson 9.1).
            _got = _gt.get_editor_property("grass_varieties") or []
            _sum = 0.0
            _rows = []
            for _gv in _got:
                _d = _gv.get_editor_property("grass_density")
                _d = float(_d.get_editor_property("default")
                           if hasattr(_d, "get_editor_property") else _d)
                _sum += _d
                _m = _gv.get_editor_property("grass_mesh")
                # Overrides re-read from the SAVED asset, not counted off
                # the list we set — setting a list and counting the list
                # you set proves nothing (lesson 9.1, the same reason the
                # densities are re-summed above).
                _ov = _gv.get_editor_property("override_materials") or []
                _rows.append({{
                    "mesh": _m.get_path_name().split(".")[0] if _m
                            else None,
                    "density": round(_d, 5),
                    "override_materials": [
                        _x.get_path_name().split(".")[0] if _x else None
                        for _x in _ov]}})
            # COMPARE the read-back against what the recipe DECLARED, and
            # carry a verdict the host can gate on.
            #
            # Until 2026-08-15 `_ov` was read, stored into `variety_rows`,
            # transported to the host — and never compared, never printed
            # and never gated, while the comment above claimed it was
            # verified. The host loop reads only mesh and density, so a
            # grass type whose overrides the engine silently dropped
            # returned exit 0 with every instrument reporting success.
            #
            # That is not hypothetical: it is exactly what happened to all
            # eight blueberry varieties hours earlier, and it was caught
            # only because a SEPARATE tool (read_grass_type, in scripts/)
            # was written  [no dot-py here: the payload transport gate
            # refuses any payload line containing that suffix]
            # to ask the saved asset. A read-back nobody compares is not a
            # read-back; it is transport.
            _declared = {{}}
            for _v2 in _g["varieties"]:
                _dov = _v2.get("override_materials") or []
                if _dov:
                    _declared[_v2["mesh"]] = [
                        str(_x).split(".")[0] for _x in _dov]
            _ovr_bad = []
            for _r in _rows:
                _want = _declared.get(_r["mesh"])
                if _want is None:
                    continue
                if _r["override_materials"] != _want:
                    _ovr_bad.append({{
                        "mesh": _r["mesh"], "declared": _want,
                        "read_back": _r["override_materials"]}})
            _out["grass"].append({{
                "name": _g["name"], "asset": _gp,
                "varieties": len(_got),
                "variety_rows": _rows,
                "density_per_10m2": _g["density"],
                "density_readback_sum": round(_sum, 5),
                "density_matches": bool(
                    abs(_sum - float(_g["density"])) <= 0.001),
                "overrides_declared": len(_declared),
                "overrides_mismatched": _ovr_bad,
                "overrides_match": bool(not _ovr_bad),
                "ok": bool(_got)}})
            _gi = _unreal.GrassInput()
            _gi.set_editor_property("name", _g["name"])
            _gi.set_editor_property("grass_type", _gt)
            _inputs.append(_gi)
            _wire.append(_g["layer_index"])

        if _inputs:
            _go = _n(_unreal.MaterialExpressionLandscapeGrassOutput,
                     900, -1400)
            _go.set_editor_property("grass_types", _inputs)
            # The output's input pins are named by the GrassInput name,
            # so each connects to its own layer's weight mask.
            for _k, _li in enumerate(_wire):
                _ll_wire(_mel, 
                    _masks[_li], "", _go, _inputs[_k].get_editor_property(
                        "name"))
            _out["grass_output_inputs"] = len(_inputs)

    # MANDATORY POST-BUILD ASSERTION (shared utility, rule 4a).
    # DISTINCT-SET mode: this material samples each surface at a detail
    # AND a macro scale, so the multiplicity is a function of the recipe
    # rather than a constant. The set check still catches a texture that
    # should not be in the graph at all -- the debris signature.
    # A SURFACE SUPERSEDES `texture` ENTIRELY (schema v1.8) -- when a
    # band has surface_c the builder takes the _surface_albedo branch
    # and never samples the generated texture_asset. Declaring both is
    # how this spec was first written, and the assertion refused it:
    # T_Alpine_Snow/Rock/Grass came back "missing" because they are
    # correctly absent. The spec must describe what the builder DOES,
    # not what the recipe mentions.
    # PROJECTION 3 OF THE DECLARATION — the assertion.
    # One expression, no second list. The preflight loaded exactly these
    # paths; the graph sampled exactly these paths; the assertion demands
    # exactly these paths. Divergence is not expressible.
    _want_tex = [_r[5] for _r in _plan]
    _out["assert"] = _ll_assert_graph(_mel, _mat, _want_tex, True)
    if not _out["assert"]["exact"]:
        _out["error"] = ("material graph does not match spec: extra="
                         + ",".join(_out["assert"]["extra"])
                         + " missing=" + ",".join(_out["assert"]["missing"]))
        raise RuntimeError(_out["error"])

    _mel.layout_material_expressions(_mat)
    _errs = _mel.recompile_material(_mat)
    _out["compile_errors"] = [str(_e) for _e in (_errs or [])]
    # CHECKED SAVE: save, then re-load from disk and confirm.
    # The return value of save_asset is not the evidence; the file
    # is. make_foliage_material printed "saved" for five weeks
    # while saving nothing, because only the return was consulted.
    _ll_must.must_save(_asset_path, _unreal.EditorAssetLibrary)

    if _assign:
        _world = _unreal.get_editor_subsystem(
            _unreal.UnrealEditorSubsystem).get_editor_world()
        _hits = [_a for _a in
                 _unreal.GameplayStatics.get_all_actors_of_class(
                     _world, _unreal.Landscape)
                 if _a.get_actor_label() == _actor_name]
        _out["matches"] = len(_hits)
        if len(_hits) == 1:
            _hits[0].set_editor_property("landscape_material", _mat)
            _out["assigned"] = True

    _out["ok"] = not _out["compile_errors"]

print("{marker}" + _json.dumps(_out))
'''.format(asset=asset_path, bands=json.dumps(bands), assign=bool(assign),
           actor=actor_name, marker=MARKER, weightmap=weightmap,
           chan=tuple(WEIGHTMAP_CHANNELS),
           vchan=tuple(VARIANTMAP_CHANNELS),
           variantmap=variantmap,
           macromap=macromap,
           plan=json.dumps(plan or []),
           tri=json.dumps(tri or {}),
           macro=json.dumps(macro or {}),
           disp=json.dumps(disp),
           hblend=json.dumps(hblend),
           org_x=float(org_x), org_y=float(org_y),
           span_cm=float(span_cm), grass=json.dumps(grass or []),
           max_pivot=float(max_pivot),
           max_base_z=float(max_base_z))
    # Shared fragments prepended AFTER .format() so their braces are
    # never seen by the formatter. Guarded together, so the transport
    # guard inspects what is actually sent.
    return _guard_payload(material_graph.CLEAR_SRC
                          + material_graph.WIRE_SRC
                          + material_graph.ASSERT_SRC + rendered)


def _grass_cull_cm(sp):
    """Grass cull in centimetres, or REFUSE. There is no default.

    See the call site for why. Bounded identically to the recipe
    validator's rule — non-negotiable 24: the two must not be able to
    disagree about what a legal grass cull is, and the number that made
    them agree is R11's locked 50 m for Meadow.
    """
    v = sp.get("cull_distance_m")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(
            "grass species {0!r} has no usable cull_distance_m ({1!r}). "
            "There is no default: the previous one was 12000.0 m, which "
            "at 12 tufts/m2 is about 5.4 billion instances."
            .format(sp.get("name"), v))
    v = float(v)
    _max = import_heightmap.GRASS_CULL_MAX_M          # ONE definition (n-n 24)
    if not (0.0 < v <= _max) or v != v:
        raise ValueError(
            "grass species {0!r} has cull_distance_m {1} m; it must be in "
            "(0, {2}]. R11 locks Meadow at 50 m; the ceiling is the streaming "
            "range and the disc guard bounds the count."
            .format(sp.get("name"), v, _max))
    # GRASS DISC GUARD, the same one the validator applies (2026-09-27):
    # pi*cull^2*density/10 instances in the cull disc.
    d = sp.get("density_per_10m2")
    if isinstance(d, (int, float)) and not isinstance(d, bool) and d > 0:
        disc = math.pi * v * v * float(d) / 10.0
        if disc > import_heightmap.GRASS_DISC_MAX_INSTANCES:
            raise ValueError(
                "grass species {0!r}: cull {1} m x density {2} per 10 m2 = "
                "{3:,.0f} instances in the cull disc, over the guard of "
                "{4:,.0f}.".format(sp.get("name"), v, d, disc,
                                     import_heightmap.GRASS_DISC_MAX_INSTANCES))
    return v * 100.0


def grass_entries(recipe):
    """Recipe -> the grass-system species, resolved for the payload.

    Returns [] when the recipe declares no foliage or none of its species
    ask for `system: "grass"`, so a recipe written before schema v1.7
    builds exactly the material it built before.
    """
    fol = recipe.get("foliage")
    if not isinstance(fol, dict):
        return []
    layers = [l["name"] for l in recipe["material"]["layers"]]
    total = float(fol.get("density_per_hectare") or 0.0)
    out = []
    for sp in fol.get("species") or []:
        if sp.get("system") != "grass":
            continue
        if sp["layer"] not in layers:
            # The validator refuses this, so reaching it means the two
            # disagree. Skip loudly rather than index into nothing.
            print("  WARNING: grass species {0!r} SKIPPED: layer {1!r} is "
                  "not in the material's layers {2!r} — this species will "
                  "NOT be built.".format(sp.get("name"), sp.get("layer"),
                                         layers))
            continue
        # VARIETIES (schema v1.10). A LandscapeGrassType holds a LIST of
        # GrassVariety, and the vendor sets are authored as size classes
        # for exactly that — grass_medium_01 ships tiny/small/mid/tall/
        # large, spanning 0.048 m to 0.323 m. Driving all of it from one
        # mesh throws away the variation the asset was built to provide
        # and reads as a stamped texture at any density worth having.
        #
        # `density_per_10m2` stays the species TOTAL and is SPLIT by
        # share, so changing the variety list does not change how much
        # ground cover there is. Shares are normalised rather than
        # required to sum to 1: a list that sums to 0.99 should render,
        # not refuse, and the alternative is a validation error for a
        # rounding decision.
        #
        # A species with no `varieties` falls back to its single `mesh`,
        # so a v1.7 recipe builds exactly what it built before.
        total_density = float(sp["density_per_10m2"])
        raw = sp.get("varieties")
        if not raw:
            raw = [{"mesh": sp["mesh"], "share": 1.0,
                    "scale_range": sp["scale_range"]}]
        shares = [float(v.get("share", 1.0)) for v in raw]
        ssum = sum(s for s in shares if s > 0.0)
        if not (ssum > 0.0):
            # Every share zero or negative means the recipe asked for no
            # grass in a roundabout way. Say so rather than dividing.
            print("  WARNING: grass species {0!r} SKIPPED: every variety "
                  "share is zero or negative — this species will NOT be "
                  "built.".format(sp.get("name")))
            continue
        varieties = []
        for v, share in zip(raw, shares):
            if share <= 0.0:
                continue
            rng = v.get("scale_range") or sp["scale_range"]
            row = {
                "mesh": v["mesh"],
                "density": round(total_density * (share / ssum), 5),
                "smin": float(rng[0]),
                "smax": float(rng[1]),
            }
            # CARRY THE OVERRIDES THROUGH. This transform is the ONLY thing
            # the payload sees — the recipe's own variety dict never
            # reaches it — so a key omitted here is a key the builder
            # cannot act on, however carefully the payload handles it.
            #
            # Cost of learning that, 2026-08-15: the payload was taught to
            # set `override_materials`, the recipe declared them, the
            # validator accepted them, the builder reported success and
            # both audits passed — and all eight blueberry varieties read
            # back `overrides: NONE` off the saved asset. The claim was
            # false everywhere except in the one place nobody had asked.
            #
            # Only set when present, so Meadow (which declares none) keeps
            # an absent key rather than an empty list that reads like a
            # decision (NN21: a silent field is an inert field).
            if v.get("override_materials"):
                row["override_materials"] = list(v["override_materials"])
            varieties.append(row)
        # Engine unit directly; see the schema note on why grass does
        # not share the persistent-instance budget.
        out.append({
            "name": sp["name"],
            "asset": "/Game/Foliage/GT_{0}_{1}".format(
                recipe["biome_id"], sp["name"]),
            "layer_index": layers.index(sp["layer"]),
            "density": round(total_density, 4),
            # NO DEFAULT. This read `sp.get("cull_distance_m", 12000.0)`
            # until 2026-08-08 — a TWELVE KILOMETRE grass cull for any
            # species that omitted the key, which at Meadow's locked
            # 12 tufts/m2 is pi*12000^2*12 = about 5.4 BILLION instances
            # on a machine that has already lost its GPU to a TDR
            # timeout. The recipe validator now REQUIRES the key, but
            # this builder is runnable without preflight, so it refuses
            # here too rather than trusting that validation happened —
            # the same assumption that let an unknown rock `role` be
            # dropped silently earlier the same day.
            "cull_cm": _grass_cull_cm(sp),
            "varieties": varieties,
        })
    return out


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(marker):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source, marker=MARKER):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        # STAGE the payload to a file and pass the PATH, not the source text.
        # MODE_EXEC_FILE means the command IS A FILENAME -- and a file exec is
        # also what defines __file__, which the payload needs for its
        # `sys.path.insert(dirname(__file__)); import ll_must` (line ~1772).
        # Passing inline text runs it as a statement with NO __file__: the
        # Brief 7 build payload grew past whatever length used to let the
        # engine fall back to a temp file, and hit `NameError: __file__`
        # BEFORE the destructive clear. ue_exec.run() has always staged for
        # exactly this reason (ue_exec.py:84-114); mirror it here.
        stage_dir = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "LLPython")
        os.makedirs(stage_dir, exist_ok=True)
        path = os.path.join(stage_dir, "make_landscape_material_payload.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        # ll_must.py beside it, copied fresh so the staged module is never
        # older than the repo's (ue_exec does the same). Non-fatal if absent:
        # a payload that does not import it is unaffected.
        _llm = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ll_must.py")
        if os.path.isfile(_llm):
            with open(_llm, "r", encoding="utf-8") as fh:
                _mod = fh.read()
            with open(os.path.join(stage_dir, "ll_must.py"), "w",
                      encoding="utf-8") as fh:
                fh.write(_mod)
        r = remote.run_command(path.replace("\\", "/"), unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("  command failed: {0}".format((r or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(r), marker)
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=6.0)
    p.add_argument("--assign", action="store_true")
    p.add_argument("--build-level", default=None,
                   help="level the gate must find open INSTEAD of the recipe's "
                        "landscape.level_path -- for rebuilding the material ASSET "
                        "while a light level is open. Refused with --assign: "
                        "assignment needs the recipe's own world. Added 2026-09-27 "
                        "(Brief 7 P3b): the 797k-tree Alpine8K editor sits at "
                        "25 GB private on this 31.4 GB host and leaves no room for "
                        "a shader-compiling rebuild; M_Alpine8K is already assigned "
                        "and the rebuild is in place at the same path.")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        for e in errors:
            print("  - {0}".format(e))
        return 2
    mat_errors = import_heightmap._validate_material(recipe.get("material"))
    if mat_errors:
        print("REFUSE: material block invalid:")
        for e in mat_errors:
            print("  - {0}".format(e))
        return 2
    # layer_bands() feeds biome_id into landscape_spec.texture_asset_path,
    # whose docstring states the caller has already validated it against
    # ^[a-z][a-z0-9_]*$. Nothing on THIS path did: derive_spec and
    # _validate_material both ignore biome_id, so an absent key raised
    # KeyError (exit 1, contradicting the documented exit-code contract)
    # and a malformed one silently produced a texture path that can never
    # match what import_layer_textures.py created. Enforce the documented
    # precondition here.
    biome = recipe.get("biome_id")
    if not isinstance(biome, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", biome):
        print("REFUSE: biome_id must match ^[a-z][a-z0-9_]*$, got {0!r} — "
              "it determines every layer's texture asset path".format(biome))
        return 2

    asset_path = recipe["material"]["parent_material"]

    # CROSS-FIELD REFUSAL, host-side, before any derivation: variant_map
    # and macro_variation both sample on the weightmap's UV chain, so
    # declaring either without weightmap plans textures the graph never
    # samples — the failure then lands at the post-build assertion AFTER
    # the destructive clear, the exact mid-build death the preflight
    # ordering exists to prevent. Refuse here instead (exit 2).
    _mat_block = recipe.get("material") or {}
    if not _mat_block.get("weightmap"):
        for _needs_wm in ("variant_map", "macro_variation"):
            if _mat_block.get(_needs_wm):
                print("REFUSE: material.{0} is declared without "
                      "material.weightmap — it rides the weightmap's UV "
                      "chain and cannot be sampled without it."
                      .format(_needs_wm))
                return 2

    # RECIPE faults from the layer_bands lane (stochastic_tiling,
    # forest_floor, band invariants) are ValueError and honour the
    # documented exit-2 contract — same class as texture_plan below.
    # Without this they fell to the generic handler as exit 1.
    try:
        bands = layer_bands(recipe)
        (weightmap_asset, variant_asset, macro_asset, _org_x, _org_y,
         span_cm) = weightmap_uv_params(recipe)
    except ValueError as exc:
        print("REFUSE: {0}".format(exc))
        return 2

    # THE ONE DECLARATION, reduced. Any fault here is a RECIPE fault and
    # is refused before a single byte reaches the editor.
    try:
        plan = texture_plan(bands, weightmap=weightmap_asset,
                            variantmap=variant_asset,
                            macromap=macro_asset)
    except TexturePlanError as exc:
        print("REFUSE: {0}".format(exc))
        return 2
    print("  texture plan : {0} sampled textures across {1} band(s)"
          .format(len(plan), len(bands)))

    # v1.21. Printed with its DERIVED engine magnitude and the physical
    # amplitude side by side, because the two differ by the landscape's
    # vertical scale and only one of them is meaningful to a reader.
    try:
        disp = displacement_spec(recipe)
    except ValueError as exc:
        print("REFUSE: {0}".format(exc))
        return 2
    if disp is None:
        print("  displacement : off (three-pin output path)")
    else:
        # schema v1.27: PER LAYER. The engine magnitude carries the MAX
        # layer (amplitude_ref); the graph scales the rest down. Print the
        # per-layer table, not a single amplitude, so the summary describes
        # the feature rather than one number.
        print("  displacement : per-layer, ref {0:.3f} m -> magnitude {1:.5f} "
              "at center {2}".format(disp["amplitude_ref"], disp["magnitude"],
                                     disp["center"]))
        for _ln, _amp in sorted(disp["per_layer"].items()):
            print("                 {0:<14} {1:.3f} m  (k {2:.3f})".format(
                _ln, _amp, _amp / disp["amplitude_ref"]))
        print("                 (scale_z {0:.1f} cm/unit; the engine "
              "default 4.0 would be +/-{1:.1f} m here)".format(
                  disp["scale_z"], 4.0 / 2.0 * disp["scale_z"] / 100.0))
        print("                 OUTPUT PATH: use_material_attributes + "
              "MakeMaterialAttributes")

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("Material        : {0}".format(asset_path))
    print("Assign to       : {0}".format(
        spec["actor_name"] if args.assign else "(not assigning)"))
    print("")
    for b in bands:
        print("  {0:<8} rgb {1}  rough {2}".format(
            b["name"], b["color"], b["roughness"]))
        print("     slope {0}..{1} deg  feather {2:.1f} deg".format(
            b["slope_deg"][0], b["slope_deg"][1], b["feather_deg"]))
        print("     height {0}..{1} m  feather {2:.0f} m".format(
            b["height_m"][0], b["height_m"][1], b["feather_m"]))
        if b["texture_asset"]:
            print("     texture {0}".format(b["texture_asset"]))
            print("       detail {0:.0f} m{1}   albedo = base_color * "
                  "{2} * samples".format(
                      b["uv_detail_cm"] / 100.0,
                      "   macro {0:.0f} m".format(b["uv_macro_cm"] / 100.0)
                      if b["uv_macro_cm"] else "",
                      4 if b["uv_macro_cm"] else 2))
        else:
            print("     texture (none) — flat base_color")
        _F = b.get("forest")
        if _F:
            if _F.get("driver") == "weightmap_alpha":
                print("     forest floor (v1.25)  mask = weightmap ALPHA "
                      "(canopy-derived)")
            else:
                print("     forest floor (v1.11)  height {0:.0f}..{1:.0f} m"
                      "  feather {2:.0f} m".format(
                          _F["height_m"][0], _F["height_m"][1],
                          _F["feather_m"]))
            print("       albedo *= lerp(white, rgb {0}, mask * {1})"
                  .format(_F["tint"], _F["strength"]))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        # Level gate (schema v1.2). Rule 7 proved the PROJECT; this proves
        # the LEVEL. Runs before anything is built, because a material
        # built against the wrong world is not merely useless — assigning
        # it would bind the recipe's material to a stranger's terrain.
        print("--- level gate (recipe landscape.level_path) ---")

        def _lvl_runner(source, marker):
            return _run(remote_exec, remote, node["node_id"], source, marker)

        # .get(), not [] — a recipe missing level_path must become a gate
        # REFUSAL with a named cause, not a KeyError that exits 1 against
        # a documented exit-code contract that has no 1 for this. Nothing
        # on this path runs _validate_landscape, so gate_level validates
        # its own expected value (fail closed on an unusable expectation).
        want_level = (recipe.get("landscape") or {}).get("level_path")
        if args.build_level:
            if args.assign:
                print("REFUSE: --build-level cannot be combined with --assign: "
                      "assignment binds the material to the landscape of the "
                      "recipe's own world, which is not the level open here.")
                return 6
            print("  --build-level {0!r}: the gate asserts THIS level; the "
                  "recipe's {1!r} is not required open for an in-place asset "
                  "rebuild without assignment".format(args.build_level, want_level))
            want_level = args.build_level
        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"], want_level, _lvl_runner)
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            print("")
            print("  Conduct rule 7 verified the PROJECT, and it matches.")
            print("  This is a different check: the wrong WORLD is open")
            print("  inside the right project. Open {0!r} and re-run."
                  .format(want_level))
            return 6
        print("  level {0}".format(detail))
        print("")

        # World Partition residency, but ONLY for --assign. Assignment
        # finds the landscape via get_all_actors_of_class, which exposes
        # LOADED actors only: on a fresh editor session that returns 0 and
        # the script would report "no landscape found" for a landscape
        # that is plainly there. Reuses capture.py's gate rather than
        # reimplementing it, so the two cannot drift.
        #
        # Building the material needs no residency - it touches an asset,
        # not the level - so a build-only run is not gated on it.
        if args.assign:
            print("--- residency (World Partition) ---")
            res = _run(remote_exec, remote, node["node_id"],
                       capture.RESIDENCY_SOURCE, capture.PROBE_MARKER)
            if res is None:
                print("FAIL: the residency probe returned nothing.")
                return 5
            if res.get("load_error"):
                print("  load error: {0}".format(res["load_error"]))
            print("  landscapes  {0} of {1} on disk".format(
                (res.get("have") or [None])[0],
                (res.get("want") or [None])[0]))
            print("  proxies     {0} of {1} on disk".format(
                (res.get("have") or [None, None])[1],
                (res.get("want") or [None, None])[1]))
            if not res.get("ok"):
                print("")
                print("REFUSE: World Partition terrain is not fully "
                      "resident, so an actor census here would be "
                      "partial. Assigning against a partial census "
                      "risks binding the material to the wrong "
                      "landscape, or reporting 0 for one that exists.")
                return 5
            print("  fully resident")
            print("")

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(asset_path, bands, args.assign,
                          spec["actor_name"],
                          weightmap=weightmap_asset,
                          variantmap=variant_asset,
                          macromap=macro_asset,
                          plan=plan,
                          tri=_tri_spec(recipe),
                          macro=(recipe['material'].get('macro_variation') or {}),
                          disp=disp,
                          hblend=height_blend_spec(recipe),
                          org_x=_org_x, org_y=_org_y,
                          span_cm=span_cm,
                          grass=grass_entries(recipe),
                          max_pivot=landscape_spec.MAX_PIVOT_OFFSET_M))
        if r is None:
            print("FAIL: build payload returned nothing (any traceback is")
            print("  printed above).")
            print("")
            print("  WARNING: the payload clears the existing graph with")
            print("  delete_all_material_expressions() before rebuilding.")
            print("  If it died mid-build, {0}".format(asset_path))
            print("  is now EMPTY in memory and dirty, while the copy on")
            print("  disk is still good. Do NOT 'Save All' and do not save")
            print("  the level — re-run this script after fixing the cause;")
            print("  a clean run rewrites the graph and saves it.")
            # NN25: this used to assert "missing texture assets are
            # pre-flighted before the clear and CANNOT cause this". It
            # printed unchanged on exactly that failure, because the
            # preflight only knows the keys it was told about. A claim
            # worth putting in a warning is a claim worth asserting;
            # this one is now a pointer to the likely cause instead.
            print("  (Texture assets ARE pre-flighted before the clear —")
            print("  but only the ones the preflight knows to look for.")
            print("  A sampler added without its preflight entry looks")
            print("  exactly like this.)")
            return 4
        if r.get("error"):
            print("FAIL: {0}".format(r["error"]))
            return 4
        print("  material {0}".format(
            "CREATED" if r.get("created") else "reused (find-or-create)"))
        # Shared clear/assert result, printed on EVERY run (rule 4a). A
        # nonzero survivor count or any EXTRA sampler is the signature of
        # the class this exists to contain; it must never require going
        # looking. This builder computed a residual count for two
        # sessions and never printed it.
        material_graph.report(r)
        if r.get("compile_errors"):
            for e in r["compile_errors"]:
                print("    {0}".format(e))
            return 4
        print("  compiled clean")

        # GRASS, read back off the asset. This was computed and never
        # printed, which is the same as not checking it: the whole point
        # of re-deriving the total from the varieties the engine kept is
        # that somebody sees the two numbers disagree.
        grass = r.get("grass") or []
        if grass:
            print("")
            print("  --- grass types (schema v1.10) ---")
        bad_grass = []
        for g in grass:
            if not g.get("ok"):
                print("  {0}: FAILED — {1}{2}".format(
                    g.get("name"), g.get("why", "no reason recorded"),
                    " {0}".format(g["missing"]) if g.get("missing") else ""))
                for row in g.get("bad_pivot") or []:
                    print("      {0}  pivot {1} m".format(
                        row[0], "UNMEASURABLE" if row[1] is None else row[1]))
                bad_grass.append(g.get("name"))
                continue
            print("  {0}  ->  {1}".format(g.get("name"), g.get("asset")))
            for row in g.get("variety_rows") or []:
                ovr = row.get("override_materials") or []
                print("      {0:<34} {1:6.3f} /10m2   overrides: {2}".format(
                    str(row.get("mesh", "")).split("/")[-1],
                    row.get("density", 0.0),
                    ", ".join(str(o).split("/")[-1] for o in ovr)
                    if ovr else "none"))
            print("      {0} variety(ies), densities sum to {1} against a "
                  "species total of {2}".format(
                      g.get("varieties"), g.get("density_readback_sum"),
                      g.get("density_per_10m2")))
            if not g.get("density_matches"):
                print("      MISMATCH: the engine kept a different total "
                      "than the recipe asked for.")
                bad_grass.append(g.get("name"))
            # OVERRIDE MATERIALS ARE NOW GATED, not merely transported.
            # Added 2026-08-15 after the read-back was found to be dead:
            # computed in the payload, carried to the host, and discarded.
            # The blueberry overrides were silently dropped and every
            # instrument here reported success.
            if g.get("overrides_declared") and not g.get("overrides_match"):
                print("      OVERRIDE MISMATCH: the recipe declared "
                      "material overrides that are NOT on the saved asset.")
                for m in g.get("overrides_mismatched") or []:
                    print("        {0}".format(
                        str(m.get("mesh", "")).split("/")[-1]))
                    print("          declared  {0}".format(m.get("declared")))
                    print("          read back {0}".format(m.get("read_back")))
                print("      The variety renders with its VENDOR material. "
                      "For a wind-off override that means wind ON, under an "
                      "asset whose name says otherwise.")
                bad_grass.append(g.get("name"))
        if bad_grass:
            print("")
            print("FAIL: grass type(s) did not verify: {0}".format(
                ", ".join(str(n) for n in bad_grass)))
            return 4
        if r.get("grass_output_inputs") is not None:
            print("  grass output wired to {0} layer mask(s)".format(
                r["grass_output_inputs"]))

        if args.assign:
            if not r.get("assigned"):
                print("FAIL: need exactly one landscape labelled {0!r} "
                      "(found {1})".format(spec["actor_name"],
                                           r.get("matches")))
                return 5
            print("  assigned to {0!r}".format(spec["actor_name"]))
            print("  NOTE: in-memory only; not saved.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    # RESOURCE GUARD. Heavy operations log the memory situation before
    # they start and hold a lock so two never drive the same editor at
    # once (scripts/resource_guard.py). Low memory WARNS; a concurrent
    # heavy op REFUSES at exit 8.
    try:
        with resource_guard.HeavyOp('landscape material rebuild') as _guard_ok:
            if not _guard_ok:
                sys.exit(8)
            sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
