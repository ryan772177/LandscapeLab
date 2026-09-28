"""brief5_r4_imposter.py -- Brief 5 REPAIR R4. READ-ONLY imposter override diff.

The desk premise: Alpine8K's SpruceSub foliage uses an override imposter MI
(MI_half_01_imposter_nowind) that the vendor Showroom does not, and that override
may be missing parameters the octahedral frame lookup needs -> the tiling. C2's
earlier read (imposter_defect_read.json) reported that MI "exists:false", but it
looked in the VENDOR folder; the recipe's override_materials point at a DIFFERENT
path, /Game/Materials/PN_NoWind/MI_half_01_imposter_nowind. R4 checks the recipe
path and does the real diff.

Reads (no spawn, no save, no material/level edit):
  1. recipe SpruceSub override_materials (provenance).
  2. the OVERRIDE imposter MI (recipe path) -- base material, every scalar /
     vector / texture / static-switch parameter.
  3. the VENDOR imposter MI (half_01_imposter, what Showroom uses on the mesh
     default slot) -- same.
  4. the diff: base-material match, per-parameter differences, and parameters the
     vendor carries that the override does NOT (the frame-lookup-starves
     hypothesis).
  5. the PLACED SpruceSub HISM components in Alpine8K -- their override_materials,
     to confirm which material actually renders the card, and whether a
     per-instance / custom-primitive-data input is present.
  6. the Instancing HLOD proxy for a spruce cell -- does it carry the override or
     the mesh default material (may be unreachable in-editor; reported honestly).
"""
import json as _json
import os as _os
import traceback as _tb
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project (rule 7)"
_root = _os.path.dirname(_os.path.normpath(_u.Paths.project_dir().rstrip("/\\")))

MESH = "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01"
VENDOR_IMPOSTER = ("/Game/PN_interactiveSpruceForest/Materials/MaterialInstances/"
                   "imposter/high/half_01_imposter")

