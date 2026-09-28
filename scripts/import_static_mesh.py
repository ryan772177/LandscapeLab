"""import_static_mesh.py — import a Free/ mesh and build its material.

Imports one manifest MESH asset as a StaticMesh, imports the textures it
needs, builds a material for it, and verifies everything by read-back.
Handles the alpha-masked foliage case, which is the only kind this
pipeline currently places.

NANITE COMES FROM THE RECIPE AND IS SET AT IMPORT TIME, never toggled on
the asset afterwards. `foliage.nanite` (schema v1.9) is read here and
passed through FbxStaticMeshImportData / the interchange options so the
build happens once with the right settings. Setting it after the fact
rebuilds the mesh a second time and leaves a window where the asset on
disk disagrees with the recipe.

NANITE IS OFF BY DEFAULT FOR ALPHA-MASKED FOLIAGE and that is not
timidity. Nanite's masked support exists in 5.8 but costs the fast path,
and the twig material here is alpha-cut over a 505k-triangle LOD; the
cheap and certain configuration is Nanite off with real LODs. The recipe
can turn it on per species, and `verify` reports what actually landed
rather than what was asked for.

MATERIAL SLOTS THE SOURCE DOES NOT TEXTURE. fir_tree_01 uses four
materials on every LOD — bark, twig, dead_branches and a per-LOD trunk —
and the vendor ships maps for only bark and twig. There is nothing
upstream to recover: the FBX package IS the whole delivery. Slots
without maps are bound to the SUBSTITUTE named in the recipe and the
substitution is reported on every run, because a silent fallback reads
as an authored choice.

Exit codes:
  0  imported, material built, everything verified by read-back
  1  unexpected error / bad arguments
  2  manifest, mesh or texture missing
  3  editor identity gate refused (conduct rule 7)
  4  import or verification failed
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402
import landscape_spec     # noqa: E402 — ruling (c) contract, one copy decides
import texture_16bit      # noqa: E402 — shared 16-bit conversion (non-negotiable 4a)

REPO_ROOT = bootstrap.REPO_ROOT
FREE_DIR = os.path.join(REPO_ROOT, "Free")
MANIFEST = os.path.join(FREE_DIR, "manifest.json")
MESH_ROOT = "/Game/Meshes"
TEX_ROOT = "/Game/Meshes/Textures"
MARKER = "__LANDSCAPELAB_MESH__"

# Roles a foliage material consumes, and how each must be imported.
TEX_ROLES = {
    "color": ("C", {"srgb": True, "compression_settings": "TC_Default"}),
    "normal": ("N", {"srgb": False,
                     "compression_settings": "TC_Normalmap"}),
    "roughness": ("R", {"srgb": False, "compression_settings": "TC_Masks"}),
    "alpha": ("A", {"srgb": False, "compression_settings": "TC_Alpha"}),
    "packed-arm": ("ARM", {"srgb": False,
                           "compression_settings": "TC_Masks"}),
}


def load_manifest():
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        return json.load(fh)


NORMALIZED_DIR = os.path.join(FREE_DIR, "_normalized")
NORMALIZED_REPORT = os.path.join(FREE_DIR, "_measured", "normalized.json")


def normalized_source(object_name):
    """Path to the pivot-normalised single-object FBX for `object_name`.

    REFUSES unless scripts/blender/normalize_asset.py recorded that exact
    object as verified. The vendor files lay their objects side by side —
    fir_tree_01_c_LOD0 sits 12.41 m from the file origin — and UE keeps
    that offset as the StaticMesh pivot. Importing the vendor file
    directly is not a smaller version of importing the normalised one; it
    is the same asset with every instance displaced by metres, silently.

    So this does not fall back. If the report is missing, does not name
    the object, or marked it not-ok, the caller gets an exception and
    the import does not happen. "I could not check" is not "it is fine"
    (lesson 2.10).
    """
    if not os.path.isfile(NORMALIZED_REPORT):
        raise ValueError(
            "no normalisation report at {0} — run "
            "scripts/blender/normalize_asset.py first".format(
                NORMALIZED_REPORT))
    with open(NORMALIZED_REPORT, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    if not isinstance(report, dict):
        raise ValueError(
            "normalisation report top level is {0}, expected a dict of "
            "groups — refusing".format(type(report).__name__))
    rows_seen = 0
    for group in report.values():
        if not isinstance(group, dict):
            continue
        # isinstance, not truthiness: "objects": 5 would raise TypeError,
        # which the caller's (OSError, ValueError) net does not catch
        # (audit F2, 2026-08-02; same guard in landscape_spec).
        rows_field = group.get("objects")
        if not isinstance(rows_field, list):
            continue
        for row in rows_field:
            if not isinstance(row, dict):
                continue
            rows_seen += 1
            if row.get("object") != object_name:
                continue
            if not row.get("ok"):
                raise ValueError(
                    "{0} was normalised but FAILED verification ({1}); "
                    "refusing to import it".format(
                        object_name, row.get("why", "no reason recorded")))
            path = os.path.abspath(
                os.path.join(NORMALIZED_DIR, object_name + ".fbx"))
            if os.path.dirname(path) != os.path.abspath(NORMALIZED_DIR):
                raise ValueError(
                    "object name {0!r} resolves outside {1} — refusing"
                    .format(object_name, NORMALIZED_DIR))
            if not os.path.isfile(path):
                raise ValueError(
                    "{0} is recorded as verified but {1} is not on disk"
                    .format(object_name, path))
            return path.replace("\\", "/"), row
    if not rows_seen:
        raise ValueError(
            "normalisation report at {0} contains no object rows — "
            "malformed or empty; refusing".format(NORMALIZED_REPORT))
    raise ValueError(
        "{0} is not in the normalisation report; the vendor file's pivot "
        "offset would be baked into the asset".format(object_name))


def plan(manifest, mesh_id):
    """(asset, mesh source path, [texture jobs]) for one mesh id."""
    for a in manifest["assets"]:
        if a["id"] != mesh_id:
            continue
        mesh_src = None
        texs = []
        for f in a["files"]:
            role = f["role"]
            src = os.path.join(FREE_DIR, f["path"].replace("/", os.sep))
            if role == "mesh":
                mesh_src = src.replace("\\", "/")
            elif role in TEX_ROLES:
                # Poly Haven names maps <asset>_<slot>_<role>_4k; keep the
                # slot in the asset name so bark and twig do not collide.
                stem = os.path.splitext(os.path.basename(f["path"]))[0]
                suffix, settings = TEX_ROLES[role]
                texs.append({
                    "role": role, "src": src.replace("\\", "/"),
                    "asset": "{0}/T_{1}".format(TEX_ROOT, stem),
                    "settings": settings, "stem": stem,
                })
        if mesh_src is None:
            raise ValueError("{0} has no mesh file".format(mesh_id))
        return a, mesh_src, texs
    raise KeyError("no asset {0!r} in the manifest".format(mesh_id))


PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "stage": "start", "textures": [], "mesh": {{}}}}
_job = _json.loads({job!r})

try:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()

    _out["stage"] = "textures"
    for _t in _job["textures"]:
        _task = _unreal.AssetImportTask()
        _task.set_editor_property("filename", _t["src"])
        _task.set_editor_property("destination_path",
                                  _t["asset"].rsplit("/", 1)[0])
        _task.set_editor_property("destination_name",
                                  _t["asset"].rsplit("/", 1)[1])
        _task.set_editor_property("automated", True)
        _task.set_editor_property("replace_existing", True)
        _task.set_editor_property("save", False)
        _tools.import_asset_tasks([_task])
        _tex = _unreal.EditorAssetLibrary.load_asset(_t["asset"])
        _row = {{"asset": _t["asset"], "role": _t["role"]}}
        if _tex is None:
            _row["error"] = "no asset produced"
            _out["textures"].append(_row)
            continue
        for _k, _v in _t["settings"].items():
            if isinstance(_v, bool):
                _tex.set_editor_property(_k, _v)
            else:
                _tex.set_editor_property(
                    _k, getattr(_unreal.TextureCompressionSettings,
                                _v.upper()))
        _wrong = []
        for _k, _v in _t["settings"].items():
            _r = _tex.get_editor_property(_k)
            _n = getattr(_r, "name", None)
            _r = _n if _n is not None else _r
            if isinstance(_v, bool):
                if bool(_r) != _v:
                    _wrong.append(_k)
            elif str(_r).upper() != _v.upper():
                _wrong.append(_k)
        _row["wrong"] = _wrong
        _unreal.EditorAssetLibrary.save_asset(_t["asset"],
                                              only_if_is_dirty=False)
        _out["textures"].append(_row)

    # ---- mesh ------------------------------------------------------
    _out["stage"] = "mesh"
    _mtask = _unreal.AssetImportTask()
    _mtask.set_editor_property("filename", _job["mesh_src"])
    _mtask.set_editor_property("destination_path", _job["mesh_dir"])
    _mtask.set_editor_property("destination_name", _job["mesh_name"])
    _mtask.set_editor_property("automated", True)
    _mtask.set_editor_property("replace_existing", True)
    _mtask.set_editor_property("save", False)

    _opts = _unreal.FbxImportUI()
    _opts.set_editor_property("import_mesh", True)
    _opts.set_editor_property("import_textures", False)
    _opts.set_editor_property("import_materials", False)
    _opts.set_editor_property("import_as_skeletal", False)
    _opts.set_editor_property("mesh_type_to_import",
                              _unreal.FBXImportType.FBXIT_STATIC_MESH)
    _sm = _opts.get_editor_property("static_mesh_import_data")
    _sm.set_editor_property("combine_meshes", bool(_job["combine"]))
    _sm.set_editor_property("generate_lightmap_u_vs", False)
    _sm.set_editor_property("build_nanite", bool(_job["nanite"]))
    _mtask.set_editor_property("options", _opts)
    _tools.import_asset_tasks([_mtask])

    _paths = list(_mtask.get_editor_property("imported_object_paths") or [])
    _out["mesh"]["imported_paths"] = _paths[:12]
    _target = None
    for _p in _paths:
        _o = _unreal.EditorAssetLibrary.load_asset(_p.split(".")[0])
        if isinstance(_o, _unreal.StaticMesh):
            if _job["want_object"] and _job["want_object"] not in _p:
                continue
            _target = _o
            _out["mesh"]["asset"] = _p.split(".")[0]
            break
    if _target is None:
        _out["error"] = ("no StaticMesh matching %r among %d imported "
                         "objects" % (_job["want_object"], len(_paths)))
    else:
        # READ BACK from the asset, never from the task's return.
        _out["mesh"]["triangles"] = int(
            _target.get_num_triangles(0)) if hasattr(
            _target, "get_num_triangles") else None
        _out["mesh"]["lods"] = int(_target.get_num_lods()) if hasattr(
            _target, "get_num_lods") else None
        try:
            _ns = _target.get_editor_property("nanite_settings")
            _out["mesh"]["nanite_enabled"] = bool(
                _ns.get_editor_property("enabled"))
        except Exception as _exc:
            # LESSON 9: a failed read is NOT a negative result.
            _out["mesh"]["nanite_enabled"] = None
            _out["mesh"]["nanite_read_error"] = "%s: %s" % (
                type(_exc).__name__, _exc)
        _out["mesh"]["material_slots"] = [
            str(_s.material_slot_name) for _s in
            _target.get_editor_property("static_materials")]
        # PIVOT, read off the imported asset. This is the number that
        # actually governs where an instance appears, and it is the one
        # the vendor files get wrong: get_bounds().origin is the offset
        # from the asset pivot to the geometry centre, in cm. A large
        # horizontal value means every instance is displaced by that
        # much and random yaw sweeps the mesh around a circle of that
        # radius. Reported unconditionally, normalised source or not, so
        # the claim is measured rather than inherited from the FBX.
        try:
            _b = _target.get_bounds()
            _o, _e = _b.origin, _b.box_extent
            _out["mesh"]["bounds_size_m"] = [
                round(_e.x * 2 / 100.0, 4), round(_e.y * 2 / 100.0, 4),
                round(_e.z * 2 / 100.0, 4)]
            _out["mesh"]["pivot_offset_xy_m"] = round(
                (_o.x * _o.x + _o.y * _o.y) ** 0.5 / 100.0, 4)
            # Base-centre convention: the geometry should sit ON the
            # pivot, so origin.z - extent.z is the distance from the
            # pivot down to the lowest point. ~0 is correct.
            _out["mesh"]["base_offset_z_m"] = round(
                (_o.z - _e.z) / 100.0, 4)
        except Exception as _exc:
            _out["mesh"]["pivot_offset_xy_m"] = None
            _out["mesh"]["pivot_read_error"] = "%s: %s" % (
                type(_exc).__name__, _exc)
        _unreal.EditorAssetLibrary.save_asset(
            _out["mesh"]["asset"], only_if_is_dirty=False)

    _out["stage"] = "done"
    _out["ok"] = ("error" not in _out
                  and not any(_t.get("wrong") or _t.get("error")
                              for _t in _out["textures"]))
except Exception as _exc:
    _out["error"] = "%s at stage %r: %s" % (
        type(_exc).__name__, _out.get("stage"), _exc)

print("{marker}" + _json.dumps(_out))
'''


def _parse(text, marker=MARKER):
    i = text.find(marker)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(marker):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mesh_id")
    p.add_argument("--object", default="",
                   help="substring of the FBX object to keep, e.g. "
                        "c_LOD0. Empty takes the first StaticMesh.")
    p.add_argument("--name", default="",
                   help="asset name; defaults to SM_<mesh_id>")
    p.add_argument("--nanite", action="store_true",
                   help="build Nanite AT IMPORT. Off by default: the "
                        "foliage here is alpha-masked and the cheap "
                        "certain path is Nanite off with real LODs.")
    p.add_argument("--combine", action="store_true",
                   help="merge every mesh in the file into one asset.")
    p.add_argument("--normalized", default="",
                   help="import the PIVOT-NORMALISED single-object FBX "
                        "for this object name instead of the vendor file. "
                        "Refuses unless normalize_asset.py recorded it as "
                        "verified. Use this for anything that will be "
                        "instanced: the vendor files carry metre-scale "
                        "pivot offsets that UE bakes into the asset.")
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    try:
        manifest = load_manifest()
        asset, mesh_src, texs = plan(manifest, args.mesh_id)
    except (OSError, ValueError, KeyError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2

    # RULING (c), Ryan 2026-08-02. A mesh some recipe NAMES must be
    # built from a normalised source. Ad-hoc vendor imports are
    # untouched — the whole point of (c) is that the recipe, not the
    # importer, knows whether a mesh will be instanced.
    #
    # This is the half the recipe validator CANNOT cover. Importing a
    # vendor file as `--name grass_medium_01_tiny_a_LOD0` leaves the
    # recipe validating perfectly, because the validator matches NAMES
    # against the report and that name is verified. The asset behind it
    # would just have been silently rebuilt with the vendor pivot.
    target_path = "{0}/{1}".format(MESH_ROOT, args.name or
                                   "SM_{0}".format(args.mesh_id))
    # Canonical keys, not raw strings: the validator accepts
    # `/Game/Meshes/X.X` and case variants, and an exact-match miss
    # here silently SKIPS this gate for exactly the asset the recipe
    # names (audit F4, 2026-08-02).
    target_key = landscape_spec.mesh_path_key(target_path)
    claimed_by = []
    try:
        for rp in sorted(glob.glob(os.path.join(REPO_ROOT, "recipes",
                                                "*.json"))):
            try:
                with open(rp, "r", encoding="utf-8") as fh:
                    rec = json.load(fh)
            except (OSError, ValueError):
                # A recipe that cannot be read cannot be shown NOT to
                # claim this path. Refusing on it would make an
                # unrelated broken recipe block every import, so it is
                # reported and the run continues -- stated here so the
                # gap is visible rather than discovered.
                print("  NOTE: {0} is unreadable; it was not checked for "
                      "claims on this asset.".format(os.path.basename(rp)))
                continue
            if target_key in {landscape_spec.mesh_path_key(mp) for mp in
                              landscape_spec.recipe_mesh_paths(rec)}:
                claimed_by.append(os.path.basename(rp))
    except OSError as exc:
        print("REFUSE: could not scan recipes/ to apply ruling (c): "
              "{0}".format(exc))
        return 2
    if claimed_by and not args.normalized:
        print("REFUSE (ruling c): {0} is named by {1}, so it will be "
              "INSTANCED and must come from a pivot-normalised source."
              .format(target_path, ", ".join(claimed_by)))
        print("  The vendor files lay their objects side by side; this "
              "asset previously imported 12.406 m from its own pivot,")
        print("  which displaces every instance and sweeps it around a "
              "circle of that radius under random yaw.")
        print("")
        print("  Run:  blender --background --factory-startup "
              "--python-exit-code 1 \\")
        print("          --python scripts/blender/normalize_asset.py \\")
        print("          -- <source> Free/_normalized")
        print("  then: python scripts/import_static_mesh.py {0} "
              "--normalized {1} --name {1}".format(
                  args.mesh_id, target_path.rsplit("/", 1)[1]))
        print("")
        print("  Ad-hoc vendor imports are NOT gated -- import under a "
              "name no recipe claims and this will not fire.")
        return 2

    # 16-BIT SINGLE-CHANNEL TEXTURE SOURCES (LESSONS Division 6,
    # 2026-08-02: the grass root cause). A PNG in mode I;16 fed to the
    # TC_Alpha import path lands its data where the material's R-pin
    # sample reads zero: the opacity mask clips every pixel and the
    # material renders NOTHING while compiling clean. The fir twig
    # rendered only because its alpha happened to ship as RGB 8-bit.
    # The class also covers roughness (TC_Masks) — the fir's roughness
    # maps are I;16 and were presumed silently wrong until this.
    #
    # Fix at the pipeline boundary, vendor file untouched: convert to
    # 8-bit grayscale into Free/_normalized/textures/ (the same
    # derivative pattern as pivot normalisation) and import THAT.
    # 65535/255 = 257: a full-range 16-bit value maps to full-range
    # 8-bit, no datum shift.
    # MIGRATED 2026-08-03 to scripts/texture_16bit.py.
    #
    # This logic used to live here inline. It then had to exist in
    # import_surface_set.py too, which is the same trap class in a SECOND
    # tool -- CLAUDE.md non-negotiable 4a promotes that to shared
    # infrastructure on the spot, and makes an individually-patched copy
    # a REJECTED pattern in its own right. Do not re-inline this.
    #
    # The shared version is strictly stronger than what was here: the old
    # check verified only mask coverage within 1%, and a TRUNCATING
    # converter -- the exact bug that made this project read three real
    # displacement maps as flat -- drifts coverage by only 0.0041 and
    # would have PASSED it. texture_16bit asserts the integer
    # requantisation residual instead, which refuses truncation, datum
    # shifts, rescales and inversions.
    CONVERT_ROLES = ("alpha", "roughness")
    try:
        for t in texs:
            if t["role"] not in CONVERT_ROLES:
                continue
            res = texture_16bit.stage_8bit(
                t["src"], t["stem"],
                os.path.join(FREE_DIR, "_normalized", "textures"),
                role=t["role"])
            if res["converted"]:
                t["src"] = res["src"]
    except texture_16bit.TextureConversionError as exc:
        print("REFUSE: {0}".format(exc))
        return 2

    norm_row = None
    if args.normalized:
        try:
            mesh_src, norm_row = normalized_source(args.normalized)
        except (OSError, ValueError) as exc:
            print("REFUSE: {0}".format(exc))
            return 2
        # A single-object file has nothing to disambiguate, and leaving a
        # stale --object substring in would silently select nothing.
        args.object = ""

    name = args.name or "SM_{0}".format(args.mesh_id)
    job = {
        "mesh_src": mesh_src,
        "mesh_dir": MESH_ROOT,
        "mesh_name": name,
        "want_object": args.object,
        "nanite": bool(args.nanite),
        "combine": bool(args.combine),
        "textures": texs,
    }

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("mesh      : {0}  ({1})".format(
        args.mesh_id, asset.get("type")))
    print("extent    : {0} m ({1})".format(
        asset.get("mesh_extent_m"), asset.get("mesh_extent_m_source")))
    if norm_row is not None:
        print("source    : PIVOT-NORMALISED  {0}".format(mesh_src))
        print("            dims {0} m, pivot was {1:.3f} m off the file "
              "origin, verified to {2:.6f} m".format(
                  norm_row.get("dims_m"),
                  norm_row.get("source_offset_m", 0.0),
                  norm_row.get("pivot_error_m", 0.0)))
    else:
        print("source    : VENDOR FILE (pivot not normalised) {0}".format(
            mesh_src))
    print("nanite    : {0}".format("ON (requested)" if args.nanite
                                   else "off — alpha-masked foliage"))
    print("target    : {0}/{1}".format(MESH_ROOT, name))
    for t in texs:
        print("    {0:<12} -> {1}".format(t["role"], t["asset"]))
    print("")

    print("--- editor identity gate (conduct rule 7) ---")
    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Nothing imported.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        source = PAYLOAD.format(job=json.dumps(job), marker=MARKER)
        if ".py" in source:
            print("REFUSE: payload names a .py file (transport trap).")
            return 1
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(source, unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            res = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:                       # noqa: BLE001
                pass

        if res is None:
            print("FAIL: the import payload returned nothing.")
            return 4

        bad = 0
        for t in res.get("textures") or []:
            wrong = t.get("wrong") or []
            ok = not wrong and "error" not in t
            print("  {0:<44} {1:<10} {2}".format(
                t["asset"].rsplit("/", 1)[-1], t["role"],
                "ok" if ok else "FAIL {0}".format(wrong or t.get("error"))))
            bad += 0 if ok else 1

        m = res.get("mesh") or {}
        print("")
        print("--- mesh, read back from the asset ---")
        print("  asset        : {0}".format(m.get("asset")))
        print("  triangles    : {0}".format(m.get("triangles")))
        print("  LODs         : {0}".format(m.get("lods")))
        print("  nanite       : {0}{1}".format(
            m.get("nanite_enabled"),
            "  (READ FAILED: {0})".format(m["nanite_read_error"])
            if m.get("nanite_read_error") else ""))
        print("  slots        : {0}".format(m.get("material_slots")))
        print("  bounds       : {0} m".format(m.get("bounds_size_m")))
        print("  pivot offset : {0} m horizontal, {1} m below base{2}"
              .format(m.get("pivot_offset_xy_m"),
                      m.get("base_offset_z_m"),
                      "  (READ FAILED: {0})".format(m["pivot_read_error"])
                      if m.get("pivot_read_error") else ""))

        if res.get("error"):
            print("")
            print("FAIL at stage {0}: {1}".format(res.get("stage"),
                                                  res["error"]))
            return 4
        if m.get("nanite_enabled") is None and not m.get(
                "nanite_read_error"):
            print("")
            print("FAIL: nanite state could not be established.")
            return 4
        if bool(m.get("nanite_enabled")) != bool(args.nanite):
            print("")
            print("FAIL: nanite is {0} but {1} was requested. The asset "
                  "and the recipe disagree.".format(
                      m.get("nanite_enabled"), args.nanite))
            return 4
        if bad:
            print("")
            print("FAIL: {0} texture(s) did not verify.".format(bad))
            return 4
        if args.normalized:
            # The normalisation was verified in Blender; this checks it
            # SURVIVED the FBX round-trip and UE's own import transform,
            # which is a different instrument reading the same quantity
            # (lesson 15.1). A metre of tolerance is generous — the
            # defect being guarded against was 12.41 m.
            #
            # DEGENERATE BOUNDS FIRST: UStaticMesh::CalculateExtendedBounds
            # falls back to FBoxSphereBounds(ForceInit) — all zeros — when
            # neither the mesh description cache nor render data exists, so
            # a bounds read of an empty/unbuilt mesh yields pivot offset
            # 0.0 and would pass the gate exactly when the import produced
            # nothing measurable (lesson: fail closed).
            size = m.get("bounds_size_m") or []
            if (len(size) != 3
                    or not all(isinstance(v, (int, float)) and v == v
                               and v > 0.0 for v in size)):
                print("")
                print("FAIL: --normalized was requested but the read-back "
                      "bounds are degenerate or unreadable ({0}); a zero "
                      "pivot offset over zero geometry proves nothing."
                      .format(size))
                return 4
            want = (norm_row or {}).get("verified_dims_m") \
                or (norm_row or {}).get("dims_m")
            if want and len(want) == 3:
                # Same quantity Blender verified, re-measured by UE.
                # Sorted so an axis permutation from FBX up-axis
                # conversion cannot fake a mismatch; a unit-scale error
                # (m vs cm, the classic FBX silent-wrong) cannot hide.
                pairs = list(zip(sorted(size), sorted(want)))
                if any(abs(a - b) > max(0.05, 0.05 * b)
                       for a, b in pairs):
                    print("")
                    print("FAIL: imported bounds {0} m disagree with the "
                          "Blender-verified dims {1} m — a unit or scale "
                          "error survived the round-trip.".format(
                              size, want))
                    return 4
            off = m.get("pivot_offset_xy_m")
            if off is None:
                print("")
                print("FAIL: --normalized was requested but the pivot "
                      "could not be read back, so the fix is unproven.")
                return 4
            # `not (off <= limit)`, NOT `off > limit`: NaN compares False
            # both ways, and `off > limit` would let NaN PASS the gate
            # (lesson 2.8 — this exact class was fixed three times).
            # The limit is the SHARED constant, not a literal: one copy
            # decides, or this gate drifts from the placement gates
            # (audit F3, 2026-08-02).
            _limit = landscape_spec.MAX_PIVOT_OFFSET_M
            if not isinstance(off, (int, float)) or not (off <= _limit):
                print("")
                print("FAIL: pivot is {0} m from the geometry after "
                      "importing a NORMALISED source. The normalisation "
                      "did not survive the round-trip.".format(off))
                return 4
        elif (m.get("pivot_offset_xy_m") is not None
              and not (m["pivot_offset_xy_m"]
                       <= landscape_spec.MAX_PIVOT_OFFSET_M)):
            print("")
            print("WARNING: pivot is {0} m from the geometry centre. Any "
                  "instance of this asset is displaced by that much and "
                  "random yaw sweeps it around a circle of that radius. "
                  "Do NOT instance this asset; re-import it with "
                  "--normalized.".format(m["pivot_offset_xy_m"]))

        print("")
        print("Imported and verified: {0} triangles, {1} LOD(s), nanite "
              "{2}.".format(m.get("triangles"), m.get("lods"),
                            m.get("nanite_enabled")))
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:                        # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
