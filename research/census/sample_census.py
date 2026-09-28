"""sample_census.py — READ-ONLY census of a reference project. Runs inside the
editor (ue_exec style: prints __LL__ + JSON). Never saves, never spawns,
never mutates. Every section is wrapped: a missing class or property in a
given engine version is recorded as {"_error": ...} for that item, not a
crash of the whole census.

WHAT IT DUMPS (each keyed by asset path so two projects can be diffed):
  hlod_layers        UHLODLayer: layer type, builder settings + every scalar/
                     bool/enum on the settings object, cell size, loading
                     range, parent, RT far-field flag
  world_partition    per loaded world: runtime grids (cell size, loading
                     range, priority), default HLOD layer, streaming settings
  foliage_types      UFoliageType: mesh, density, scale, slope/height/align,
                     cull min/max, mesh Nanite flag, LOD count/screen sizes/
                     triangle counts, materials, whether any material graph
                     contains a PerInstanceFadeAmount node
  impostors          any material/mesh whose name or path contains
                     "Impostor"/"Imposter"/"Billboard": material params,
                     texture sizes
  pcg_graphs         UPCGGraph: node list with class + settings scalars
  landscape_materials UMaterial referenced by any Landscape in loaded worlds:
                     expression class histogram, LandscapeLayerBlend layer
                     names + blend types, scalar/vector parameters, texture
                     samples with tiling-relevant params
  lighting           per loaded world: directional lights, sky lights, sky
                     atmosphere, height fog, volumetric cloud, PostProcess
                     volumes (only overridden settings), exposure
  water              WaterBody actors: type, material, shading model
  project            engine version, plugins enabled (from the uproject)

Usage (from the repo's ue_exec, with the target project's editor open):
  python scripts/ue_exec.py scripts/payloads/sample_census.py \
      --set __OUT__=C:/Users/Admin/UE5LandscapePipeline/research/census/<project>.json \
      --set __MAPS__=/Game/Levels/Foo,/Game/Levels/Bar   (optional; default = current world only)

VERIFY notes for Claude Code: property names are the 5.8 reflected names
(leading 'b' stripped on booleans). Anything that raises is captured per
item; grep the output for "_error" and fix names against the headers cited
in the comments before trusting a null.
"""
import json as _json
import os as _os
import unreal as _u

_OUT = "__OUT__"
_MAPS = "__MAPS__"
_out = {"ok": False, "sections": {}, "errors": []}


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # noqa
        return {"_error": str(e)[:300]}


def _props(obj, names):
    d = {}
    for n in names:
        try:
            v = obj.get_editor_property(n)
            d[n] = _jsonable(v)
        except Exception as e:  # noqa
            d[n] = {"_error": str(e)[:120]}
    return d


def _jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (_u.Vector, _u.Vector2D, _u.Rotator, _u.LinearColor, _u.Color, _u.IntPoint)):
        return str(v)
    if isinstance(v, _u.Name):
        return str(v)
    if isinstance(v, _u.Text):
        return str(v)
    if isinstance(v, (list, tuple, _u.Array)):
        return [_jsonable(x) for x in v]
    if isinstance(v, _u.Object):
        try:
            return v.get_path_name()
        except Exception:  # noqa
            return str(v)
    if isinstance(v, _u.StructBase):
        d = {}
        try:
            for n in dir(v):
                if n.startswith("_") or callable(getattr(v, n, None)):
                    continue
                try:
                    d[n] = _jsonable(v.get_editor_property(n))
                except Exception:  # noqa
                    pass
        except Exception:  # noqa
            pass
        return d or str(v)
    return str(v)


def _all_props(obj):
    """Dump every reflected editor property we can read; used for settings
    structs whose field names vary by engine version."""
    d = {}
    for n in dir(obj):
        if n.startswith("_") or callable(getattr(obj, n, None)):
            continue
        try:
            d[n] = _jsonable(obj.get_editor_property(n))
        except Exception:  # noqa
            pass
    return d


_ar = _u.AssetRegistryHelpers.get_asset_registry()