out = {"ok": False, "_what": "Brief 5 R4 imposter override diff (read-only)."}
try:
    eal = _u.EditorAssetLibrary
    mel = _u.MaterialEditingLibrary

    # (1) recipe provenance
    recipe = _json.load(open(_os.path.join(_root, "recipes", "alpine_8k.json"),
                             encoding="utf-8-sig"))
    sp = next((s for s in recipe["foliage"]["species"]
               if s.get("name") == "SpruceSub"), {})
    ov = sp.get("override_materials") or []
    out["recipe_override_materials"] = ov
    # the imposter slot is the last override (LOD4 card slot half_01_imposter)
    override_imposter = next((p for p in ov if "imposter" in p.lower()), None)
    out["override_imposter_path"] = override_imposter

    def mi_full(path):
        # M1 (audit): a getter failure must NOT read as "override lacks this
        # param". Every enumerated name is written -- with an "err: ..." SENTINEL
        # when its value getter fails -- so absence from a map means true absence,
        # not a swallowed exception. Per-kind counts (names enumerated vs values
        # read) travel with the record so the diff can refuse an unreliable kind
        # (rule 13: a sample count beside every verdict).
        rec = {"path": path, "exists": bool(path and eal.does_asset_exist(path))}
        if not rec["exists"]:
            return rec
        mi = eal.load_asset(path)
        rec["class"] = mi.get_class().get_name()
        try:
            base = mi.get_base_material()
        except Exception:
            base = None
        rec["base_material"] = base.get_path_name().split(".")[0] if base else None
        rec["scalars"], rec["vectors"] = {}, {}
        rec["textures"], rec["switches"] = {}, {}
        rec["counts"] = {}
        rec["enumerate_errors"] = {}
        ref = base or mi

        def harvest(kind, name_getter, value_fn):
            names, read = 0, 0
            try:
                pns = name_getter(ref)
            except Exception as e:
                rec["enumerate_errors"][kind] = "%s: %s" % (type(e).__name__, e)
                rec["counts"][kind] = {"names": None, "read": 0}
                return
            for pn in (pns or []):
                names += 1
                try:
                    rec[kind][str(pn)] = value_fn(pn)
                    read += 1
                except Exception as e:
                    rec[kind][str(pn)] = "err: %s" % type(e).__name__
            rec["counts"][kind] = {"names": names, "read": read}

        harvest("scalars", mel.get_scalar_parameter_names,
                lambda pn: round(float(
                    mel.get_material_instance_scalar_parameter_value(mi, pn)), 5))

        def _vec(pn):
            v = mel.get_material_instance_vector_parameter_value(mi, pn)
            return [round(v.r, 4), round(v.g, 4), round(v.b, 4), round(v.a, 4)]
        harvest("vectors", mel.get_vector_parameter_names, _vec)

        def _tex(pn):
            t = mel.get_material_instance_texture_parameter_value(mi, pn)
            return t.get_path_name().split(".")[0] if t else None
        harvest("textures", mel.get_texture_parameter_names, _tex)

        harvest("switches", mel.get_static_switch_parameter_names,
                lambda pn: bool(
                    mel.get_material_instance_static_switch_parameter_value(mi, pn)))
        return rec

    vendor = mi_full(VENDOR_IMPOSTER)
    override = mi_full(override_imposter) if override_imposter else {"exists": False}
    out["vendor_imposter"] = vendor
    out["override_imposter"] = override

    # (4) the diff
    def diff_maps(a, b, kind):
        a, b = a or {}, b or {}
        keys = set(a) | set(b)
        d = {}
        for k in sorted(keys):
            if k not in a:
                d[k] = {"vendor": None, "override": b[k], "note": "override-only"}
            elif k not in b:
                d[k] = {"vendor": a[k], "override": None,
                        "note": "VENDOR-ONLY (override lacks this %s)" % kind}
            elif a[k] != b[k]:
                d[k] = {"vendor": a[k], "override": b[k]}
        return d

    def kind_reliable(kind):
        # both sides must have enumerated that kind without error, and neither may
        # report names>0 with 0 values read (an all-failed getter would masquerade
        # as "override lacks every param"). M1 / rule 13.
        for side in (vendor, override):
            if kind in (side.get("enumerate_errors") or {}):
                return False, "enumerate error on %s side" % (
                    "vendor" if side is vendor else "override")
            c = (side.get("counts") or {}).get(kind)
            if c is None:
                return False, "no counts for %s side" % (
                    "vendor" if side is vendor else "override")
            if c.get("names") and not c.get("read"):
                return False, ("%s side read 0 of %s %s values"
                               % ("vendor" if side is vendor else "override",
                                  c.get("names"), kind))
        return True, "ok"

    if vendor.get("exists") and override.get("exists"):
        out["diff"] = {
            "base_material_match": vendor.get("base_material") == override.get("base_material"),
            "vendor_base": vendor.get("base_material"),
            "override_base": override.get("base_material"),
            "vendor_counts": vendor.get("counts"),
            "override_counts": override.get("counts"),
            "reliability": {},
        }
        vonly = []
        for kind, label in (("scalars", "scalar"), ("vectors", "vector"),
                            ("textures", "texture"), ("switches", "switch")):
            ok, why = kind_reliable(kind)
            out["diff"]["reliability"][kind] = {"reliable": ok, "why": why}
            if not ok:
                out["diff"][kind] = {"UNRELIABLE": why}
                continue
            out["diff"][kind] = diff_maps(vendor.get(kind), override.get(kind), label)
            vonly += [k for k, v in out["diff"][kind].items()
                      if "VENDOR-ONLY" in v.get("note", "")]
        out["diff"]["vendor_only_params"] = vonly
        # the hypothesis flag fires ONLY from reliable kinds
        out["diff"]["override_missing_vendor_params"] = bool(vonly)
        out["diff"]["all_kinds_reliable"] = all(
            r["reliable"] for r in out["diff"]["reliability"].values())
    else:
        out["diff"] = {"_note": "one side missing; vendor_exists=%s override_exists=%s"
                       % (vendor.get("exists"), override.get("exists"))}

    # (5) placed SpruceSub HISM override_materials in Alpine8K
    ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    w = ues.get_editor_world()
    out["level"] = w.get_name() if w else None
    placed = {"components_found": 0, "override_material_slots": None, "sample": []}
    try:
        for a in eas.get_all_level_actors():
            for comp in a.get_components_by_class(_u.InstancedStaticMeshComponent):
                sm = comp.static_mesh
                if not sm or sm.get_path_name().split(".")[0] != MESH:
                    continue
                placed["components_found"] += 1
                if placed["override_material_slots"] is None:
                    oms = comp.get_editor_property("override_materials")
                    slots = []
                    for i, mtl in enumerate(oms or []):
                        slots.append({"slot": i,
                                      "material": mtl.get_path_name().split(".")[0] if mtl else None})
                    placed["override_material_slots"] = slots
                    # per-instance custom data width (frame-lookup input candidate)
                    try:
                        placed["num_custom_data_floats"] = int(
                            comp.get_editor_property("num_custom_data_floats"))
                    except Exception as e:
                        placed["num_custom_data_floats"] = "err: %s" % e
                if len(placed["sample"]) < 2:
                    placed["sample"].append(a.get_actor_label())
    except Exception as e:
        placed["error"] = str(e)
    out["placed_spruce_hism"] = placed

    # (6) HLOD Instancing proxy material for a spruce cell (best-effort)
    hlod = {"_note": "Instancing-layer HLOD ISM components are often not registered "
            "in the editor session (find_instanced_cell_by_grid.py); reported "
            "honestly if unreachable."}
    try:
        n_hlod = 0
        found_mtl = None
        for a in eas.get_all_level_actors():
            cn = a.get_class().get_name()
            if "HLOD" not in cn:
                continue
            for comp in a.get_components_by_class(_u.InstancedStaticMeshComponent):
                sm = comp.static_mesh
                if sm and "spruce" in sm.get_path_name().lower():
                    n_hlod += 1
                    oms = comp.get_editor_property("override_materials")
                    if oms:
                        found_mtl = [m.get_path_name().split(".")[0] if m else None
                                     for m in oms]
                    break
        hlod["spruce_hlod_ism_components"] = n_hlod
        hlod["override_materials"] = found_mtl
        hlod["reachable"] = n_hlod > 0
    except Exception as e:
        hlod["error"] = str(e)
    out["hlod_proxy"] = hlod

    out["ok"] = True
except Exception as e:
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = _tb.format_exc()[-1500:]

try:
    dest = _os.path.join(_root, "research", "brief5", "input", "r4_imposter_read.json")
    _json.dump(out, open(dest, "w", encoding="utf-8"), indent=1, default=str)
    out["written_to"] = dest
except Exception as e:
    out["write_error"] = str(e)
print("__LL__" + _json.dumps({"ok": out.get("ok"), "error": out.get("error"),
                              "override_exists": out.get("override_imposter", {}).get("exists"),
                              "base_match": out.get("diff", {}).get("base_material_match"),
                              "all_kinds_reliable": out.get("diff", {}).get("all_kinds_reliable"),
                              "vendor_counts": out.get("diff", {}).get("vendor_counts"),
                              "override_counts": out.get("diff", {}).get("override_counts"),
                              "vendor_only": out.get("diff", {}).get("vendor_only_params"),
                              "placed_slots": out.get("placed_spruce_hism", {}).get("override_material_slots"),
                              "written": out.get("written_to")}, default=str))
