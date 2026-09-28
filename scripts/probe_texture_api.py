"""probe_texture_api.py — read-only introspection of the texture API surface.

Written for the textures milestone. Its whole purpose is lesson 6.1: the
C++ header is not the binding signature, and the reflected Python surface
is the contract. Rather than guess a property name per attempt and burn
the conduct rule 6 budget two failures at a time (lesson 7.3), this reads
every name the material/texture work needs in ONE pass.

STRICTLY READ-ONLY. It creates no assets, modifies no objects, saves
nothing. It only reads class attribute names and enum members off the
`unreal` module. Safe to re-run at any time.

Exit codes:
  0  probe completed (see output)
  1  unexpected error / bad arguments
  3  editor identity gate refused (conduct rule 7)
  4  probe payload returned nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
MARKER = "__LANDSCAPELAB_PROBE__"

# Classes whose *editor property* names we need, and the substring filter
# that keeps the output readable. An empty filter means "list everything".
TARGETS = [
    ("MaterialExpressionTextureSample", ""),
    ("MaterialExpressionTextureCoordinate", ""),
    ("MaterialExpressionComponentMask", ""),
    ("Texture2D", "srgb|compression|address|mip|lod|filter|group"),
    ("AssetImportTask", ""),
    ("TextureFactory", "create|srgb|compression|mip|lod"),
]

ENUMS = [
    "SamplerSourceMode",
    "MaterialSamplerType",
    "TextureCompressionSettings",
    "TextureAddress",
    "TextureGroup",
    "TextureMipGenSettings",
]


def _payload(targets, enums):
    return '''
import json as _json
import unreal as _unreal

_targets = _json.loads({targets!r})
_enums = _json.loads({enums!r})
_out = {{"classes": {{}}, "enums": {{}}, "missing": [], "funcs": {{}}}}


def _props(_cls):
    """Editor-property names as the Python binding exposes them.

    dir() on a wrapped UClass lists properties and methods together; the
    properties are the non-callable, non-dunder entries. This is the
    reflected surface, which is what set_editor_property() will accept -
    NOT what the C++ header declares.
    """
    _names = []
    for _n in dir(_cls):
        if _n.startswith("_"):
            continue
        try:
            _a = getattr(_cls, _n)
        except Exception:
            continue
        if callable(_a):
            continue
        _names.append(_n)
    return sorted(_names)


for _entry in _targets:
    _name, _filt = _entry[0], _entry[1]
    _cls = getattr(_unreal, _name, None)
    if _cls is None:
        _out["missing"].append(_name)
        continue
    _all = _props(_cls)
    if _filt:
        _terms = _filt.split("|")
        _all = [_p for _p in _all if any(_t in _p for _t in _terms)]
    _out["classes"][_name] = _all

for _name in _enums:
    _e = getattr(_unreal, _name, None)
    if _e is None:
        _out["missing"].append(_name)
        continue
    _out["enums"][_name] = sorted(
        [_n for _n in dir(_e) if not _n.startswith("_")])

# Function-level surface we intend to call. Existence only - presence of a
# name is not proof of its signature, but absence IS proof we must not
# call it (lesson: "unknown" is never "yes").
_mel = getattr(_unreal, "MaterialEditingLibrary", None)
_out["funcs"]["MaterialEditingLibrary"] = sorted(
    [_n for _n in dir(_mel)
     if not _n.startswith("_") and callable(getattr(_mel, _n, None))]
) if _mel is not None else None

_at = _unreal.AssetToolsHelpers.get_asset_tools()
_out["funcs"]["AssetTools_import"] = sorted(
    [_n for _n in dir(_at) if "import" in _n.lower()])

_eal = getattr(_unreal, "EditorAssetLibrary", None)
_out["funcs"]["EditorAssetLibrary_sample"] = sorted(
    [_n for _n in dir(_eal)
     if not _n.startswith("_")
     and any(_k in _n for _k in ("save", "delete", "exist", "load"))]
) if _eal is not None else None

print("{marker}" + _json.dumps(_out))
'''.format(targets=json.dumps(targets), enums=json.dumps(enums),
           marker=MARKER)


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
    p.add_argument("--timeout", type=float, default=6.0)
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("READ-ONLY : creates nothing, saves nothing")
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

        r = _run(remote_exec, remote, node["node_id"],
                 _payload(TARGETS, ENUMS))
        if r is None:
            print("FAIL: probe returned nothing.")
            return 4

        for name, props in sorted(r.get("classes", {}).items()):
            print("=== {0} ({1} properties) ===".format(name, len(props)))
            for chunk in [props[i:i + 4] for i in range(0, len(props), 4)]:
                print("    " + "  ".join("{0:<28}".format(c)
                                         for c in chunk).rstrip())
            print("")

        for name, members in sorted(r.get("enums", {}).items()):
            print("=== enum {0} ===".format(name))
            for chunk in [members[i:i + 4]
                          for i in range(0, len(members), 4)]:
                print("    " + "  ".join("{0:<28}".format(c)
                                         for c in chunk).rstrip())
            print("")

        for name, funcs in sorted(r.get("funcs", {}).items()):
            if funcs is None:
                print("=== {0}: ABSENT ===".format(name))
                continue
            print("=== {0} ({1}) ===".format(name, len(funcs)))
            for chunk in [funcs[i:i + 3] for i in range(0, len(funcs), 3)]:
                print("    " + "  ".join("{0:<36}".format(c)
                                         for c in chunk).rstrip())
            print("")

        if r.get("missing"):
            print("!!! ABSENT FROM THE BINDING: {0}".format(
                ", ".join(r["missing"])))
            print("    Absence is authoritative — do not call these.")
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
