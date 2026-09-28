"""measure_mesh_collision.py — do the scattered meshes have simple collision?

PHASE2_PLAN.md unit 3. READ-ONLY: loads assets and reads properties. Spawns
nothing, saves nothing, mutates nothing.

=====================================================================
WHY THIS BLOCKS UNIT 6
=====================================================================
Unit 6 ("trees stop him") sets `collision_enabled = QUERY_ONLY` on the four
instanced species. That work is silently wasted if the meshes carry no simple
collision primitive, because a per-instance body with no shapes collides with
nothing -- and every property read-back would still say the setting landed.

`UInstancedStaticMeshComponent::CreateAllInstanceBodies` early-returns at
`InstancedStaticMesh.cpp:2877-2882`:

    UBodySetup* BodySetup = GetBodySetup();
    if (!BodySetup) { UE_LOGF(... "unable to create InstanceBodies!"); return; }

**AND THAT GUARD IS NARROWER THAN PHASE2_PLAN.md DESCRIBES.** It fires only
when the BodySetup is NULL. A mesh with a BodySetup whose `agg_geom` holds
ZERO elements sails past it, creates bodies, and still collides with nothing.
So the question to ask the asset is not "does it have a BodySetup" but
**"how many simple primitives are in its agg_geom"** -- which is what this
reads.

=====================================================================
WHY NOT AN EXTENSION OF measure_tree_packs, WHICH THE PLAN ASKED FOR
=====================================================================
That tool measures ATLASES and pack intake -- opacity, texture roles, blend
modes. Collision is a different question about a different object, and
bolting it on would give one tool two reasons to change. The real precedent
is `measure_palette_live.py`, which reads LOADED meshes one at a time and
declares partial runs. This follows that shape. Stated rather than done
quietly, because it is a deviation from the plan.

=====================================================================
THE REFLECTED SURFACE, RESOLVED AGAINST THIS INSTALL
=====================================================================
    StaticMesh.body_setup            PythonStub 289980  -> BodySetup
    BodySetup.agg_geom               PythonStub 348565  -> KAggregateGeom
    BodySetup.collision_trace_flag   PythonStub 348568
    BodySetup.walkable_slope_override PythonStub 348579
    KAggregateGeom.{box,convex,sphere,sphyl,tapered_capsule}_elems
                                     PythonStub 81489-81497

All reached with `get_editor_property`, because these are struct fields and
not generated accessors.

Exit codes:
  0  measured; every instanced species has simple collision
  1  could not look
  2  bad arguments
  3  rule 7: no verified editor node
  4  AT LEAST ONE INSTANCED SPECIES HAS NO SIMPLE COLLISION PRIMITIVE
     -- unit 6 would silently do nothing on it
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_COLL__"
OUT = os.path.join(bootstrap.REPO_ROOT, "Free", "_measured", "mesh_collision.json")

ELEM_FIELDS = ("box_elems", "convex_elems", "sphere_elems", "sphyl_elems",
               "tapered_capsule_elems", "level_set_elems")


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "meshes": []}
_paths = __PATHS__
try:
    for _p in _paths:
        _rec = {"path": _p, "loaded": False, "why": None,
                "body_setup": None, "elems": {}, "total_simple": None,
                "collision_trace_flag": None, "walkable_slope_override": None,
                "collision_profile": None, "nanite": None, "lods": None,
                "triangles_lod0": None}
        try:
            _m = _unreal.load_asset(_p)
        except Exception as _le:
            _rec["why"] = "load raised: " + type(_le).__name__ + ": " + str(_le)
            _out["meshes"].append(_rec)
            continue
        if _m is None:
            _rec["why"] = "load_asset returned None -- asset absent?"
            _out["meshes"].append(_rec)
            continue
        _rec["loaded"] = True

        # Context, so a zero can be read against what the mesh IS.
        try:
            _rec["lods"] = int(_m.get_num_lods())
        except Exception:
            pass
        try:
            _rec["triangles_lod0"] = int(_m.get_num_triangles(0))
        except Exception:
            pass
        try:
            _ns = _m.get_editor_property("nanite_settings")
            _rec["nanite"] = bool(_ns.get_editor_property("enabled"))
        except Exception:
            pass

        try:
            _bs = _m.get_editor_property("body_setup")
        except Exception as _be:
            _rec["why"] = ("body_setup unreadable: " + type(_be).__name__
                           + ": " + str(_be))
            _out["meshes"].append(_rec)
            continue
        if _bs is None:
            # THE CreateAllInstanceBodies EARLY RETURN. Distinct from an
            # empty agg_geom and recorded as its own state.
            _rec["body_setup"] = "NULL"
            _rec["total_simple"] = 0
            _out["meshes"].append(_rec)
            continue
        _rec["body_setup"] = "present"

        try:
            _rec["collision_trace_flag"] = str(
                _bs.get_editor_property("collision_trace_flag"))
        except Exception:
            pass
        try:
            _rec["walkable_slope_override"] = str(
                _bs.get_editor_property("walkable_slope_override"))
        except Exception:
            pass
        try:
            _di = _bs.get_editor_property("default_instance")
            _rec["collision_profile"] = str(
                _di.get_editor_property("collision_profile_name"))
        except Exception:
            pass

        try:
            _ag = _bs.get_editor_property("agg_geom")
        except Exception as _ae:
            _rec["why"] = ("agg_geom unreadable: " + type(_ae).__name__
                           + ": " + str(_ae))
            _out["meshes"].append(_rec)
            continue

        _tot = 0
        _unread = []
        for _f in __ELEMS__:
            try:
                _v = _ag.get_editor_property(_f)
                _n = 0 if _v is None else len(_v)
                _rec["elems"][_f] = _n
                _tot += _n
            except Exception:
                # An unreadable field is NOT zero. Recorded separately so the
                # total can be marked untrustworthy rather than quietly low.
                _unread.append(_f)
        if _unread:
            _rec["elems_unreadable"] = _unread
            _rec["why"] = "some element arrays unreadable: " + ",".join(_unread)
            _rec["total_simple"] = None
        else:
            _rec["total_simple"] = _tot
        _out["meshes"].append(_rec)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_COLL__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload):
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    return d, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default="recipes/alpine_8k.json")
    ap.add_argument("--mesh", action="append", default=None,
                    help="extra mesh path to measure (repeatable)")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)

    rpath = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    try:
        with open(rpath, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception as e:
        print("COULD NOT READ THE RECIPE: %s: %s" % (type(e).__name__, e))
        return 1

    species = rec.get("foliage", {}).get("species", [])
    # The instanced ones are the only ones that CAN collide. Ruling 17:
    # LandscapeGrass.cpp:3170-3172 hard-codes NoCollision + bDisableCollision
    # on the grass system, so a grass species is measured for the record but
    # never gated.
    wanted = []
    for sp in species:
        wanted.append({"name": sp.get("name"),
                       "mesh": sp.get("mesh"),
                       "system": sp.get("system", "instanced")})
    for m in (args.mesh or []):
        wanted.append({"name": "(--mesh)", "mesh": m, "system": "instanced"})

    paths = [w["mesh"] for w in wanted if w["mesh"]]
    if not paths:
        print("REFUSE: no meshes to measure.")
        return 2

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])

        payload = (PAYLOAD.replace("__PATHS__", repr(paths))
                          .replace("__ELEMS__", repr(list(ELEM_FIELDS))))
        d, raw = _run(remote, remote_exec, payload)
        if d is None:
            print("NO MARKER — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    by_path = {m["path"]: m for m in d["meshes"]}
    rc = 0
    print("=== UNIT 3 — SIMPLE COLLISION ON THE SCATTERED MESHES ===")
    print("")
    print("%-15s %-9s %8s %7s %9s  %s"
          % ("species", "system", "prims", "nanite", "tris LOD0", "trace flag"))
    for w in wanted:
        m = by_path.get(w["mesh"])
        if m is None:
            continue
        tot = m.get("total_simple")
        print("%-15s %-9s %8s %7s %9s  %s"
              % (w["name"], w["system"],
                 "UNREADABLE" if tot is None else tot,
                 m.get("nanite"), m.get("triangles_lod0"),
                 (m.get("collision_trace_flag") or "?")))
        if m.get("why"):
            print("%-15s   %s" % ("", m["why"]))
        if m.get("elems"):
            nz = ", ".join("%s=%d" % (k.replace("_elems", ""), v)
                           for k, v in sorted(m["elems"].items()) if v)
            print("%-15s   %s" % ("", nz if nz else "no simple primitives of any kind"))

    print("")
    print("--- the gate ---")
    for w in wanted:
        m = by_path.get(w["mesh"])
        if m is None or w["system"] != "instanced":
            continue
        tot = m.get("total_simple")
        if tot is None:
            print("  %-15s NO VERDICT — collision could not be read. That is"
                  % w["name"])
            print("  %-15s 'could not look', not a pass." % "")
            rc = max(rc, 4)
        elif tot == 0:
            print("  %-15s NO SIMPLE COLLISION. Unit 6 would set QUERY_ONLY on"
                  % w["name"])
            print("  %-15s this species, every read-back would confirm it, and" % "")
            print("  %-15s a line trace would still pass through the trunk." % "")
            rc = max(rc, 4)
        else:
            print("  %-15s OK — %d simple primitive(s)." % (w["name"], tot))

    print("")
    print("  Grass-system species are NOT gated: LandscapeGrass.cpp:3170-3172")
    print("  hard-codes NoCollision + bDisableCollision, so they can never")
    print("  collide and nothing should ask (PHASE2_PLAN.md ruling 17).")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"measured_by": "measure_mesh_collision",
                   "recipe": args.recipe,
                   "note": ("Supersedes any 'collision_prims' from the asset-"
                            "registry TAG scan, which is already DO-NOT-CONSUME "
                            "for material_slots on 23 of 38 meshes. These are "
                            "read from the LOADED asset."),
                   "species": wanted,
                   "meshes": d["meshes"]}, fh, indent=1)
    print("")
    print("ARTEFACT: %s" % args.out)
    return rc


if __name__ == "__main__":
    sys.exit(main())
