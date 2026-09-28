"""apply_character_recipe.py — project recipes/character.json into the engine.

PHASE2_PLAN.md unit 5. Two phases:

  A. CREATE the Enhanced Input assets the recipe declares (needs the editor)
  B. WRITE DefaultGame.ini's character section from the recipe (offline)

The character class reads that ini section as `config` UPROPERTYs and applies
it in PostInitializeComponents. So the chain is:

    recipes/character.json  ->  this tool  ->  DefaultGame.ini  ->  the CDO
                            ->  this tool  ->  /Game/Characters/Input/*

and the recipe stays the single declaration. The alternative -- literal
/Game/ paths in the C++ constructor -- would put a second copy of every path
somewhere nothing would notice it drifting.

=====================================================================
IDEMPOTENT, AND THE INI SECTION IS REWRITTEN WHOLE
=====================================================================
Pipeline rule 3. Re-running rebuilds the same assets and rewrites the same
ini block. The ini section is replaced ENTIRELY rather than key-by-key,
because a key that the recipe stopped declaring must DISAPPEAR -- a stale key
left behind is a value in effect that no recipe records, which is exactly the
class non-negotiable 17 is about.

Exit codes:
  0  applied
  1  could not look / an asset could not be created
  2  bad arguments or a malformed recipe
  3  rule 7: no verified editor node
  4  an asset was created but did not read back with what was asked for
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import terrain_erosion as te  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_CHAR__"
INI = os.path.join(bootstrap.UE_PROJECT_ROOT, "Config", "DefaultGame.ini")
SECTION = "/Script/LandscapeLabGameplay.LandscapeLabCharacter"

VALUE_TYPES = {
    "boolean": "BOOLEAN",
    "axis1d": "AXIS1D",
    "axis2d": "AXIS2D",
    "axis3d": "AXIS3D",
}


PAYLOAD = r'''
import json as _json
import unreal as _unreal
_out = {"error": None, "created": [], "failed": [], "readback": {}}
_spec = _json.loads(r"""__SPEC__""")
try:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    _root = _spec["content_root"]

    def _make(name, factory_cls, asset_cls):
        _existing = _unreal.EditorAssetLibrary.load_asset(_root + "/" + name)
        if _existing is not None:
            return _existing, False
        _a = _tools.create_asset(name, _root, asset_cls, factory_cls())
        return _a, True

    # ---- the actions -------------------------------------------------
    _actions = {}
    for _spec_a in _spec["actions"]:
        _name = _spec_a["name"]
        _a, _new = _make(_name, _unreal.InputAction_Factory, _unreal.InputAction)
        if _a is None:
            _out["failed"].append("could not create " + _name)
            continue
        try:
            _a.set_editor_property(
                "value_type",
                getattr(_unreal.InputActionValueType, _spec_a["value_type"]))
        except Exception as _ve:
            _out["failed"].append(_name + " value_type: " + str(_ve))
        _actions[_name] = _a
        _out["created"].append({"asset": _name, "new": bool(_new)})

    # ---- the mapping context ------------------------------------------
    _imc, _new = _make(_spec["mapping_context"],
                       _unreal.InputMappingContext_Factory,
                       _unreal.InputMappingContext)
    if _imc is None:
        _out["error"] = "could not create the mapping context"
    else:
        _out["created"].append({"asset": _spec["mapping_context"], "new": bool(_new)})
        _mappings = []
        for _spec_a in _spec["actions"]:
            _act = _actions.get(_spec_a["name"])
            if _act is None:
                continue
            for _b in _spec_a["bindings"]:
                _m = _unreal.EnhancedActionKeyMapping()
                _m.set_editor_property("action", _act)
                # unreal.Key.__init__ takes NO arguments in 5.8 (PythonStub
                # 119303), so it is built empty and populated. Key(key_name=..)
                # raises "call() takes at most 0 arguments".
                _k = _unreal.Key()
                _k.set_editor_property("key_name", _b["key"])
                _m.set_editor_property("key", _k)
                _mods = []
                if _b.get("swizzle"):
                    _sw = _unreal.InputModifierSwizzleAxis()
                    _sw.set_editor_property(
                        "order", getattr(_unreal.InputAxisSwizzle, _b["swizzle"]))
                    _mods.append(_sw)
                if _b.get("negate"):
                    _mods.append(_unreal.InputModifierNegate())
                if _mods:
                    _m.set_editor_property("modifiers", _mods)
                _mappings.append(_m)
        # default_key_mappings is an InputMappingContextMappingData STRUCT in
        # 5.8, not a bare array -- the array lives on its .mappings field.
        _data = _imc.get_editor_property("default_key_mappings")
        _data.set_editor_property("mappings", _mappings)
        _imc.set_editor_property("default_key_mappings", _data)

        # READ BACK from the asset, not from the list we just built.
        _rb = _imc.get_editor_property("default_key_mappings")
        _out["readback"]["mapping_count"] = len(
            _rb.get_editor_property("mappings"))

    # ---- save ----------------------------------------------------------
    for _spec_a in _spec["actions"]:
        _unreal.EditorAssetLibrary.save_asset(_root + "/" + _spec_a["name"], False)
    _unreal.EditorAssetLibrary.save_asset(_root + "/" + _spec["mapping_context"], False)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_CHAR__" + _json.dumps(_out))
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


def _write_ini(ch, expected_mappings):
    """Rewrite the character's ini section whole. Returns the block written."""
    root = ch["input"]["content_root"]
    a = ch["assets"]
    names = {x["name"] for x in ch["input"]["actions"]}
    mv, cap = ch["movement"], ch["capsule"]

    def obj(p):
        return "%s.%s" % (p, p.rsplit("/", 1)[-1])

    lines = [
        "[%s]" % SECTION,
        "; GENERATED by scripts/apply_character_recipe from",
        "; recipes/character.json. Do not hand-edit: the next run rewrites",
        "; this whole section, and a key the recipe stopped declaring must",
        "; DISAPPEAR rather than linger as a value in effect that no recipe",
        "; records.",
        "MeshPath=%s" % obj(a["skeletal_mesh"]),
        # An AnimBP's runtime class is the asset name with a _C suffix. The
        # asset itself is a UAnimBlueprint and is NOT a UAnimInstance subclass,
        # so loading the asset path as a class silently yields nothing.
        "AnimClassPath=%s_C" % obj(a["anim_blueprint"]),
        "MappingContextPath=%s" % obj("%s/%s" % (root, ch["input"]["mapping_context"])),
    ]
    # OPTIONAL, and the key must DISAPPEAR when the recipe stops declaring it.
    # A MetaHuman is body + face; a mannequin is one mesh. Emitting an empty
    # FaceMeshPath would make "no face" indistinguishable from "a face that
    # failed to load", and the character deliberately treats those as
    # different facts.
    if a.get("face_mesh"):
        lines.append("FaceMeshPath=%s" % obj(a["face_mesh"]))
    # Camera is OPTIONAL for the same reason: a key the recipe stops declaring
    # must disappear rather than linger as a value in effect no recipe records.
    cam = ch.get("camera") or {}
    for key, cfg in (("arm_length_cm", "CfgCameraArmLengthCm"),
                     ("probe_size_cm", "CfgCameraProbeSizeCm"),
                     ("socket_offset_z_cm", "CfgCameraSocketOffsetZCm")):
        if cam.get(key) is not None:
            lines.append("%s=%s" % (cfg, cam[key]))
    for logical, asset in (("MoveActionPath", "IA_Move"),
                           ("LookActionPath", "IA_Look"),
                           ("JumpActionPath", "IA_Jump")):
        if asset in names:
            lines.append("%s=%s" % (logical, obj("%s/%s" % (root, asset))))
    lines += [
        "CfgMaxWalkSpeedCmS=%s" % mv["max_walk_speed_cm_s"],
        "CfgMaxStepHeightCm=%s" % mv["max_step_height_cm"],
        "CfgJumpZVelocityCmS=%s" % mv["jump_z_velocity_cm_s"],
        "CfgMaxAccelerationCmS2=%s" % mv["max_acceleration_cm_s2"],
        "CfgGravityScale=%s" % mv["gravity_scale"],
        "CfgCapsuleRadiusCm=%s" % cap["radius_cm"],
        "CfgCapsuleHalfHeightCm=%s" % cap["half_height_cm"],
        # DERIVED from movement.profile, never read from the recipe as a
        # number. Ruling 19: declared once, derived twice. This ini line is a
        # PROJECTION of terrain_erosion.MOVEMENT_PROFILES, which is why the
        # recipe still refuses to carry an angle of its own.
        "CfgWalkableFloorAngleDeg=%s"
        % te.MOVEMENT_PROFILES[mv["profile"]]["max_slope_deg"],
    ]
    block = "\n".join(lines) + "\n"

    existing = ""
    if os.path.exists(INI):
        with open(INI, "r", encoding="utf-8") as fh:
            existing = fh.read()
    pattern = re.compile(
        r"^\[" + re.escape(SECTION) + r"\]\r?\n(?:(?!^\[).*\r?\n?)*",
        re.M)
    if pattern.search(existing):
        new = pattern.sub(block, existing)
    else:
        sep = "" if existing.endswith("\n") or not existing else "\n"
        new = existing + sep + "\n" + block
    os.makedirs(os.path.dirname(INI), exist_ok=True)
    with open(INI, "w", encoding="utf-8") as fh:
        fh.write(new)
    return block


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default="recipes/character.json")
    ap.add_argument("--ini-only", action="store_true",
                    help="skip asset creation; write the ini only (no editor)")
    args = ap.parse_args(argv)

    try:
        with open(os.path.join(bootstrap.REPO_ROOT, args.recipe),
                  "r", encoding="utf-8") as fh:
            ch = json.load(fh)
    except Exception as e:
        print("COULD NOT READ THE RECIPE: %s: %s" % (type(e).__name__, e))
        return 1

    if ch.get("assets", {}).get("status") != "migrated":
        print("REFUSE: assets.status is %r, not 'migrated'. Pointing the "
              "character at assets that are not in /Game/ would configure "
              "paths that cannot resolve."
              % ch.get("assets", {}).get("status"))
        return 2

    spec = dict(ch["input"])
    for a in spec["actions"]:
        vt = a.get("value_type", "").lower()
        if vt not in VALUE_TYPES:
            print("REFUSE: action %r has value_type %r; known: %s"
                  % (a.get("name"), a.get("value_type"),
                     ", ".join(sorted(VALUE_TYPES))))
            return 2
        a["value_type"] = VALUE_TYPES[vt]
    expected = sum(len(a["bindings"]) for a in spec["actions"])

    rc = 0
    if not args.ini_only:
        remote_exec = bootstrap._load_remote_execution()
        remote = remote_exec.RemoteExecution()
        remote.start()
        try:
            node, reason = verify_landscape._select_verified_node(
                remote_exec, remote,
                bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
            if node is None:
                print("REFUSE (rule 7):", reason)
                return 3
            remote.open_command_connection(node["node_id"])
            d, raw = _run(remote, remote_exec,
                          PAYLOAD.replace("__SPEC__", json.dumps(spec)))
        finally:
            try:
                remote.stop()
            except Exception:
                pass

        if d is None:
            print("NO MARKER — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("PAYLOAD ERROR:", d["error"])
            return 1

        print("=== A. INPUT ASSETS ===")
        for c in d.get("created", []):
            print("  %-28s %s" % (c["asset"], "CREATED" if c["new"] else "existing"))
        for f in d.get("failed", []):
            print("  FAILED: %s" % f)
            rc = max(rc, 1)
        got = d.get("readback", {}).get("mapping_count")
        print("  key mappings   recipe declares %d, asset reads back %s"
              % (expected, got))
        if got != expected:
            print("  REFUSE: the mapping context does not carry what the recipe")
            print("          asked for. Read back off the ASSET, not off the")
            print("          list that was built, so this is a real mismatch.")
            rc = max(rc, 4)

    print("")
    print("=== B. DefaultGame.ini ===")
    block = _write_ini(ch, expected)
    print("  wrote [%s], %d keys" % (SECTION, len(block.splitlines()) - 6))
    print("  %s" % INI)
    print("")
    print("  NOT YET IN EFFECT: config UPROPERTYs are read at class load, so")
    print("  this needs an editor restart before the CDO carries it. That is")
    print("  non-negotiable 17 and it applies to this tool's own output.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