# A CLASS IS NOT ALWAYS IN /Script/Engine, AND GETTING THAT WRONG RETURNS
# CLEANLY WITH NOTHING. Measured 2026-09-09 on the Electric Dreams census:
# `pcg_graphs` came back 0 on the PCG REFERENCE PROJECT, which has 22 PCG
# graph assets on disk. UPCGGraph lives in /Script/PCG; the query asked
# /Script/Engine, found no such class, and returned an empty list -- no
# exception, no error record, just a zero that reads as "this project has
# none". `foliage_types` was 0 in all three censuses for the same reason:
# UFoliageType is in /Script/Foliage.
#
# Same failure family as world_partition's dead accessor: well-formed,
# error-free, and describing something other than what was asked.
_CLASS_PACKAGES = {
    "PCGGraph": "/Script/PCG",
    "FoliageType": "/Script/Foliage",
    "FoliageType_InstancedStaticMesh": "/Script/Foliage",
    "FoliageType_Actor": "/Script/Foliage",
    "WaterBody": "/Script/Water",
    "LandscapeGrassType": "/Script/Landscape",
}


def _assets_of(class_name):
    # Try the class's own package first, then Engine, then every other
    # package we know of -- a class that moves between engine versions still
    # gets found, and a genuine zero stays a zero.
    seen, tried = [], []
    pkgs = []
    if class_name in _CLASS_PACKAGES:
        pkgs.append(_CLASS_PACKAGES[class_name])
    pkgs.append("/Script/Engine")
    for p in set(_CLASS_PACKAGES.values()):
        if p not in pkgs:
            pkgs.append(p)
    for pkg in pkgs:
        try:
            got = list(_ar.get_assets_by_class(
                _u.TopLevelAssetPath(pkg, class_name), True))
        except Exception:  # noqa
            got = []
        tried.append("%s:%d" % (pkg, len(got)))
        if got:
            seen = got
            break
    if not seen:
        # Deprecated string form, as a last resort.
        try:
            seen = list(_ar.get_assets_by_class(class_name, True))
        except Exception:  # noqa
            seen = []
    _ASSET_LOOKUP_TRACE[class_name] = tried
    return seen


_ASSET_LOOKUP_TRACE = {}


# --------------------------------------------------------------- project ---
def sec_project():
    d = {"engine": _u.SystemLibrary.get_engine_version(),
         "project_dir": _u.Paths.project_dir()}
    up = None
    try:
        for f in _os.listdir(_u.Paths.project_dir()):
            if f.endswith(".uproject"):
                up = _os.path.join(_u.Paths.project_dir(), f)
        if up:
            j = _json.load(open(up, "r", encoding="utf-8"))
            d["plugins_enabled"] = [p.get("Name") for p in j.get("Plugins", []) if p.get("Enabled", True)]
    except Exception as e:  # noqa
        d["_error"] = str(e)[:200]
    return d


# ------------------------------------------------------------ hlod layers ---
def sec_hlod_layers():
    out = {}
    for a in _assets_of("HLODLayer"):
        path = str(a.package_name)
        try:
            L = a.get_asset()
            rec = _props(L, ["layer_type", "cell_size", "loading_range", "is_spatially_loaded",
                             "parent_layer", "force_ray_tracing_far_field", "editor_loading_behavior"])
            hb = None
            for n in ("hlod_builder_settings", "hlod_builder_class"):
                try:
                    hb = L.get_editor_property(n)
                    rec[n] = _jsonable(hb)
                except Exception:  # noqa
                    pass
            try:
                bs = L.get_editor_property("hlod_builder_settings")
                rec["builder_settings_class"] = bs.get_class().get_name()
                rec["builder_settings"] = _all_props(bs)
                for inner in ("mesh_approximation_settings", "mesh_merge_settings",
                              "mesh_simplify_settings", "material_settings"):
                    try:
                        rec["builder_settings"][inner] = _all_props(bs.get_editor_property(inner))
                    except Exception:  # noqa
                        pass
            except Exception as e:  # noqa
                rec["builder_settings_error"] = str(e)[:200]
            out[path] = rec
        except Exception as e:  # noqa
            out[path] = {"_error": str(e)[:200]}
    return out


# --------------------------------------------------------- world partition --
def _worlds():
    ws = []
    try:
        w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
        if w:
            ws.append(w)
    except Exception:  # noqa
        pass
    return ws


