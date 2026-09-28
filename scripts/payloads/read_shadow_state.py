"""Task 4 stage 2 read-backs: what is casting shadow on the meadow, and how.

READ-ONLY. No edits, by ruling.

⭐ WHY SHADOW AND NOT MORE CARD COLOUR. Task 4's metric is std/mean of
luminance over the meadow, and stage 1 measured that it is dominated by
LIGHTING structure: +/-8% hue and brightness on the cards moved 40% of
meadow pixels by more than 1% and moved the statistic by 0.09%. The
references read 1.22-1.26 on the same metric and their meadows carry
heavy shadow structure. So the candidates are the things that would put
SHADOW between the blades.

FOUR GROUPS, each reported whether or not it is currently on:

  1. per-FOLIAGE-TYPE shadow casting, all five meadow meshes
  2. the project's shadow METHOD (virtual shadow maps vs shadow maps)
     and whether foliage/Nanite is included
  3. the sun's CONTACT SHADOWS -- length and whether that length is in
     world space
  4. the card material's NORMAL handling and shading model: a flat
     up-vector normal gives every blade the same N.L and erases exactly
     the variation this task is trying to find

⛔ THE GRASS TYPE IS NOT A FOLIAGE TYPE ASSET IN THE USUAL SENSE. Meadow
is `system: grass`, so its per-instance settings live on the LANDSCAPE
GRASS TYPE's varieties (FGrassVariety), NOT on a UFoliageType. Only the
grass-type path is read here (a UFoliageType would not carry meadow's
settings); an absent grass type is reported as `_error`, and a run that
reads no varieties refuses rather than reading "shadows are off".
"""
import json as _json
import traceback as _tb

import unreal as _u

GRASS_TYPES = ("/Game/Foliage/GT_alpine_8k_Meadow",)
MESHES = ("/Game/Meshes/grass_medium_01_large_a_LOD0",
          "/Game/Meshes/grass_medium_01_tiny_a_LOD0",
          "/Game/Meshes/grass_medium_01_tall_a_LOD0",
          "/Game/Meshes/grass_medium_01_small_a_LOD0",
          "/Game/Meshes/grass_medium_01_mid_b_LOD0")
CARD_MAT = "/Game/Meshes/Materials/M_grass_medium_01"
_out = {"ok": False}


def _props(obj, names):
    d = {}
    for n in names:
        try:
            v = obj.get_editor_property(n)
        except Exception as e:
            d[n] = "ABSENT (%s)" % type(e).__name__
            continue
        d[n] = (v if isinstance(v, (int, float, bool, str, type(None)))
                else str(v))
    return d


