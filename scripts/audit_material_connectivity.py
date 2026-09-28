"""audit_material_connectivity.py — is the graph CONNECTED, or just PRESENT?

READ-ONLY. Mutates no asset, saves nothing.

WHY THIS EXISTS
---------------
The pass audit (2026-08-06) confirmed Pass 2's material identity and
then said the thing that mattered: "Sub-surfaces, triplanar, macro
variation in the graph" is proven as **PRESENCE, not CONNECTIVITY** — a
name-table reference and a node count cannot distinguish a wired graph
from orphaned debris. This project has been bitten by exactly that three
times (`8bbe231d`, `9f5d573e`, and M_fir_bark sampling the twig atlas),
and `delete_all_material_expressions` was caught leaving SEVEN WIRED
SURVIVORS behind.

A TextureSample that exists, declares the right sampler type, and is
connected to NOTHING renders exactly like a texture that was never
imported. `audit_material_samplers.py` will pass it. The compiler will
not complain. Only reachability answers it.

METHOD — reachability from the material's outputs, backwards
------------------------------------------------------------
Seed the frontier with the node feeding each `MaterialProperty` output
(`get_material_property_input_node`), then walk backwards through
`get_inputs_for_material_expression` until closure. Every expression in
the material that is NOT in that reachable set contributes nothing to
any output.

Both accessors are verified present in the 5.8 reflected surface
(`PythonStub/unreal.py:427686` and `:427942`) — note that the sibling
`get_inputs_for_material_function` does NOT exist and was
non-negotiable 23's motivating case. These two are real; that one was
invented.

THE TRAP THIS INSTRUMENT MUST NOT FALL INTO
-------------------------------------------
Both accessors are documented "**from an active material editor**". If
they need an open editor and none is open, they return nothing — and a
naive reader would conclude that EVERY node is orphaned, which is the
most alarming possible false positive and would read as a catastrophic
finding.

So the reachable set is POSITIVE-CONTROLLED before any verdict:
  * at least one output property must resolve to a node, and
  * the reachable set must be a non-trivial fraction of the graph.
If either fails, this exits 4 COULD NOT MEASURE and says the accessor
returned nothing — it never reports "everything is orphaned"
(non-negotiable 6, and 1: fail closed).

Use `--open-editor` to have the editor open the asset first and close it
afterwards, if the bare read cannot see the graph.

Exit codes:
  0  measured; every expression is reachable from some output
  2  editor gate refused (rule 7), or the material is missing
  3  measured; ORPHANED EXPRESSIONS FOUND
  4  COULD NOT MEASURE — the accessor saw nothing; never "all orphaned"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_CONNECTIVITY__"

# Outputs a surface material can legitimately drive. MP_MATERIAL_
# ATTRIBUTES is included because a graph may drive everything through it.
PROPERTIES = [
    "MP_BASE_COLOR", "MP_METALLIC", "MP_SPECULAR", "MP_ROUGHNESS",
    "MP_ANISOTROPY", "MP_NORMAL", "MP_TANGENT", "MP_EMISSIVE_COLOR",
    "MP_OPACITY", "MP_OPACITY_MASK", "MP_AMBIENT_OCCLUSION",
    "MP_SUBSURFACE_COLOR", "MP_WORLD_POSITION_OFFSET", "MP_REFRACTION",
    "MP_MATERIAL_ATTRIBUTES",
]

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"exists": False, "error": None, "nodes": [], "seeds": {{}},
         "reachable": [], "accessor_calls": 0, "accessor_errors": 0}}


def _pos(_e):
    try:
        _x = int(_e.get_editor_property("material_expression_editor_x"))
        _y = int(_e.get_editor_property("material_expression_editor_y"))
    except Exception:
        _x, _y = -999999, -999999
    return "{{0}}@{{1}},{{2}}".format(type(_e).__name__, _x, _y)


def _key(_e):
    """UNIQUE identity for one expression: its object path name.

    It was `class@editorX,editorY` and that COLLIDES. Caught 2026-08-06
    by M_grass_medium_01 reporting "18 expressions in graph" and then
    "all 10 expressions reachable" — eight nodes sat on top of one
    another at shared positions and collapsed. A collision is not just
    a miscount: an ORPHAN sharing a position with a CONNECTED node would
    inherit its reachability and disappear from the finding. Position is
    a LABEL, never an identity.
    """
    try:
        return _e.get_path_name()
    except Exception:
        try:
            return "NAME:" + _e.get_name()
        except Exception:
            return "POS:" + _pos(_e)


def _label(_e):
    _t = None
    try:
        _tex = _e.get_editor_property("texture")
        if _tex is not None:
            _t = _tex.get_path_name().split(".")[0].split("/")[-1]
    except Exception:
        pass
    if _t is None:
        for _p in ("parameter_name", "desc"):
            try:
                _v = _e.get_editor_property(_p)
                if _v:
                    _t = str(_v)
                    break
            except Exception:
                pass
    return _t


try:
    _p = {path!r}
    if _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["exists"] = True
        _mat = _unreal.EditorAssetLibrary.load_asset(_p)
        _mel = _unreal.MaterialEditingLibrary

        if {open_editor}:
            try:
                _aes = _unreal.get_editor_subsystem(
                    _unreal.AssetEditorSubsystem)
                _aes.open_editor_for_assets([_mat])
                _out["opened_editor"] = True
            except Exception as _e:
                _out["opened_editor"] = "FAILED: " + str(_e)[:160]

        _all = list(_mel.get_material_expressions(_mat))
        _by_key = {{}}
        for _e in _all:
            _k = _key(_e)
            _by_key.setdefault(_k, _e)
            _out["nodes"].append({{"key": _k, "class": type(_e).__name__,
                                  "label": _label(_e), "pos": _pos(_e)}})

        # ---- seeds: the node feeding each material output ----------
        _frontier = []
        for _pname in {props!r}:
            try:
                _prop = getattr(_unreal.MaterialProperty, _pname)
            except Exception:
                continue
            try:
                _n = _mel.get_material_property_input_node(_mat, _prop)
            except Exception as _e:
                _out["seeds"][_pname] = "ERROR: " + str(_e)[:120]
                continue
            if _n is None:
                _out["seeds"][_pname] = None
            else:
                _k = _key(_n)
                _out["seeds"][_pname] = _k
                _frontier.append(_n)

        # ---- ALSO SEED EVERY CUSTOM OUTPUT -------------------------
        # A UMaterialExpressionCustomOutput is a ROOT of its own: it is
        # an output the engine reads directly and it is reachable from
        # NO MaterialProperty. LandscapeGrassOutput is the one that
        # matters here — grass density is fed to it, and seeding only
        # the MP_* properties condemns it and its whole input subtree as
        # "orphaned". Measured on M_AutoLandscape: without this seed the
        # instrument reported 42 orphans including the grass output
        # itself. Verified hierarchy:
        # PythonStub/unreal.py:532187 LandscapeGrassOutput ->
        # :373274 MaterialExpressionCustomOutput -> MaterialExpression.
        _out["custom_outputs"] = []
        for _e in _all:
            if isinstance(_e, _unreal.MaterialExpressionCustomOutput):
                _out["custom_outputs"].append(
                    {{"key": _key(_e), "class": type(_e).__name__}})
                _frontier.append(_e)

        # ---- backwards closure -------------------------------------
        _seen = set()
        for _n in _frontier:
            _seen.add(_key(_n))
        _stack = list(_frontier)
        while _stack:
            _cur = _stack.pop()
            try:
                _ins = _mel.get_inputs_for_material_expression(_mat, _cur)
                _out["accessor_calls"] += 1
            except Exception:
                _out["accessor_errors"] += 1
                continue
            for _i in (_ins or []):
                if _i is None:
                    continue
                _k = _key(_i)
                if _k not in _seen:
                    _seen.add(_k)
                    _stack.append(_i)
        _out["reachable"] = sorted(_seen)

        if {open_editor}:
            try:
                _aes.close_all_editors_for_asset(_mat)
            except Exception:
                pass
except Exception as _exc:
    _out["error"] = str(_exc)[:400]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--material", default="/Game/Materials/M_AutoLandscape")
    ap.add_argument("--open-editor", action="store_true",
                    help="open the asset editor first (some accessors "
                         "are documented 'from an active material "
                         "editor'), then close it")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("material  : {0}".format(args.material))
    print("READ-ONLY: mutates no asset, saves nothing.")
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(
                PAYLOAD.format(path=args.material, marker=MARKER,
                               props=PROPERTIES,
                               open_editor=bool(args.open_editor)),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            if not r or not r.get("success"):
                print("command failed: {0}".format((r or {}).get("result")))
                return 2
            data = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None:
        print("COULD NOT MEASURE: no parseable result from the editor.")
        return 4
    if data.get("error"):
        print("COULD NOT MEASURE: editor-side error: {0}"
              .format(data["error"]))
        return 4
    if not data.get("exists"):
        print("REFUSE: material not found: {0}".format(args.material))
        return 2

    nodes = data.get("nodes") or []
    reach = set(data.get("reachable") or [])
    seeds = data.get("seeds") or {}
    driven = {k: v for k, v in seeds.items()
              if v and not str(v).startswith("ERROR")}

    print("expressions in graph : {0}".format(len(nodes)))
    print("outputs driven       : {0} ({1})".format(
        len(driven), ", ".join(sorted(driven)) or "none"))
    custom = data.get("custom_outputs") or []
    print("custom outputs seeded: {0} ({1})".format(
        len(custom),
        ", ".join(sorted({c["class"] for c in custom})) or "none"))
    print("reachable from output: {0}".format(len(reach)))
    print("accessor calls / errors: {0} / {1}".format(
        data.get("accessor_calls"), data.get("accessor_errors")))
    if "opened_editor" in data:
        print("opened asset editor  : {0}".format(data["opened_editor"]))
    print("")

    # ---- POSITIVE CONTROL, before any verdict --------------------
    # If the accessors cannot see the graph, EVERY node looks orphaned.
    # That is the most alarming possible false positive, so it must be
    # impossible to report it as a finding.
    if not driven:
        print("COULD NOT MEASURE: no material output resolved to a node.")
        print("Both accessors are documented 'from an active material")
        print("editor'. Re-run with --open-editor. This is NOT a finding")
        print("that the graph is disconnected (non-negotiable 6).")
        return 4
    if len(nodes) and len(reach) < max(2, 0.10 * len(nodes)):
        print("COULD NOT MEASURE: only {0} of {1} expressions were "
              "reachable.".format(len(reach), len(nodes)))
        print("That is below the plausibility floor for a compiling")
        print("material and reads as an accessor that is not seeing the")
        print("graph, not as a graph that is 90% debris. Re-run with")
        print("--open-editor before believing any orphan list.")
        return 4

    keys = {}
    for n in nodes:
        keys.setdefault(n["key"], n)
    # IDENTITY MUST BE UNIQUE, and the instrument says so out loud. If
    # two expressions share a key, one of them silently inherits the
    # other's reachability and an orphan can vanish from the finding.
    if len(keys) != len(nodes):
        print("COULD NOT MEASURE: {0} expressions collapsed to {1} unique "
              "keys — identity is colliding, so a reachable node can mask "
              "an orphan.".format(len(nodes), len(keys)))
        return 4
    orphans = [n for k, n in sorted(keys.items()) if k not in reach]

    # Texture-level summary: which textures actually reach an output.
    tex_reach, tex_orph = {}, {}
    for k, n in keys.items():
        # Substring, not equality: the TextureSampleParameter family are
        # SUBCLASSES, and exact-name matching hid all three of M_C0_House's
        # samplers from this listing on 2026-08-30. The VERDICT was
        # unaffected -- reachability does not care what class a node is --
        # but the listing under it read as "no textures in this graph".
        if "TextureSample" not in n["class"]:
            continue
        lab = n.get("label") or "<no texture>"
        if k in reach:
            tex_reach[lab] = tex_reach.get(lab, 0) + 1
        else:
            tex_orph[lab] = tex_orph.get(lab, 0) + 1

    print("TextureSample nodes reaching an output:")
    for lab in sorted(set(list(tex_reach) + list(tex_orph))):
        print("  {0:<28s} connected {1:<3d} ORPHANED {2}".format(
            lab[:28], tex_reach.get(lab, 0), tex_orph.get(lab, 0)))

    print("")
    if not orphans:
        print("VERDICT: CONNECTED — all {0} expressions are reachable "
              "from a material output.".format(len(keys)))
        print("This is reachability, not correctness: it proves nothing")
        print("about WHAT the graph computes, only that no node is")
        print("contributing to nothing.")
        return 0

    print("VERDICT: {0} ORPHANED EXPRESSION(S) — present in the graph, "
          "reachable from no output.".format(len(orphans)))
    byclass = {}
    for o in orphans:
        byclass[o["class"]] = byclass.get(o["class"], 0) + 1
    for cls in sorted(byclass, key=lambda c: -byclass[c]):
        print("  {0:<44s} {1}".format(cls[:44], byclass[cls]))
    print("")
    print("  first 25, by key:")
    for o in orphans[:25]:
        print("    {0:<46s} {1}".format(
            (o.get("pos") or o["key"])[:46], o.get("label") or ""))
    if len(orphans) > 25:
        print("    ... and {0} more".format(len(orphans) - 25))
    return 3


if __name__ == "__main__":
    sys.exit(main())
