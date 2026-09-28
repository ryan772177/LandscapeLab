import json as _json
import os
import traceback as _tb
import unreal as _u

# LOD CAPTURE SCENE -- E2. Stage one tree against a flat magenta backdrop,
# force a specific LOD, and READ THE FORCED LOD BACK.
#
# NOTHING IS CREATED ON DISK AND NOTHING IS SAVED.
#   * 8,637 LandscapeLab files are tracked by git, so a scratch level or a
#     debug material would add ASSETS to the repo. Ryan authorised the PNGs
#     and the JSON, not new content.
#   * So the actors are spawned into the ALREADY-LOADED level and destroyed
#     again by MODE=teardown. World Partition writes external actor packages
#     on SAVE, and this never saves, so unsaved spawns stay in memory.
#   * The PRIMARY backdrop material is built in memory as an UNSAVED Material
#     asset at KEY_MAT (deleted at teardown); a MaterialInstanceDynamic is the
#     FALLBACK. Nothing is saved, so neither reaches disk.
#
# The backdrop is enormous and sits between the camera and everything else,
# so the terrain, sky and town are simply not in frame. That is what makes it
# safe to do this in the live level rather than a scratch one.
#
# Teardown identifies our actors by a unique LABEL PREFIX (TAG) AND a property
# signature (StaticMeshActor). Rule 8 warns labels collide, so the prefix
# alone is not identity before destroy_actor -- the class check narrows it.

MODE = r"__MODE__"
SPECIES = r"__SPECIES__"
FORCE_LOD = __FORCE_LOD__

TAG = "E2LODCAP"
TREE_XYZ = (0.0, 0.0, 250000.0)      # above the 1552.5 m terrain, clear of all
BACKDROP_BEHIND_CM = 3000.0
BACKDROP_SCALE = 500.0                # /Engine/BasicShapes/Plane is 100 cm
KEY_RGB = (1.0, 0.0, 1.0)
KEY_MAT = "/Game/Debug/M_E2FlatKey"   # built in memory, deleted at teardown
KEY_GAIN = 5000.0                     # emissive gain: saturate past exposure
# Gain 40 rendered (7, 0, 8): the right HUE, crushed by exposure and the
# filmic tonemapper. Overshooting is free -- the channel clips at the key
# colour, which is exactly the value wanted -- so the gain is set far past
# where it saturates rather than tuned to a number that would drift with the
# level's lighting.