try:
    _eal = _u.EditorAssetLibrary

    # ---- 1. GRASS VARIETIES -----------------------------------------
    gt = {}
    for p in GRASS_TYPES:
        if not _eal.does_asset_exist(p):
            gt[p] = {"_error": "asset does not exist"}
            continue
        a = _eal.load_asset(p)
        rows = []
        try:
            varieties = a.get_editor_property("grass_varieties")
        except Exception as e:
            varieties = []
            gt[p] = {"_error": "grass_varieties unreadable: %s" % e}
        for v in (varieties or []):
            r = _props(v, ["grass_mesh", "cast_dynamic_shadow",
                           "cast_static_shadow", "receives_decals",
                           "affect_distance_field_lighting",
                           "grass_density", "start_cull_distance",
                           "end_cull_distance", "align_to_surface",
                           "random_rotation", "use_grid",
                           "scaling", "light_map_channel"])
            try:
                m = v.get_editor_property("grass_mesh")
                r["mesh_name"] = m.get_name() if m else None
            except Exception as _me:
                # F6: ABSENT, not silently dropped (matches _props' convention).
                r["mesh_name"] = "ABSENT (%s)" % type(_me).__name__
            rows.append(r)
        gt.setdefault(p, {})["varieties"] = rows
        gt[p]["n_varieties"] = len(rows)
    _out["grass_types"] = gt

    # ---- the meshes' own defaults, which the variety may override ----
    mesh_rows = {}
    for p in MESHES:
        if not _eal.does_asset_exist(p):
            mesh_rows[p.rsplit("/", 1)[-1]] = {"_error": "missing"}
            continue
        m = _eal.load_asset(p)
        mesh_rows[p.rsplit("/", 1)[-1]] = _props(
            m, ["cast_shadow", "nanite_settings", "num_lods"])
    _out["meshes"] = mesh_rows

    # ---- 2. SHADOW METHOD -------------------------------------------
    cv = {}
    for n in ("r.Shadow.Virtual.Enable", "r.Shadow.Virtual.Nanite.Enable",
              "r.Shadow.Virtual.SMRT.RayCountDirectional",
              "r.Shadow.Virtual.ResolutionLodBiasDirectional",
              "r.Shadow.Virtual.NonNanite.IncludeInCoarsePages",
              "r.ContactShadows", "r.ContactShadows.NonShadowCastingIntensity",
              "foliage.DitheredLOD", "r.Shadow.CSM.MaxCascades"):
        v = _u.SystemLibrary.get_console_variable_string_value(n)
        cv[n] = {"value": v, "exists": v != ""}
    _out["cvars"] = cv

    # ---- 3. THE SUN --------------------------------------------------
    eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    suns = []
    for act in eas.get_all_level_actors():
        # F5: identify the sun by the PRESENCE of a DirectionalLightComponent,
        # not an exact actor-class-name match -- a Blueprint-derived light or a
        # SunSky carries the component under a different class name and an exact
        # "DirectionalLight" test would skip it, leaving group 3 silently empty.
        comp = None
        try:
            comp = act.get_component_by_class(_u.DirectionalLightComponent)
        except Exception:
            comp = None
        if comp is None:
            continue
        row = {"label": act.get_actor_label(),
               "class": type(act).__name__}
        if comp is not None:
            row["component"] = _props(comp, [
                "contact_shadow_length",
                "contact_shadow_length_in_ws",
                "contact_shadow_casting_intensity",
                "contact_shadow_non_shadow_casting_intensity",
                "cast_shadows", "cast_dynamic_shadows",
                "dynamic_shadow_distance_movable_light",
                "dynamic_shadow_cascades", "shadow_bias",
                "shadow_slope_bias", "cast_translucent_shadows",
                "intensity", "light_source_angle",
                "atmosphere_sun_light"])
        suns.append(row)
    _out["directional_lights"] = suns

    # ---- 4. THE CARD MATERIAL ---------------------------------------
    mat = _eal.load_asset(CARD_MAT)
    # F3: a missing card material makes mat None; get_material_expressions(None)
    # below would raise and discard the whole probe. Guard it as its own group
    # error instead.
    _card_ok = mat is not None
    if not _card_ok:
        _out["card_material"] = {"_error": "asset not found: " + CARD_MAT}
    else:
        _out["card_material"] = _props(mat, [
            "shading_model", "two_sided", "blend_mode",
            "material_domain", "use_material_attributes",
            "translucency_lighting_mode", "opacity_mask_clip_value",
            "num_customized_u_vs", "allow_translucent_custom_depth_writes"])
        mel = _u.MaterialEditingLibrary
        try:
            n_node = mel.get_material_property_input_node(
                mat, _u.MaterialProperty.MP_NORMAL)
            _out["card_material"]["normal_input_node"] = (
                type(n_node).__name__ if n_node else "NOT CONNECTED")
        except Exception as e:
            _out["card_material"]["normal_input_node"] = (
                "UNREADABLE: %s" % type(e).__name__)
        classes = {}
        for e in mel.get_material_expressions(mat):
            cn = type(e).__name__.replace("MaterialExpression", "")
            classes[cn] = classes.get(cn, 0) + 1
        _out["card_material"]["expression_classes"] = classes

    # F1/NN13: the four groups are all load-bearing; a run that read no grass
    # variety, no directional light, or no card material answered nothing for
    # that group -- do not report the whole probe as ok over it.
    _grass_ok = any(g.get("n_varieties", 0) > 0 for g in gt.values())
    _sun_ok = len(suns) > 0
    _out["ok"] = _grass_ok and _sun_ok and _card_ok
    if not _out["ok"]:
        _out["refused"] = (
            "grass_varieties_read=%s, directional_lights=%d, card_material=%s "
            "-- a load-bearing group read nothing"
            % (_grass_ok, len(suns), _card_ok))
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
