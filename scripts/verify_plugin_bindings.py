"""verify_plugin_bindings.py — does LandscapeLabEditor actually exist in the
running editor, and do its gates refuse?

READ-ONLY. Spawns nothing, imports nothing, saves nothing. It reads a heightmap
header through the plugin and asks the plugin to refuse two bad inputs.

WHY THIS EXISTS AS A SEPARATE STEP

The plugin compiled. That proves the C++ is well-formed and proves nothing
about whether the editor loaded the module or whether the Python bindings were
generated for it. Non-negotiable 17 in its usual shape: the .uplugin records an
INTENT to be enabled by default; only the live editor records what is in
effect.

And a binding that exists is not a gate that works. This project's rule 2 --
"a gate that has only seen good input has not been tested" -- applies to the
resolution check the whole 8129 import depends on. So the run below is three
directions, positive control FIRST:

  A. a real 8129 x 8129 heightmap    -> 8129 x 8129, exit ok
  B. a path that does not exist      -> REFUSE, and 0 x 0 must NOT be returned
                                        as if it were a measurement
  C. a real file at a layout that
     does not tile                   -> REFUSE naming both resolutions

C is checked by asking create_landscape_from_heightmap for a component layout
whose vertex count cannot match the file. It must refuse BEFORE spawning
anything, so the actor count in the level is read before and after and must be
identical -- that is the check that the refusal is a refusal and not a
half-built landscape with an error string attached.

Exit codes:
  0  bindings present, all three directions correct
  1  could not look (no marker, payload exception, transport failure)
  2  bindings absent -- getattr(unreal, "LandscapeLabTools") found no such
     class (module not loaded OR not reflected; this getattr cannot tell which,
     though the payload records module_loaded/exposed for diagnostics)
  3  rule 7: no verified editor node
  4  a gate did not behave: something was admitted that should have been
     refused, or refused that should have been admitted
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_BINDINGS__"

# Build 006 is the canonical 8129 package (CURRENT STATE 2026-08-12). The alias
# is what the import will actually be handed.
GOOD_HEIGHTMAP = (
    r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\006\UE5_Ready\AlpineLabHeight.png"
)
MISSING_HEIGHTMAP = (
    r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\006\UE5_Ready\__no_such_file__.png"
)

EXPECT_W = 8129
EXPECT_H = 8129

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_out = {"error": None}
try:
    _out["level"] = _unreal.EditorLevelLibrary.get_editor_world().get_path_name()

    # ---- Is the module loaded, per the LIVE editor rather than the .uplugin?
    _out["module_loaded"] = bool(
        _unreal.SystemLibrary.is_valid_class(_unreal.load_class(None, "/Script/LandscapeLabEditor.LandscapeLabTools"))
    ) if hasattr(_unreal, "SystemLibrary") else None

    _tools = getattr(_unreal, "LandscapeLabTools", None)
    _out["binding_present"] = _tools is not None
    if _tools is None:
        _out["exposed"] = []
    else:
        _out["exposed"] = sorted(
            n for n in dir(_tools) if not n.startswith("_")
        )

    if _tools is not None:
        # Signature read from the LIVE editor, not from the C++ header:
        #   get_heightmap_resolution(path) -> (out_width, out_height,
        #                                      b_out_success, out_error)
        # next(iter(...), "") not [...][0]: an empty/None docstring splits to []
        # and [0] would IndexError -- caught below and mis-reported as exit 1
        # "could not look" over a binding that is in fact present and functional.
        _out["signature"] = next(iter(
            (_tools.get_heightmap_resolution.__doc__ or "").splitlines()), "")

        # ---- A. positive control: a file we know is 8129 x 8129
        _w, _h, _ok, _err = _tools.get_heightmap_resolution(r"__GOOD__")
        _out["A"] = {"ok": bool(_ok), "w": int(_w), "h": int(_h), "err": _err}

        # ---- B. negative control: a path that is not there
        _w2, _h2, _ok2, _err2 = _tools.get_heightmap_resolution(r"__MISSING__")
        _out["B"] = {"ok": bool(_ok2), "w": int(_w2), "h": int(_h2), "err": _err2}

        # ---- C. the resolution gate, on a layout that cannot tile 8129.
        # 32 x 32 components at 2 x 63 quads = 4033, not 8129. If this spawns
        # anything the refusal is not a refusal.
        _before = len(_unreal.EditorLevelLibrary.get_all_level_actors())
        _land, _err3 = _tools.create_landscape_from_heightmap(
            r"__GOOD__",
            _unreal.Vector(0.0, 0.0, 0.0),
            _unreal.Rotator(0.0, 0.0, 0.0),
            _unreal.Vector(100.0, 100.0, 180.8358),
            2, 63, 32, 32,
            None, 0, "", False, True,
        )
        _after = len(_unreal.EditorLevelLibrary.get_all_level_actors())
        _out["C"] = {
            "landscape_is_none": _land is None,
            "err": _err3,
            "actors_before": _before,
            "actors_after": _after,
        }
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_BINDINGS__" + _json.dumps(_out))
'''


def main() -> int:
    # The two placeholders sit inside r"..." literals in the payload, so the
    # path goes in verbatim. Escaping it here would put doubled separators in
    # the error strings the gates print, which would misreport what was asked
    # for. Neither path ends in a backslash, which is the only case a raw
    # literal cannot carry.
    assert not GOOD_HEIGHTMAP.endswith("\\") and not MISSING_HEIGHTMAP.endswith("\\")
    payload = (PAYLOAD
               .replace("__GOOD__", GOOD_HEIGHTMAP)
               .replace("__MISSING__", MISSING_HEIGHTMAP))

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
            print("NO MARKER — could not look. Raw output follows:")
            print(text[:4000])
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

    print("level                :", d.get("level"))
    print("binding present      :", d.get("binding_present"))
    if not d.get("binding_present"):
        print()
        print("unreal.LandscapeLabTools DOES NOT EXIST in this editor.")
        print("The DLL built, so this is a load/reflection failure, not a compile one.")
        return 2

    print("reflected signature  :", d.get("signature"))
    print()

    failures = []

    a = d.get("A") or {}
    ok_a = a.get("ok") and a.get("w") == EXPECT_W and a.get("h") == EXPECT_H
    print("A  positive control  : ok=%s  %sx%s  err=%r"
          % (a.get("ok"), a.get("w"), a.get("h"), a.get("err")))
    print("   expected          : ok=True  %dx%d" % (EXPECT_W, EXPECT_H))
    if not ok_a:
        failures.append("A: the real 8129 heightmap was not read as 8129x8129")

    b = d.get("B") or {}
    # The refusal must be a refusal AND must not hand back 0 x 0 as a number.
    ok_b = (b.get("ok") is False) and bool(b.get("err"))
    print()
    print("B  missing file      : ok=%s  %sx%s  err=%r"
          % (b.get("ok"), b.get("w"), b.get("h"), b.get("err")))
    print("   expected          : ok=False with a reason (never 0x0 as a measurement)")
    if not ok_b:
        failures.append("B: a missing file was not refused, or was refused without a reason")

    c = d.get("C") or {}
    spawned = (c.get("actors_after") or 0) - (c.get("actors_before") or 0)
    ok_c = (c.get("landscape_is_none") is True
            and bool(c.get("err"))
            and spawned == 0)
    print()
    print("C  4033 layout on an 8129 file")
    print("   landscape is None : %s" % c.get("landscape_is_none"))
    print("   actors spawned    : %d  (before %s, after %s)"
          % (spawned, c.get("actors_before"), c.get("actors_after")))
    print("   err               : %s" % (c.get("err") or "(none)"))
    print("   expected          : None, 0 actors spawned, a reason naming both resolutions")
    if not ok_c:
        failures.append("C: the resolution gate did not refuse cleanly, or it "
                        "spawned %d actor(s) before refusing" % spawned)

    print()
    if failures:
        print("VERDICT: %d of 3 directions WRONG" % len(failures))
        for f in failures:
            print("  -", f)
        return 4

    print("VERDICT: bindings present, all three directions correct.")
    print("The resolution gate refuses BEFORE spawning, which is the property")
    print("the 8129 import depends on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