def sec_world_partition():
    out = {}
    for w in _worlds():
        rec = {}
        try:
            # `World.get_world_partition()` DOES NOT EXIST in 5.8 -- it raised
            # "'World' object has no attribute 'get_world_partition'" on every
            # world in both sample projects, and because it was the first
            # statement in the try, the entire section below was unreached and
            # the result was a lone {"_error": ...} that COUNTS AS ONE ENTRY
            # in a section summary. It reads exactly like a captured result.
            #
            # The route below is the one this project already proved in
            # scripts/payloads/bench_grid_derive.py:
            #     UWorldSettings.world_partition   WorldPartition.h:556
            #     runtime_hash reached by find_object, NOT get_editor_property
            wp = None
            for _get in (
                    lambda: w.get_world_settings().get_editor_property(
                        "world_partition"),
                    lambda: w.get_editor_property("world_partition")):
                try:
                    wp = _get()
                    if wp is not None:
                        break
                except Exception:  # noqa
                    continue
            if wp is None:
                rec["world_partition"] = None
                rec["_note"] = ("no UWorldPartition on this world -- it is "
                                "not a World Partition map")
            else:
                rec["world_partition_path"] = _jsonable(wp)
                rec["default_hlod_layer"] = _jsonable(_safe(wp.get_editor_property, "default_hlod_layer"))
                # WorldPartition.h:555-556 declares runtime_hash as a bare
                # UPROPERTY() with no accessor, so get_editor_property is
                # refused. find_object on the sub-object DOES reach it.
                rh = _safe(wp.get_editor_property, "runtime_hash")
                if not isinstance(rh, _u.Object):
                    for _cand in ("WorldPartitionRuntimeHashSet_0",
                                  "WorldPartitionRuntimeSpatialHash_0"):
                        try:
                            _found = _u.find_object(wp, _cand)
                        except Exception:  # noqa
                            _found = None
                        if _found is not None:
                            rh = _found
                            rec["runtime_hash_route"] = "find_object(%s)" % _cand
                            break
                rec["runtime_hash_class"] = rh.get_class().get_name() if isinstance(rh, _u.Object) else _jsonable(rh)
                if isinstance(rh, _u.Object):
                    rec["runtime_hash"] = _all_props(rh)
                    # Two hash classes, two different properties, and the
                    # fallback must not report the WRONG cause. A HashSet has
                    # `runtime_partitions`; a SpatialHash has `grids`. Trying
                    # grids on a HashSet and reporting "Failed to find
                    # property 'grids'" names a property that was never the
                    # right one -- it reads as an API gap when the real
                    # situation is that RuntimePartitions is declared
                    # `private:` (WorldPartitionRuntimeHashSet.h) and is
                    # UNREACHABLE from Python. This project established that
                    # already: bench_grid_derive.py:139.
                    _cls = rh.get_class().get_name()
                    _want = ("runtime_partitions"
                             if "HashSet" in _cls else "grids")
                    try:
                        _vals = rh.get_editor_property(_want)
                        rec[_want] = [_all_props(p) for p in _vals]
                    except Exception as e:  # noqa
                        rec["%s_error" % _want] = str(e)[:120]
                        if _want == "runtime_partitions":
                            rec["_runtime_partitions_note"] = (
                                "EXPECTED, NOT A BUG: UWorldPartitionRuntime"
                                "HashSet declares RuntimePartitions as "
                                "private, so it is not reflected to Python. "
                                "The cell size and loading range live inside "
                                "it and cannot be read this way. See "
                                "scripts/payloads/bench_grid_derive.py:139.")
        except Exception as e:  # noqa
            rec["_error"] = str(e)[:200]
        out[w.get_path_name()] = rec
    return out


# ----------------------------------------------------------- foliage types --
def _material_has_fade(mat):
    try:
        mel = _u.MaterialEditingLibrary
        base = mat
        while isinstance(base, _u.MaterialInstance):
            base = base.get_editor_property("parent")
        exprs = _safe(_u.MaterialEditingLibrary.get_material_expressions, base) if hasattr(mel, "get_material_expressions") else None
        if isinstance(exprs, list):
            return any("PerInstanceFade" in e.get_class().get_name() for e in exprs)
        # fallback: name-based on the base material's path
        return None
    except Exception:  # noqa
        return None


