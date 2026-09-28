"""apply_foliage_collision.py — make scattered instances collide, from the recipe.

WHAT THIS FIXES, MEASURED
    2026-08-16: all fourteen `FT_*` foliage types in this project read
    NoCollision, so 219,659 trees and 13,515 rock instances were
    pass-through -- INCLUDING the three tree species whose MESHES carry a
    vendor-authored trunk capsule. Nothing collided but the landscape.

    Root cause at two source lines. `UFoliageType`'s constructor does
    `BodyInstance.SetCollisionProfileName(NoCollision)`
    (InstancedFoliage.cpp:640), and `UpdateComponentSettings` copies that
    onto the component UNCONDITIONALLY (:1822) -- no "if changed" guard --
    overriding whatever the MESH's own BodySetup says. The placement tool
    never mentioned collision in any form, so the default stood.

TWO OBJECTS, ONE PATH
    The mesh's `BodySetup.default_instance.collision_profile_name` and the
    foliage type's `BodyInstance` are DIFFERENT OBJECTS. All six meshes read
    `BlockAll` while nothing collided. Only the foliage type is on the path
    that decides whether a trace hits. This tool writes the foliage type;
    it writes the MESH only where the recipe declares an authored capsule.

THE JOIN KEY IS THE MESH PATH, NOT A NAME
    Foliage types are discovered by matching their `mesh` property against
    the recipe species' `mesh`. Deriving `FT_<name>` here would be a second
    copy of a convention that lives in the placement tool -- two lists that
    must agree are one list, badly stored (non-negotiable 24). Duplicate
    meshes across two foliage types are REFUSED rather than guessed.

THE FAB BOUNDARY IS A REFUSAL, NOT A CONVENTION
    RECIPES.md names "changing its LOD or collision" on a Fab static mesh as
    its worked example of an edit that vanishes on re-download. An authored
    capsule is therefore legal only on a repo-TRACKED mesh, and that is
    checked with `git check-ignore` against the real file, not assumed.

Exit codes:
    0  applied (or dry run completed) and every read-back matched
    2  bad arguments, bad recipe, or a refusal (Fab boundary, duplicate
       foliage type, species with no foliage type, capsule/mesh mismatch)
    3  rule 7: no verified editor node
    4  applied but a read-back DISAGREED -- the value did not land
    5  the editor payload reported an error
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap        # noqa: E402
import import_heightmap as ih   # noqa: E402
import ue_exec          # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
UE_CONTENT = os.path.join(bootstrap.UE_PROJECT_ROOT, "Content")

_ENABLED_ENUM = {"none": "NO_COLLISION", "query_only": "QUERY_ONLY"}
_NAV_ENUM = {"yes": "YES", "no": "NO", "dont_export": "DONT_EXPORT",
             "even_if_not_collidable": "EVEN_IF_NOT_COLLIDABLE"}


def _content_path_to_disk(game_path):
    """`/Game/Foo/Bar` -> `<project>/Content/Foo/Bar.uasset`.

    Returns None for anything not under /Game/, which is how an engine or
    plugin path (which we must never edit) declines to resolve.
    """
    if not game_path.startswith("/Game/"):
        return None
    rel = game_path[len("/Game/"):].split(".")[0]
    return os.path.join(UE_CONTENT, rel.replace("/", os.sep) + ".uasset")


def _is_gitignored(disk_path):
    """True if git ignores the file. UNKNOWN is never treated as 'tracked'.

    Raises rather than returning a default: a wrong answer here authorises
    an edit to vendor content that will vanish on re-download, so 'I could
    not look' must stop the run (non-negotiable 6).
    """
    if not os.path.isfile(disk_path):
        raise RuntimeError("no such file on disk: " + disk_path)
    r = subprocess.run(["git", "check-ignore", "-q", disk_path],
                       cwd=REPO_ROOT, capture_output=True)
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    raise RuntimeError("git check-ignore could not decide for %s (rc=%d): %s"
                       % (disk_path, r.returncode,
                          r.stderr.decode("utf-8", "replace").strip()))


def build_plan(recipe, recipe_path):
    """Recipe -> the list of edits, with every refusal raised here.

    Everything that can be decided WITHOUT the editor is decided here, so a
    refusal costs no editor round trip and cannot half-apply.
    """
    errs = ih._validate_recipe(json.loads(json.dumps(recipe)), recipe_path)
    if errs:
        raise ValueError("recipe does not validate:\n  " + "\n  ".join(errs))

    species = (recipe.get("foliage") or {}).get("species") or []
    plan = {"types": [], "capsules": []}
    capsule_by_mesh = {}

    for sp in species:
        if not isinstance(sp, dict):
            continue
        system = "instanced" if "role" in sp else sp.get("system", "instanced")
        if system != "instanced":
            continue
        c = sp.get("collision")
        if not isinstance(c, dict):
            # Unreachable while the schema holds; asserted rather than
            # trusted, because a validator and a consumer that disagree
            # about whether a block is required is exactly the shape this
            # whole change exists to remove.
            raise ValueError("%s has no collision block but validated; the "
                             "schema and this tool disagree"
                             % sp.get("name"))
        enabled = c["enabled"]
        plan["types"].append({
            "species": sp.get("name"),
            "mesh": sp["mesh"],
            "enabled": _ENABLED_ENUM[enabled],
            # An engine profile name is only meaningful when something is
            # enabled; `NoCollision` is the engine's own name for the off
            # state, so the two fields cannot contradict each other.
            "profile": c.get("profile") or "NoCollision",
            "nav": _NAV_ENUM[c["navigable_geometry"]],
        })

        cap = c.get("capsule")
        if not cap:
            continue
        mesh = sp["mesh"]
        prev = capsule_by_mesh.get(mesh)
        if prev is not None and prev != cap:
            raise ValueError(
                "two species declare DIFFERENT capsules for the same mesh "
                "%s. A capsule is a property of the MESH, so two "
                "declarations can only drift (non-negotiable 19)" % mesh)
        if prev is not None:
            continue
        capsule_by_mesh[mesh] = cap

        disk = _content_path_to_disk(mesh)
        if disk is None:
            raise ValueError(
                "%s declares a capsule on %s, which is not under /Game/. "
                "This tool edits project content only" % (sp.get("name"), mesh))
        if _is_gitignored(disk):
            raise ValueError(
                "REFUSED: %s declares a capsule on %s, which is GITIGNORED "
                "vendor content. RECIPES.md names 'changing its LOD or "
                "collision' on a Fab static mesh as the worked example of an "
                "edit that vanishes on re-download. If that mesh needs "
                "collision it already has it, or it needs a mesh we own."
                % (sp.get("name"), mesh))

        radius = float(cap["radius_cm"])
        z0, z1 = float(cap["z_min_cm"]), float(cap["z_max_cm"])
        # KSphylElem.length is the LINE SEGMENT -- "add Radius to both ends
        # to find total length" (SphylElem.h). Derived once, here, from a
        # span the recipe cannot misdeclare. The schema already refused a
        # span that does not exceed the diameter; asserted anyway, because
        # a prose claim that something cannot happen is worth asserting or
        # deleting, never printing (non-negotiable 25).
        length = (z1 - z0) - 2.0 * radius
        if length <= 0.0:
            raise AssertionError(
                "derived KSphylElem.length %.4f <= 0 for %s; the schema "
                "should have refused this span" % (length, mesh))
        plan["capsules"].append({
            "species": sp.get("name"),
            "mesh": mesh,
            "disk": disk,
            "radius": radius,
            "length": length,
            "center_z": (z0 + z1) / 2.0,
            "z_min": z0,
            "z_max": z1,
        })
    return plan


PAYLOAD = r'''
import json as _json
import unreal as _u

SPEC = _json.loads(r"""__SPEC__""")
FT_DIR = "__FT_DIR__"
APPLY = __APPLY__

_out = {"ok": False, "error": None, "apply": APPLY, "types": [],
        "capsules": [], "unmatched_foliage_types": [], "refusals": []}


def _norm(p):
    """/Game/A/B.B -> /Game/A/B, so a recipe path and an object path join."""
    return p.split(".")[0] if p else p


try:
    # ---- index every foliage type by the MESH it uses ------------------
    index = {}
    dupes = {}
    for p in _u.EditorAssetLibrary.list_assets(FT_DIR, recursive=True,
                                               include_folder=False):
        a = _u.EditorAssetLibrary.load_asset(p)
        if a is None or not isinstance(a, _u.FoliageType):
            continue
        m = a.get_editor_property("mesh")
        if m is None:
            continue
        key = _norm(m.get_path_name())
        if key in index:
            dupes.setdefault(key, [index[key][0]]).append(p)
        index[key] = (p, a)

    wanted = set(_norm(t["mesh"]) for t in SPEC["types"])
    for key in sorted(wanted):
        if key in dupes:
            _out["refusals"].append(
                "two foliage types share mesh %s: %s -- cannot decide which "
                "the recipe means" % (key, dupes[key]))
    for key, (p, _a) in sorted(index.items()):
        if key not in wanted:
            _out["unmatched_foliage_types"].append(p)

    for t in SPEC["types"]:
        key = _norm(t["mesh"])
        if key not in index:
            _out["refusals"].append(
                "species %r declares collision but NO foliage type in %s "
                "uses its mesh %s" % (t["species"], FT_DIR, key))
    if _out["refusals"]:
        raise RuntimeError("refused before touching anything")

    # ---- the authored capsules, on meshes we own ----------------------
    for cap in SPEC["capsules"]:
        rec = {"species": cap["species"], "mesh": cap["mesh"],
               "want_radius": cap["radius"], "want_length": cap["length"],
               "want_center_z": cap["center_z"]}
        mesh = _u.EditorAssetLibrary.load_asset(_norm(cap["mesh"]))
        if mesh is None:
            raise RuntimeError("could not load mesh " + cap["mesh"])
        bs = mesh.get_editor_property("body_setup")
        if bs is None:
            raise RuntimeError("mesh %s has NO BodySetup" % cap["mesh"])
        ag = bs.get_editor_property("agg_geom")
        rec["before"] = {
            "sphyl": len(ag.get_editor_property("sphyl_elems")),
            "box": len(ag.get_editor_property("box_elems")),
            "convex": len(ag.get_editor_property("convex_elems")),
            "sphere": len(ag.get_editor_property("sphere_elems")),
        }
        if APPLY:
            el = _u.KSphylElem()
            el.set_editor_property("name", "TrunkCapsule")
            el.set_editor_property("center",
                                   _u.Vector(0.0, 0.0, cap["center_z"]))
            el.set_editor_property("rotation", _u.Rotator(0.0, 0.0, 0.0))
            el.set_editor_property("radius", cap["radius"])
            el.set_editor_property("length", cap["length"])
            # Structs read back as COPIES, so each level is written back
            # explicitly. A set that is never re-assigned lands in a
            # temporary and reports success.
            ag.set_editor_property("sphyl_elems", [el])
            bs.set_editor_property("agg_geom", ag)
            _u.EditorAssetLibrary.save_asset(_norm(cap["mesh"]), False)

            bs2 = _u.EditorAssetLibrary.load_asset(
                _norm(cap["mesh"])).get_editor_property("body_setup")
            ag2 = bs2.get_editor_property("agg_geom")
            got = ag2.get_editor_property("sphyl_elems")
            rec["after"] = {"sphyl": len(got)}
            if len(got) == 1:
                g = got[0]
                gc = g.get_editor_property("center")
                rec["read_back"] = {
                    "radius": round(float(g.get_editor_property("radius")), 4),
                    "length": round(float(g.get_editor_property("length")), 4),
                    "center_z": round(float(gc.z), 4),
                }
        _out["capsules"].append(rec)

    # ---- the foliage types: the object actually on the runtime path ----
    for t in SPEC["types"]:
        p, a = index[_norm(t["mesh"])]
        rec = {"species": t["species"], "foliage_type": p,
               "want_enabled": t["enabled"], "want_profile": t["profile"],
               "want_nav": t["nav"]}
        bi = a.get_editor_property("body_instance")
        rec["before"] = {
            "enabled": str(bi.get_editor_property("collision_enabled")),
            "profile": str(bi.get_editor_property("collision_profile_name")),
            "nav": str(a.get_editor_property("custom_navigable_geometry")),
        }
        if APPLY:
            # BOTH fields are written, and neither is redundant.
            #
            # `set_editor_property` writes the raw UPROPERTY; it does NOT
            # call FBodyInstance::SetCollisionProfileName, so the profile's
            # responses are NOT loaded in this session. They land on the
            # NEXT load, when UFoliageType::PostLoad -> FixupData ->
            # LoadProfileData reads the profile
            # (InstancedFoliage.cpp:806-812, BodyInstance.cpp:4567/4509).
            # That is also what makes the profile authoritative rather than
            # advisory, and it is why the acceptance test for this tool is
            # a COLD read plus a trace, never this read-back.
            #
            # Writing `collision_enabled` explicitly matters for the
            # in-between state: until that reload, the enabled flag is the
            # only thing standing between the instances and the
            # NoCollision value the constructor left there.
            bi.set_editor_property("collision_profile_name", t["profile"])
            bi.set_editor_property("collision_enabled",
                                   getattr(_u.CollisionEnabled, t["enabled"]))
            a.set_editor_property("body_instance", bi)
            a.set_editor_property(
                "custom_navigable_geometry",
                getattr(_u.HasCustomNavigableGeometry, t["nav"]))
            _u.EditorAssetLibrary.save_asset(p, False)

            a2 = _u.EditorAssetLibrary.load_asset(p)
            bi2 = a2.get_editor_property("body_instance")
            rec["after"] = {
                "enabled": str(bi2.get_editor_property("collision_enabled")),
                "profile": str(bi2.get_editor_property("collision_profile_name")),
                "nav": str(a2.get_editor_property("custom_navigable_geometry")),
            }
        _out["types"].append(rec)

    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--ft-dir", default="/Game/Foliage",
                    help="content dir holding the FoliageType assets")
    ap.add_argument("--go", action="store_true",
                    help="apply; without it this is a dry run that still "
                         "reads and reports the live state")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args(argv)

    rp = args.recipe if os.path.isabs(args.recipe) else os.path.join(
        REPO_ROOT, args.recipe)
    with open(rp, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)

    try:
        plan = build_plan(recipe, rp)
    except (ValueError, AssertionError, RuntimeError) as exc:
        print("REFUSE:", exc)
        return 2

    print("PLAN from", os.path.relpath(rp, REPO_ROOT))
    for t in plan["types"]:
        print("  type    %-16s %-14s %-12s nav=%s"
              % (t["species"], t["enabled"], t["profile"], t["nav"]))
    for c in plan["capsules"]:
        print("  capsule %-16s r=%.2f cm  length=%.2f cm  centre_z=%.2f cm  "
              "(span %.1f..%.1f)"
              % (c["species"], c["radius"], c["length"], c["center_z"],
                 c["z_min"], c["z_max"]))
    if not plan["capsules"]:
        print("  capsule (none declared)")

    payload = (PAYLOAD
               .replace("__SPEC__", json.dumps(plan))
               .replace("__FT_DIR__", args.ft_dir)
               .replace("__APPLY__", "True" if args.go else "False"))
    rc, d, _raw = ue_exec.run(payload, timeout=args.timeout,
                              stage_name="apply_foliage_collision")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: the payload produced no result.")
        return 5
    if d.get("error"):
        print("PAYLOAD ERROR:\n" + d["error"])
        for r in d.get("refusals", []):
            print("  REFUSE:", r)
        return 2 if d.get("refusals") else 5

    print()
    print("FOLIAGE TYPES" + ("" if args.go else "  (dry run — read only)"))
    bad = 0
    for r in d["types"]:
        b = r["before"]
        print("  %-16s %s" % (r["species"], r["foliage_type"]))
        print("      before  %-34s %-14s nav=%s"
              % (b["enabled"], b["profile"], b["nav"]))
        if "after" in r:
            a = r["after"]
            ok = (r["want_enabled"] in a["enabled"]
                  and a["profile"] == r["want_profile"]
                  and r["want_nav"] in a["nav"])
            bad += 0 if ok else 1
            print("      after   %-34s %-14s nav=%s   %s"
                  % (a["enabled"], a["profile"], a["nav"],
                     "OK" if ok else "*** DID NOT LAND ***"))

    if d["capsules"]:
        print()
        print("AUTHORED CAPSULES")
        for r in d["capsules"]:
            print("  %-16s %s" % (r["species"], r["mesh"]))
            print("      before  simple prims: %s" % (r["before"],))
            if "read_back" in r:
                g = r["read_back"]
                ok = (abs(g["radius"] - r["want_radius"]) < 1e-3
                      and abs(g["length"] - r["want_length"]) < 1e-3
                      and abs(g["center_z"] - r["want_center_z"]) < 1e-3)
                bad += 0 if ok else 1
                print("      after   radius=%.3f length=%.3f centre_z=%.3f  %s"
                      % (g["radius"], g["length"], g["center_z"],
                         "OK" if ok else "*** DID NOT LAND ***"))
            elif "after" in r:
                bad += 1
                print("      after   %s  *** expected exactly 1 sphyl ***"
                      % (r["after"],))

    if d["unmatched_foliage_types"]:
        print()
        print("FOLIAGE TYPES THIS RECIPE DOES NOT NAME (untouched, reported "
              "so a silence is not read as coverage):")
        for p in d["unmatched_foliage_types"]:
            print("   ", p)

    print()
    if not args.go:
        print("DRY RUN — nothing was written. Re-run with --go to apply.")
        return 0
    if bad:
        print("APPLIED BUT %d READ-BACK(S) DISAGREED. A read-back proves the "
              "value landed, not that the engine reads it — settle this "
              "before trusting any of it." % bad)
        return 4
    print("APPLIED AND READ BACK CLEAN — AND THAT IS THE WEAKEST OF THE "
          "THREE CHECKS THIS NEEDS.")
    print()
    print("  1. read-back (done) reads the field the setter wrote.")
    print("  2. RESTART THE EDITOR, then re-run measure_foliage_collision.")
    print("     `set_editor_property` writes the raw property and does NOT")
    print("     load the collision profile. The profile's responses — and")
    print("     its own CollisionEnabled — are applied by")
    print("     UFoliageType::PostLoad -> FBodyInstance::FixupData ->")
    print("     LoadProfileData, which runs on EVERY load. Until that has")
    print("     happened once, the responses are still the ones the")
    print("     NoCollision profile left behind, and those IGNORE the")
    print("     Visibility and Camera channels.")
    print("     If the profile name reads back as 'Custom' after the")
    print("     restart, the profile does not exist and the write silently")
    print("     degraded.")
    print("  3. A WORLD LINE TRACE against a real instance in PIE, with a")
    print("     negative control. Only that proves anything collides")
    print("     (non-negotiable 8).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
