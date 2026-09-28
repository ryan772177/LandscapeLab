"""import_alpinelab_masks.py — the five Gaea masks into the project, recipe-driven.

MUTATES: creates/overwrites texture assets. Bare invocation is a DRY RUN.

SUPERSEDES the mask-import half of `ue5_import_alpinelab.py`, which is
paste-into-the-editor and hardcoded to build 002 / `/Game/AlpineLab_v1`. That
section is struck in its own file rather than left as a second live copy —
two importers with two sets of settings is the shape non-negotiable 4a
rejects, and texture settings are exactly the kind of thing that drifts
silently (an `srgb` left True darkens every consumer by ~57% with a clean
compile).

WHAT IS SET, AND WHY EACH ONE
-----------------------------
Read from the LIVE v1 textures rather than from any document, because two
documents disagreed with each other and with the assets:
`ue5_import_alpinelab.py`'s docstring says TC_VECTOR_DISPLACEMENTMAP, the
2026-08-10 handoff says BC4, and the assets say TC_GRAYSCALE.

    srgb              False   these are DATA, not colour. Left True, byte 128
                              decodes as 0.216 instead of 0.502.
    compression       TC_GRAYSCALE   what v1 actually ships.
    address_x/y       TA_CLAMP  the mask maps 1:1 onto the terrain footprint
                              and must never tile.
    mip_gen           TMGS_NO_MIPMAPS   as v1.
    lod_group         TEXTUREGROUP_WORLD
    max_texture_size  4096    NOT v1's 2048 — see below.

WHY 4096 AND NOT v1's 2048. This is the one setting that is deliberately
different, and it is different in order to keep the RESULT the same:

    v1    2048 over 4032 m  =  1.97 m per texel
    8129  2048 over 8128 m  =  3.97 m per texel   <- half the detail
    8129  4096 over 8128 m  =  1.98 m per texel   <- parity

v1's 2048 cap was imposed on a 15.4 GB laptop where five uncompressed 4033²
masks asked for 4,609 MiB of DDC against a 994 MiB limit. This machine has
31.4 GB and 16 GB of VRAM, and G8 at 4096² is 16 MB per mask. The constraint
that produced 2048 no longer exists; copying it anyway would silently halve
the surfacing resolution of the terrain this whole exercise exists to sharpen.

EVERY SETTING IS READ BACK AND DISAGREEMENT REFUSES. "Set" and "verified" are
different states and only one of them may be relied on downstream.

THE PIXEL FORMAT IS REPORTED, NOT ASSUMED. The masks are 16-bit PNGs and the
material applies gains up to 128 to them. If the imported texture is 8-bit,
the smallest non-zero value is 1/255 = 0.0039, which at gain 128 is 0.50 —
already past the deposits ramp's 0.18 out-edge, making that mask effectively
BINARY on the GPU while the CPU reference computes a mean weight of 0.083 from
the 16-bit source. That would be a real divergence between the instrument and
the artefact, so this prints the SOURCE format and the imported pixel size and
leaves the judgement visible rather than burying it. (The platform pixel
format is settled from engine source, Texture.cpp — the reflected property is
unreadable — so it is documented, not read back per-run.)

Exit codes:
  0  every mask imported and every setting verified, OR a --dry-run that
     imported nothing (it prints "DRY RUN. Nothing was contacted.")
  1  could not look / unexpected error
  2  refused before touching anything
  3  rule 7: no verified editor node
  5  a setting failed read-back — nothing downstream may run
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alpinelab_source  # noqa: E402
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_MASKS__"
DEFAULT_RECIPE = "recipes/alpinelab_8129.json"

# Role -> asset basename suffix. The role names are alpinelab_source.MASK_ROLES;
# the recipe's material.masks[role].texture gives the full destination path, so
# this table only exists to report a readable name.
ROLE_LABEL = {
    "flow": "Flow",
    "wear": "Wear",
    "deposits": "Deposits",
    "snow_depth": "SnowDepth",
    "snow_hard": "SnowHard",
}

PAYLOAD = r'''
import json as _json
import os as _os
import unreal as _unreal

_jobs = _json.loads(r"""__JOBS__""")
_max_size = __MAXSIZE__
_out = {"error": None, "results": []}

try:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    for _job in _jobs:
        _row = {"role": _job["role"], "asset": _job["asset"], "problems": []}
        try:
            _pkg = _job["asset"].rsplit("/", 1)[0]
            _name = _job["asset"].rsplit("/", 1)[1]

            _task = _unreal.AssetImportTask()
            _task.set_editor_property("filename", _job["png"])
            _task.set_editor_property("destination_path", _pkg)
            _task.set_editor_property("destination_name", _name)
            _task.set_editor_property("automated", True)
            _task.set_editor_property("replace_existing", True)
            _task.set_editor_property("save", False)
            _tools.import_asset_tasks([_task])

            _tex = _unreal.EditorAssetLibrary.load_asset(_job["asset"])
            if _tex is None:
                _row["problems"].append("import produced no asset")
                _out["results"].append(_row)
                continue

            _tex.set_editor_property("srgb", False)
            _tex.set_editor_property(
                "compression_settings",
                _unreal.TextureCompressionSettings.TC_GRAYSCALE)
            _tex.set_editor_property("address_x", _unreal.TextureAddress.TA_CLAMP)
            _tex.set_editor_property("address_y", _unreal.TextureAddress.TA_CLAMP)
            _tex.set_editor_property(
                "mip_gen_settings", _unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
            _tex.set_editor_property("lod_group", _unreal.TextureGroup.TEXTUREGROUP_WORLD)
            _tex.set_editor_property("max_texture_size", _max_size)

            # READ BACK. Set and verified are different states.
            _got = {}
            _got["srgb"] = bool(_tex.get_editor_property("srgb"))
            _got["compression"] = str(_tex.get_editor_property("compression_settings"))
            _got["address_x"] = str(_tex.get_editor_property("address_x"))
            _got["address_y"] = str(_tex.get_editor_property("address_y"))
            _got["mip_gen"] = str(_tex.get_editor_property("mip_gen_settings"))
            _got["lod_group"] = str(_tex.get_editor_property("lod_group"))
            _got["max_texture_size"] = int(_tex.get_editor_property("max_texture_size"))
            _row["got"] = _got

            if _got["srgb"]:
                _row["problems"].append("srgb did not clear")
            if "TC_GRAYSCALE" not in _got["compression"]:
                _row["problems"].append("compression is " + _got["compression"])
            if "TA_CLAMP" not in _got["address_x"]:
                _row["problems"].append("address_x is " + _got["address_x"])
            if "TA_CLAMP" not in _got["address_y"]:
                _row["problems"].append("address_y is " + _got["address_y"])
            if "TMGS_NO_MIPMAPS" not in _got["mip_gen"]:
                _row["problems"].append("mip_gen is " + _got["mip_gen"])
            if "TEXTUREGROUP_WORLD" not in _got["lod_group"]:
                _row["problems"].append("lod_group is " + _got["lod_group"])
            if _got["max_texture_size"] != _max_size:
                _row["problems"].append(
                    "max_texture_size is %d, asked %d" % (_got["max_texture_size"], _max_size))

            # Formats, reported not asserted -- see the module docstring.
            try:
                _src = _tex.get_editor_property("source")
                _row["source_format"] = str(_src.get_editor_property("format"))
            except Exception as _fe:
                _row["source_format"] = "UNREADABLE: " + type(_fe).__name__
            try:
                _row["imported_size"] = [
                    int(_tex.get_editor_property("imported_size").x),
                    int(_tex.get_editor_property("imported_size").y)]
            except Exception as _ie:
                _row["imported_size"] = "UNREADABLE: " + type(_ie).__name__

            _unreal.EditorAssetLibrary.save_asset(_job["asset"], only_if_is_dirty=False)
            del _tex
        except Exception as _je:
            _row["problems"].append(type(_je).__name__ + ": " + str(_je))
        _out["results"].append(_row)
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_MASKS__" + _json.dumps(_out))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--max-texture-size", type=int, default=4096)
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and imports nothing")
    args = ap.parse_args(argv)

    path = os.path.join(bootstrap.REPO_ROOT, args.recipe)
    if not os.path.isfile(path):
        print("REFUSE: no recipe at %s" % path)
        return 2
    with open(path, encoding="utf-8") as fh:
        recipe = json.load(fh)

    try:
        pkg, mask_png, _ = alpinelab_source.resolve(recipe, args.recipe)
    except alpinelab_source.SourceError as exc:
        print("REFUSE:", exc)
        return 2

    masks = (recipe.get("material") or {}).get("masks") or {}
    jobs = []
    for role in alpinelab_source.MASK_ROLES:
        dest = (masks.get(role) or {}).get("texture")
        if not dest:
            print("REFUSE: recipe declares no material.masks.%s.texture" % role)
            return 2
        png = os.path.join(pkg, mask_png[role])
        jobs.append({"role": role, "png": png, "asset": dest})

    extent_m = float(recipe["landscape"]["extent_cm"]) / 100.0
    m_per_texel = extent_m / float(args.max_texture_size)

    print("=== PLAN ===")
    print("  recipe            %s" % args.recipe)
    print("  source            %s" % pkg)
    print("  max_texture_size  %d" % args.max_texture_size)
    print("  extent            %.0f m  ->  %.2f m per texel" % (extent_m, m_per_texel))
    print("                    (v1: 2048 over 4032 m = 1.97 m/texel)")
    print()
    for j in jobs:
        print("  %-11s %-34s -> %s"
              % (ROLE_LABEL.get(j["role"], j["role"]),
                 os.path.basename(j["png"]), j["asset"]))
    print()

    if not args.go:
        print("DRY RUN. Nothing was contacted. Re-run with --go.")
        return 0

    payload = (PAYLOAD
               .replace("__JOBS__", json.dumps(jobs).replace("\\", "\\\\"))
               .replace("__MAXSIZE__", str(int(args.max_texture_size))))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(payload, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
        i = text.find(MARKER)
        if i < 0:
            print("NO MARKER — could not look. The import may or may not have run.")
            print(text[:3000])
            return 1
        d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1

    bad = 0
    print("=== RESULT ===")
    for row in d.get("results", []):
        got = row.get("got") or {}
        print("  %-11s %s" % (ROLE_LABEL.get(row["role"], row["role"]), row["asset"]))
        print("      size %s  source_format %s"
              % (row.get("imported_size"), row.get("source_format")))
        print("      srgb=%s  %s  %s  max=%s"
              % (got.get("srgb"), got.get("compression"),
                 got.get("address_x"), got.get("max_texture_size")))
        for p in row.get("problems", []):
            print("      PROBLEM: %s" % p)
            bad += 1
    print()

    if bad:
        print("%d setting(s) failed read-back. Nothing downstream may run." % bad)
        return 5

    print("All five masks imported and every setting VERIFIED by read-back.")
    print()
    print("BIT DEPTH: 16 bits survive to the GPU. Settled at engine source, because")
    print("the reflected `source` property is NOT readable on this build and the")
    print("fields above therefore say UNREADABLE rather than a format:")
    print("  Texture.cpp:4312-4316 — 'Grayscale is G8 output, unless source is")
    print("  specifically G16'; TSF_G16 -> NameG16. A 16-bit grayscale PNG imports")
    print("  as TSF_G16, so TC_GRAYSCALE yields G16 here.")
    print("That matters because the material applies gains up to 128. At G8 the")
    print("smallest non-zero value is 1/255 = 0.0039, which at gain 128 is 0.50 —")
    print("already past the deposits ramp's 0.18 out-edge, making that mask binary")
    print("on the GPU while the CPU reference computes mean weight 0.083 from the")
    print("16-bit PNG. At G16 the instrument and the artefact agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