_out = {"ok": False, "error": None, "mode": MODE, "species": SPECIES}
try:
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _eal = _u.EditorAssetLibrary

    def _ours():
        # Label prefix AND class signature (rule 8): only a StaticMeshActor
        # carrying our TAG prefix is ours to destroy.
        return [a for a in _eas.get_all_level_actors()
                if a and isinstance(a, _u.StaticMeshActor)
                and a.get_actor_label().startswith(TAG)]

    def _destroy_ours():
        _n = 0
        for _a in _ours():
            _eas.destroy_actor(_a)
            _n += 1
        return _n

    # ---- TEARDOWN ------------------------------------------------------
    if MODE == "teardown":
        _out["destroyed"] = _destroy_ours()
        # The key material was built in memory and never saved. Delete it so
        # that even a later Save All cannot land it in /Game/Debug.
        try:
            if _eal.does_asset_exist(KEY_MAT):
                _eal.delete_asset(KEY_MAT)
            _out["key_material_deleted"] = not _eal.does_asset_exist(KEY_MAT)
        except Exception as _e:
            _out["key_material_delete_error"] = str(_e)
        _u.SystemLibrary.execute_console_command(_w, "r.ForceLOD -1")
        _u.SystemLibrary.execute_console_command(_w, "viewmode lit")
        try:
            _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
            _les.editor_set_game_view(False)
            _out["game_view_readback"] = bool(_les.editor_get_game_view())
        except Exception as _e:
            _out["game_view_error"] = str(_e)
        try:
            _out["force_lod_readback"] = int(
                _u.SystemLibrary.get_console_variable_int_value("r.ForceLOD"))
        except Exception as _e:
            _out["force_lod_readback"] = None
            _out["force_lod_readback_error"] = str(_e)
        _out["force_lod_reset_ok"] = (_out.get("force_lod_readback") == -1)
        _out["remaining"] = len(_ours())
        # Teardown's contract is to leave NO instrument actor and NO key
        # material behind (a later Save All must not land it). ok reflects that,
        # not merely "no exception".
        _out["ok"] = (_out["remaining"] == 0
                      and _out.get("key_material_deleted", False)
                      and _out["force_lod_reset_ok"])

    else:
        # ---- resolve the mesh from the RECIPE, never from an argument ----
        # R-UEEXEC: a /Game/ path through the shell is rewritten (Git Bash) or
        # stripped of quotes (PowerShell). SPECIES is a bare identifier.
        _root = os.path.dirname(
            os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))
        with open(os.path.join(_root, "recipes", "alpine_8k.json"),
                  "r", encoding="utf-8-sig") as _fh:
            _recipe = _json.load(_fh)
        _sp = None
        for _s in (_recipe.get("foliage") or {}).get("species") or []:
            if _s.get("name") == SPECIES:
                _sp = _s
                break
        if _sp is None:
            raise RuntimeError("species %r not in recipe" % SPECIES)
        _mesh_path = _sp["mesh"]
        _mesh = _eal.load_asset(_mesh_path)
        if _mesh is None:
            raise RuntimeError("could not load %s" % _mesh_path)
        _out["mesh"] = _mesh_path

        # ---- (re)build the scene ----------------------------------------
        if MODE == "setup":
            _destroy_ours()

            _b = _mesh.get_bounds()
            _ext = _b.box_extent
            _origin = _b.origin
            _h = float(_ext.z) * 2.0
            _out["height_cm"] = _h
            _out["sphere_radius_cm"] = float(_b.sphere_radius)
            _out["bounds_origin_cm"] = [float(_origin.x), float(_origin.y),
                                        float(_origin.z)]

            # The tree: put its BOUNDS CENTRE at TREE_XYZ, so the camera can
            # aim straight at TREE_XYZ regardless of where the pivot sits.
            # A pivot at the base and a pivot at the centre would otherwise
            # frame two different things at the same camera.
            _loc = _u.Vector(TREE_XYZ[0] - float(_origin.x),
                             TREE_XYZ[1] - float(_origin.y),
                             TREE_XYZ[2] - float(_origin.z))
            _tree = _eas.spawn_actor_from_object(_mesh, _loc,
                                                 _u.Rotator(0.0, 0.0, 0.0))
            if _tree is None:
                raise RuntimeError("tree spawn failed for %s" % _mesh_path)
            _tree.set_actor_label("%s_TREE_%s" % (TAG, SPECIES))
            _out["tree_actor"] = _tree.get_actor_label()

            # The backdrop is a CUBE at zero rotation with a two-sided material,
            # so facing is IRRELEVANT (an earlier plane version needed a pitch
            # to face the camera; that no longer applies).
            # A CUBE, NOT A PLANE. The opaque unlit material is two_sided
            # False, and a plane presents exactly one face -- so a backdrop
            # built from one is invisible whenever the facing is wrong, which
            # it was for four straight smoke frames. DebugMeshMaterial is
            # two-sided and rendered anyway, which HID the facing error behind
            # a different symptom. A cube always presents a face to the camera
            # whatever its rotation, so the question does not arise.
            _plane = _eal.load_asset("/Engine/BasicShapes/Cube")
            if _plane is None:
                raise RuntimeError("/Engine/BasicShapes/Cube missing")
            # KEYWORDS, NOT POSITION. `unreal.Rotator` takes ROLL FIRST, and
            # shoot.py's own --rot help records that this project has set a
            # roll believing it was a pitch THREE times. I made it the fourth:
            # Rotator(-90, 0, 0) ROLLED the backdrop, leaving it edge-on and
            # invisible, and the first smoke frame came back sky-blue.
            # Keyword arguments are order-independent, so the trap cannot fire.
            _bd = _eas.spawn_actor_from_object(
                _plane,
                _u.Vector(TREE_XYZ[0] + BACKDROP_BEHIND_CM,
                          TREE_XYZ[1], TREE_XYZ[2]),
                _u.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            if _bd is None:
                raise RuntimeError("backdrop spawn failed")
            _bd.set_actor_label("%s_BACKDROP" % TAG)
            # Thin in X, enormous in Y and Z: a wall, not a block. Its near
            # face sits BACKDROP_BEHIND_CM minus half its thickness behind the
            # tree, so it cannot swallow the subject.
            _bd.set_actor_scale3d(_u.Vector(1.0, BACKDROP_SCALE,
                                            BACKDROP_SCALE))

            # Flat magenta, UNLIT, as a transient MID. The parameter name is
            # PROBED rather than assumed -- ue58-api-protocol: the reflected
            # surface is the contract. Whatever succeeds is reported, and the
            # driver additionally verifies the BACKGROUND PIXEL of the PNG,
            # which is the only check that cannot be fooled by a silent
            # no-op setter.
            # BUILD THE MATERIAL. Three engine materials were tried first and
            # all three failed, each for a DIFFERENT reason -- additive,
            # translucent, and a `Color` parameter its graph does not use
            # (LevelColorationUnlitMaterial rendered pure black). Building one
            # takes the same technique make_layer_debug_material.py already
            # uses and leaves nothing to discover.
            #
            # IT IS NEVER SAVED. create_asset builds it in memory; teardown
            # deletes it. Nothing reaches disk, which matters because 8,637
            # LandscapeLab files are tracked.
            _mi = None
            _tried = []
            try:
                _mel = _u.MaterialEditingLibrary
                # ALWAYS REBUILD THE GRAPH. `delete_asset` on this material
                # returns without deleting (key_material_deleted came back
                # false), so a "create if absent" branch silently reuses
                # whatever the FIRST attempt built -- which is how an emissive
                # gain change produced a byte-identical black frame twice.
                # Loading and rebuilding makes the asset's content a function
                # of THIS run's constants.
                if _eal.does_asset_exist(KEY_MAT):
                    _mat = _eal.load_asset(KEY_MAT)
                    _out["key_material_reused"] = True
                else:
                    _mat = _u.AssetToolsHelpers.get_asset_tools().create_asset(
                        KEY_MAT.rsplit("/", 1)[1], KEY_MAT.rsplit("/", 1)[0],
                        _u.Material, _u.MaterialFactoryNew())
                if True:
                    _mat.set_editor_property(
                        "shading_model", _u.MaterialShadingModel.MSM_UNLIT)
                    _mat.set_editor_property(
                        "blend_mode", _u.BlendMode.BLEND_OPAQUE)
                    _mat.set_editor_property("two_sided", True)
                    try:
                        _mel.delete_all_material_expressions(_mat)
                    except Exception as _e:
                        _out["expr_clear_error"] = str(_e)
                    _c3 = _mel.create_material_expression(
                        _mat, _u.MaterialExpressionConstant3Vector, -350, 0)
                    # EMISSIVE 1.0 IS NOT BRIGHT. It goes through exposure and
                    # tone mapping like anything else, and in this dim scene
                    # it lands near black. KEY_GAIN pushes it far enough to
                    # SATURATE, so the backdrop clips to full magenta whatever
                    # the eye adaptation is doing. The driver still measures
                    # the pixel rather than trusting this.
                    _c3.set_editor_property(
                        "constant", _u.LinearColor(KEY_RGB[0] * KEY_GAIN,
                                                   KEY_RGB[1] * KEY_GAIN,
                                                   KEY_RGB[2] * KEY_GAIN, 1.0))
                    _mel.connect_material_property(
                        _c3, "", _u.MaterialProperty.MP_EMISSIVE_COLOR)
                    _mel.recompile_material(_mat)
                _bd.static_mesh_component.set_material(0, _mat)
                # Read the material back off the component (rule 12): backdrop_
                # built reflects the read-back, not merely "no exception".
                _rbm = _bd.static_mesh_component.get_material(0)
                _out["backdrop_material_readback"] = (
                    _rbm.get_path_name() if _rbm is not None else None)
                _mi = _mat
                _out["backdrop_material"] = KEY_MAT
                _out["backdrop_built"] = (
                    _rbm is not None and _rbm.get_path_name() == KEY_MAT)
            except Exception as _e:
                _tried.append("built %s: %s" % (KEY_MAT, _e))
            # THE DISCRIMINATOR IS THE BLEND MODE, NOT THE PARAMETER.
            # All three of these expose a `Color` vector parameter, and
            # set/get on a MID succeeds for ANY name because it reads back the
            # MID's own override table rather than the material graph. Two of
            # them are useless as a key backdrop and both were tried first:
            #
            #   EmissiveMeshMaterial          Color  ADDITIVE     -> invisible
            #   DebugMeshMaterial             Color  TRANSLUCENT  -> navy
            #   LevelColorationUnlitMaterial  Color  OPAQUE/UNLIT -> correct
            #
            # Measured by material_param_probe.py, which asks the MATERIAL.
            # two_sided is False on the opaque one, so the backdrop's facing
            # (pitch -90) is load-bearing.
            for _mpath in ([] if _mi is not None else [
                    "/Engine/EngineDebugMaterials/LevelColorationUnlitMaterial",
                    "/Engine/EngineMaterials/EmissiveMeshMaterial",
                    "/Engine/EngineDebugMaterials/DebugMeshMaterial"]):
                _parent = _eal.load_asset(_mpath)
                if _parent is None:
                    _tried.append("%s: absent" % _mpath)
                    continue
                _cand = _u.MaterialLibrary.create_dynamic_material_instance(
                    _bd.static_mesh_component, _parent)
                if _cand is None:
                    _tried.append("%s: MID refused" % _mpath)
                    continue
                for _pname in ("Color", "BaseColor", "Colour",
                               "EmissiveColor"):
                    try:
                        _cand.set_vector_parameter_value(
                            _pname, _u.LinearColor(KEY_RGB[0], KEY_RGB[1],
                                                   KEY_RGB[2], 1.0))
                        _rb = _cand.get_vector_parameter_value(_pname)
                        if (abs(_rb.r - KEY_RGB[0]) < 1e-3
                                and abs(_rb.g - KEY_RGB[1]) < 1e-3
                                and abs(_rb.b - KEY_RGB[2]) < 1e-3):
                            _mi = _cand
                            _out["backdrop_material"] = _mpath
                            _out["backdrop_param"] = _pname
                            _out["backdrop_readback"] = [_rb.r, _rb.g, _rb.b]
                            _out["backdrop_readback_note"] = (
                                "MID override table only -- NOT a material-graph "
                                "confirmation; the driver's PNG pixel check is "
                                "the real verifier")
                            break
                        _tried.append("%s.%s: set did not stick" %
                                      (_mpath, _pname))
                    except Exception as _e:
                        _tried.append("%s.%s: %s" % (_mpath, _pname, _e))
                if _mi is not None:
                    break
            _out["backdrop_attempts"] = _tried
            if _mi is None:
                # NOT fatal here: say so loudly and let the PNG check decide.
                _out["backdrop_warning"] = (
                    "no flat-colour material could be parameterised; the "
                    "background will NOT be magenta and the driver's pixel "
                    "check must refuse the captures")
            _bd.static_mesh_component.set_material(0, _mi) if _mi else None
            _out["backdrop_actor"] = _bd.get_actor_label()

        # ---- keep the EDITOR out of the frame ----------------------------
        # The first smoke frame carried a CameraActor billboard upper-right
        # and the viewport axis gizmo lower-left. Those are non-key pixels, so
        # the mask counts them as SUBJECT and every coverage ratio is wrong by
        # a constant. They are identical across LODs, which is exactly what
        # makes the corruption hard to notice in a comparison.
        # `ShowFlag.Sprites 0` did NOT remove them: an editor billboard is
        # drawn without a depth test, so the backdrop cannot occlude it
        # either. GAME VIEW is the flag that actually governs editor-only
        # primitives, and LevelEditorSubsystem exposes a GETTER, so it can be
        # read back rather than assumed.
        try:
            _les = _u.get_editor_subsystem(_u.LevelEditorSubsystem)
            _les.editor_set_game_view(True)
            _out["game_view_readback"] = bool(_les.editor_get_game_view())
        except Exception as _e:
            _out["game_view_readback"] = None
            _out["game_view_error"] = str(_e)

        # UNLIT. Two reasons, not one. It makes the backdrop render its base
        # colour as pure magenta regardless of where the sun is -- lit, it
        # came back dark navy. And it removes lighting from the silhouette
        # comparison altogether, so a coverage or IoU difference between two
        # LODs is GEOMETRY and cannot be a shading accident.
        # `execute_console_command(world, "viewmode unlit")` did NOT take --
        # the frame came back lit, with sun highlights along the branches.
        # `viewmode` is an EDITOR VIEWPORT command, so it is also issued with
        # world=None, which routes to GEngine's exec rather than the world's.
        # LIT, DELIBERATELY -- and this is a term collision worth writing down.
        # `viewmode unlit` visualises BASE COLOR. An MSM_UNLIT MATERIAL has no
        # base colour at all; its output is EmissiveColor. So the built
        # magenta backdrop rendered PURE BLACK under `viewmode unlit`, and so
        # did LevelColorationUnlitMaterial before it -- two different
        # materials, one cause, and it looked like the colour was not being
        # applied.
        #
        # The emissive backdrop needs no help from the view mode: it is
        # self-illuminated, so the sun angle cannot shade it.
        for _target in (_w, None):
            try:
                _u.SystemLibrary.execute_console_command(_target,
                                                         "viewmode lit")
            except Exception as _e:
                _out.setdefault("viewmode_errors", []).append(str(_e))

        try:
            _eas.set_selected_level_actors([])   # shoot.py warns; this acts
        except Exception as _e:
            _out["deselect_error"] = str(_e)

        # ---- force the LOD and READ IT BACK ------------------------------
        _u.SystemLibrary.execute_console_command(
            _w, "r.ForceLOD %d" % int(FORCE_LOD))
        try:
            _out["force_lod_readback"] = int(
                _u.SystemLibrary.get_console_variable_int_value("r.ForceLOD"))
        except Exception as _e:
            _out["force_lod_readback"] = None
            _out["force_lod_readback_error"] = str(_e)
        _out["force_lod_requested"] = int(FORCE_LOD)
        _out["force_lod_ok"] = (_out.get("force_lod_readback")
                                == int(FORCE_LOD))
        _out["actors"] = [a.get_actor_label() for a in _ours()]
        # The stated purpose is to force a LOD and read it back; ok must reflect
        # that read-back, not merely "no exception". (setup forces LOD 0.)
        _out["ok"] = _out["force_lod_ok"] is True

except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _out["traceback"] = _tb.format_exc()

print(_json.dumps(_out, indent=2))
