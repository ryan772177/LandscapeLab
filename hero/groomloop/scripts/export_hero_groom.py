"""export_hero_groom.py -- export an edited HERO groom through the MetaHuman
Groom add-on's own exporter.

    blender --background <edited.blend> --python export_hero_groom.py -- <out.abc>

WHY NOT alembic_export, WHICH THE REST OF THIS LOOP USES. The pack-groom loop
exports with `bpy.ops.wm.alembic_export`, and that path is why every candidate
it produced landed on the hero's JAW: it writes positions and radius and NOTHING
ELSE. The vendor MetaHuman grooms that seat correctly all carry `groom_root_uv`,
and a binding with no root UVs can only project each root onto the nearest
triangle of the target -- from a groom authored on another head, the nearest
triangle is the jaw.

`bpy.ops.groom.buttonexport` is the add-on operator `author_hero_hair.py`
already ships through, and it writes the UVs and the GroomProperty mapping. The
arguments are copied from that call rather than chosen, because it is the proven
one: groom_scale 1.0 (this file is already in centimetres -- do NOT apply the
x100 the pack-groom exports need), width scaling on, radius-to-diameter on.

IT ASSERTS WHAT IT SHIPPED. The whole point of this export is the root UVs, so
their presence is checked and reported rather than assumed.
"""

import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_curves import pick_curves_object


