"""prove_gates.py — make every gate REFUSE, on purpose, on demand.

Non-negotiable 2: *a gate that has only seen good input has not been
tested.* This is the instrument that gives that rule teeth. It runs
entirely on the CPU — no editor, no remote execution, no assets — so it
can run on every commit and during a cold recipe replay.

FOUR KINDS OF PROOF
-------------------
`mutations`  Break the CPU model of a shader construct in a way a real
             mis-wiring would, and require the invariant suite to catch
             it. This is the only way to know a suite that PASSES is
             doing any work at all.

`probes`     Feed the recipe validator a value that must be rejected,
             and require a matching error. Each probe names the DAMAGE
             the value would do, not just the rule it breaks.

`adoption`   Exercise `place_foliage.adopt_rock_plans` through its real
             filesystem path. This is the gate in front of the orphan
             sweep, and its failure mode is 157,554 conifers deleted —
             not a wrong number in a printout.

`dead-gate`  Fail if ANY check-like function in `scripts/` has no call
             site. The structural half of the lesson below: wiring three
             dead suites up was the local fix, this is what stops a
             fourth.

WHY IT EXISTS
-------------
`_assert_triplanar_invariants()` and `_assert_heightlerp_invariants()`
were written carefully, were correct, and were DEAD — both return a
failure list and nothing ever called them. RECIPES.md R2 meanwhile said
the heightlerp properties were "proven by `_assert_heightlerp_
invariants()` before" the build. For as long as that sentence stood, the
prose was the only thing holding the claim up.

The first run after wiring them up refused 3 of 5 mutations. The two
survivors were both real:

  * sign independence was asserted at `S = 2.0` alone — the value in
    `recipes/alpine.json` — and at an EVEN exponent `nx**s == |nx|**s`
    identically, so the property could not fail. The validator admits
    any sharpness in [1, 8]. **A suite pinned to the shipped value
    tests the recipe, not the code, and the recipe is the part that is
    free to change.**
  * applying the slope mask to the Z weight as well as the side weights
    survived all six properties — m=0 still collapsed to the top-down
    sample, walls still excluded it, routing was intact, the blend
    stayed convex — while being wrong across the whole 45-50 degree
    band the feature exists for. It took a property stated against an
    INDEPENDENT reference (canonical triplanar) rather than against the
    same arithmetic.

Exit codes:
  0  every mutation refused and every probe rejected
  4  at least one mutation survived or one probe was accepted
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import import_heightmap as ih   # noqa: E402
import landscape_spec as ls     # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
TARGET = os.path.join(REPO_ROOT, "scripts", "make_landscape_material.py")
RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine.json")

# (label, exact source to replace, replacement). Each is a mis-wiring
# somebody could plausibly commit — not a random character edit. A
# mutation that no reviewer would ever write proves nothing about the
# suite's ability to catch the ones they would.
MUTATIONS = [
    ("triplanar: drop Abs on the X normal",
     "    wx = (abs(nx) ** sharpness) * m",
     "    wx = (nx ** sharpness) * m"),
    ("triplanar: swap the X and Y weight routing",
     "    wx = (abs(nx) ** sharpness) * m\n"
     "    wy = (abs(ny) ** sharpness) * m",
     "    wx = (abs(ny) ** sharpness) * m\n"
     "    wy = (abs(nx) ** sharpness) * m"),
    ("triplanar: forget the normalising divide",
     "    return (sx * wx + sy * wy + sz * wz) / den",
     "    return (sx * wx + sy * wy + sz * wz)"),
    ("triplanar: mask the Z weight as well as the sides",
     "    wz = abs(nz) ** sharpness",
     "    wz = (abs(nz) ** sharpness) * (1.0 - m)"),
    ("triplanar: mask reaches only ONE side plane",
     "    wy = (abs(ny) ** sharpness) * m",
     "    wy = (abs(ny) ** sharpness)"),
    ("triplanar: sharpness ignored on the Z plane",
     "    wz = abs(nz) ** sharpness",
     "    wz = abs(nz)"),
]


def _heightlerp_mutation(src):
    """The height window is what makes this a height blend, not a lerp."""
    i = src.find("def _cpu_heightlerp(")
    if i < 0:
        return None
    for ln in src[i:src.find("\ndef ", i + 10)].split("\n"):
        if "hw" in ln and "4" in ln and "=" in ln:
            return ("heightlerp: kill the height window (becomes a lerp)",
                    ln, ln.split("=")[0] + "= 0.0")
    return None


def run_mutations(verbose=True):
    src = io.open(TARGET, encoding="utf-8").read()
    cases = list(MUTATIONS)
    hm = _heightlerp_mutation(src)
    if hm:
        cases.append(hm)

    tmpdir = tempfile.mkdtemp(prefix="ll_prove_")
    caught = survived = skipped = 0
    for n, (label, old, new) in enumerate(cases):
        if src.count(old) != 1:
            if verbose:
                print("  SKIP (anchor not unique)  {0}".format(label))
            skipped += 1
            continue
        path = os.path.join(tmpdir, "mutant_{0}.py".format(n))
        io.open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
        spec = importlib.util.spec_from_file_location("_mut%d" % n, path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            caught += 1
            if verbose:
                print("  refused   {0}".format(label))
        else:
            survived += 1
            if verbose:
                print("  SURVIVED  {0}".format(label))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass
    return caught, survived, skipped


def _species(recipe, rock):
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if ("role" in sp) == rock:
            return sp
    return None


def _grass_sp(recipe):
    """The first grass-system species, for whole-recipe probes."""
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if isinstance(sp, dict) and sp.get("system") == "grass":
            return sp
    return None


def _inst_sp(recipe):
    """The first INSTANCED (non-grass) vegetation species.

    Its cull is the one that actually hung this GPU. `system` defaults to
    "instanced" when absent, so the default must be treated as instanced
    here exactly as the validator treats it — reading only an explicit
    `system == "instanced"` would silently skip every species that relies
    on the default, which is most of them.
    """
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if isinstance(sp, dict) and sp.get("system", "instanced") == "instanced":
            return sp
    return None


def _nav(**over):
    """A VALID navigation block, with overrides.

    The probe baseline recipe carries no `navigation` (the block is
    optional and arrived with alpine_8k), so each probe installs a good
    one and breaks exactly one field. That keeps every refusal
    attributable to the field under test rather than to the block being
    malformed in some other way.
    """
    nav = {
        "tile_size_uu": 1600.0,
        "average_layers_per_tile": 1.5,
        "max_simultaneous_tile_generation_jobs": 16,
        "min_region_dimension_uu": 400.0,
        "data_gathering_mode": "lazy",
        "chunk_grid_size_cm": 102400,
        "builder_loading_cell_size_cm": 102400,
        "bounds_volumes": [{
            "name": "NavBounds_Probe",
            "min_cm": [307200.0, -409600.0, 24500.0],
            "max_cm": [409600.0, -307200.0, 42000.0],
            "basis": "probe",
        }],
    }
    nav.update(over)
    return nav


def _install_nav(recipe, **over):
    recipe["navigation"] = _nav(**over)
    return recipe["navigation"]


def _set_rock(recipe, key, value):
    """Set a key on the first ROCK species, for whole-recipe probes.

    Cross-field probes mutate the recipe rather than one species, but
    still need the species side of the condition set — otherwise the
    probe would test "recipe missing a block nobody asked for", which no
    gate should refuse and which would therefore read as a FALSE PASS.
    """
    sp = _species(recipe, True)
    if sp is not None:
        sp[key] = value
    return sp


# (label, is_rock, mutation, substring the error must contain)
PROBES = [
    # --- rock species: keys that belong to the OTHER kind -------------
    ("rock carrying weight_share (would raid the tree budget)", True,
     lambda s: s.update(weight_share=0.2), "unknown key"),
    ("rock carrying layer= (vegetation's spelling of a mask)", True,
     lambda s: s.update(layer="Grass"), "unknown key"),
    ("rock carrying density_per_10m2", True,
     lambda s: s.update(density_per_10m2=3.0), "unknown key"),
    # --- vegetation must NOT have loosened when the sets were split ---
    ("tree carrying mask= (rock's spelling)", False,
     lambda s: s.update(mask={"kind": "slope"}), "unknown key"),
    ("tree carrying embed_frac", False,
     lambda s: s.update(embed_frac=0.2), "unknown key"),
    ("tree carrying a typo'd key", False,
     lambda s: s.update(weightshare=0.2), "unknown key"),
    ("tree sink_depth_m 0.9 (buries the first branches)", False,
     lambda s: s.update(sink_depth_m=0.9), "sink_depth_m"),
    ("tree sink_depth_m negative (floats the flare)", False,
     lambda s: s.update(sink_depth_m=-0.05), "sink_depth_m"),
    ("rock carrying sink_depth_m (embed_frac is its spelling)", True,
     lambda s: s.update(sink_depth_m=0.1), "unknown key"),
    # --- rock bounds --------------------------------------------------
    ("role misspelt", True, lambda s: s.update(role="heros"),
     "role must be one of"),
    ("mask absent", True, lambda s: s.pop("mask"),
     "mask must be an object"),
    ("mask.kind unknown", True,
     lambda s: s["mask"].update(kind="curvature"), "mask.kind"),
    ("mask.layer names no material layer", True,
     lambda s: s["mask"].update(layer="Lava"), "must name a material layer"),
    ("talus mask with no saturation", True,
     lambda s: s["mask"].update(kind="talus", saturation=None),
     "saturation is required"),
    ("density 0/ha (places nothing, silently)", True,
     lambda s: s.update(density_per_hectare_on_mask=0.0),
     "density_per_hectare_on_mask"),
    ("density 900/ha (would exceed the instance budget)", True,
     lambda s: s.update(density_per_hectare_on_mask=900.0),
     "density_per_hectare_on_mask"),
    ("embed_frac 0.9 (buries more than half the rock)", True,
     lambda s: s.update(embed_frac=0.9), "embed_frac"),
    ("embed_frac negative (floats the rock)", True,
     lambda s: s.update(embed_frac=-0.1), "embed_frac"),
    ("align_to_normal 1.4", True,
     lambda s: s.update(align_to_normal=1.4), "align_to_normal"),
    ("tumble_deg 200", True, lambda s: s.update(tumble_deg=200.0),
     "tumble_deg"),
    # --- placement priors (schema v1.21) -----------------------------
    # Both knobs feed placement_priors.centred_bias, whose multiplier is
    # clip(1 + bias*(v - ref)*2, 0, 2). Past |1.0| the clip does the work
    # and the number stops changing the result — a knob that lies.
    ("flow_bias 2.0 (past the shared multiplier's own clip)", True,
     lambda s: s.update(flow_bias=2.0), "flow_bias must be in"),
    ("flow_bias -1.5", True, lambda s: s.update(flow_bias=-1.5),
     "flow_bias must be in"),
    ("canopy_bias 3.0", True, lambda s: s.update(canopy_bias=3.0),
     "canopy_bias must be in"),
    ("canopy_bias 'lots' (a string)", True,
     lambda s: s.update(canopy_bias="lots"), "canopy_bias must be in"),
    # CROSS-FIELD: a canopy prior with no declared canopy source. The
    # planner refuses too; this proves preflight catches it FIRST, which
    # is the point of a preflight (non-negotiable 24 — both checks key
    # off canopy_bias != 0, so they cannot disagree about whether the
    # block is required).
    ("canopy_bias set but foliage.canopy REMOVED", None,
     lambda r: (_set_rock(r, "canopy_bias", 0.6),
                r["foliage"].pop("canopy", None)),
     "no `foliage.canopy` block"),
    ("foliage.canopy.radius_m 0 (a canopy with no extent)", None,
     lambda r: (_set_rock(r, "canopy_bias", 0.6),
                r["foliage"]["canopy"].update(radius_m=0.0)),
     "radius_m must be in"),
    ("foliage.canopy.radius_m 90 (a 90 m fir)", None,
     lambda r: (_set_rock(r, "canopy_bias", 0.6),
                r["foliage"]["canopy"].update(radius_m=90.0)),
     "radius_m must be in"),
    ("foliage.canopy.plan absent", None,
     lambda r: (_set_rock(r, "canopy_bias", 0.6),
                r["foliage"]["canopy"].pop("plan", None)),
     "canopy.plan must be a filename"),
    # --- grass cull: the field that once hung this GPU ----------------
    # Optional until 2026-08-08, and the builder then substituted
    # 12000.0 m — about 5.4 BILLION instances at Meadow's locked
    # 12 tufts/m2. Non-negotiable 3: the catastrophic value is now
    # unreachable rather than rejected.
    ("grass species with NO cull_distance_m (was a 12 km default)", None,
     lambda r: _grass_sp(r).pop("cull_distance_m", None),
     "cull_distance_m is REQUIRED"),
    ("grass cull_distance_m 12000 (the old default, explicitly)", None,
     lambda r: _grass_sp(r).update(cull_distance_m=12000.0),
     "cull_distance_m is REQUIRED"),
    ("grass cull_distance_m 0 (0 means DISABLED, not unlimited)", None,
     lambda r: _grass_sp(r).update(cull_distance_m=0.0),
     "cull_distance_m is REQUIRED"),
    ("grass cull_distance_m 'far' (a string)", None,
     lambda r: _grass_sp(r).update(cull_distance_m="far"),
     "cull_distance_m is REQUIRED"),
    # --- INSTANCED cull: the same field, on the path that actually hung
    # the GPU. Closed 2026-08-15, seven days after the GRASS half.
    #
    # The 2026-08-08 fix went into the grass branch and was never swept to
    # the instanced branch forty lines above it — even though the hang
    # happened on the INSTANCED path and the grass comment says so in its
    # own words. Non-negotiable 4: fixed locally, never swept. These four
    # probes exist so the sweep cannot silently come undone.
    ("instanced species with NO cull_distance_m (engine default is 0)",
     None, lambda r: _inst_sp(r).pop("cull_distance_m", None),
     "cull_distance_m is REQUIRED"),
    ("instanced cull_distance_m 0 (FoliageType.h:292 — 0 DISABLES)",
     None, lambda r: _inst_sp(r).update(cull_distance_m=0.0),
     "cull_distance_m is REQUIRED"),
    ("instanced cull_distance_m 100000 (was the accepted ceiling)",
     None, lambda r: _inst_sp(r).update(cull_distance_m=100000.0),
     "cull_distance_m is REQUIRED"),
    ("instanced cull_distance_m 'far' (a string)",
     None, lambda r: _inst_sp(r).update(cull_distance_m="far"),
     "cull_distance_m is REQUIRED"),
    ("scale_range inverted", True,
     lambda s: s.update(scale_range=[2.0, 0.5]), "scale_range"),
    ("cull_distance_m 0", True, lambda s: s.update(cull_distance_m=0.0),
     "cull_distance"),
    ("lod_depth 0", True, lambda s: s.update(lod_depth=0), "lod_depth"),
    ("lod_depth True (a bool IS an int in Python)", True,
     lambda s: s.update(lod_depth=True), "lod_depth"),
    ("lod_depth 3.5", True, lambda s: s.update(lod_depth=3.5), "lod_depth"),
    ("lod_depth 5 (longer than the cost model can express)", True,
     lambda s: s.update(lod_depth=5), "cannot express a longer chain"),
    ("lod_depth 3 while the mesh MEASURES 4", True,
     lambda s: s.update(lod_depth=3), "but the mesh MEASURES"),
    # --- lighting physics ---------------------------------------------
    ("sun intensity_lux 18000 (a GROUND reading in a TOA field)", None,
     lambda r: r["lighting"]["sun"].update(intensity_lux=18000.0),
     "TOP-OF-ATMOSPHERE"),
    ("sun intensity_lux 5.0 (the historical black-frame value)", None,
     lambda r: r["lighting"]["sun"].update(intensity_lux=5.0),
     "TOP-OF-ATMOSPHERE"),
    ("sun intensity_lux 1e6", None,
     lambda r: r["lighting"]["sun"].update(intensity_lux=1000000.0),
     "TOP-OF-ATMOSPHERE"),
    # --- the pivot substitution ---------------------------------------
    ("rock mesh with no measured-pivot row", True,
     lambda s: s.update(mesh="/Game/KiteDemo/Environments/Rocks/No/No"),
     "no row in the measured-pivot report"),
    # --- COLLISION (schema v1.23) --------------------------------------
    # Measured 2026-08-16: all 14 FT_* assets read NoCollision, so NOTHING
    # in either world collided but the landscape — including the three
    # species whose MESHES carry a vendor-authored trunk capsule. The
    # cause was silence: place_foliage.py never mentioned collision in any
    # form, so UFoliageType's NoCollision constructor default stood
    # (InstancedFoliage.cpp:640) and was copied onto the component
    # unconditionally (:1822), overriding the mesh's own BodySetup.
    #
    # The field is REQUIRED rather than defaulted precisely because a
    # default is what failed. These probes exist so it cannot quietly
    # become optional again.
    ("instanced species with NO collision block", None,
     lambda r: _inst_sp(r).pop("collision", None),
     "collision is REQUIRED"),
    ("rock species with NO collision block", None,
     lambda r: _species(r, True).pop("collision", None),
     "collision is REQUIRED"),
    ("grass species CARRYING a collision block (engine hard-codes "
     "NoCollision, so it could never take effect)", None,
     lambda r: _grass_sp(r).update(
         collision={"enabled": "query_only", "profile": "BlockAll",
                    "navigable_geometry": "yes"}),
     "refused on a grass species"),
    ("collision.enabled 'physics_only' (traces would MISS while every "
     "property read looks set)", None,
     lambda r: _inst_sp(r)["collision"].update(enabled="physics_only"),
     "collision.enabled must be one of"),
    ("collision.enabled absent", None,
     lambda r: _inst_sp(r)["collision"].pop("enabled", None),
     "collision.enabled must be one of"),
    ("collision.navigable_geometry absent (inherited, not declared)", None,
     lambda r: _inst_sp(r)["collision"].pop("navigable_geometry", None),
     "navigable_geometry must be one of"),
    ("collision.navigable_geometry 'off' (not an engine value)", None,
     lambda r: _inst_sp(r)["collision"].update(navigable_geometry="off"),
     "navigable_geometry must be one of"),
    ("collision.profile declared while enabled is 'none' (inert field "
     "that reads like a setting)", None,
     lambda r: _inst_sp(r)["collision"].update(profile="BlockAll"),
     "profile is refused when enabled is 'none'"),
    ("collision query_only with NO profile", None,
     lambda r: _inst_sp(r)["collision"].update(enabled="query_only"),
     "profile must be a non-empty"),
    ("unknown key inside collision", None,
     lambda r: _inst_sp(r)["collision"].update(collide="yes"),
     "unknown key in"),
    # --- the authored capsule -----------------------------------------
    ("capsule declared while enabled is 'none' (authoring geometry "
     "nothing can query)", None,
     lambda r: _inst_sp(r)["collision"].update(
         capsule={"radius_cm": 38.0, "z_min_cm": 0.0, "z_max_cm": 2731.0,
                  "basis": "probe"}),
     "refused when collision.enabled is 'none'"),
    ("capsule span NOT exceeding its own diameter (derived "
     "KSphylElem.length would go <= 0)", None,
     lambda r: _inst_sp(r)["collision"].update(
         enabled="query_only", profile="BlockAll",
         capsule={"radius_cm": 38.0, "z_min_cm": 0.0, "z_max_cm": 70.0,
                  "basis": "probe"}),
     "does not exceed its own diameter"),
    ("capsule with an inverted span", None,
     lambda r: _inst_sp(r)["collision"].update(
         enabled="query_only", profile="BlockAll",
         capsule={"radius_cm": 38.0, "z_min_cm": 2731.0, "z_max_cm": 0.0,
                  "basis": "probe"}),
     "must be greater than z_min_cm"),
    ("capsule radius 0", None,
     lambda r: _inst_sp(r)["collision"].update(
         enabled="query_only", profile="BlockAll",
         capsule={"radius_cm": 0.0, "z_min_cm": 0.0, "z_max_cm": 2731.0,
                  "basis": "probe"}),
     "radius_cm must be a finite number"),
    ("capsule with no `basis` (a measurement with no provenance)", None,
     lambda r: _inst_sp(r)["collision"].update(
         enabled="query_only", profile="BlockAll",
         capsule={"radius_cm": 38.0, "z_min_cm": 0.0, "z_max_cm": 2731.0}),
     "basis must be a non-empty string"),
    ("capsule carrying `length_cm` (the engine's own field name, which "
     "EXCLUDES the caps and would read as a total height)", None,
     lambda r: _inst_sp(r)["collision"].update(
         enabled="query_only", profile="BlockAll",
         capsule={"radius_cm": 38.0, "length_cm": 2731.0, "basis": "probe"}),
     "unknown key in"),
    # --- NAVIGATION (schema v1.24) -------------------------------------
    # The positive control is the shipped recipe itself, which validates
    # clean with a navigation block present (run_probes checks that first).
    ("navigation.tile_size_uu 100 (under the engine ClampMin)", None,
     lambda r: _install_nav(r, tile_size_uu=100.0), "tile_size_uu must be"),
    ("navigation.tile_size_uu 30000 (SILENTLY clamped to CellSize*1024)",
     None, lambda r: _install_nav(r, tile_size_uu=30000.0),
     "tile_size_uu must be"),
    ("navigation.average_layers_per_tile 0.5 (under engine ClampMin 1.0)",
     None, lambda r: _install_nav(r, average_layers_per_tile=0.5),
     "average_layers_per_tile"),
    ("navigation jobs 0 (a build that never schedules a tile)", None,
     lambda r: _install_nav(r, max_simultaneous_tile_generation_jobs=0),
     "max_simultaneous_tile_generation_jobs"),
    ("navigation.min_region_dimension_uu negative", None,
     lambda r: _install_nav(r, min_region_dimension_uu=-1.0),
     "min_region_dimension_uu"),
    ("navigation.data_gathering_mode 'eager' (not an engine value)", None,
     lambda r: _install_nav(r, data_gathering_mode="eager"),
     "data_gathering_mode must be one of"),
    ("navigation.builder_loading_cell_size_cm 4000 (under ClampMin 5000)",
     None, lambda r: _install_nav(r, builder_loading_cell_size_cm=4000),
     "builder_loading_cell_size_cm"),
    ("navigation loading cell NOT a multiple of the chunk grid (integer "
     "division rounds it DOWN silently)", None,
     lambda r: _install_nav(r, builder_loading_cell_size_cm=150000),
     "silently rounded down"),
    ("navigation with NO bounds volumes (bWholeWorldNavigable is broken, "
     "so nothing would be navigable and the build would succeed having "
     "produced nothing)", None,
     lambda r: _install_nav(r, bounds_volumes=[]),
     "bounds_volumes must be a non-empty list"),
    ("navigation bounds volume with zero thickness on Z", None,
     lambda r: _install_nav(r, bounds_volumes=[{
         "name": "flat", "min_cm": [0.0, 0.0, 100.0],
         "max_cm": [1000.0, 1000.0, 100.0], "basis": "probe"}]),
     "must exceed min_cm"),
    ("navigation bounds volume with no `basis`", None,
     lambda r: _install_nav(r, bounds_volumes=[{
         "name": "nobasis", "min_cm": [0.0, 0.0, 0.0],
         "max_cm": [1000.0, 1000.0, 1000.0]}]),
     "basis must be a non-empty string"),
    ("two navigation bounds volumes with the SAME name (actor labels "
     "collide, and this project has two landscapes that proved it)", None,
     lambda r: _install_nav(r, bounds_volumes=[
         {"name": "dup", "min_cm": [0.0, 0.0, 0.0],
          "max_cm": [1000.0, 1000.0, 1000.0], "basis": "probe"},
         {"name": "dup", "min_cm": [2000.0, 0.0, 0.0],
          "max_cm": [3000.0, 1000.0, 1000.0], "basis": "probe"}]),
     "is declared twice"),
    # THE ONE THIS GATE EXISTS FOR. A world-sized navigable region at the
    # ENGINE DEFAULTS needs ~1.99M tiles against TileNumberHardLimit 1<<20.
    # The engine does not fail: it logs an error and CLAMPS, leaving a
    # navmesh quietly smaller than the region it claims to cover. This is
    # the standing 1.89x overflow, reproduced as a refusal.
    ("navigation: WHOLE WORLD navigable at the engine defaults "
     "(TileSizeUU 1000, 3 layers) -- the recorded 1.89x tile overflow",
     None,
     lambda r: _install_nav(
         r, tile_size_uu=1000.0, average_layers_per_tile=3.0,
         bounds_volumes=[{
             "name": "NavBounds_World",
             "min_cm": [-406400.0, -406400.0, 0.0],
             "max_cm": [406400.0, 406400.0, 155300.0],
             "basis": "probe"}]),
     "TileNumberHardLimit"),
]


def run_probes(verbose=True):
    base = json.load(io.open(RECIPE, encoding="utf-8"))
    clean = ih._validate_recipe(copy.deepcopy(base), RECIPE)
    if clean:
        print("  NOTE: the recipe does not validate clean; probe results "
              "below are still meaningful but the baseline is dirty:")
        for e in clean[:4]:
            print("        {0}".format(e))
    rejected = accepted = skipped = 0
    for label, is_rock, mutate, expect in PROBES:
        r = copy.deepcopy(base)
        if is_rock is None:
            # A whole-recipe probe: the mutation takes the RECIPE, not a
            # species. Kept in the same list so one runner proves every
            # kind of refusal and none can be silently dropped.
            mutate(r)
            errs = ih._validate_recipe(r, RECIPE)
            hit = [e for e in errs if expect.lower() in e.lower()]
            if hit:
                rejected += 1
                if verbose:
                    print("  rejected  {0}".format(label))
            else:
                accepted += 1
                if verbose:
                    print("  ACCEPTED  {0}   (wanted {1!r})".format(
                        label, expect))
            continue
        sp = _species(r, is_rock)
        if sp is None:
            if verbose:
                print("  SKIP (no {0} species)  {1}".format(
                    "rock" if is_rock else "vegetation", label))
            skipped += 1
            continue
        try:
            mutate(sp)
        except (KeyError, TypeError):
            skipped += 1
            continue
        errs = ih._validate_recipe(r, RECIPE)
        hit = [e for e in errs if expect.lower() in e.lower()]
        if hit:
            rejected += 1
            if verbose:
                print("  rejected  {0}".format(label))
        else:
            accepted += 1
            if verbose:
                print("  ACCEPTED  {0}   (wanted {1!r})".format(label, expect))
    return rejected, accepted, skipped


def run_could_not_look(verbose=True):
    """The measured-pivot gate must say 'I could not look' (NN6).

    A missing report is NOT a clean bill of health. This is the branch
    that a validator run against a healthy checkout never exercises,
    which is exactly why it is proven here instead.
    """
    ok = True
    real = os.path.isfile
    os.path.isfile = lambda p: False
    ls.os.path.isfile = os.path.isfile
    try:
        errs = ls.measured_pivot_errors({"/Game/Rocks/X"})
    finally:
        os.path.isfile = real
        ls.os.path.isfile = real
    if not errs or "could not look" not in errs[0]:
        ok = False
        if verbose:
            print("  FAIL  a missing report did not report 'could not look'")
    elif verbose:
        print("  refused   missing report reports 'I could not look', not ok")

    if not ls.measured_pivot_errors(set()):
        if verbose:
            print("  refused   no rocks named -> no claim made")
    return ok


# Names that legitimately have no in-repo caller. Each needs a REASON,
# because the whole point is that "no caller" is normally a defect.
_UNCALLED_OK = {
    # (none yet — add with a one-line justification, never silently)
}

_CHECKISH = ("assert", "invariant", "check", "validate", "verify",
             "_errors", "prove", "gate", "refuse")


def run_dead_gate_sweep(verbose=True):
    """Fail if any check-like function has NO call site in `scripts/`.

    The structural half of the 2026-08-03 lesson. Wiring three dead
    suites up was the local fix; this is what stops a fourth. A checker
    that reports by RETURN VALUE and is never called passes forever, and
    the only symptom is the absence of one.

    Deliberately crude — a name-based AST sweep with false positives. A
    false positive costs one line in `_UNCALLED_OK` **with a reason**;
    a false negative costs a gate nobody knows is off.
    """
    import ast
    import collections

    root = os.path.join(REPO_ROOT, "scripts")
    defs = collections.defaultdict(list)
    calls = collections.Counter()
    for dirpath, _dirs, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(io.open(path, encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    if isinstance(f, ast.Name):
                        calls[f.id] += 1
                    elif isinstance(f, ast.Attribute):
                        calls[f.attr] += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(k in node.name.lower() for k in _CHECKISH):
                        defs[node.name].append((path, node.lineno))

    dead = []
    for name in sorted(defs):
        if calls[name] or name in _UNCALLED_OK:
            continue
        for path, line in defs[name]:
            dead.append((name, path, line))
    if verbose:
        for name, path, line in dead:
            print("  DEAD      {0}  ({1}:{2})".format(
                name, os.path.relpath(path, REPO_ROOT), line))
        if not dead:
            print("  clean     every check-like function has a call site "
                  "({0} scanned)".format(len(defs)))
    return dead


def run_adoption_probes(verbose=True):
    """Prove `place_foliage.adopt_rock_plans` REFUSES every bad plan.

    The highest-stakes gate in the repo. Its failure mode is not a wrong
    number in a printout -- it is `remove_all_instances` running over
    157,554 conifers because a rock plan was missing from the list the
    orphan sweep checks against. Nothing about that is recoverable by
    git; the world is saved after placement.

    Each probe writes a real plan file into a scratch FOLIAGE_DIR, so
    the function is exercised through its actual filesystem path rather
    than through a mock that could disagree with it.
    """
    import shutil
    import tempfile
    import place_foliage as pf

    good_mesh = "/Game/Rocks/Boulder"
    recipe = {"biome_id": "probe",
              "foliage": {"species": [
                  {"name": "Tree", "layer": "Grass", "weight_share": 1.0,
                   "mesh": "/Game/Meshes/Tree"},
                  {"name": "Boulder", "role": "hero", "mesh": good_mesh}]}}

    def plan_doc(**over):
        doc = {"biome": "probe", "species": "Boulder", "mesh": good_mesh,
               "count": 2, "units": "cm, degrees, uniform scale",
               "cull_cm": 14000,
               "instances": [[0, 0, 0, 0, 0, 0, 1], [1, 1, 1, 0, 0, 0, 1]]}
        doc.update(over)
        return doc

    # (label, doc or None for "write no file", must_refuse)
    CASES = [
        ("no plan file at all (rock would be swept next run)", None, True),
        ("plan with an empty instances list", plan_doc(instances=[]), True),
        ("plan for a DIFFERENT mesh than the recipe names",
         plan_doc(mesh="/Game/Rocks/SomethingElse"), True),
        ("plan whose species name is another species",
         plan_doc(species="Scree"), True),
        ("a correct plan", plan_doc(), False),
    ]

    tmp = tempfile.mkdtemp(prefix="ll_adopt_")
    real_dir, real_inside = pf.FOLIAGE_DIR, pf._inside_repo
    pf.FOLIAGE_DIR = tmp
    pf._inside_repo = lambda p: True      # the real check is proven above
    ok = bad = 0
    try:
        for label, doc, must_refuse in CASES:
            target = os.path.join(tmp, "probe_Boulder.json")
            if os.path.isfile(target):
                os.remove(target)
            if doc is not None:
                with io.open(target, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh)
            adopted, errs = pf.adopt_rock_plans(recipe)
            refused = bool(errs)
            if refused == must_refuse and (must_refuse or len(adopted) == 1):
                ok += 1
                if verbose:
                    print("  {0}  {1}".format(
                        "refused " if must_refuse else "adopted ", label))
            else:
                bad += 1
                if verbose:
                    print("  WRONG     {0}  (errs={1} adopted={2})".format(
                        label, errs, adopted))
    finally:
        pf.FOLIAGE_DIR, pf._inside_repo = real_dir, real_inside
        shutil.rmtree(tmp, ignore_errors=True)

    # And the whole point: a rock species must reach the plan list.
    if verbose:
        print("  note      a rock species is SKIPPED by plan() and must be "
              "re-added by adopt_rock_plans, or the sweep deletes it")
    return ok, bad


def run_planner_role_probes(verbose=True):
    """The PLANNER's own role gate, which the validator cannot stand in for.

    `import_heightmap._validate_rock_species` refuses an unknown role
    (probe "role misspelt" above). That gate only fires if somebody runs
    the validator. `rock_scatter.py` is runnable on its own and reads the
    recipe directly, and until 2026-08-08 its species filter was

        specs = [s for s in species if s.get("role") in ROLES]

    which cannot tell "no role key, therefore vegetation, skip it" from
    "a role key we do not recognise, therefore a rock we would silently
    NOT PLAN". The second case printed nothing and planned nothing, so a
    recipe could declare a species, preflight could pass it, and the plan
    would report success having never seen it.

    Two cases, because a gate that refuses everything is not a gate:
      NEGATIVE  an unrecognised role must REFUSE with exit 2.
      POSITIVE  a recognised role must NOT trip this refusal, and
                execution must REACH THE NEXT GATE. The control recipe
                deliberately points `heightmap.source` outside REPO_ROOT,
                so a correct run refuses at the heightmap check that sits
                immediately after the role filter. Asserting the LATER
                message appears is strictly stronger than asserting the
                role message is absent: absence alone would also be
                produced by the function returning early, or by the whole
                probe silently not running.

    The control also keeps this suite FAST. Letting a valid role proceed
    into a real plan would cost the talus MFD routing — about eight
    minutes per R12's REJECTED section — and a proof suite nobody waits
    for is a proof suite nobody runs.

    The probe recipe is written INSIDE REPO_ROOT on purpose: rock_scatter
    refuses a recipe outside it, and a refusal for the wrong reason would
    read as a pass.
    """
    import rock_scatter as _rs

    base = json.load(io.open(RECIPE, encoding="utf-8"))
    tmpdir = tempfile.mkdtemp(prefix=".ll_prove_role_", dir=REPO_ROOT)
    ok = bad = 0
    try:
        for label, role, must_refuse in (
                # NOT 'clutter' — that WAS the example here until it
                # became a real role hours later, at which point the
                # probe would have passed for the wrong reason. A probe
                # whose invalid value can be made valid by ordinary work
                # is a probe with a shelf life; use something that will
                # never be a role.
                ("planner: role 'scenery' (not a role)", "scenery", True),
                ("planner: role misspelt 'heros'", "heros", True),
                ("planner: role 'hero' must NOT trip this gate  [+ve control]",
                 "hero", False)):
            r = copy.deepcopy(base)
            sp = _species(r, True)
            if sp is None:
                if verbose:
                    print("  SKIP (no rock species)  {0}".format(label))
                continue
            sp["role"] = role
            if not must_refuse:
                # Send the positive control into the NEXT gate, fast.
                r["heightmap"]["source"] = os.path.join(
                    "..", "outside_the_repo.png")
            path = os.path.join(tmpdir, "probe.json")
            io.open(path, "w", encoding="utf-8").write(
                json.dumps(r, indent=1))

            buf = io.StringIO()
            keep = sys.stdout
            sys.stdout = buf
            try:
                rc = _rs.main(["--recipe", path])
            except SystemExit as exc:          # argparse or an explicit exit
                rc = exc.code
            except Exception as exc:           # a crash is not a refusal
                rc = "raised {0}".format(type(exc).__name__)
            finally:
                sys.stdout = keep
            out = buf.getvalue()

            tripped = "does not know" in out
            if must_refuse:
                good = tripped and rc == 2
            else:
                # Not merely "the role gate stayed quiet" — execution
                # must have REACHED the heightmap gate beyond it.
                good = (not tripped) and "heightmap escapes" in out
            if good:
                ok += 1
                if verbose:
                    print("  {0:<9} {1}".format(
                        "refused" if must_refuse else "passed", label))
            else:
                bad += 1
                if verbose:
                    print("  FAILED    {0}  (rc={1!r}, tripped={2})".format(
                        label, rc, tripped))
    finally:
        for nm in os.listdir(tmpdir):
            try:
                os.remove(os.path.join(tmpdir, nm))
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    return ok, bad


def run_uncorrected_pivot_probes(verbose=True):
    """The GRASS system applies no pivot correction. Prove the gate knows.

    `rock_scatter` READS `base_offset_z_m` and subtracts it, so a rock
    instance lands on its base whatever the vendor pivot. The engine's
    landscape grass system places the mesh's PIVOT on the surface and the
    geometry falls where it falls. So the same measured row means two
    different things depending on who places the mesh, and a mesh that is
    safe as a rock can be half-buried as grass.

    A box-centred pivot buries exactly 50% by construction
    (`base_offset == -extent_z`), which is why those cases are the
    sharpest probes available — the expected value is arithmetic, not a
    guess.
    """
    import landscape_spec as ls

    base = json.load(io.open(RECIPE, encoding="utf-8"))
    piv_path = os.path.join(REPO_ROOT, "Free", "_measured",
                            "rock_pivots.json")
    if not os.path.isfile(piv_path):
        if verbose:
            print("  SKIP (no measured-pivot report)")
        return 0, 0
    piv = json.load(io.open(piv_path, encoding="utf-8"))
    mesh = {v["id"]: p for p, v in piv.items()
            if isinstance(v, dict) and v.get("id")}

    def _grass(r):
        for s in r["foliage"]["species"]:
            if s.get("system") == "grass" and s.get("varieties"):
                return s
        return None

    cases = []

    def _noop(r):
        return True

    cases.append(("the shipped recipe passes  [+ve control]", _noop, False))

    def _mk_box(mid):
        def _f(r):
            g = _grass(r)
            if g is None or mid not in mesh:
                return False
            g["varieties"][0]["mesh"] = mesh[mid]
            return True
        return _f

    for mid in ("hero_boulder_large", "boulder_medium_01"):
        cases.append(("grass variety = {0} (box-centred, ~50% buried)"
                      .format(mid), _mk_box(mid), True))

    def _unknown(r):
        g = _grass(r)
        if g is None:
            return False
        g["varieties"][0]["mesh"] = "/Game/Nope/SM_InNeitherRegistry"
        return True

    cases.append(("grass variety in NEITHER registry", _unknown, True))

    def _rock_unknown(r):
        for s in r["foliage"]["species"]:
            if s.get("role"):
                s["mesh"] = "/Game/Nope/SM_NoMeasuredRow"
                return True
        return False

    cases.append(("rock species with no measured row (path unchanged)",
                  _rock_unknown, True))

    ok = bad = 0
    for label, mutate, must_refuse in cases:
        r = copy.deepcopy(base)
        if not mutate(r):
            if verbose:
                print("  SKIP (recipe lacks the shape)  {0}".format(label))
            continue
        errs = ls.recipe_normalization_errors(r)
        good = bool(errs) == must_refuse
        if good:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format(
                    "refused" if must_refuse else "passed", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}  (errors={1})".format(label, len(errs)))
    return ok, bad


def run_grass_cull_builder_probes(verbose=True):
    """The BUILDER's own grass-cull refusal, which preflight cannot cover.

    `make_landscape_material.py` is runnable without the recipe
    validator, exactly as `rock_scatter.py` is. When its grass cull was a
    `.get(key, 12000.0)` default, a recipe that never saw preflight got a
    twelve-kilometre grass cull with no error anywhere. Requiring the key
    in the validator alone would have left that path open.
    """
    import make_landscape_material as mlm

    base = json.load(io.open(RECIPE, encoding="utf-8"))
    if _grass_sp(base) is None:
        if verbose:
            print("  SKIP (recipe declares no grass species)")
        return 0, 0

    cases = [
        ("the shipped recipe resolves  [+ve control]", None, False),
        ("cull_distance_m REMOVED", "pop", True),
        ("cull_distance_m 12000.0", 12000.0, True),
        ("cull_distance_m 0.0", 0.0, True),
        ("cull_distance_m True (a bool IS an int in Python)", True, True),
    ]
    ok = bad = 0
    for label, val, must_refuse in cases:
        r = copy.deepcopy(base)
        sp = _grass_sp(r)
        if val == "pop":
            sp.pop("cull_distance_m", None)
        elif val is not None:
            sp["cull_distance_m"] = val
        try:
            got = mlm.grass_entries(r)
            refused = False
        except ValueError:
            got, refused = None, True
        good = refused == must_refuse
        if good and not must_refuse:
            # The positive control must also produce the RIGHT number,
            # not merely fail to raise.
            good = bool(got) and all(g["cull_cm"] > 0.0 for g in got)
        if good:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format(
                    "refused" if must_refuse else "resolved", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}".format(label))
    return ok, bad


def run_render_cvar_probes(verbose=True):
    """`render_condition --cvar`, which sets RENDER STATE on a live editor.

    The gate matters because this tool proves a change landed by reading
    the cvar back with `get_console_variable_float_value`. A value it
    cannot read back cannot be proven, so the refusal is what keeps
    "CONDITION SET" from being printed over an unverifiable change.

    The float case is the one a reviewer should look at. The payload
    formatted its value with `int()`, which is right for the on/off
    GROUPS (all 0.0/1.0) and would SILENTLY TRUNCATE a fractional cvar to
    zero — setting the opposite of a small value. The positive controls
    below assert the VALUE SURVIVES, not merely that nothing raised.
    """
    import render_condition as rc

    cases = [
        # label,                              specs,                    refuse?
        ("shipped-shape spec  [+ve control]", ["r.ScreenPercentage=100"], False),
        ("fractional value    [+ve control]", ["r.Foo=0.5"], False),
        ("negative value      [+ve control]", ["r.Foo=-1.5"], False),
        ("no '=' separator", ["r.ScreenPercentage100"], True),
        ("non-numeric value", ["r.ScreenPercentage=high"], True),
        ("empty name", ["=100"], True),
        ("empty value", ["r.Foo="], True),
    ]
    ok = bad = 0
    for label, specs, must_refuse in cases:
        got, err = rc.parse_cvar_specs(specs)
        refused = err is not None
        good = refused == must_refuse
        if good and not must_refuse:
            # A parse that returns the WRONG number is not a pass. This is
            # the check that fails if int()-truncation is ever reinstated.
            want = float(specs[0].split("=", 1)[1])
            good = (got is not None and len(got) == 1
                    and got[0][1] == want and isinstance(got[0][1], float))
        if good:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format(
                    "refused" if must_refuse else "parsed", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}  (got={1!r} err={2!r})".format(
                    label, got, err))
    return ok, bad


def run_displacement_probes(verbose=True):
    """schema v1.21 `material.displacement` and the predicate it widened.

    WHY THIS SECTION EXISTS. Displacement is declared in METRES and the
    engine consumes a unitless LOCAL-SPACE magnitude; on this landscape
    those differ by 500x. The engine's own default magnitude, 4.0
    (EngineTypes.h:3456), is +/-10 m of terrain movement here — two and a
    half times the 4.00 m heightmap sampling cap the feature exists to
    add detail beneath. So the gate that matters is not "is the number
    well-formed" but "can the catastrophic value be expressed at all".

    THE ARITHMETIC IS CHECKED AGAINST AN INDEPENDENT RECOMPUTATION, not
    against itself: `displacement_spec` is asked for the magnitude, and
    the expected value is recomputed here from the shader's own formula
    (NaniteRasterizationCommon.ush:568/578/588) and the landscape's
    z_scale_cm. A reducer compared only to its own output proves nothing.

    IT ALSO PROVES THE TWO PREDICATES CANNOT PART. `d_active` is a
    superset of `sub_active` by construction; if they ever drift, the
    plan omits the primary's height map while still emitting the sub's,
    and the HeightLerp silently degrades to a linear lerp.
    """
    import import_heightmap as ih
    import make_landscape_material as mlm

    ok = bad = 0

    def _check(label, condition):
        nonlocal ok, bad
        if condition:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format("refused", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}".format(label))

    # schema v1.27 (Brief 7 Phase 1): displacement is PER LAYER. These
    # probes run against a three-layer world (Snow/Rock/Grass, alpine.json).
    L = ["Snow", "Rock", "Grass"]
    good_pl = {"Snow": 0.02, "Rock": 0.20, "Grass": 0.03}

    # --- the validator must refuse ------------------------------------
    for label, block in (
            ("retired amplitude_m key (pre-v1.27 recipe)",
             {"enabled": True, "center": 0.5, "amplitude_m": 0.4}),
            ("per_layer 10.0 m (what the engine default 4.0 would give)",
             {"enabled": True, "center": 0.5,
              "per_layer": {"Snow": 0.02, "Rock": 10.0, "Grass": 0.03}}),
            ("per_layer 0.0 — inert config, invisible at the heightmap",
             {"enabled": True, "center": 0.5,
              "per_layer": {"Snow": 0.02, "Rock": 0.0, "Grass": 0.03}}),
            ("per_layer negative",
             {"enabled": True, "center": 0.5,
              "per_layer": {"Snow": 0.02, "Rock": -0.4, "Grass": 0.03}}),
            ("per_layer NaN (NaN fails every comparison)",
             {"enabled": True, "center": 0.5,
              "per_layer": {"Snow": 0.02, "Rock": float("nan"),
                            "Grass": 0.03}}),
            ("enabled truthy-but-not-bool",
             {"enabled": 1, "center": 0.5, "per_layer": good_pl}),
            ("unknown key — a typo is otherwise silent",
             {"enabled": True, "center": 0.5, "per_layer": good_pl,
              "magnitude": 4.0}),
            ("per_layer missing", {"enabled": True, "center": 0.5}),
            ("center missing", {"enabled": True, "per_layer": good_pl}),
            ("center out of [0,1]",
             {"enabled": True, "center": 1.5, "per_layer": good_pl}),
            ("per_layer missing a layer (silent zero-displacement)",
             {"enabled": True, "center": 0.5,
              "per_layer": {"Snow": 0.02, "Rock": 0.20}}),
            ("per_layer extra key (a layer that does not exist)",
             {"enabled": True, "center": 0.5,
              "per_layer": dict(good_pl, Meadow=0.03)}),
            ("not an object", [1, 2])):
        _check(label, bool(ih._validate_displacement(block, L)))

    # --- and ACCEPT the three legitimate shapes [+ve controls] --------
    for label, block in (
            ("shipped per-layer       [+ve control]",
             {"enabled": True, "center": 0.5, "per_layer": good_pl}),
            ("enabled:false           [+ve control]",
             {"enabled": False, "center": 0.5, "per_layer": good_pl}),
            ("block absent            [+ve control]", None)):
        errs = ih._validate_displacement(block, L)
        if not errs:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format("accepted", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}  ({1})".format(label, errs))

    # --- the reducer, against an INDEPENDENT recomputation ------------
    recipe, err = ls.load_recipe(
        os.path.join(REPO_ROOT, "recipes", "alpine.json"))
    if err or not recipe:
        bad += 1
        if verbose:
            print("  FAILED    could not load alpine.json: {0}".format(err))
        return ok, bad

    spec = mlm.displacement_spec(recipe)
    if spec is None:
        if verbose:
            print("  skipped   alpine.json has displacement off")
    else:
        scale_z = float(recipe["landscape"]["z_scale_cm"]) / 512.0
        # schema v1.27 (Brief 7 Phase 1): displacement is PER LAYER, and
        # the reducer sets the engine magnitude from the MAX layer. Recompute
        # from the max independently of displacement_spec.
        want = 2.0 * max(
            float(v) for v in
            recipe["material"]["displacement"]["per_layer"].values()
        ) * 100.0 / scale_z
        if abs(spec["magnitude"] - want) <= 1e-12:
            ok += 1
            if verbose:
                print("  {0:<9} magnitude {1:.5f} == independent "
                      "recomputation (+/-{2:.3f} m)".format(
                          "matched", spec["magnitude"],
                          spec["magnitude"] / 2.0 * scale_z / 100.0))
        else:
            bad += 1
            if verbose:
                print("  FAILED    magnitude {0!r} != recomputed {1!r}".format(
                    spec["magnitude"], want))
        # CENTER 0.5 IS CORRECT ONLY BECAUSE THE GRAPH RE-CENTRES EACH MAP
        # ONTO IT. The maps' own means run 0.5257 to 0.7602 (measured
        # 2026-08-11), so 0.5 is NOT their neutral; `_centred_height`
        # subtracts each texture's fully-mipped value and adds `center`
        # back, making the composited value centred by construction.
        #
        # An earlier version of this line printed "the height maps'
        # neutral, so a missing sample displaces by zero" — an unverified
        # claim asserted BY A GATE, which is worse than one in a comment
        # because "asserted" reads as proven. The value is asserted here;
        # the mechanism that makes it true lives in the payload and is
        # verified by the render, not by this line.
        if spec["center"] == 0.5:
            ok += 1
            if verbose:
                print("  {0:<9} center 0.5, with per-map re-centring in the "
                      "graph (_centred_height) — symmetric "
                      "+/-magnitude/2".format("asserted"))
        else:
            bad += 1
            if verbose:
                print("  FAILED    center is {0!r}, not 0.5; the whole "
                      "terrain would take a constant Z offset".format(
                          spec["center"]))

    # `enabled: false` must read as OFF. Truthiness of the block is the
    # wrong test and would make the flag unable to turn anything off.
    off = copy.deepcopy(recipe)
    off["material"].setdefault("displacement", {})["enabled"] = False
    off["material"]["displacement"].setdefault("per_layer", {"Rock": 0.2})
    _check("enabled:false still produced a spec",
           mlm.displacement_spec(off) is None)

    # --- the band invariant -------------------------------------------
    bands = mlm.layer_bands(recipe)
    sub_idx = [i for i, b in enumerate(bands) if b.get("sub_active")]
    if sub_idx:
        drift = copy.deepcopy(bands)
        drift[sub_idx[0]]["d_active"] = False
        try:
            mlm._assert_band_invariant(drift)
            _check("sub_active without d_active", False)
        except mlm.BandInvariantError:
            _check("sub_active without d_active", True)
    d_idx = [i for i, b in enumerate(bands) if b.get("d_active")]
    if d_idx:
        nopath = copy.deepcopy(bands)
        nopath[d_idx[0]]["surface_d"] = None
        try:
            mlm._assert_band_invariant(nopath)
            _check("d_active with no surface_d path", False)
        except mlm.BandInvariantError:
            _check("d_active with no surface_d path", True)

    # --- the plan reducer's own displacement cases --------------------
    # NOT a for/else: that construct runs its else on every loop that
    # does not break, so it would report success over a list of failures.
    plan_fails = mlm.assert_texture_plan_gates()
    if plan_fails:
        for label in plan_fails:
            bad += 1
            if verbose:
                print("  FAILED    texture-plan gate: {0}".format(label))
    else:
        ok += 1
        if verbose:
            print("  {0:<9} texture_plan refused every malformed "
                  "declaration".format("refused"))
    return ok, bad


def run_height_blend_probes(verbose=True):
    """schema v1.28 (Brief 7 Phase 1 addendum) — the height-weighted blend.

    Two halves:
      * the validator must refuse a bad k/eps and accept the shipped shape;
      * the reweighting, run over the REAL baked weightmap, must leave the
        partition IDENTICAL (it only redistributes weight among the stored
        layers) and never drive a texel all-zero. `_cpu_height_blend`'s
        arithmetic properties are proven at import; this is the other half
        the desk asked for -- the check against real data, not synthetic.
    """
    import import_heightmap as ih
    import make_landscape_material as mlm

    ok = bad = 0

    def _check(label, condition):
        nonlocal ok, bad
        if condition:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format("refused", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}".format(label))

    # --- the validator must refuse ------------------------------------
    for label, block in (
            ("k negative", {"k": -1.0, "eps": 0.02}),
            ("k above 16 (a stair-step cut)", {"k": 20.0, "eps": 0.02}),
            ("k NaN", {"k": float("nan"), "eps": 0.02}),
            ("eps 0 (loses the divide-by-zero floor)", {"k": 4.0, "eps": 0.0}),
            ("eps above 1", {"k": 4.0, "eps": 1.5}),
            ("k missing", {"eps": 0.02}),
            ("eps missing", {"k": 4.0}),
            ("unknown key", {"k": 4.0, "eps": 0.02, "power": 2.0}),
            ("not an object", [4, 0.02])):
        _check(label, bool(ih._validate_height_blend(block)))

    # --- and ACCEPT the legitimate shapes [+ve controls] --------------
    for label, block in (
            ("shipped k=4 eps=0.02   [+ve control]", {"k": 4.0, "eps": 0.02}),
            ("k=0 disables           [+ve control]", {"k": 0.0, "eps": 0.02}),
            ("block absent           [+ve control]", None)):
        errs = ih._validate_height_blend(block)
        if not errs:
            ok += 1
            if verbose:
                print("  {0:<9} {1}".format("accepted", label))
        else:
            bad += 1
            if verbose:
                print("  FAILED    {0}  ({1})".format(label, errs))

    # --- cross-field refusals (audit F1/F3), in _validate_material -----
    _r8 = json.load(open(
        os.path.join(REPO_ROOT, "recipes", "alpine_8k.json"),
        encoding="utf-8"))
    _m = _r8["material"]
    if not ih._validate_material(copy.deepcopy(_m)):
        ok += 1
        if verbose:
            print("  {0} alpine_8k material valid [+ve control]".format(
                "accepted"))
    else:
        bad += 1
        if verbose:
            print("  FAILED    alpine_8k material did not validate")
    _m3 = copy.deepcopy(_m)
    _m3.pop("weightmap", None)
    _check("height_blend without weightmap (silent no-op)",
           any("requires material.weightmap" in x
               for x in ih._validate_material(_m3)))
    _m1 = copy.deepcopy(_m)
    # put stochastic_tiling on a STORED layer (index 1 = Rock)
    _m1["layers"][1]["stochastic_tiling"] = True
    _check("height_blend + stochastic_tiling on a stored layer",
           any("stochastic_tiling" in x
               for x in ih._validate_material(_m1)))
    # v1.29 feather: the >=4-layer weightmap contract must refuse an absent
    # weightmap_feather_sigma_px (the retired near-binary bake path).
    _mf = copy.deepcopy(_m)
    _mf.pop("weightmap_feather_sigma_px", None)
    _check("feather sigma required for a >=4-layer weightmap",
           any("weightmap_feather_sigma_px is required" in x
               for x in ih._validate_material(_mf)))

    # --- k==0 collapses to no reducer (no dead nodes) -----------------
    _off = {"material": {"height_blend": {"k": 0.0, "eps": 0.02}}}
    if mlm.height_blend_spec(_off) is None:
        ok += 1
        if verbose:
            print("  {0:<9} k=0 -> height_blend_spec None (no reweighting)"
                  .format("collapsed"))
    else:
        bad += 1
        if verbose:
            print("  FAILED    k=0 still produced a height_blend spec")

    # --- the reweighting over the REAL weightmap ----------------------
    wpath = os.path.join(REPO_ROOT, "textures", "alpine_8k_weights.png")
    if not os.path.isfile(wpath):
        bad += 1
        if verbose:
            print("  FAILED    real weightmap absent at {0} — cannot prove "
                  "the partition holds on real data".format(wpath))
        return ok, bad
    try:
        from PIL import Image
    except ImportError:
        if verbose:
            print("  skipped   PIL not importable; real-weightmap scan not "
                  "run (env, not a gate failure)")
        return ok, bad

    im = Image.open(wpath).convert("RGBA").resize((128, 128), Image.NEAREST)
    px = list(im.getdata())
    k, eps = 4.0, 0.02
    height_cfgs = ([0.0, 0.0, 0.0, 0.0],
                   [1.0, 1.0, 1.0, 1.0],
                   [0.1, 0.9, 0.3, 0.7])
    worst_part = 0.0
    min_total = 2.0
    n = 0
    for r8, g8, b8, a8 in px:
        base = [r8 / 255.0, g8 / 255.0, b8 / 255.0, a8 / 255.0]
        rem = max(0.0, 1.0 - sum(base))            # shader saturate remainder
        total_without = sum(base) + rem
        for h in height_cfgs:
            blended = mlm._cpu_height_blend(base, h, k, eps)
            total_with = sum(blended) + rem
            worst_part = max(worst_part, abs(total_with - total_without))
            min_total = min(min_total, total_with)
            n += 1
    # Rule 13: a zero-count scan refuses rather than passing silently.
    if n == 0:
        bad += 1
        if verbose:
            print("  FAILED    real-weightmap scan compared 0 texels")
        return ok, bad
    # Partition invariant: the height blend must not move sum(stored)+rem,
    # so the world does not repaint. Never all-zero: total is >= ~1 always.
    if worst_part <= 1e-6:
        ok += 1
        if verbose:
            print("  {0}  partition identical under height-blend over {1} "
                  "texel-configs (max drift {2:.2e})".format(
                      "held    ", n, worst_part))
    else:
        bad += 1
        if verbose:
            print("  FAILED    height-blend moved the partition on real data "
                  "(max drift {0:.2e} over {1})".format(worst_part, n))
    if min_total > 1e-6:
        ok += 1
        if verbose:
            print("  {0}  no texel went all-zero (min total {1:.4f})".format(
                "held    ", min_total))
    else:
        bad += 1
        if verbose:
            print("  FAILED    a texel resolved all-zero (min total {0:.2e})"
                  .format(min_total))
    return ok, bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    v = not args.quiet

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("")
    print("CPU-MODEL MUTATIONS — break the model, require the suite to catch")
    c, s, sk = run_mutations(v)
    print("  {0}/{1} refused{2}".format(c, c + s,
                                        ", {0} skipped".format(sk) if sk else ""))
    print("")
    print("RECIPE PROBES — feed a value that must be rejected")
    r, a, pk = run_probes(v)
    print("  {0}/{1} rejected{2}".format(r, r + a,
                                         ", {0} skipped".format(pk) if pk else ""))
    print("")
    print("ROCK-PLAN ADOPTION — the gate in front of the orphan sweep")
    aok, abad = run_adoption_probes(v)
    print("  {0}/{1} correct".format(aok, aok + abad))
    print("")
    print("PLANNER ROLE GATE — the validator cannot stand in for this one")
    pok, pbad = run_planner_role_probes(v)
    print("  {0}/{1} correct".format(pok, pok + pbad))
    print("")
    print("UNCORRECTED PIVOT — the grass system corrects nothing")
    uok, ubad = run_uncorrected_pivot_probes(v)
    print("  {0}/{1} correct".format(uok, uok + ubad))
    print("")
    print("GRASS CULL IN THE BUILDER — the field that once hung this GPU")
    gok, gbad = run_grass_cull_builder_probes(v)
    print("  {0}/{1} correct".format(gok, gok + gbad))
    print("")
    print("RENDER CVAR GATE — a value that cannot be read back cannot be proven")
    rok, rbad = run_render_cvar_probes(v)
    print("  {0}/{1} correct".format(rok, rok + rbad))
    print("")
    print("DISPLACEMENT (v1.27) — per-layer metres in, engine magnitude out")
    dok, dbad = run_displacement_probes(v)
    print("  {0}/{1} correct".format(dok, dok + dbad))
    print("")
    print("HEIGHT-BLEND (v1.28) — reweighting preserves the partition")
    hok, hbad = run_height_blend_probes(v)
    print("  {0}/{1} correct".format(hok, hok + hbad))
    print("")
    print("'I COULD NOT LOOK' BRANCHES")
    cnl = run_could_not_look(v)
    print("")
    print("DEAD-GATE SWEEP — a checker with no call site is zero gate")
    dead = run_dead_gate_sweep(v)
    print("")
    bad = (s + a + abad + pbad + ubad + gbad + rbad + dbad + hbad + len(dead)
           + (0 if cnl else 1))
    if bad:
        print("{0} gate(s) failed to refuse. A gate that cannot fail is not "
              "a weaker gate — it is zero gate wearing the documentation of "
              "one.".format(bad))
        return 4
    print("Every gate refused. This proves the gates REFUSE; it does not "
          "prove they accept everything valid — `--recipe` validation of "
          "the real recipe is the other half.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