def _mesh_summary(m):
    rec = {"path": m.get_path_name()}
    try:
        rec["nanite"] = bool(m.get_editor_property("nanite_settings").get_editor_property("enabled"))
    except Exception:  # noqa
        rec["nanite"] = None
    try:
        n = m.get_num_lods()
        rec["lods"] = []
        for i in range(n):
            lod = {"index": i}
            try:
                lod["triangles"] = m.get_num_triangles(i)
            except Exception:  # noqa
                pass
            try:
                ss = m.get_editor_property("lod_settings")  # may not exist; screen sizes live in source models
                lod["lod_settings"] = _jsonable(ss)
            except Exception:  # noqa
                pass
            rec["lods"].append(lod)
    except Exception as e:  # noqa
        rec["lods_error"] = str(e)[:120]
    try:
        rec["screen_sizes"] = [_jsonable(x) for x in _u.EditorStaticMeshLibrary.get_lod_screen_sizes(m)]
    except Exception:  # noqa
        try:
            rec["screen_sizes"] = [_jsonable(x) for x in _u.StaticMeshEditorSubsystem().get_lod_screen_sizes(m)]
        except Exception as e:  # noqa
            rec["screen_sizes_error"] = str(e)[:120]
    try:
        mats = m.get_editor_property("static_materials")
        rec["materials"] = []
        for sm in mats:
            mi = sm.get_editor_property("material_interface")
            rec["materials"].append({"path": mi.get_path_name() if mi else None,
                                     "has_per_instance_fade": _material_has_fade(mi) if mi else None})
    except Exception as e:  # noqa
        rec["materials_error"] = str(e)[:120]
    return rec


def sec_foliage_types():
    out = {}
    for a in _assets_of("FoliageType_InstancedStaticMesh") + _assets_of("FoliageType"):
        path = str(a.package_name)
        if path in out:
            continue
        try:
            ft = a.get_asset()
            rec = _props(ft, ["density", "density_adjustment_factor", "radius", "single_instance_mode_radius",
                              "scaling", "scale_x", "scale_y", "scale_z", "align_to_normal", "align_max_angle",
                              "random_pitch_angle", "random_yaw", "ground_slope_angle", "height",
                              "landscape_layers", "min_scale", "max_scale", "cull_distance",
                              "enable_cull_distance", "enable_density_scaling", "enable_static_lighting",
                              "cast_shadow", "collision_with_world", "mobility", "lod_distance_scale",
                              "world_position_offset_disable_distance", "receives_decals", "enable_discard_on_load"])
            try:
                mesh = ft.get_editor_property("mesh")
                rec["mesh"] = _mesh_summary(mesh) if mesh else None
            except Exception as e:  # noqa
                rec["mesh_error"] = str(e)[:120]
            out[path] = rec
        except Exception as e:  # noqa
            out[path] = {"_error": str(e)[:200]}
    return out


# --------------------------------------------------------------- impostors --
def sec_impostors():
    out = {}
    try:
        for cls in ("Material", "MaterialInstanceConstant", "StaticMesh", "Texture2D"):
            for a in _assets_of(cls):
                p = str(a.package_name)
                low = p.lower()
                if any(k in low for k in ("impostor", "imposter", "billboard", "octahedral")):
                    rec = {"class": cls}
                    try:
                        o = a.get_asset()
                        if cls == "Texture2D":
                            rec["size"] = [o.blueprint_get_size_x(), o.blueprint_get_size_y()]
                        elif cls == "MaterialInstanceConstant":
                            rec["parent"] = _jsonable(o.get_editor_property("parent"))
                            rec["scalar_params"] = [_jsonable(x) for x in o.get_editor_property("scalar_parameter_values")]
                            rec["texture_params"] = [_jsonable(x) for x in o.get_editor_property("texture_parameter_values")]
                        elif cls == "StaticMesh":
                            rec["mesh"] = _mesh_summary(o)
                    except Exception as e:  # noqa
                        rec["_error"] = str(e)[:150]
                    out[p] = rec
    except Exception as e:  # noqa
        out["_error"] = str(e)[:200]
    return out


# ------------------------------------------------------------- pcg graphs ---
def sec_pcg_graphs():
    out = {}
    for a in _assets_of("PCGGraph"):
        path = str(a.package_name)
        try:
            g = a.get_asset()
            rec = {"nodes": []}
            try:
                nodes = g.get_editor_property("nodes")
            except Exception:  # noqa
                nodes = _safe(g.get_nodes)
            for n in (nodes or []):
                nd = {"class": n.get_class().get_name()}
                try:
                    s = n.get_editor_property("settings_interface") or n.get_editor_property("settings")
                    if isinstance(s, _u.Object):
                        nd["settings_class"] = s.get_class().get_name()
                        nd["settings"] = {k: v for k, v in _all_props(s).items()
                                          if isinstance(v, (int, float, bool, str)) or isinstance(v, list) and len(v) < 16}
                except Exception:  # noqa
                    pass
                rec["nodes"].append(nd)
            out[path] = rec
        except Exception as e:  # noqa
            out[path] = {"_error": str(e)[:200]}
    return out