def main():
    a = sys.argv
    tail = a[a.index("--") + 1:] if "--" in a else []
    out_abc = tail[0]
    rep = {"ok": False, "out": out_abc}

    ob = pick_curves_object(bpy)
    d = ob.data
    rep["object"] = ob.name
    rep["curves"] = len(d.curves)
    rep["points"] = len(d.points)
    rep["attributes"] = [x.name for x in d.attributes]

    # THE REASON THIS EXPORTER EXISTS. Refuse before writing rather than
    # discovering it after a bind puts the hair on his jaw again.
    #
    # ==== 2026-08-22: THIS CHECK WAS THE BUG, AND IT PASSED FOR THREE DAYS ====
    #
    # The old form asked `"groom_root_uv" in rep["attributes"]`. That is the
    # attribute I CREATE in land_difflocks.py, checked by the name I chose. The
    # exporter does not read attributes by that name. It reads the name held in
    # a PER-OBJECT POINTER and skips the whole param, silently, when the pointer
    # does not resolve:
    #
    #   AlembicGroomExporter.py:282  getAttribute(..., groomProperty
    #                                .att_groom_root_uv, ..., ["FLOAT2",
    #                                "FLOAT_VECTOR"])
    #   ExporterOperators.py:42      `if att_name != "":`  -- an EMPTY pointer
    #                                short-circuits and att_valid stays False
    #   AlembicGroomExporter.py:349  `if att_surface_uv_valid:` -- groom_root_uv
    #                                is written ONLY here. No warning otherwise.
    #   GroomPanel.py:211            the addon-pref default is
    #                                "surface_uv_coordinate"
    #
    # MEASURED: cr_g75 (DRAWS) carries att_groom_root_uv = 'groom_root_uv',
    # because it was built through the add-on's own operator, which sets the
    # pointer (GroomOperators.py:45). Both DiffLocks objects, built by hand with
    # `bpy.data.hair_curves.new()`, carry the EMPTY STRING. So their ABCs went
    # out with arb params ['groom_group_id', 'groom_group_name'] and no
    # groom_root_uv at all -- while this gate reported PASS on every run.
    #
    # NON-NEGOTIABLE 5, EXACTLY: a check that consumes the value it is verifying
    # verifies nothing. The gate confirmed my own naming convention. The fix is
    # to POINT the exporter at the attribute and then assert what the EXPORTER
    # would resolve, not what I named.
    #
    # (The type theory is dead and is recorded so nobody revives it: line 282
    # accepts BOTH FLOAT2 and FLOAT_VECTOR, so FLOAT2-vs-FLOAT_VECTOR -- the
    # visible difference between the two blends -- cannot be the discriminator.)
    if "groom_root_uv" not in rep["attributes"]:
        rep["error"] = ("REFUSE: no 'groom_root_uv' on this groom. Exporting "
                        "it would reproduce the jaw-seating failure that the "
                        "whole hero-authored route exists to avoid.")
        print("__EXPORT__" + json.dumps(rep))
        return

    gp = getattr(ob, "GroomProperty", None)
    if gp is None:
        rep["error"] = ("REFUSE: object has no GroomProperty, so the add-on "
                        "cannot be pointed at any attribute.")
        print("__EXPORT__" + json.dumps(rep))
        return
    rep["att_groom_root_uv_before"] = gp.att_groom_root_uv
    gp.att_groom_root_uv = "groom_root_uv"

    # ---- AND THE WIDTH POINTER, WHICH IS THE SAME BUG ONE FIELD OVER.
    #
    # A full audit of all TWELVE exporter pointers (groom_pointer_audit.py)
    # found a second silent skip. The clay object, built through the add-on's
    # operator, carries `att_groom_width = 'radius'` and the exporter WRITES.
    # Every hand-built object carries "" and the exporter SKIPS.
    #
    # `groom_width` is not an arb geom param -- it feeds the ICurves schema's
    # own `widths`, which is why the schema diff showed `widths` PRESENT on both
    # files and flagged only its LENGTH. `getAttributeArray` returns early on an
    # invalid attribute (ExporterOperators.py:51-52), so `out_widths` keeps the
    # zeros it was allocated with and the file ships full-length zeros.
    #
    # MEASURED in the written files:
    #     cr_g75_ue.abc          min 0.012  mean 0.0235  max 0.035  12 distinct
    #     difflocks_k12_ue.abc   min 0.0    mean 0.0     max 0.0     1 distinct
    #
    # A groom with zero width draws zero pixels. That is the first line of
    # `validate_groom_export.py`'s docstring, and I read "widths: present" off
    # the schema diff and moved on -- the same presence-over-values mistake the
    # root_uv fix was supposed to have taught.
    rep["att_groom_width_before"] = gp.att_groom_width
    _w = d.attributes.get("radius")
    if _w is None or _w.data_type != "FLOAT":
        rep["error"] = ("REFUSE: no FLOAT 'radius' attribute to drive "
                        "groom_width; the export would ship zero widths and "
                        "the groom would draw nothing.")
        print("__EXPORT__" + json.dumps(rep))
        return
    gp.att_groom_width = "radius"
    rep["att_groom_width_after"] = gp.att_groom_width

    # ---- AND NOW THE OTHER TEN, FROM ONE DECLARATION.
    #
    # Two hand-written cases is how this bug got found twice instead of once.
    # All twelve exporter attributes resolve through their own pointer with the
    # same silent skip, so the fix is a LOOP OVER A DECLARATION, not a line per
    # field (non-negotiable 24: two lists that must agree are one list, badly
    # stored).
    #
    # `ue_consumed` is from `EHairAttribute` (HairAttributes.h:50-61): RootUV,
    # ClumpID, StrandID, PrecomputedGuideWeights, Color, Roughness, AO, Width.
    # A pointer UE cannot consume is still set when a source exists, because the
    # cost is zero and the alternative is deciding on its behalf.
    #
    # A pointer with NO source attribute is reported as NO SOURCE -- deliberately
    # absent, not silently skipped. That distinction is the whole lesson.
    POINTERS = [
        # (pointer,                 candidate source names, accepted types,
        #  ue_consumed)
        ("att_groom_color",  ("groom_color", "color"),
         ("FLOAT_COLOR", "FLOAT_VECTOR"), True),
        ("att_groom_roughness", ("groom_roughness", "roughness"),
         ("FLOAT",), True),
        ("att_groom_ao", ("groom_ao", "ao"), ("FLOAT",), True),
        ("att_groom_id", ("groom_id", "strand_id"), ("INT", "INT8"), True),
        ("att_groom_guide", ("groom_guide", "guide"), ("INT", "INT8"), True),
        ("att_groom_closest_guides", ("groom_closest_guides",),
         ("BYTE_COLOR", "FLOAT_COLOR"), True),
        ("att_groom_guide_weights", ("groom_guide_weights",),
         ("FLOAT_VECTOR",), True),
        ("att_groom_knots", ("groom_knots",), ("FLOAT",), False),
        ("att_groom_orders", ("groom_orders",), ("INT8",), False),
        ("att_groom_cards_name", ("groom_cards_name",), ("STRING",), False),
    ]
    ptr_report = {}
    for pname, candidates, types, ue_used in POINTERS:
        hit = None
        for cand in candidates:
            at = d.attributes.get(cand)
            if at is not None and at.data_type in types:
                hit = cand
                break
        if hit:
            setattr(gp, pname, hit)
            ptr_report[pname] = {"source": hit, "state": "SET",
                                 "ue_consumed": ue_used}
        else:
            ptr_report[pname] = {
                "source": None,
                "state": "NO SOURCE ATTRIBUTE -- deliberately absent",
                "ue_consumed": ue_used,
                "looked_for": list(candidates)}
    rep["pointer_table"] = ptr_report
    rep["pointers_set"] = sorted(k for k, v in ptr_report.items()
                                 if v["state"] == "SET")
    rep["ue_consumed_absent"] = sorted(
        k for k, v in ptr_report.items()
        if v["ue_consumed"] and v["state"] != "SET")

    # ---- AND THE WRITE MUST REACH THE EVALUATED COPY, WHICH IS THE ONLY ONE
    # THE EXPORTER EVER LOOKS AT.
    #
    #   ExporterOperators.py:26-28   GetCurvesObjects returns
    #                                obj.evaluated_get(depsgraph)
    #   AlembicGroomExporter.py:231  groomProperty = obj.GroomProperty
    #                                -- read off THAT evaluated copy
    #
    # Setting the pointer on the original left the evaluated copy at "" and the
    # export wrote no groom_root_uv while reporting FINISHED. `update_tag()` is
    # sufficient, measured: evaluated pointer "" -> "groom_root_uv".
    #
    # This is the SECOND time in one hour that a gate here read a different
    # representation than the consumer -- first the wrong NAME, then the right
    # name on the wrong COPY. So the assertion below is taken from the evaluated
    # object, deliberately, and not from `d`.
    # ---- FLOAT2 CANNOT EXPORT THROUGH THIS ADD-ON. Convert to FLOAT_VECTOR.
    #
    # Once the pointer resolved, the export stopped silently skipping and
    # CRASHED instead, inside the add-on:
    #
    #   ExporterOperators.py:65-75, case "FLOAT2":
    #       data    = np.empty(2 * len(att_prop.data), np.float32)  # (201886,)
    #       memView = imathnumpy.arrayToNumpy(out_array)            # (100943,2)
    #       np.copyto(memView, data)
    #   ValueError: could not broadcast input array from shape (201886,)
    #               into shape (100943,2)
    #
    # The flat buffer is never reshaped. The FLOAT_VECTOR branch below it does
    # the same job correctly, and `GroomText.py:47` records FLOAT_VECTOR as the
    # supported route in the add-on's own words. The groom that DRAWS carries
    # groom_root_uv as FLOAT_VECTOR; both DiffLocks blends carry FLOAT2, which
    # is the semantically correct type for a UV and is what a careful author
    # picks -- and it is unexportable.
    #
    # CORRECTION TO MY OWN NOTE ABOVE: I wrote "the type theory is dead" on the
    # strength of line 282 accepting both types. It accepts both at the VALIDITY
    # check and only one of them survives the ARRAY COPY. Half-right is wrong.
    #
    # Converted IN MEMORY only. Nothing is written back to the source blend.
    _raw_uv = d.attributes.get("groom_root_uv")
    rep["root_uv_source_type"] = getattr(_raw_uv, "data_type", None)
    if _raw_uv is not None and _raw_uv.data_type == "FLOAT2":
        import numpy as _np
        n_c = len(d.curves)
        buf = _np.zeros(n_c * 2, dtype=_np.float32)
        d.attributes["groom_root_uv"].data.foreach_get("vector", buf)
        uv2 = buf.reshape(n_c, 2)
        d.attributes.remove(d.attributes["groom_root_uv"])
        a3 = d.attributes.new("groom_root_uv", "FLOAT_VECTOR", "CURVE")
        uv3 = _np.zeros((n_c, 3), dtype=_np.float32)
        uv3[:, :2] = uv2
        a3.data.foreach_set("vector", uv3.ravel())
        rep["root_uv_converted"] = "FLOAT2 -> FLOAT_VECTOR (w=0)"
        # read back through a different array than the one written
        chk = _np.zeros(n_c * 3, dtype=_np.float32)
        d.attributes["groom_root_uv"].data.foreach_get("vector", chk)
        rep["root_uv_conversion_max_err"] = float(
            _np.abs(chk.reshape(n_c, 3)[:, :2] - uv2).max())
        if rep["root_uv_conversion_max_err"] > 1e-6:
            rep["error"] = ("REFUSE: root UV conversion lost data, max err %g"
                            % rep["root_uv_conversion_max_err"])
            print("__EXPORT__" + json.dumps(rep))
            return

    ob.update_tag()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = bpy.data.objects[ob.name].evaluated_get(dg)
    nm = ev.GroomProperty.att_groom_root_uv
    ev_attrs = ev.data.attributes
    resolved = ev_attrs.get(nm) if nm else None
    rep["att_groom_root_uv_after"] = gp.att_groom_root_uv
    rep["att_groom_root_uv_evaluated"] = nm
    rep["root_uv_resolves_on_evaluated"] = resolved is not None
    rep["root_uv_data_type"] = getattr(resolved, "data_type", None)
    rep["root_uv_domain"] = getattr(resolved, "domain", None)
    if resolved is None or resolved.data_type not in ("FLOAT2", "FLOAT_VECTOR"):
        rep["error"] = ("REFUSE: on the EVALUATED object att_groom_root_uv=%r "
                        "does not resolve to a FLOAT2/FLOAT_VECTOR attribute, "
                        "so the exporter would skip groom_root_uv silently "
                        "(AlembicGroomExporter.py:349)." % nm)
        print("__EXPORT__" + json.dumps(rep))
        return

    # IDENTITY TO 1e-3, AND REPORT THE DEVIATION.
    # At 1e-9 this refused a matrix that prints as pure identity: the hair is
    # PARENTED to the face mesh, and the composed parent-inverse leaves signed
    # zeros and sub-1e-8 terms. A refusal that cannot say HOW FAR from identity
    # it was is a refusal nobody can act on -- so the number goes in the report
    # either way. MEASURED: this file deviates by 1.48e-05 -- 0.15 microns on a
    # 9.2 cm head, from the parent-inverse composition rather than any transform
    # anybody applied. The bar is 1e-3 cm (10 microns): no styling transform hides
    # under it, and note author_hero_hair.py exports this same object through this
    # same operator with no such assertion at all, so a tighter bar than the
    # pipeline's own proven path was refusing a file the pipeline itself ships.
    m = ob.matrix_world
    dev = max(abs(m[r][c] - (1.0 if r == c else 0.0))
              for r in range(4) for c in range(4))
    rep["transform_deviation_from_identity"] = float(dev)
    if dev > 1e-3:
        rep["error"] = ("object transform deviates from identity by %g; "
                        "refusing to export" % dev)
        print("__EXPORT__" + json.dumps(rep))
        return

    # ---- AND THE FLOAT_VECTOR BRANCH SILENTLY WRITES ZEROS. Patch it in memory.
    #
    #   ExporterOperators.py:53   out_type = type(out_array)      # a TYPE object
    #   ExporterOperators.py:78   case "FLOAT_VECTOR":
    #   ExporterOperators.py:79       match out_type:
    #   ExporterOperators.py:80           case "imath.V3fArray":  # a STRING
    #   ExporterOperators.py:85           case "imath.V2fArray":
    #
    # A type object never equals a string, so neither case matches, the `match`
    # falls through with no default, the function returns None, and `out_uvs`
    # keeps the zeros it was allocated with at AlembicGroomExporter.py:244.
    #
    # MEASURED, and this is why it matters beyond DiffLocks: cr_g75.blend holds
    # real root UVs (u 0.003-0.997, v 0.097-0.990, 1,223 distinct) and
    # cr_g75_ue.abc ships 48,000 rows of V2f(0, 0). **Every groom this project
    # has exported through this add-on has all-zero root UVs.** The same bug
    # zeroes FLOAT_COLOR and BYTE_COLOR.
    #
    # Patched on the MODULE OBJECT at run time. The vendor add-on on disk is not
    # touched -- it lives outside both roots and standing rule 1 forbids it.
    # ---- STAMP THE EXPORTER THAT PRODUCED THIS FILE.
    # The add-on ON DISK still writes zeros; the fix below is an IN-MEMORY patch
    # that dies with the process. So an .abc produced by an unpatched run and
    # one produced here are indistinguishable by filename, and the difference
    # decides whether the groom renders. Hash the two files that carry the bugs
    # so any export can be traced to the exporter that made it.
    try:
        import hashlib as _hl
        from GroomExporter import ExporterOperators as _EOm
        _addon = os.path.dirname(os.path.abspath(_EOm.__file__))
        _h = {}
        for _fn in ("ExporterOperators.py", "AlembicGroomExporter.py"):
            _p = os.path.join(_addon, _fn)
            with open(_p, "rb") as _fh:
                _h[_fn] = _hl.sha256(_fh.read()).hexdigest()[:16]
        rep["exporter_sha256_16"] = _h
        rep["exporter_dir"] = _addon
    except Exception as exc:
        rep["exporter_sha256_16"] = "COULD NOT READ: %s" % type(exc).__name__

    try:
        from GroomExporter import ExporterOperators as _EO
        import numpy as _np2

        _orig_gaa = _EO.getAttributeArray

        def _patched(att_valid, att_prop, out_array, groom_scale=1.0,
                     uv_flip=False):
            if att_valid and att_prop.data_type == "FLOAT_VECTOR":
                import imathnumpy as _inp
                n = len(att_prop.data)
                buf = _np2.empty(3 * n, dtype=_np2.float32)
                att_prop.data.foreach_get("vector", buf)
                src = buf.reshape(n, 3)
                mv = _inp.arrayToNumpy(out_array)
                w = mv.shape[1] if mv.ndim > 1 else 1
                if w == 2:
                    d2 = src[:, :2]
                    if uv_flip:
                        f = _np2.empty_like(d2)
                        f[:, 0] = d2[:, 1]
                        f[:, 1] = 1.0 - d2[:, 0]
                        d2 = f
                    _np2.copyto(mv, d2)
                elif w == 3:
                    _np2.copyto(mv, src)
                else:
                    return _orig_gaa(att_valid, att_prop, out_array,
                                     groom_scale, uv_flip)
                return
            return _orig_gaa(att_valid, att_prop, out_array, groom_scale,
                             uv_flip)

        _EO.getAttributeArray = _patched
        rep["float_vector_patch"] = "applied"
    except Exception as exc:
        rep["float_vector_patch"] = "NOT APPLIED: %s: %s" % (
            type(exc).__name__, exc)

    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    os.makedirs(os.path.dirname(os.path.abspath(out_abc)) or ".",
                exist_ok=True)
    try:
        res = bpy.ops.groom.buttonexport(
            filepath=out_abc, check_existing=False, groom_scale=1.0,
            groom_width_scale=True, groom_radius_to_diameter=True,
            groom_animation=False, node_execution=False)
        rep["operator_result"] = list(res)
    except Exception as exc:
        rep["error"] = "export raised: %s: %s" % (type(exc).__name__, exc)
        print("__EXPORT__" + json.dumps(rep))
        return

    rep["bytes"] = os.path.getsize(out_abc) if os.path.isfile(out_abc) else 0

    # ---- READ THE FILE BACK. The operator returned {'FINISHED'} on every one
    # of the exports that shipped without groom_root_uv, so its return value is
    # not evidence about the artefact. Open the ABC and ask for the param by
    # the name UE's Alembic hair translator reads.
    rep["abc_arb_params"] = "NOT READ"
    try:
        from alembic.Abc import IArchive
        from alembic import AbcGeom

        def walk(o, acc):
            for i in range(o.getNumChildren()):
                c = o.getChild(i)
                if AbcGeom.ICurves.matches(c.getMetaData()):
                    ag = AbcGeom.ICurves(o, c.getName()).getSchema() \
                        .getArbGeomParams()
                    if ag.valid():
                        acc.extend(ag.getPropertyHeader(j).getName()
                                   for j in range(ag.getNumProperties()))
                else:
                    walk(c, acc)

        acc = []
        walk(IArchive(out_abc).getTop(), acc)
        rep["abc_arb_params"] = acc
        if "groom_root_uv" not in acc:
            rep["error"] = ("REFUSE: the written ABC carries arb params %s "
                            "and no groom_root_uv. The export SUCCEEDED and "
                            "the file is unusable." % acc)
            rep["ok"] = False
            print("__EXPORT__" + json.dumps(rep))
            return

        # PRESENCE IS NOT THE CLAIM. The add-on shipped 48,000 rows of
        # V2f(0, 0) for a groom whose Blender attribute holds 1,223 distinct
        # real UVs, and a presence check calls that a pass. Read the VALUES.
        from alembic.Abc import IArrayProperty as _IAP
        from alembic import AbcGeom as _AG
        import numpy as _np3

        def walk_vals(o, out):
            for i in range(o.getNumChildren()):
                c = o.getChild(i)
                if _AG.ICurves.matches(c.getMetaData()):
                    ag = _AG.ICurves(o, c.getName()).getSchema() \
                        .getArbGeomParams()
                    v = _IAP(ag, "groom_root_uv").getValue()
                    out.append(_np3.array([[p[0], p[1]] for p in v]))
                else:
                    walk_vals(c, out)

        vals = []
        walk_vals(IArchive(out_abc).getTop(), vals)
        A = vals[0]
        uniq = int(len(_np3.unique(_np3.round(A, 6), axis=0)))
        rep["abc_root_uv"] = {
            "n": int(A.shape[0]), "unique": uniq,
            "u": [round(float(A[:, 0].min()), 5),
                  round(float(A[:, 0].max()), 5)],
            "v": [round(float(A[:, 1].min()), 5),
                  round(float(A[:, 1].max()), 5)],
            "all_zero": bool((A == 0.0).all())}
        # AND THE WIDTHS, for the same reason: presence is not the claim.
        def walk_w(o, out):
            for i in range(o.getNumChildren()):
                c = o.getChild(i)
                if _AG.ICurves.matches(c.getMetaData()):
                    wp = _AG.ICurves(o, c.getName()).getSchema().getWidthsParam()
                    if wp.valid():
                        out.append(_np3.array(
                            [float(x) for x in wp.getExpandedValue().getVals()]))
                else:
                    walk_w(c, out)

        wv = []
        walk_w(IArchive(out_abc).getTop(), wv)
        if wv:
            W = wv[0]
            rep["abc_widths"] = {"n": int(W.size),
                                 "min": round(float(W.min()), 8),
                                 "mean": round(float(W.mean()), 8),
                                 "max": round(float(W.max()), 8),
                                 "all_zero": bool((W == 0.0).all())}
            if rep["abc_widths"]["all_zero"]:
                rep["error"] = ("REFUSE: the written ABC carries full-length "
                                "ZERO widths. A groom with zero width draws "
                                "zero pixels.")
                rep["ok"] = False
                print("__EXPORT__" + json.dumps(rep))
                return
        else:
            rep["abc_widths"] = "COULD NOT READ"

        if rep["abc_root_uv"]["all_zero"] or uniq < 2:
            rep["error"] = ("REFUSE: groom_root_uv is present in the ABC and "
                            "carries %d distinct value(s). The FLOAT_VECTOR "
                            "patch did not take (ExporterOperators.py:78-97)."
                            % uniq)
            rep["ok"] = False
            print("__EXPORT__" + json.dumps(rep))
            return
    except Exception as exc:
        # "I could not look" is not "it is fine" -- say which one this is.
        rep["abc_arb_params"] = "COULD NOT READ: %s: %s" % (
            type(exc).__name__, exc)

    rep["ok"] = rep["bytes"] > 0

    # ---- SIDECAR. The ingest side cannot read this itself.
    #
    # `max_import_width` is NOT a reflected property on GroomAsset in 5.8 --
    # measured, it raises -- so the zero-width defect is INVISIBLE from UE. And
    # PyAlembic ships inside the Blender add-on and will not load in system
    # Python (ImportError: DLL load failed), so ingest_groom.py cannot open the
    # .abc either without paying a 40 s Blender launch per ingest.
    #
    # So the only process that can see the widths is THIS one. It writes what it
    # measured beside the file, hashed, and `ingest_groom.py` refuses an .abc
    # whose sidecar is missing or whose hash does not match. A file from outside
    # the fixed path has no sidecar and is refused by construction -- which is
    # non-negotiable 3's preference for an unreachable state over a gate, as far
    # as it can be taken here.
    if rep["ok"]:
        try:
            import hashlib as _hl2
            with open(out_abc, "rb") as _f:
                _sha = _hl2.sha256(_f.read()).hexdigest()
            side = {
                "abc": os.path.basename(out_abc),
                "abc_sha256": _sha,
                "abc_bytes": rep["bytes"],
                "curves": rep["curves"],
                "points": rep["points"],
                "widths": rep.get("abc_widths"),
                "root_uv": rep.get("abc_root_uv"),
                "arb_params": rep.get("abc_arb_params"),
                "pointers_set": rep.get("pointers_set"),
                "ue_consumed_absent": rep.get("ue_consumed_absent"),
                "exporter_sha256_16": rep.get("exporter_sha256_16"),
                "float_vector_patch": rep.get("float_vector_patch"),
                "gate": "widths non-zero and root UVs distinct, verified by "
                        "reopening the written file",
            }
            sp = out_abc + ".groomstats.json"
            with open(sp, "w", encoding="utf-8") as _f:
                json.dump(side, _f, indent=2)
            rep["sidecar"] = sp
        except Exception as exc:
            rep["sidecar"] = "FAILED: %s: %s" % (type(exc).__name__, exc)
            rep["ok"] = False

    print("__EXPORT__" + json.dumps(rep))


if __name__ == "__main__":
    main()
