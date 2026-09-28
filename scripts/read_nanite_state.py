"""read_nanite_state.py — the landscape's Nanite + displacement state. Read-only.

WHY THIS EXISTS BEFORE ANY NANITE WORK

The terrain's silhouette detail is capped at 4.00 m per heightmap texel
(2017 vertices, scale_xy_cm 400.0, 8.064 km side). Landscape Nanite
DISPLACEMENT is the only route to finer silhouette that does not require
re-importing the terrain and re-deriving all 171,069 placements, so it is
worth establishing exactly what is on and what is not BEFORE mutating a
world that took days to populate.

WHAT IS ALREADY CITED, so this script does not re-argue it:
  LandscapeProxy.enable_nanite          PythonStub :531548
  r.Nanite.Tessellation                 NaniteCullRaster.cpp:94
  r.Landscape.AllowNanitePerClusterDisplacementDisable
                                        LandscapeRender.cpp:224-228, whose
                                        help text reads "Allow Nanite
                                        landscape to disable displcement on
                                        individual clusters in the distance"
  MaterialInstanceBasePropertyOverrides.enable_tessellation
                                        PythonStub :81519, "Required for
                                        displacement to work"

DISCIPLINE. Every read is individually guarded and a value that could not
be read comes back as {"error": ...}, never as a default and never as
False. "I could not look" is not "it is off" (non-negotiable 6) — and that
distinction matters more than usual here, because reading enable_nanite as
a spurious False would argue for enabling something that may already be on.

READ-ONLY. Spawns nothing, mutates nothing, saves nothing, sets no cvar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_NANITE__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "landscapes": [], "cvars": {{}}, "material": {{}},
        "error": None}}


def _prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception as _e:
        return {{"error": "{{0}}: {{1}}".format(type(_e).__name__, _e)}}


try:
    _sl = _unreal.SystemLibrary
    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _actors = _eas.get_all_level_actors()

    _fields = ["enable_nanite", "nanite_lod_index",
               "nanite_max_edge_length_factor", "nanite_position_precision",
               "nanite_skirt_depth", "nanite_skirt_enabled"]

    for _a in _actors:
        if not isinstance(_a, _unreal.LandscapeProxy):
            continue
        _row = {{"label": str(_a.get_actor_label()),
                "class": type(_a).__name__,
                "is_streaming_proxy": isinstance(_a, _unreal.LandscapeStreamingProxy)}}
        for _f in _fields:
            _v = _prop(_a, _f)
            _row[_f] = _v if isinstance(_v, dict) else (
                bool(_v) if isinstance(_v, bool) else _v)
        # the material, so the displacement question has an address
        _m = _prop(_a, "landscape_material")
        _row["landscape_material"] = (
            _m if isinstance(_m, dict)
            else (str(_m.get_path_name()) if _m else None))
        _out["landscapes"].append(_row)
        if len(_out["landscapes"]) >= 6:
            break

    # ONLY cvars whose declaration was found in 5.8 engine source are read
    # here. get_console_variable_float_value RETURNS 0.0 FOR A CVAR THAT
    # DOES NOT EXIST, which is indistinguishable from one that exists and
    # is off -- absence reading as a value, the same class as
    # non-negotiable 17. This bit the first run of this very script: it
    # reported r.Landscape.NaniteEnabled 0.0 and r.Nanite.AllowTessellation
    # 0.0 as "two gates are off". NEITHER CVAR EXISTS. bAllowTessellation
    # is a C++ struct member defaulting to TRUE (NaniteCullRaster.h:141)
    # and IsNaniteEnabled() is a method returning the per-actor
    # bEnableNanite (LandscapeProxy.h:1078). The false reading argued for
    # setting two things that cannot be set.
    for _c in ["r.Nanite",                       # NaniteCullRaster.cpp
               "r.Nanite.Tessellation",          # NaniteCullRaster.cpp:94
               "r.Nanite.MaxPixelsPerEdge",      # NaniteCullRaster.cpp
               # LandscapeRender.cpp:224-228
               "r.Landscape.AllowNanitePerClusterDisplacementDisable"]:
        try:
            _out["cvars"][_c] = _sl.get_console_variable_float_value(_c)
        except Exception as _e:
            _out["cvars"][_c] = {{"error": type(_e).__name__}}

    # THE MATERIAL'S DISPLACEMENT GATES (v1.21).
    #
    # This dict was DECLARED in _out from the first version of this script
    # and never populated — an inert field in the one instrument whose
    # docstring says the displacement question needs an address
    # (non-negotiable 21: a silent channel is an inert field). Filled now,
    # and read from the MATERIAL ASSET rather than from the builder's own
    # report, so it is a different instrument than the setter (NN8).
    #
    # enable_tessellation is the gate that makes a wired Displacement pin
    # actually move geometry ("Required for displacement to work",
    # PythonStub :81519). use_material_attributes is the gate that makes
    # the Displacement pin reachable at all, MP_Displacement being absent
    # from the reflected enum.
    _mp = None
    for _row in _out["landscapes"]:
        if isinstance(_row.get("landscape_material"), str):
            _mp = _row["landscape_material"]
            break
    if _mp:
        _mat = _unreal.EditorAssetLibrary.load_asset(_mp.split(".")[0])
        if _mat is None:
            _out["material"] = {{"error": "could not load " + str(_mp)}}
        else:
            _md = {{"path": _mp}}
            for _f in ("use_material_attributes", "enable_tessellation",
                       "enable_displacement_fade"):
                _v = _prop(_mat, _f)
                _md[_f] = _v if isinstance(_v, dict) else bool(_v)
            _ds = _prop(_mat, "displacement_scaling")
            if isinstance(_ds, dict):
                _md["displacement_scaling"] = _ds
            else:
                _md["displacement_scaling"] = {{
                    "magnitude": float(
                        _ds.get_editor_property("magnitude")),
                    "center": float(_ds.get_editor_property("center")),
                }}
            _out["material"] = _md
    else:
        # "I could not look" is not "it is off" (non-negotiable 6).
        _out["material"] = {{
            "error": "no landscape reported a material path, so the "
                     "displacement gates were NOT read"}}

    _out["ok"] = True
except Exception as _e:
    _out["error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("READ-ONLY: no asset, no actor, no cvar, no save.")
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(PAYLOAD.format(marker=MARKER),
                               unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r) if r else ""
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    got = _parse(text)
    if got is None:
        print("COULD NOT READ: no marker in the reply. This is 'I could not "
              "look', NOT 'Nanite is off'.")
        print(str(text)[:600])
        return 3
    if got.get("error"):
        print("COULD NOT READ: payload error: {0}".format(got["error"]))
        return 3

    print("CVARS  (only names whose declaration exists in 5.8 engine source;")
    print("        a cvar that does NOT exist also reads 0.0, so an unverified")
    print("        name here would be an absence masquerading as 'off')")
    for k, v in got["cvars"].items():
        print("  {0:<52s} {1}".format(k, v))
    print("")
    print("LANDSCAPE ACTORS ({0} reported, proxies capped at 6)".format(
        len(got["landscapes"])))
    for row in got["landscapes"]:
        print("  {0}  [{1}]".format(row.get("label"), row.get("class")))
        for k, v in row.items():
            if k in ("label", "class"):
                continue
            print("      {0:<32s} {1}".format(k, v))
    print("")
    # THE MATERIAL'S DISPLACEMENT GATES. Printed, because a field that is
    # collected and never shown is the same inert-field trap as one that
    # is declared and never filled — which is exactly what this block was
    # until 2026-08-11.
    mat = got.get("material") or {}
    print("MATERIAL DISPLACEMENT GATES")
    if not mat:
        print("  NOT READ — the payload returned no material block.")
    elif mat.get("error"):
        print("  COULD NOT READ: {0}".format(mat["error"]))
    else:
        print("  {0}".format(mat.get("path")))
        for k in ("use_material_attributes", "enable_tessellation",
                  "enable_displacement_fade"):
            print("      {0:<32s} {1}".format(k, mat.get(k)))
        ds = mat.get("displacement_scaling") or {}
        if "error" in ds:
            print("      {0:<32s} COULD NOT READ: {1}".format(
                "displacement_scaling", ds["error"]))
        else:
            mag = ds.get("magnitude")
            print("      {0:<32s} magnitude {1}  center {2}".format(
                "displacement_scaling", mag, ds.get("center")))
    print("")
    unread = sum(1 for row in got["landscapes"]
                 for v in row.values() if isinstance(v, dict))
    if unread:
        print("{0} property/properties COULD NOT BE READ. Those are UNKNOWN, "
              "not False.".format(unread))
    return 0


if __name__ == "__main__":
    sys.exit(main())