# ------------------------------------------------------ landscape materials --
def _material_census(mat):
    rec = {"path": mat.get_path_name()}
    try:
        base = mat
        chain = []
        while isinstance(base, _u.MaterialInstance):
            chain.append(base.get_path_name())
            base = base.get_editor_property("parent")
        rec["instance_chain"] = chain
        rec["base"] = base.get_path_name() if base else None
        exprs = _u.MaterialEditingLibrary.get_material_expressions(base) if base else []
        hist = {}
        layers = []
        params = {}
        for e in exprs:
            cn = e.get_class().get_name()
            hist[cn] = hist.get(cn, 0) + 1
            if "LandscapeLayerBlend" in cn:
                try:
                    for l in e.get_editor_property("layers"):
                        layers.append({"name": _jsonable(l.get_editor_property("layer_name")),
                                       "blend_type": _jsonable(l.get_editor_property("blend_type")),
                                       "preview_weight": _jsonable(l.get_editor_property("preview_weight"))})
                except Exception:  # noqa
                    pass
            if cn.endswith("ScalarParameter") or cn.endswith("VectorParameter"):
                try:
                    params[str(e.get_editor_property("parameter_name"))] = _jsonable(
                        e.get_editor_property("default_value"))
                except Exception:  # noqa
                    pass
        rec["expression_histogram"] = hist
        rec["layer_blend_layers"] = layers
        rec["parameters"] = params
        if isinstance(mat, _u.MaterialInstance):
            rec["instance_scalars"] = [_jsonable(x) for x in mat.get_editor_property("scalar_parameter_values")]
            rec["instance_vectors"] = [_jsonable(x) for x in mat.get_editor_property("vector_parameter_values")]
    except Exception as e:  # noqa
        rec["_error"] = str(e)[:200]
    return rec


