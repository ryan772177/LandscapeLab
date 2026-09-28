"""bake_skeletal_to_static.py — SkeletalMesh -> StaticMesh, LOD chain intact.

WHY THIS EXISTS
---------------
The Megaplants conifers ship their four tree variants as **SkeletalMesh**
(measured 2026-08-14, `Free/_measured/tree_packs.json`). The foliage system
instances **StaticMesh only**, so as shipped neither pack can join the
153,796-instance forest. Ryan ruled: bake them to static meshes.

THE ROUTE, every name verified against THIS install's PythonStub before a
line was written (UE 5.8 RESOLUTION PROTOCOL; an API remembered is an API
guessed):

    GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(...)   :415697
    GeometryScript_NewAssetUtils
        .create_new_static_mesh_asset_from_mesh_lods(...)          :416423
    SkeletalMeshEditorSubsystem.get_lod_count(skeletal_mesh)       :633577
    DynamicMesh.get_num_triangle_i_ds()                            :265344
    unreal.new_object(unreal.DynamicMesh)                          :707201

**Two of those were WRONG when first written and the stub caught it.** I
typed `GeometryScript_NewAssets` (the class is `GeometryScript_NewAssetUtils`)
and called `get_num_triangle_i_ds` as a library function when it is a method
on the mesh. Both read as knowledge and would have died at the first call.
Resolving the enclosing class from the line number, rather than trusting the
name that came to mind, is what the protocol is for.

**THE LOD CHAIN IS COPIED, NOT REGENERATED.** `create_new_..._from_mesh_lods`
takes an ARRAY of DynamicMeshes, one per LOD, so the vendor's own chain
carries across verbatim. That deliberately avoids the reduction path, where
this project has a documented casualty: `ReductionSettings[0]` IS LOD 0, so
the obvious LOD chain decimates the source mesh.

WHERE IT WRITES, AND WHY IT REFUSES ANYWHERE ELSE
-------------------------------------------------
Output goes under `/Game/Meshes/Trees/`. The tool REFUSES a destination
inside a vendor root. R-ASSET forbids authoring into a Fab folder, and
`Content/Megaplant_Library/` is gitignored -- anything written there is lost
work that looks like committed work the moment the pack is re-downloaded.

SAFETY
------
Dry run by default; `--go` is required to create anything. Every bake is
followed by a READ-BACK from the created asset -- LOD count, LOD-0 triangle
count (within 15%), bounds and material count -- compared against the source,
AND save_asset's return is checked so a package that did not persist to disk
is not counted as success. The read-back reads the in-memory created asset
(load_asset returns the just-registered object), so it verifies the BUILD;
save_asset's boolean is the on-disk evidence. A bake that cannot be verified
is reported as UNVERIFIED, never as success.

Exit codes:
  0  dry run completed, or every requested mesh baked AND verified
  2  editor gate refused (conduct rule 7), bad arguments, or a refused
     destination
  3  one or more meshes failed to bake or failed verification
  4  stopped early on the RAM floor
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap             # noqa: E402
import resource_guard        # noqa: E402
import verify_landscape      # noqa: E402

MARKER = "__LANDSCAPELAB_BAKESKM__"
FLOOR_GB = 1.0

# Destination must be under one of these. Everything else is refused --
# see the module docstring.
ALLOWED_DEST_ROOTS = ("/Game/Meshes/",)

# Vendor roots, named so the refusal message can say WHICH rule applies.
VENDOR_ROOTS = (
    "/Game/Megaplant_Library/", "/Game/Fab/", "/Game/KiteDemo/",
    "/Game/Megascans/", "/Game/GV_FreeShrubsPack/",
    "/Game/PN_interactiveSpruceForest/", "/Game/PN_WildBerries/",
    "/Game/TreesGen02_01/", "/Game/HighPoly_Tree_Model/",
)

DEFAULT_SOURCES = [
    "/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/"
    "Tree_Norway_Spruce_01_" + v for v in ("A", "B", "C", "D")
] + [
    "/Game/Megaplant_Library/Tree_Baltic_Pine/Tree_Baltic_Pine_01/"
    "Tree_Baltic_Pine_01_" + v for v in ("A", "B", "C", "D")
]

DEST_DIR = "/Game/Meshes/Trees"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"src": {src!r}, "dest": {dest!r}, "ok": False, "error": None,
        "lods_read": 0, "source_lod_count": None}}
try:
    _src = {src!r}
    _dest = {dest!r}
    if not _unreal.EditorAssetLibrary.does_asset_exist(_src):
        _out["error"] = "source asset does not exist"
    else:
        _skm = _unreal.EditorAssetLibrary.load_asset(_src)
        if _skm is None:
            _out["error"] = "load_asset returned None"
        elif type(_skm).__name__ != "SkeletalMesh":
            # Fail closed on the premise. Baking something that is already a
            # StaticMesh would silently produce a duplicate.
            _out["error"] = "source is {{0}}, not SkeletalMesh".format(
                type(_skm).__name__)
        else:
            _sub = _unreal.get_editor_subsystem(
                _unreal.SkeletalMeshEditorSubsystem)
            _n = int(_sub.get_lod_count(_skm))
            _out["source_lod_count"] = _n
            if _n < 1:
                _out["error"] = "source reports {{0}} LODs".format(_n)
            else:
                _asset_opts = (
                    _unreal.GeometryScriptCopyMeshFromAssetOptions())
                _asset_opts.set_editor_property("request_tangents", True)
                _meshes = []
                _tri_src = []
                for _i in range(_n):
                    _dm = _unreal.new_object(_unreal.DynamicMesh)
                    _lod = _unreal.GeometryScriptMeshReadLOD()
                    _lod.set_editor_property("lod_index", _i)
                    _res = (_unreal.GeometryScript_AssetUtils
                            .copy_mesh_from_skeletal_mesh(
                                _skm, _dm, _asset_opts, _lod))
                    # Returns (DynamicMesh, outcome). Take the mesh it hands
                    # back rather than assuming it mutated ours in place.
                    _dm2 = _res[0] if isinstance(_res, tuple) else _res
                    _meshes.append(_dm2)
                    try:
                        # Method ON the DynamicMesh (PythonStub:265344), not
                        # a library call. Verified, not recalled.
                        _tri_src.append(int(_dm2.get_num_triangle_i_ds()))
                    except Exception:
                        _tri_src.append(None)
                _out["lods_read"] = len(_meshes)
                _out["source_lod_triangles"] = _tri_src

                _new_opts = (
                    _unreal.GeometryScriptCreateNewStaticMeshAssetOptions())
                _new_opts.set_editor_property("enable_nanite", {nanite})
                _new_opts.set_editor_property("enable_collision", {collision})
                _res2 = (_unreal.GeometryScript_NewAssetUtils
                         .create_new_static_mesh_asset_from_mesh_lods(
                             _meshes, _dest, _new_opts))
                _sm = _res2[0] if isinstance(_res2, tuple) else _res2
                if _sm is None:
                    _out["error"] = "create_new_static_mesh returned None"
                else:
                    # Carry the vendor materials across. The creation options
                    # struct has no materials field, so this is a separate
                    # step and is asserted below rather than assumed.
                    try:
                        # SkeletalMesh.materials is Array[SkeletalMaterial]
                        # (PythonStub, SkeletalMesh class), each carrying
                        # material_interface AND material_slot_name. The slot
                        # NAME is carried too, deliberately: this project's
                        # M_fir_bark defect -- trunks rendering the twig atlas
                        # because texture_map last-wins on a contested role --
                        # is only detectable when the slots are named.
                        # EACH STEP IS INDEPENDENTLY FAULT-TOLERANT. The
                        # first version wrapped the whole loop in one try, so
                        # a single failing set_editor_property zeroed the
                        # entire assignment and every mesh came back with
                        # WorldGridMaterial in slot 0 and nulls after it. One
                        # optional cosmetic field must not be able to discard
                        # the material carry-over.
                        _mats = list(_skm.get_editor_property("materials"))
                        _out["src_material_count"] = len(_mats)
                        _sms = []
                        _names = []
                        for _m in _mats:
                            _mi, _nm = _m, None
                            try:
                                _mi = _m.get_editor_property(
                                    "material_interface")
                            except Exception:
                                pass
                            try:
                                _nm = _m.get_editor_property(
                                    "material_slot_name")
                            except Exception:
                                _nm = None
                            _sm_entry = _unreal.StaticMaterial()
                            _sm_entry.set_editor_property(
                                "material_interface", _mi)
                            if _nm is not None:
                                try:
                                    _sm_entry.set_editor_property(
                                        "material_slot_name", _nm)
                                except Exception as _nex:
                                    _out["slot_name_error"] = str(_nex)[:160]
                            _names.append(str(_nm))
                            _sms.append(_sm_entry)
                        if _sms:
                            _sm.set_editor_property("static_materials", _sms)
                        _out["materials_set"] = len(_sms)
                        _out["material_slot_names"] = _names
                    except Exception as _mex:
                        _out["materials_set"] = 0
                        _out["material_error"] = str(_mex)[:200]

                    # save_asset returns whether the package persisted to
                    # disk. A discarded return is rule 12's "value not read
                    # back is prose" -- and it is the ONLY disk-persistence
                    # signal here (the read-back below re-reads the same
                    # in-memory object, so it verifies the BUILD, not the
                    # save). Capture it and make it a term of acceptance.
                    _out["saved"] = bool(
                        _unreal.EditorAssetLibrary.save_asset(_dest, False))

                    # --- READ-BACK from the created asset (IN MEMORY) -----
                    # load_asset on an asset just created and registered
                    # returns that same UObject, so these quantities verify
                    # the BUILD against the source, not the on-disk package;
                    # _out["saved"] above is the disk-persistence evidence.
                    _chk = _unreal.EditorAssetLibrary.load_asset(_dest)
                    _out["verify_class"] = type(_chk).__name__
                    try:
                        _ss = _unreal.get_editor_subsystem(
                            _unreal.StaticMeshEditorSubsystem)
                        _ln = int(_ss.get_lod_count(_chk))
                        _out["dest_lod_count"] = _ln
                        _out["dest_lod_triangles"] = [
                            int(_chk.get_num_triangles(_i))
                            for _i in range(_ln)]
                        # A SECOND QUANTITY on the same pair of artefacts.
                        # Triangles alone cannot distinguish "the build
                        # removed degenerate faces" from "geometry was lost":
                        # vertices can. Both are reported.
                        _out["dest_lod_vertices"] = [
                            int(_chk.get_num_vertices(_i))
                            for _i in range(_ln)]
                        _out["src_lod_vertices"] = [
                            int(_sub.get_num_verts(_skm, _i))
                            for _i in range(_n)]
                    except Exception as _vex:
                        _out["dest_lod_count"] = None
                        _out["verify_error"] = str(_vex)[:200]
                    try:
                        _b = _chk.get_bounds()
                        _out["dest_extent_cm"] = [
                            _b.box_extent.x, _b.box_extent.y, _b.box_extent.z]
                        _bs = _skm.get_bounds()
                        _out["src_extent_cm"] = [
                            _bs.box_extent.x, _bs.box_extent.y,
                            _bs.box_extent.z]
                    except Exception:
                        pass
                    try:
                        _out["dest_material_slots"] = len(
                            _chk.static_materials)
                    except Exception:
                        _out["dest_material_slots"] = None
                    _out["ok"] = True
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


def dest_for(src, dest_dir):
    """/Game/.../Tree_Norway_Spruce_01_A -> <dest_dir>/SM_Tree_Norway_Spruce_01_A"""
    return "{0}/SM_{1}".format(dest_dir.rstrip("/"), src.rsplit("/", 1)[-1])


def check_dest(dest_dir):
    """(ok, message). Refuses vendor roots explicitly and by name."""
    d = dest_dir if dest_dir.endswith("/") else dest_dir + "/"
    for v in VENDOR_ROOTS:
        if d.startswith(v):
            return False, (
                "{0} is a VENDOR root. R-ASSET forbids authoring into vendor "
                "folders and this one is gitignored, so the bake would be "
                "lost work that looks like committed work the moment the "
                "pack is re-downloaded.".format(v))
    for a in ALLOWED_DEST_ROOTS:
        if d.startswith(a):
            return True, ""
    return False, (
        "destination must be under one of {0}; got {1}".format(
            ALLOWED_DEST_ROOTS, dest_dir))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", action="append", default=None,
                    help="/Game path to a SkeletalMesh (repeatable).")
    ap.add_argument("--dest-dir", default=DEST_DIR)
    ap.add_argument("--nanite", action="store_true",
                    help="Enable Nanite on the baked mesh. OFF by default: "
                         "alpha-tested/dense foliage under Nanite has "
                         "trade-offs this project has not measured, and the "
                         "incumbent conifers are not Nanite.")
    ap.add_argument("--collision", action="store_true",
                    help="Generate collision. OFF by default -- foliage "
                         "instances do not need per-tree collision and it "
                         "costs memory at 150k instances.")
    ap.add_argument("--go", action="store_true",
                    help="Actually create assets. Without this it is a dry "
                         "run.")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    sources = args.src or DEFAULT_SOURCES
    ok, why = check_dest(args.dest_dir)
    if not ok:
        print("REFUSE: {0}".format(why))
        return 2

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("sources   : {0}".format(len(sources)))
    print("dest      : {0}".format(args.dest_dir))
    print("nanite    : {0}   collision: {1}".format(args.nanite,
                                                    args.collision))
    print("mode      : {0}".format("GO (creates assets)" if args.go
                                   else "DRY RUN (creates nothing)"))
    print("")
    for s in sources:
        print("  {0}".format(s))
        print("     -> {0}".format(dest_for(s, args.dest_dir)))
    if not args.go:
        print("")
        print("DRY RUN. Nothing was created. Re-run with --go.")
        return 0

    results = []
    failed = 0
    stopped = False

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
        remote.open_command_connection(node["node_id"])

        print("")
        for src in sources:
            free, _total = resource_guard.available_gb()
            if free < FLOOR_GB:
                print("STOP: {0:.2f} GB free is below the {1:.1f} GB floor. "
                      "Partial run DECLARED.".format(free, FLOOR_GB))
                stopped = True
                break
            dest = dest_for(src, args.dest_dir)
            payload = PAYLOAD.format(
                src=src, dest=dest, marker=MARKER,
                nanite="True" if args.nanite else "False",
                collision="True" if args.collision else "False")
            r = remote.run_command(payload, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            row = _parse(bootstrap._collect_output(r) if r else "")
            if row is None:
                row = {"src": src, "dest": dest, "ok": False,
                       "error": "no parseable result (could not look)"}
            results.append(row)
            name = src.rsplit("/", 1)[-1]
            if not row.get("ok"):
                failed += 1
                print("  {0:<30} FAILED: {1}".format(name, row.get("error")))
                continue
            st = row.get("source_lod_triangles") or []
            dt = row.get("dest_lod_triangles") or []
            sv = row.get("src_lod_vertices") or []
            dv = row.get("dest_lod_vertices") or []
            se = row.get("src_extent_cm") or []
            de = row.get("dest_extent_cm") or []

            # ACCEPTANCE IS SILHOUETTE + MATERIALS + LOD STRUCTURE, not
            # triangle parity. The StaticMesh build welds and drops
            # degenerate faces, so an exact triangle match is not achievable
            # and demanding one would reject every correct bake. What must
            # hold is that the tree occupies the same space, keeps its
            # material assignments in order, and keeps its LOD count.
            bounds_ok = bool(se and de and len(se) == len(de) and all(
                abs(a - b) <= 1.0 for a, b in zip(se, de)))
            lods_ok = (row.get("source_lod_count") ==
                       row.get("dest_lod_count"))
            # Compare the dest slot count against the SOURCE material count,
            # not against materials_set (which is derived from the same list
            # -- comparing it to dest_material_slots was an object-vs-itself
            # tautology that could never fail).
            mats_ok = bool(row.get("dest_material_slots")) and (
                row.get("dest_material_slots") == row.get("src_material_count"))
            tri_delta = None
            if st and dt and st[0] and dt[0]:
                tri_delta = (dt[0] - st[0]) / float(st[0])
            tris_ok = tri_delta is not None and abs(tri_delta) <= 0.15

            match = (bounds_ok and lods_ok and mats_ok and tris_ok
                     and bool(row.get("saved")))
            if not match:
                failed += 1
            print("  {0:<30} LODs {1}->{2}  tris {3}->{4} ({5})  "
                  "verts {6}->{7}".format(
                      name, row.get("source_lod_count"),
                      row.get("dest_lod_count"),
                      st[0] if st else "?", dt[0] if dt else "?",
                      "{0:+.1%}".format(tri_delta)
                      if tri_delta is not None else "?",
                      sv[0] if sv else "?", dv[0] if dv else "?"))
            print("      bounds {0}  materials {1} ({2})  saved {3}  -> {4}"
                  .format(
                      "MATCH" if bounds_ok else "DIFFER",
                      row.get("materials_set"),
                      ", ".join(row.get("material_slot_names") or [])
                      or "unnamed",
                      "OK" if row.get("saved") else "NOT SAVED",
                      "VERIFIED" if match else "NOT VERIFIED"))
            for k in ("material_error", "slot_name_error", "verify_error"):
                if row.get(k):
                    print("      {0}: {1}".format(k, row[k]))
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    print("")
    if stopped:
        print("baked {0} of {1} ATTEMPTED ({2} requested); {3} failed or "
              "unverified. Meshes past the RAM-floor stop were not attempted."
              .format(len(results) - failed, len(results), len(sources),
                      failed))
    else:
        print("baked {0} of {1}; {2} failed or unverified".format(
            len(results) - failed, len(sources), failed))
    print("Acceptance is bounds + LOD count + material count + LOD-0 triangle "
          "count (within 15%) + save_asset persisting the package. The build "
          "welds and drops degenerate faces, so exact triangle parity is not "
          "required; the read-back verifies the BUILD (from the in-memory "
          "created asset) and save_asset is the on-disk evidence.")

    if stopped:
        return 4
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
