"""Apply the census settings to the LANDSCAPE HLOD layer ONLY.

⛔ ONLY THAT LAYER, BY RULING. The HLOD build is incremental on source
changes: touching FoliageApprox or Merged flags every one of their cells
and they would rebuild wholesale. They rebuild once, after Brief 5, when
the forest is final.

⭐ UNITS READ FROM THE ENGINE SOURCE BEFORE WRITING, as ruled.
`MeshApproximationSettings.h`:

    /** Approximation Accuracy in Meters, will determine (eg) voxel resolution */
    meta = (DisplayName = "Approximation Accuracy (meters)", ClampMin="0.001")

So a 0.25 m tolerance is 0.25, NOT 25.0.

⛔ AND IT DOES NOT APPLY TO THIS LAYER. Alpine8K_HLODLayer_Landscape is
MESH_MERGE, whose settings struct is `MeshMergingSettings` -- 18
properties, none of them a geometric tolerance, a simplification method
or a triangle budget. Those live on MeshApproximationSettings /
MeshProxySettings, which a MERGE builder does not carry. A merge builder
does not simplify; it merges. So of the four census values, two are
applicable here and two are NOT EXPOSED ON THIS LAYER TYPE, and this
payload reports that rather than writing them somewhere they would look
applied:

    merge_materials                       -> True          APPLIED
    material_settings.texture_sizing_type -> AutomaticFrom
                                             MeshDrawDistance  APPLIED
    geometric tolerance 0.25 m            NOT ON MESH_MERGE
    2 tris per m^2                        NOT ON MESH_MERGE

⛔ NESTED STRUCTS ARE COPIES AND MUST BE WRITTEN BACK. Measured on this
project today: `grass_varieties` handed out copies, a per-element write
read back True on the copy and False on the asset, and re-assigning the
SAME Array object was a silent no-op. The same shape applies here --
`mesh_merge_settings` and its `material_settings` are structs. Each is
read, modified, and written back UP the chain, and every level is
re-read from the saved asset at the end.
"""
import json as _json
import traceback as _tb

import unreal as _u

LAYER = "/Game/Alpine8K_HLODLayer_Landscape"
_out = {"ok": False, "layer": LAYER}
try:
    _eal = _u.EditorAssetLibrary
    _L = _eal.load_asset(LAYER)
    if _L is None:
        raise RuntimeError("could not load " + LAYER)
    _out["layer_type"] = str(_L.get_editor_property("layer_type"))
    _bs = _L.get_editor_property("hlod_builder_settings")
    _out["builder_settings_class"] = type(_bs).__name__
    if "MeshMerge" not in type(_bs).__name__:
        raise RuntimeError(
            "expected a MeshMerge builder on the Landscape layer, found %s "
            "-- refusing to write settings whose meaning depends on the "
            "builder type" % type(_bs).__name__)

    _mm = _bs.get_editor_property("mesh_merge_settings")
    _ms = _mm.get_editor_property("material_settings")
    _out["before"] = {
        "merge_materials": bool(_mm.get_editor_property("merge_materials")),
        "texture_sizing_type": str(
            _ms.get_editor_property("texture_sizing_type")),
        "lod_selection_type": str(
            _mm.get_editor_property("lod_selection_type")),
        "use_texture_binning": bool(
            _mm.get_editor_property("use_texture_binning")),
    }

    _want_sizing = _u.TextureSizingType.TEXTURE_SIZING_TYPE_AUTOMATIC_FROM_MESH_DRAW_DISTANCE
    _ms.set_editor_property("texture_sizing_type", _want_sizing)
    _mm.set_editor_property("material_settings", _ms)      # write back up
    _mm.set_editor_property("merge_materials", True)
    _bs.set_editor_property("mesh_merge_settings", _mm)    # and again

    # save_asset returns whether the package persisted; a discarded return is
    # rule 12's "value not read back is prose" and it is the ONLY on-disk
    # evidence (the re-read below returns the resident object, not a disk load).
    _saved = bool(_eal.save_asset(LAYER, only_if_is_dirty=False))
    _out["saved"] = _saved
    if not _saved:
        raise RuntimeError("save_asset returned False for " + LAYER)

    # ---- RE-READ the resident asset (load_asset returns the in-memory object,
    #      so this re-fetches FRESH STRUCT COPIES -- which is what verifies the
    #      nested write-back-up-the-chain -- rather than a disk round-trip;
    #      _saved above is the persistence evidence) ----
    _re = _eal.load_asset(LAYER)
    if _re is None:
        raise RuntimeError("could not re-load " + LAYER)
    _rbs = _re.get_editor_property("hlod_builder_settings")
    _rmm = _rbs.get_editor_property("mesh_merge_settings")
    _rms = _rmm.get_editor_property("material_settings")
    _out["after"] = {
        "merge_materials": bool(_rmm.get_editor_property("merge_materials")),
        "texture_sizing_type": str(
            _rms.get_editor_property("texture_sizing_type")),
        "lod_selection_type": str(
            _rmm.get_editor_property("lod_selection_type")),
        "use_texture_binning": bool(
            _rmm.get_editor_property("use_texture_binning")),
    }
    _out["not_applicable_on_this_layer"] = {
        "geometric_tolerance_m": 0.25,
        "tris_per_m2": 2,
        "_why": ("MeshMergingSettings carries no geometric tolerance, "
                 "simplification method or triangle budget -- a MERGE "
                 "builder does not simplify. Those properties live on "
                 "MeshApproximationSettings / MeshProxySettings. Applying "
                 "them would require changing the Landscape layer's TYPE, "
                 "which the ruling did not ask for."),
    }
    if _out["after"]["merge_materials"] is not True:
        raise RuntimeError("merge_materials read back %r after the write"
                           % _out["after"]["merge_materials"])
    if "DRAW_DISTANCE" not in _out["after"]["texture_sizing_type"].upper():
        raise RuntimeError(
            "texture_sizing_type read back %r, not the draw-distance "
            "member" % _out["after"]["texture_sizing_type"])
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