def sec_landscape_materials():
    out = {}
    for w in _worlds():
        try:
            eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
            for actor in eas.get_all_level_actors():
                if actor.get_class().get_name() in ("Landscape", "LandscapeStreamingProxy"):
                    mat = _safe(actor.get_editor_property, "landscape_material")
                    if isinstance(mat, _u.Object) and mat.get_path_name() not in out:
                        out[mat.get_path_name()] = _material_census(mat)
                    if len(out) > 8:
                        break
        except Exception as e:  # noqa
            out["_error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------- lighting --
def sec_lighting():
    out = {}
    for w in _worlds():
        rec = {"directional": [], "skylight": [], "sky_atmosphere": [], "height_fog": [],
               "volumetric_cloud": [], "post_process": []}
        try:
            eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
            for a in eas.get_all_level_actors():
                cn = a.get_class().get_name()
                if cn == "DirectionalLight":
                    c = a.get_component_by_class(_u.DirectionalLightComponent)
                    rec["directional"].append({"label": a.get_actor_label(), "rotation": str(a.get_actor_rotation()),
                                               **_props(c, ["intensity", "light_color", "temperature", "use_temperature",
                                                            "light_source_angle", "atmosphere_sun_light", "cast_shadows",
                                                            "dynamic_shadow_distance_movable_light", "cascade_distribution_exponent",
                                                            # The reflected names carry the `enable_` prefix: the engine
                                                            # declares bEnableLightShaftOcclusion (DirectionalLightComponent.h:32)
                                                            # and bEnableLightShaftBloom (LightComponent.h:249). Without it
                                                            # both came back "_error: Failed to find property" on every
                                                            # directional light in both sample projects.
                                                            "enable_light_shaft_occlusion", "enable_light_shaft_bloom", "volumetric_scattering_intensity",
                                                            "forward_shading_priority", "lighting_channels"])})
                elif cn == "SkyLight":
                    c = a.get_component_by_class(_u.SkyLightComponent)
                    rec["skylight"].append({"label": a.get_actor_label(),
                                            **_props(c, ["intensity", "light_color", "real_time_capture", "source_type",
                                                         "lower_hemisphere_color", "lower_hemisphere_is_black",
                                                         "cast_shadows", "volumetric_scattering_intensity", "cubemap_resolution"])})
                elif cn == "SkyAtmosphere":
                    c = a.get_component_by_class(_u.SkyAtmosphereComponent)
                    rec["sky_atmosphere"].append({"label": a.get_actor_label(), **_all_props(c)})
                elif cn == "ExponentialHeightFog":
                    c = a.get_component_by_class(_u.ExponentialHeightFogComponent)
                    rec["height_fog"].append({"label": a.get_actor_label(), **_all_props(c)})
                elif cn == "VolumetricCloud":
                    c = a.get_component_by_class(_u.VolumetricCloudComponent)
                    rec["volumetric_cloud"].append({"label": a.get_actor_label(), **_all_props(c)})
                elif cn == "PostProcessVolume":
                    s = a.get_editor_property("settings")
                    over = {}
                    for n in dir(s):
                        if n.startswith("override_"):
                            try:
                                if s.get_editor_property(n):
                                    key = n[len("override_"):]
                                    over[key] = _jsonable(s.get_editor_property(key))
                            except Exception:  # noqa
                                pass
                    rec["post_process"].append({"label": a.get_actor_label(),
                                                "unbound": _jsonable(_safe(a.get_editor_property, "unbound")),
                                                "priority": _jsonable(_safe(a.get_editor_property, "priority")),
                                                "overrides": over})
        except Exception as e:  # noqa
            rec["_error"] = str(e)[:200]
        out[w.get_path_name()] = rec
    return out


# ------------------------------------------------------------------ water ---
def sec_water():
    out = []
    for w in _worlds():
        try:
            eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
            for a in eas.get_all_level_actors():
                cn = a.get_class().get_name()
                if cn.startswith("WaterBody") or "Water" in cn:
                    rec = {"class": cn, "label": a.get_actor_label()}
                    try:
                        comp = a.get_component_by_class(_u.WaterBodyComponent)
                        rec.update(_props(comp, ["water_material", "water_hlod_material", "water_static_mesh_material",
                                                 "water_info_material", "wave_attenuation_water_depth", "max_wave_height_offset"]))
                        mat = comp.get_editor_property("water_material")
                        if mat:
                            base = mat
                            while isinstance(base, _u.MaterialInstance):
                                base = base.get_editor_property("parent")
                            rec["shading_model"] = _jsonable(_safe(base.get_editor_property, "shading_model"))
                    except Exception as e:  # noqa
                        rec["_error"] = str(e)[:120]
                    out.append(rec)
        except Exception as e:  # noqa
            out.append({"_error": str(e)[:200]})
    return out


# ------------------------------------------------------------------- main ---
try:
    maps = [m for m in _MAPS.split(",") if m and not m.startswith("__")]
    _out["maps_requested"] = maps
    # per-world sections are taken on the currently loaded world; Claude Code
    # loads each map (EditorLoadingAndSavingUtils.load_map) and re-runs with
    # the same __OUT__ suffixed by map name — never save.
    _out["sections"]["project"] = _safe(sec_project)
    _out["sections"]["hlod_layers"] = _safe(sec_hlod_layers)
    _out["sections"]["world_partition"] = _safe(sec_world_partition)
    _out["sections"]["foliage_types"] = _safe(sec_foliage_types)
    _out["sections"]["impostors"] = _safe(sec_impostors)
    _out["sections"]["pcg_graphs"] = _safe(sec_pcg_graphs)
    _out["sections"]["landscape_materials"] = _safe(sec_landscape_materials)
    _out["sections"]["lighting"] = _safe(sec_lighting)
    _out["sections"]["water"] = _safe(sec_water)
    _out["current_world"] = [w.get_path_name() for w in _worlds()]
    # WHICH PACKAGE EACH CLASS LOOKUP ACTUALLY HIT, and how many it found
    # there. A zero in a section is only trustworthy if the lookup reached a
    # package where the class EXISTS -- `pcg_graphs: 0` on the PCG reference
    # project came from asking /Script/Engine for a /Script/PCG class. This
    # makes that visible in the artefact instead of requiring a re-run to
    # discover it.
    _out["asset_lookup_trace"] = _ASSET_LOOKUP_TRACE
    _os.makedirs(_os.path.dirname(_OUT), exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as f:
        _json.dump(_out, f, indent=1, default=str)
    _out["ok"] = True
    _out["written"] = _OUT
    _out["bytes"] = _os.path.getsize(_OUT)
except Exception as e:  # noqa
    import traceback as _tb
    _out["errors"].append(str(e) + " | " + _tb.format_exc()[:800])
print("__LL__" + _json.dumps({k: v for k, v in _out.items() if k != "sections"}, default=str))
