"""measure_foliage_collision.py — does a FOLIAGE TYPE let anything hit it?

READ-ONLY. Writes `Free/_measured/foliage_collision.json`.

WHY THIS EXISTS SEPARATELY FROM `measure_mesh_collision`
    That tool reads the MESH's BodySetup and is correct about it. This one
    reads the FOLIAGE TYPE. They are different objects and only one is on
    the path that decides whether a trace hits:

        InstancedFoliage.cpp:640   UFoliageType's constructor sets
                                   BodyInstance -> NoCollision
        InstancedFoliage.cpp:1822  UpdateComponentSettings copies the
                                   foliage type's BodyInstance onto the
                                   component UNCONDITIONALLY, overriding
                                   whatever the mesh's BodySetup says

    On 2026-08-16 all six meshes read `BlockAll` while all fourteen foliage
    types read `NoCollision`, and nothing in either world collided but the
    landscape. Reading the mesh and quoting it as the runtime answer is the
    agreement-among-instruments-that-share-no-source error inverted: two
    instruments that do not even describe the same object.

WHAT A CLEAN RESULT LOOKS LIKE, AND THE TELL THAT IT IS NOT
    A species meant to collide should read `QUERY_ONLY` with the profile
    name the recipe declares. **A profile name of `Custom` means the
    declared profile DOES NOT EXIST**: LoadProfileData calls
    InvalidateCollisionProfileName when the name is unknown
    (BodyInstance.cpp:4499-4512), so a typo'd or unregistered profile
    degrades silently to Custom, keeping whatever CollisionEnabled happened
    to be serialized and whatever responses were last left behind.

    RUN THIS ON A FRESHLY STARTED EDITOR. `set_editor_property` writes the
    raw property without loading the profile; the profile is applied by
    UFoliageType::PostLoad -> FixupData -> LoadProfileData
    (InstancedFoliage.cpp:806-812), which runs on load. A same-session read
    therefore cannot tell a value that will SURVIVE from one that will be
    overwritten on the next start.

Exit codes:
    0  measured; every declared expectation matched (or none was given)
    1  the payload could not look
    2  bad arguments
    3  rule 7: no verified editor node
    5  measured and a species DISAGREED with the recipe
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap   # noqa: E402
import ue_exec     # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
OUT = os.path.join(REPO_ROOT, "Free", "_measured", "foliage_collision.json")

PAYLOAD = r'''
import json as _json
import unreal as _u

FT_DIR = "__FT_DIR__"
_out = {"ok": False, "error": None, "level": None, "types": [], "skipped": []}


def _rd(obj, prop):
    """Read a property, or say plainly that it could NOT be read.

    Never substitutes a plausible default: a failed measurement must not
    read as a measurement (non-negotiable 6).
    """
    try:
        return str(obj.get_editor_property(prop))
    except Exception as _e:
        return "UNREADABLE(%s): %s" % (prop, _e)


try:
    try:
        _out["level"] = _u.UnrealEditorSubsystem().get_editor_world().get_path_name()
    except Exception as _e:
        _out["level"] = "UNREADABLE: %s" % _e

    for p in sorted(_u.EditorAssetLibrary.list_assets(
            FT_DIR, recursive=True, include_folder=False)):
        try:
            a = _u.EditorAssetLibrary.load_asset(p)
        except Exception as _e:
            _out["skipped"].append({"path": p, "why": "load raised: %s" % _e})
            continue
        if a is None:
            _out["skipped"].append({"path": p, "why": "load returned None"})
            continue
        if not isinstance(a, _u.FoliageType):
            _out["skipped"].append({"path": p, "why": "not a FoliageType: %s"
                                    % a.get_class().get_name()})
            continue

        rec = {"path": p, "class": a.get_class().get_name()}
        try:
            m = a.get_editor_property("mesh")
            rec["mesh"] = m.get_path_name() if m else None
        except Exception as _e:
            rec["mesh"] = "UNREADABLE: %s" % _e

        try:
            bi = a.get_editor_property("body_instance")
            rec["collision_enabled"] = _rd(bi, "collision_enabled")
            rec["collision_profile_name"] = _rd(bi, "collision_profile_name")
        except Exception as _e:
            rec["collision_enabled"] = "UNREADABLE: %s" % _e
            rec["collision_profile_name"] = "UNREADABLE: %s" % _e

        rec["custom_navigable_geometry"] = _rd(a, "custom_navigable_geometry")
        # PLACEMENT-time overlap test. NOT runtime collision, and the names
        # are close enough that one has been read as the other.
        rec["collision_with_world"] = _rd(a, "collision_with_world")

        # The MESH side, so both objects appear in one artefact and nobody
        # has to quote one as the other.
        try:
            mm = a.get_editor_property("mesh")
            bs = mm.get_editor_property("body_setup") if mm else None
            if bs is None:
                rec["mesh_simple_prims"] = None
                rec["mesh_prims_why"] = "no BodySetup"
            else:
                ag = bs.get_editor_property("agg_geom")
                counts = {}
                total = 0
                for k in ("box_elems", "convex_elems", "sphere_elems",
                          "sphyl_elems", "tapered_capsule_elems"):
                    try:
                        n = len(ag.get_editor_property(k))
                    except Exception:
                        n = None
                    counts[k] = n
                    if n is None:
                        total = None
                    elif total is not None:
                        total += n
                rec["mesh_prim_counts"] = counts
                rec["mesh_simple_prims"] = total
        except Exception as _e:
            rec["mesh_simple_prims"] = None
            rec["mesh_prims_why"] = "UNREADABLE: %s" % _e

        _out["types"].append(rec)

    _out["ok"] = True
except Exception as _e:
    import traceback as _tb
    _out["error"] = "%s\n%s" % (_e, _tb.format_exc())

print("__LL__" + _json.dumps(_out))
'''


def _norm(p):
    return p.split(".")[0] if p else p


def expectations(recipe):
    """mesh path -> (enabled, profile) the recipe declares. One declaration."""
    want = {}
    for sp in (recipe.get("foliage") or {}).get("species") or []:
        if not isinstance(sp, dict):
            continue
        system = "instanced" if "role" in sp else sp.get("system", "instanced")
        if system != "instanced":
            continue
        c = sp.get("collision")
        if not isinstance(c, dict):
            continue
        en = "NO_COLLISION" if c.get("enabled") == "none" else "QUERY_ONLY"
        want[_norm(sp.get("mesh"))] = (sp.get("name"), en,
                                       c.get("profile") or "NoCollision")
    return want


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ft-dir", default="/Game/Foliage")
    ap.add_argument("--recipe", default=None,
                    help="if given, every instanced species is checked "
                         "against its declaration and a mismatch exits 5")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args(argv)

    rc, d, _raw = ue_exec.run(PAYLOAD.replace("__FT_DIR__", args.ft_dir),
                              timeout=args.timeout,
                              stage_name="measure_foliage_collision")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: no result from the editor.")
        return 1
    if d.get("error"):
        print("PAYLOAD ERROR:\n" + d["error"])
        return 1

    print("level:", d.get("level"))
    print()
    print("%-28s %-22s %-24s %-6s %s"
          % ("foliage type", "collision_enabled", "profile", "prims", "nav"))
    for r in d["types"]:
        print("%-28s %-22s %-24s %-6s %s"
              % (os.path.basename(_norm(r["path"])),
                 r["collision_enabled"].replace("<CollisionEnabled.", "")
                                       .replace(">", ""),
                 r["collision_profile_name"],
                 r.get("mesh_simple_prims"),
                 r["custom_navigable_geometry"]
                 .replace("<HasCustomNavigableGeometry.", "")
                 .replace(">", "")))

    custom = [r for r in d["types"]
              if r.get("collision_profile_name") == "Custom"]
    if custom:
        print()
        print("*** %d foliage type(s) read profile 'Custom'. That is the "
              "engine's marker for a profile it could NOT find "
              "(BodyInstance.cpp:4499-4512) — the declared profile does not "
              "exist and the write degraded silently." % len(custom))

    bad = 0
    if args.recipe:
        rp = args.recipe if os.path.isabs(args.recipe) else os.path.join(
            REPO_ROOT, args.recipe)
        with open(rp, "r", encoding="utf-8") as fh:
            want = expectations(json.load(fh))
        print()
        print("AGAINST", os.path.relpath(rp, REPO_ROOT))
        by_mesh = {_norm(r.get("mesh")): r for r in d["types"]}
        for mesh, (name, en, prof) in sorted(want.items()):
            r = by_mesh.get(mesh)
            if r is None:
                print("  %-16s NO FOLIAGE TYPE uses %s" % (name, mesh))
                bad += 1
                continue
            ok = (en in r["collision_enabled"]
                  and r["collision_profile_name"] == prof)
            bad += 0 if ok else 1
            print("  %-16s %s  want %s/%s  got %s/%s"
                  % (name, "OK " if ok else "MISMATCH", en, prof,
                     r["collision_enabled"].replace("<CollisionEnabled.", "")
                                           .replace(">", ""),
                     r["collision_profile_name"]))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    d["_note"] = ("A foliage type's BodyInstance is what the component gets "
                  "(InstancedFoliage.cpp:1822); the mesh's own BodySetup "
                  "profile is NOT the runtime value. Profile 'Custom' means "
                  "the declared profile was not found.")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    print()
    print("wrote", os.path.relpath(args.out, REPO_ROOT))
    if bad:
        print("%d species DISAGREE with the recipe." % bad)
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
