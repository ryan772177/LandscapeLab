"""verify_texture_source.py — prove which FILE an imported texture came from.

R3 rules that for anything texture-driven, a settings read-back is NOT
sufficient proof: settings read-backs passed for two sessions while the
grass was invisible. This is not a render, so it is not that proof
either. It answers one narrower question that a settings read-back
CANNOT, and that the grass defect turned on:

    did the engine ingest the STAGED 8-BIT DERIVATIVE, or the 16-BIT
    ORIGINAL?

`import_surface_set.py` substitutes `job["src"]` with the staged copy
before importing. If that substitution ever silently fails — a path that
does not round-trip, a task that re-resolves the source, a reimport
triggered later from the original — every downstream check still passes:
the asset exists, its dimensions are right, its compression settings read
back exactly as specified, and its data is quietly the thing the
conversion existed to avoid.

So this reads `AssetImportData`'s recorded source filename off the asset
in the LIVE EDITOR and asserts it ends in `_8bit.png`. Different
instrument, different failure mode, and it is cheap.

WHAT THIS DOES NOT PROVE, stated so nobody promotes it:
  - It does NOT prove the pixels are correct. It proves provenance.
  - It does NOT prove TC_Grayscale decodes I;16 correctly — that
    question is now MOOT for these assets, because nothing 16-bit is
    being handed to it any more. That is the point of the conversion.
  - The sufficient proof for the surface reading correctly is a RENDER,
    and it arrives when the material samples the map (Pass 2a).

Exit codes:
  0  every requested asset traces to an _8bit.png source
  2  editor gate refused, or an asset is missing
  4  an asset traces to something other than the staged derivative
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_TEXSRC__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"rows": [], "error": None}}
try:
    for _path in _json.loads({paths!r}):
        _row = {{"asset": _path, "exists": False, "sources": [],
                 "width": None, "height": None, "compression": None}}
        if _unreal.EditorAssetLibrary.does_asset_exist(_path):
            _row["exists"] = True
            _t = _unreal.EditorAssetLibrary.load_asset(_path)
            try:
                _row["width"] = int(_t.blueprint_get_size_x())
                _row["height"] = int(_t.blueprint_get_size_y())
            except Exception:
                pass
            try:
                _row["compression"] = str(
                    _t.get_editor_property("compression_settings"))
            except Exception:
                pass
            # AssetImportData records the file the import actually read.
            try:
                _aid = _t.get_editor_property("asset_import_data")
                for _f in _aid.extract_filenames():
                    _row["sources"].append(str(_f))
            except Exception as _e:
                _row["sources"] = ["<unreadable: {{0}}>".format(_e)]
        _out["rows"].append(_row)
except Exception as _e:
    _out["error"] = str(_e)[:300]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    """Same shape as probe_texture_api._parse — raw_decode after the marker.

    `run_command` returns output as a LIST of log records, not a string.
    `bootstrap._collect_output` is the one place that knows how to
    flatten it; reimplementing that here is exactly the duplicated-helper
    pattern non-negotiable 4a rejects.
    """
    i = (text or "").find(MARKER)
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
        return bootstrap._collect_output(r)
    except Exception as exc:
        print("  errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("assets", nargs="+",
                    help="/Game/... texture asset paths")
    ap.add_argument("--expect-suffix", default="_8bit.png",
                    help="the source filename suffix that must match")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("expecting source files ending: {0}".format(args.expect_suffix))
    print("")

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
        out = _run(remote_exec, remote, node["node_id"],
                   PAYLOAD.format(paths=json.dumps(args.assets),
                                  marker=MARKER))
    finally:
        remote.stop()

    data = _parse(out)
    if data is None:
        print("REFUSE: no parseable result from the editor.")
        print(out[:1200])
        return 2
    if data.get("error"):
        print("REFUSE: editor-side error: {0}".format(data["error"]))
        return 2

    bad, missing = [], []
    for row in data["rows"]:
        if not row["exists"]:
            missing.append(row["asset"])
            print("  MISSING   {0}".format(row["asset"]))
            continue
        srcs = row["sources"]
        ok = bool(srcs) and all(
            s.lower().endswith(args.expect_suffix.lower()) for s in srcs)
        print("  {0} {1}".format("TRACES OK " if ok else "WRONG SRC ",
                                 row["asset"]))
        print("      size {0}x{1}  {2}".format(
            row["width"], row["height"], row["compression"]))
        for s in srcs:
            print("      source: {0}".format(s))
        if not ok:
            bad.append(row["asset"])

    print("")
    if missing:
        print("REFUSE: {0} asset(s) not present in the editor.".format(
            len(missing)))
        return 2
    if bad:
        print("REFUSE: {0} asset(s) did NOT come from the staged 8-bit "
              "derivative. The conversion ran and did not take effect, "
              "which is the failure a settings read-back cannot see."
              .format(len(bad)))
        return 4

    print("All {0} asset(s) trace to a {1} source.".format(
        len(data["rows"]), args.expect_suffix))
    print("")
    print("This proves PROVENANCE, not pixels. The sufficient proof that")
    print("the surface reads correctly is a RENDER, and it arrives when")
    print("the material samples these maps (Pass 2a).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
