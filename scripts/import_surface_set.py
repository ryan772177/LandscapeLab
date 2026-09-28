"""import_surface_set.py — bring a Free/ surface into UE, correctly.

Imports the maps of one or more manifest surfaces as Texture2D assets
with per-ROLE settings, and verifies every setting by READ-BACK before
claiming success.

WHY PER-ROLE SETTINGS ARE THE WHOLE JOB
A texture imported with the wrong colour space or compression is not a
loud failure. It renders. `import_layer_textures` already records what
that costs: a stuck sRGB flag darkens a layer by ~57% with a clean
compile, a correct-looking asset and no error anywhere. The same trap
has four more doors here, and each is silent:

  color         sRGB TRUE. Photogrammetry albedo is authored in sRGB;
                importing it linear washes every surface out.
  normal        sRGB FALSE, TC_NORMALMAP. Normals are vectors, not
                colour. TC_NORMALMAP also selects BC5, which stores
                only X and Y and reconstructs Z — so it must never be
                applied to anything that is not a tangent-space normal.
  roughness     sRGB FALSE. A gamma curve on a scalar map is a silent
                remap of the whole gloss range.
  displacement  sRGB FALSE, and 16-bit source, so no block compression:
                banding in displacement becomes terracing in geometry.
  ambient-occ   sRGB FALSE.

THE NORMAL CONVENTION IS DX, RULING 1 (2026-08-02). The DX map is
consumed directly and there is no green-channel flip anywhere in this
pipeline. The GL variant ships and is ignored. Do not add a flip
"to be safe" — a double flip is invisible on flat ground and inverts
every slope, which reads as bad lighting rather than as a bug.

Paths come from Free/manifest.json, never from a glob, so the recipe
names a surface id and the manifest decides which file is the normal.
One source of truth for roles (lesson 1.9).

Exit codes:
  0  imported and every setting verified by read-back
  1  unexpected error / bad arguments
  2  manifest or a source file missing
  3  editor identity gate refused (conduct rule 7)
  4  import failed, or a setting did not read back as set
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402
import texture_16bit      # noqa: E402 — shared 16-bit conversion (non-negotiable 4a)

REPO_ROOT = bootstrap.REPO_ROOT
FREE_DIR = os.path.join(REPO_ROOT, "Free")
MANIFEST = os.path.join(FREE_DIR, "manifest.json")
DEST_ROOT = "/Game/Surfaces"
MARKER = "__LANDSCAPELAB_SURFACE__"

# role -> (asset suffix, settings that must read back exactly)
ROLE_SETTINGS = {
    "color": ("C", {
        "srgb": True,
        "compression_settings": "TC_Default",
        "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP",
    }),
    "normal": ("N", {
        "srgb": False,
        "compression_settings": "TC_Normalmap",
        "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP",
    }),
    "roughness": ("R", {
        "srgb": False,
        "compression_settings": "TC_Masks",
        "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP",
    }),
    "ambient-occlusion": ("AO", {
        "srgb": False,
        "compression_settings": "TC_Masks",
        "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP",
    }),
    "displacement": ("D", {
        "srgb": False,
        "compression_settings": "TC_Grayscale",
        "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP",
    }),
}

# `displacement` added 2026-08-03 for Pass 2a (HeightLerp needs a height
# map per surface). Safe to default ONLY because texture_16bit now runs on
# this path: every ambientCG Displacement is 16-bit single-channel grey,
# which is the exact shape of both known 16-bit defects.
DEFAULT_ROLES = ("color", "normal", "roughness", "displacement")


def load_manifest():
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve(manifest, surface_id, roles):
    """[(role, abs source path, asset path)] for one surface."""
    for a in manifest["assets"]:
        if a["id"] != surface_id:
            continue
        by_role = {}
        for f in a["files"]:
            by_role.setdefault(f["role"], f["path"])
        out = []
        for role in roles:
            if role not in by_role:
                continue
            src = os.path.join(FREE_DIR, by_role[role].replace("/", os.sep))
            if not os.path.isfile(src):
                raise FileNotFoundError(src)
            suffix, _ = ROLE_SETTINGS[role]
            out.append((role, src.replace("\\", "/"),
                        "{0}/T_{1}_{2}".format(DEST_ROOT, surface_id,
                                               suffix)))
        if not out:
            raise ValueError(
                "surface {0!r} has none of the requested roles {1}"
                .format(surface_id, list(roles)))
        return a, out
    raise KeyError("no asset {0!r} in the manifest".format(surface_id))


PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "stage": "start", "textures": []}}
_jobs = _json.loads({jobs!r})

try:
    _tools = _unreal.AssetToolsHelpers.get_asset_tools()
    for _j in _jobs:
        _row = {{"asset": _j["asset"], "role": _j["role"]}}
        _out["stage"] = "import:" + _j["asset"]

        _task = _unreal.AssetImportTask()
        _task.set_editor_property("filename", _j["src"])
        _task.set_editor_property("destination_path",
                                  _j["asset"].rsplit("/", 1)[0])
        _task.set_editor_property("destination_name",
                                  _j["asset"].rsplit("/", 1)[1])
        _task.set_editor_property("automated", True)
        _task.set_editor_property("replace_existing", True)
        _task.set_editor_property("save", False)
        _tools.import_asset_tasks([_task])

        _tex = _unreal.EditorAssetLibrary.load_asset(_j["asset"])
        if _tex is None:
            _row["error"] = "import produced no asset"
            _out["textures"].append(_row)
            continue

        for _k, _v in _j["settings"].items():
            if isinstance(_v, bool):
                _tex.set_editor_property(_k, _v)
            elif _k == "compression_settings":
                _tex.set_editor_property(
                    _k, getattr(_unreal.TextureCompressionSettings,
                                _v.upper()))
            elif _k == "mip_gen_settings":
                _tex.set_editor_property(
                    _k, getattr(_unreal.TextureMipGenSettings, _v.upper()))

        # READ BACK. A wrong colour space or compression renders without
        # error and looks like art direction, so the setter returning is
        # not evidence (lesson 11.2).
        _bad = []
        _got = {{}}
        for _k, _v in _j["settings"].items():
            _r = _tex.get_editor_property(_k)
            _n = getattr(_r, "name", None)
            _r = _n if _n is not None else _r
            _got[_k] = str(_r)
            if isinstance(_v, bool):
                if bool(_r) != _v:
                    _bad.append(_k)
            elif str(_r).upper() != _v.upper():
                _bad.append(_k)
        _row["settings"] = _got
        _row["wrong"] = _bad

        try:
            _sz = _tex.blueprint_get_built_texture_size()
            _row["built_size"] = [int(_sz.x), int(_sz.y)]
        except Exception as _exc:
            _row["built_size"] = None
            _row["size_error"] = "%s: %s" % (type(_exc).__name__, _exc)

        if not _bad:
            _unreal.EditorAssetLibrary.save_asset(_j["asset"],
                                                  only_if_is_dirty=False)
            _row["saved"] = True
        _out["textures"].append(_row)

    _out["stage"] = "done"
    _out["ok"] = all(not _t.get("wrong") and "error" not in _t
                     for _t in _out["textures"])
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
    p.add_argument("surfaces", nargs="+",
                   help="manifest ids, e.g. Snow006 Rock026 Ground037")
    p.add_argument("--roles", default=",".join(DEFAULT_ROLES),
                   help="comma-separated roles to import")
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    unknown = [r for r in roles if r not in ROLE_SETTINGS]
    if unknown:
        print("REFUSE: unknown role(s) {0}; known: {1}".format(
            unknown, sorted(ROLE_SETTINGS)))
        return 1

    try:
        manifest = load_manifest()
    except (OSError, ValueError) as exc:
        print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
        return 2

    jobs = []
    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("destination: {0}".format(DEST_ROOT))
    print("")
    for sid in args.surfaces:
        try:
            asset, items = resolve(manifest, sid, roles)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            print("REFUSE: {0}: {1}".format(type(exc).__name__, exc))
            return 2
        tile = asset.get("surface_tile_m")
        src = asset.get("surface_tile_m_source", "-")
        print("  {0:<12} tile {1} m ({2})  normals {3}".format(
            sid, tile, src, asset.get("normal_convention")))
        for role, srcpath, assetpath in items:
            suffix, settings = ROLE_SETTINGS[role]
            print("      {0:<18} -> {1}".format(role, assetpath))
            jobs.append({"role": role, "src": srcpath,
                         "asset": assetpath, "settings": settings,
                         "stem": "{0}_{1}".format(sid, role)})
    print("")

    # ------------------------------------------------------------------
    # 16-bit source conversion. Runs BEFORE the editor gate, so a bad
    # conversion costs no editor contact at all.
    #
    # This importer had NO 16-bit handling until 2026-08-03, while the
    # equivalent fix had existed in import_static_mesh.py for two
    # sessions. That is the same trap class in a SECOND tool, which
    # CLAUDE.md non-negotiable 4a promotes to shared infrastructure on
    # the spot. Hence `texture_16bit`, and hence NO local copy here:
    # a re-implementation of this logic is itself the defect now.
    #
    # Measured on this vendor's output, all five surfaces:
    #   Color / Roughness / AO   8-bit  -> untouched
    #   NormalDX / NormalGL     16-bit RGB -> untouched (see below)
    #   Displacement            16-bit GREY -> CONVERTED
    #
    # RGB 16-bit is deliberately NOT in DEFECT_MODES. It is a different
    # code path (TC_Normalmap / BC5) and has never been shown to fail
    # here; converting it on suspicion would be a change with no
    # evidence behind it. It is an open BACKLOG question, not a defect
    # and not a clearance.
    # ------------------------------------------------------------------
    print("--- 16-bit source conversion (shared: scripts/texture_16bit.py) ---")
    stage_dir = os.path.join(FREE_DIR, "_normalized", "textures")
    converted = 0
    try:
        for job in jobs:
            res = texture_16bit.stage_8bit(
                job["src"], job["stem"], stage_dir, role=job["role"])
            if res["converted"]:
                job["src"] = res["src"]
                converted += 1
    except texture_16bit.TextureConversionError as exc:
        print("REFUSE: {0}".format(exc))
        print("Nothing imported; the editor was never contacted.")
        return 2
    print("  {0} of {1} sources converted; {2} already 8-bit or "
          "uninspectable".format(converted, len(jobs), len(jobs) - converted))
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

        source = PAYLOAD.format(jobs=json.dumps(jobs), marker=MARKER)
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
            except Exception:                        # noqa: BLE001
                pass

        if res is None:
            print("FAIL: the import payload returned nothing.")
            return 4

        print("--- imported, verified by read-back ---")
        bad = 0
        for t in res.get("textures") or []:
            wrong = t.get("wrong") or []
            status = "ok" if not wrong and "error" not in t else "FAIL"
            print("  {0:<34} {1:<6} {2}  size {3}".format(
                t["asset"].rsplit("/", 1)[-1], t["role"], status,
                t.get("built_size")))
            for k, v in sorted((t.get("settings") or {}).items()):
                flag = "  <-- WRONG" if k in wrong else ""
                print("      {0:<24} {1}{2}".format(k, v, flag))
            if t.get("error"):
                print("      error: {0}".format(t["error"]))
            if wrong or t.get("error"):
                bad += 1

        if res.get("error"):
            print("")
            print("FAIL at stage {0}: {1}".format(res.get("stage"),
                                                  res["error"]))
            return 4
        if bad:
            print("")
            print("FAIL: {0} texture(s) did not read back as set. They were "
                  "NOT saved. A wrong colour space or compression renders "
                  "cleanly and looks like art direction.".format(bad))
            return 4

        print("")
        print("All {0} textures imported and VERIFIED by read-back."
              .format(len(res.get("textures") or [])))
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
