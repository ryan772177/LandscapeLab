"""import_layer_textures.py — import recipe layer textures into the project.

Reads every `material.layers[].texture` in the recipe, imports the
repo-relative PNG find-or-create (hard rule 3) to the deterministic content
path from landscape_spec.texture_asset_path, configures it, and then READS
EVERY SETTING BACK and refuses if any disagrees.

WHY THE READ-BACK IS THE POINT
------------------------------
These textures are linear multiplicative variation maps (schema v1.2
texture datum). If `srgb` is left True, byte 128 decodes as 0.216 instead
of 0.502 and every textured layer darkens by ~57% — with a clean compile,
no error, and nothing wrong-looking in the texture asset itself. That is
the silent-wrong class (lesson 6.2): the call succeeded, the value landed,
the meaning was different.

So this script does not trust that set_editor_property took effect. It
sets, reads back, compares, and exits non-zero on any mismatch. "Set
without verification" and "verified" are different states and only one of
them is allowed downstream.

Settings applied, and why:
  srgb                False   linear multiplier, not colour (see above)
  compression_settings TC_BC7 multiplier maps band worse than albedo under
                             DXT1; BC7 is ~1 MB per 1024^2 with mips, which
                             is nothing for three textures
  address_x/address_y TA_WRAP the maps tile; CLAMP would smear the edge
                             texel across the whole terrain
  lod_group    TEXTUREGROUP_WORLD  standard terrain-surface streaming

Exit codes:
  0  every texture imported and VERIFIED
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or invalid
  3  editor identity gate refused (conduct rule 7)
  4  import failed in the editor
  5  a setting failed read-back verification (nothing downstream may run)
  6  a declared source file is missing on disk
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import import_heightmap   # noqa: E402 — shared recipe validation
import landscape_spec     # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
MARKER = "__LANDSCAPELAB_TEXIMPORT__"

# name -> (expected value as read back, human description)
EXPECTED = {
    "detail": {
        "srgb": (False, "linear multiplier, not colour"),
        "compression_settings": ("TC_BC7",
                                 "low banding on multiplier maps"),
        "address_x": ("TA_WRAP", "textures tile"),
        "address_y": ("TA_WRAP", "textures tile"),
    },
    # A weight map is DATA. Block compression mixes neighbouring texels
    # across channels, which here means bleeding one LAYER into another at
    # every boundary, and wrapping would fold the far edge of the terrain
    # back over the near one.
    "weightmap": {
        "srgb": (False, "layer weights, not colour"),
        "compression_settings": ("TC_VECTOR_DISPLACEMENTMAP",
                                 "uncompressed; a block compressor would "
                                 "bleed one layer into another"),
        "address_x": ("TA_CLAMP", "maps 1:1 onto the terrain, never tiles"),
        "address_y": ("TA_CLAMP", "maps 1:1 onto the terrain, never tiles"),
        "mip_gen_settings": ("TMGS_SIMPLE_AVERAGE",
                             "box average is the only mip filter that "
                             "preserves sum(weights)=1; NO_MIPMAPS aliased "
                             "the 8129^2 mask into ~1 m blocks (Brief 7 P1)"),
    },
}


def plan(recipe):
    """Recipe -> list of import jobs. No editor contact."""
    biome = recipe["biome_id"]
    jobs, missing = [], []
    for layer in recipe["material"]["layers"]:
        src = layer.get("texture")
        if not src:
            continue
        # Recipe validation already rejected absolute paths and '..'
        # segments (conduct rule 1); this resolves and re-checks
        # containment rather than assuming the earlier check held.
        abs_src = os.path.realpath(os.path.join(REPO_ROOT, src))
        if os.path.commonpath([abs_src, os.path.realpath(REPO_ROOT)]) != \
                os.path.realpath(REPO_ROOT):
            missing.append("{0}: texture escapes REPO_ROOT: {1}".format(
                layer["name"], src))
            continue
        if not os.path.isfile(abs_src):
            missing.append("{0}: texture source not found: {1}".format(
                layer["name"], src))
            continue
        # Authoritative dimensions come from the PNG header on disk, NOT
        # from the engine. See the note on blueprint_get_size_x below.
        try:
            w, h, depth, colour = import_heightmap._read_png_header(abs_src)
        except (ValueError, OSError) as exc:
            missing.append("{0}: unreadable PNG {1}: {2}".format(
                layer["name"], src, exc))
            continue
        if depth != 8 or colour != 2:
            missing.append(
                "{0}: {1} must be 8-bit RGB (PNG colour type 2), got "
                "bit depth {2} colour type {3}".format(
                    layer["name"], src, depth, colour))
            continue
        if w != h or w < 16 or (w & (w - 1)) != 0:
            missing.append(
                "{0}: {1} must be square and a power of two, got "
                "{2}x{3}".format(layer["name"], src, w, h))
            continue
        jobs.append({
            "layer": layer["name"],
            "source": abs_src.replace("\\", "/"),
            "asset": landscape_spec.texture_asset_path(biome, layer["name"]),
            "src_size": [w, h],
            "kind": "detail",
        })

    # The baked layer weightmap (schema v1.3). Different settings from a
    # detail texture, and the differences are load-bearing:
    #   * UNCOMPRESSED (TC_VectorDisplacementmap). A block compressor mixes
    #     neighbouring texels across channels, which here means bleeding
    #     one LAYER into another at every boundary. Detail textures can
    #     absorb that; a weight map cannot.
    #   * TA_CLAMP, not WRAP. It maps one-to-one onto the terrain footprint
    #     and is never tiled; wrapping would fold the far edge back over
    #     the near one.
    #   * srgb=False, like the detail maps - these are weights, not colour.
    wm = (recipe.get("material") or {}).get("weightmap")
    if wm:
        abs_wm = os.path.realpath(os.path.join(REPO_ROOT, wm))
        if os.path.commonpath([abs_wm, os.path.realpath(REPO_ROOT)]) != \
                os.path.realpath(REPO_ROOT):
            missing.append("weightmap escapes REPO_ROOT: {0}".format(wm))
        elif not os.path.isfile(abs_wm):
            missing.append("weightmap not found: {0} — run the "
                           "make_layer_weightmap script".format(wm))
        else:
            try:
                w, h, depth, colour = import_heightmap._read_png_header(
                    abs_wm)
            except (ValueError, OSError) as exc:
                missing.append("unreadable weightmap {0}: {1}".format(
                    wm, exc))
            else:
                # Colour type 2 = RGB, 6 = RGBA. RGBA ADMITTED 2026-09-11
                # (schema v1.25): the alpha channel carries the
                # CANOPY-derived forest_floor weight that the material's
                # forest_floor driver "weightmap_alpha" reads. Refusing
                # it would have refused the very map the feature needs --
                # but the refusal is NARROWED, not dropped: 8-bit and
                # square still hold, and a 4-channel map is accepted only
                # because a consumer for the 4th channel now exists.
                if depth != 8 or colour not in (2, 6):
                    missing.append(
                        "weightmap {0} must be 8-bit RGB or RGBA, got "
                        "depth {1} colour type {2}".format(wm, depth,
                                                           colour))
                elif w != h:
                    missing.append(
                        "weightmap {0} must be square, got {1}x{2}".format(
                            wm, w, h))
                else:
                    jobs.append({
                        "layer": "_weightmap",
                        "source": abs_wm.replace("\\", "/"),
                        "asset": landscape_spec.weightmap_asset_path(biome),
                        "src_size": [w, h],
                        "kind": "weightmap",
                    })

    # The sub-surface SELECTOR map (schema v1.14). Same shape and same
    # import settings as the weightmap by design — 8-bit RGB, square, one
    # channel per layer in recipe order, srgb=False. They are read by the
    # same material at the same UVs, and a reader who understands one
    # should not have to learn a second convention.
    #
    # OPTIONAL, and its absence is NOT an error: a biome may declare no
    # sub-surfaces at all. Absence is reported, never defaulted.
    vm = (recipe.get("material") or {}).get("variant_map")
    if vm:
        abs_vm = os.path.realpath(os.path.join(REPO_ROOT, vm))
        if os.path.commonpath([abs_vm, os.path.realpath(REPO_ROOT)]) != \
                os.path.realpath(REPO_ROOT):
            missing.append("variant_map escapes REPO_ROOT: {0}".format(vm))
        elif not os.path.isfile(abs_vm):
            missing.append("variant_map not found: {0} — run "
                           "scripts/make_variant_map.py".format(vm))
        else:
            try:
                w, h, depth, colour = import_heightmap._read_png_header(
                    abs_vm)
            except (ValueError, OSError) as exc:
                missing.append("unreadable variant_map {0}: {1}".format(
                    vm, exc))
            else:
                if depth != 8 or colour != 2:
                    missing.append(
                        "variant_map {0} must be 8-bit RGB, got depth {1} "
                        "colour type {2}".format(vm, depth, colour))
                elif w != h:
                    missing.append(
                        "variant_map {0} must be square, got {1}x{2}"
                        .format(vm, w, h))
                else:
                    jobs.append({
                        "layer": "_variantmap",
                        "source": abs_vm.replace("\\", "/"),
                        "asset": landscape_spec.variant_map_asset_path(
                            biome),
                        "src_size": [w, h],
                        "kind": "weightmap",
                    })
    # The km-scale MACRO VARIATION map (schema v1.19). Clamped 1:1 like
    # the weightmap -- a wrapped macro map would repeat ~3x across the
    # terrain and reintroduce the very tiling it exists to break up.
    # TC_BC7 (not uncompressed): this is a smooth low-frequency signal
    # where banding matters and channel bleed does not.
    mv = (recipe.get("material") or {}).get("macro_variation")
    if mv:
        rel = "textures/{0}_macro.png".format(recipe["biome_id"])
        abs_mv = os.path.realpath(os.path.join(REPO_ROOT, rel))
        if not os.path.isfile(abs_mv):
            missing.append("macro variation map not found: {0} — run the "
                           "macro variation bake first".format(rel))
        else:
            try:
                w, h, depth, colour = import_heightmap._read_png_header(
                    abs_mv)
            except (ValueError, OSError) as exc:
                missing.append("unreadable macro map {0}: {1}".format(
                    rel, exc))
            else:
                if depth != 8 or colour != 2:
                    missing.append(
                        "macro map {0} must be 8-bit RGB, got depth {1} "
                        "colour type {2}".format(rel, depth, colour))
                else:
                    jobs.append({
                        "layer": "_macromap",
                        "source": abs_mv.replace("\\", "/"),
                        "asset": landscape_spec.macro_map_asset_path(biome),
                        "src_size": [w, h],
                        "kind": "detail",
                    })
    return jobs, missing


def _payload(jobs):
    return '''
import json as _json
import os as _os
import unreal as _unreal

_jobs = _json.loads({jobs!r})
_out = {{"results": []}}

_at = _unreal.AssetToolsHelpers.get_asset_tools()

for _j in _jobs:
    _r = {{"layer": _j["layer"], "asset": _j["asset"],
          "imported": False, "settings": {{}}, "error": None}}
    try:
        _pkg, _name = _j["asset"].rsplit("/", 1)

        _task = _unreal.AssetImportTask()
        _task.set_editor_property("filename", _j["source"])
        _task.set_editor_property("destination_path", _pkg)
        _task.set_editor_property("destination_name", _name)
        _task.set_editor_property("automated", True)
        _task.set_editor_property("replace_existing", True)
        _task.set_editor_property("save", False)
        _at.import_asset_tasks([_task])

        _tex = _unreal.EditorAssetLibrary.load_asset(_j["asset"])
        if _tex is None:
            _r["error"] = "import produced no asset at " + _j["asset"]
            _out["results"].append(_r)
            continue
        _r["imported"] = True
        _r["class"] = type(_tex).__name__

        _is_wm = (_j.get("kind") == "weightmap")
        # The mip fix applies to the TRUE weightmap only. The variant/selector
        # map shares kind=="weightmap" but layer=="_variantmap"; box-averaging
        # a discrete selector across mips is a separate, unruled question, so
        # it keeps its existing (default) mip behaviour here.
        _is_true_wm = (_j.get("layer") == "_weightmap")
        _tex.set_editor_property("srgb", False)
        _tex.set_editor_property(
            "compression_settings",
            _unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP
            if _is_wm else _unreal.TextureCompressionSettings.TC_BC7)
        _addr = (_unreal.TextureAddress.TA_CLAMP if _is_wm
                 else _unreal.TextureAddress.TA_WRAP)
        _tex.set_editor_property("address_x", _addr)
        _tex.set_editor_property("address_y", _addr)
        _tex.set_editor_property(
            "lod_group", _unreal.TextureGroup.TEXTUREGROUP_WORLD)

        if _is_true_wm:
            # MIP FILTER = SIMPLE_AVERAGE (box). Brief 7 P1 ruling (Ryan
            # 2026-09-24): the weightmap defaulted to NO_MIPMAPS, and an
            # 8129^2 mask with no mip chain aliases into ~1 m blocks under
            # minification at distance (research/brief7/p1_block_diff.md).
            # A box average is the ONLY mip filter that preserves the
            # per-texel weight partition (sum(weights)=1): mip = average, and
            # average is linear, so sum-of-averages == average-of-sums. Any
            # sharpening filter (FROM_TEXTURE_GROUP's sharpen kernels) breaks
            # the partition and rings at layer boundaries -- the CPU invariant
            # check_weightmap_mip_partition.py holds the <=1e-3 drift bound.
            _tex.set_editor_property(
                "mip_gen_settings",
                _unreal.TextureMipGenSettings.TMGS_SIMPLE_AVERAGE)

        # READ BACK. Enum reads come back as enum objects, so compare on
        # .name; a str() would render "TextureAddress.TA_WRAP" and a
        # naive equality check against "TA_WRAP" would fail for the wrong
        # reason and look like a real mismatch.
        def _rb(_prop):
            _v = _tex.get_editor_property(_prop)
            _n = getattr(_v, "name", None)
            return _n if _n is not None else _v

        for _p in ("srgb", "compression_settings",
                   "address_x", "address_y"):
            _r["settings"][_p] = _rb(_p)
        _r["settings"]["lod_group"] = _rb("lod_group")
        # blueprint_get_size_x/y report the size of the currently RESIDENT
        # streamed mip, NOT the asset's dimensions. A freshly imported
        # 1024^2 texture that nothing is rendering reports 32x32 here.
        # Recorded as "resident_mip" so nobody reads it as the import
        # having silently downsampled - the authoritative dimensions are
        # taken from the PNG header on disk, before import.
        _r["resident_mip"] = [_tex.blueprint_get_size_x(),
                              _tex.blueprint_get_size_y()]

        _unreal.EditorAssetLibrary.save_asset(_j["asset"],
                                              only_if_is_dirty=False)

        if _is_true_wm:
            # Read the SETTING back (mip_gen_settings IS reflected); this
            # proves the box filter was applied, not that mips built.
            _r["settings"]["mip_gen_settings"] = _rb("mip_gen_settings")
            # constraint 2: 8129^2 is non-power-of-two. 5.8's mip builder
            # handles NPOT via clamp addressing (TextureCompressorModule.cpp:
            # 1119 GenerateMipChain, :1204 returns MGTAM_Clamp for !bIsPow2),
            # and PowerOfTwoMode (Engine/Classes/Engine/Texture.h:1394)
            # defaults to None, so mips SHOULD generate on D3D12.
            #
            # There is NO reflected per-asset built-mip-count getter in 5.8
            # (UTexture2D::GetNumMips has no UFUNCTION; no Blueprint_GetNumMips
            # exists in Engine/Source; AR tags emit only Dimensions/Format).
            # So mip GENERATION is NOT verifiable from a texture property here
            # -- it is proven by the POST-MERGE ACCEPTANCE RENDER: the tight
            # terrain crop must be smooth at distance. If the crop is STILL
            # blocky, the RHI did not mip the NPOT texture -> set
            # power_of_two_mode = PTM_PadToPowerOfTwo (8192) AND scale the
            # WorldPosition composite UV by 8129/8192 (never Stretch),
            # verifying registration with the Brief 3 skyline-IoU check.
            # (A fake num_mips read that swallowed an AttributeError and passed
            # was REMOVED here -- rule 13. research/brief7/p1_block_diff.md.)
    except Exception as _exc:
        _r["error"] = "{{0}}: {{1}}".format(type(_exc).__name__, _exc)
    _out["results"].append(_r)

print("{marker}" + _json.dumps(_out))
'''.format(jobs=json.dumps(jobs), marker=MARKER)


def _parse(text):
    i = text.find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id, source):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        r = remote.run_command(source, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        if not r or not r.get("success"):
            print("  command failed: {0}".format((r or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(r))
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    errors = import_heightmap._validate_recipe(recipe,
                                               os.path.abspath(args.recipe))
    if errors:
        print("REFUSE: recipe invalid:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    jobs, missing = plan(recipe)
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("Recipe    : {0}".format(os.path.abspath(args.recipe)))
    print("")
    if missing:
        print("REFUSE: declared texture sources unusable:")
        for m in missing:
            print("  - {0}".format(m))
        return 6
    if not jobs:
        print("No layer declares `texture`; nothing to import.")
        return 0

    for j in jobs:
        print("  {0:<8} {1}".format(j["layer"],
                                    os.path.relpath(j["source"], REPO_ROOT)))
        print("           -> {0}".format(j["asset"]))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        r = _run(remote_exec, remote, node["node_id"], _payload(jobs))
        if r is None:
            print("FAIL: import payload returned nothing.")
            return 4

        by_layer = {j["layer"]: j for j in jobs}
        bad, failed = [], []
        for res in r.get("results", []):
            print("  {0}".format(res["asset"]))
            if res.get("error"):
                print("    ERROR: {0}".format(res["error"]))
                failed.append(res["layer"])
                continue
            if not res.get("imported"):
                print("    ERROR: not imported")
                failed.append(res["layer"])
                continue
            src_size = by_layer.get(res["layer"], {}).get("src_size")
            print("    {0}  source {1}x{2} (PNG header, authoritative)"
                  .format(res.get("class"), src_size[0], src_size[1]))
            print("    {0:<22} {1}  (streaming state, NOT the asset size)"
                  .format("resident mip", res.get("resident_mip")))
            kind = by_layer.get(res["layer"], {}).get("kind", "detail")
            for prop, (want, why) in sorted(EXPECTED[kind].items()):
                # mip_gen_settings is set/read-back only for the TRUE weightmap
                # (layer "_weightmap"); the variant/selector map shares
                # kind=="weightmap" but keeps its default mip behaviour, so its
                # settings dict never carries this prop -- skip it there rather
                # than raise a false MISMATCH.
                if prop == "mip_gen_settings" and res["layer"] != "_weightmap":
                    continue
                got = res["settings"].get(prop)
                ok = (got == want)
                print("    {0:<22} {1!r:<12} {2}  ({3})".format(
                    prop, got, "ok" if ok else "MISMATCH", why))
                if not ok:
                    bad.append("{0}.{1}: set {2!r}, read back {3!r}".format(
                        res["layer"], prop, want, got))
            print("    {0:<22} {1!r}".format(
                "lod_group", res["settings"].get("lod_group")))

        if failed:
            print("")
            print("FAIL: import failed for: {0}".format(", ".join(failed)))
            return 4
        if bad:
            print("")
            print("REFUSE: settings did not survive read-back:")
            for b in bad:
                print("  - {0}".format(b))
            print("")
            print("  Nothing downstream may run. An srgb mismatch in "
                  "particular darkens every textured layer by ~57% with a "
                  "clean compile and no visible defect in the asset.")
            return 5

        print("")
        print("All textures imported and VERIFIED by read-back.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
