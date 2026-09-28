"""landscape_nanite_build.py — enable landscape Nanite on the CURRENT level and
BUILD it through the plugin, not through a side effect.

MUTATES actor properties and builds Nanite meshes. Bare invocation is a DRY RUN.

=====================================================================
WHY THIS EXISTS ALONGSIDE enable_landscape_nanite.py
=====================================================================
Two reasons, and the second is the substantive one.

1. `enable_landscape_nanite.py` validates the FULL biome schema
   (heightmap.section_size, sections_per_component, component_count ...). The
   AlpineLab evaluation recipes are deliberately lean and cannot satisfy it.
   Inventing those keys to get past a validator is how a recipe stops
   describing anything.

2. IT BUILDS NANITE BY SIDE EFFECT. Its mechanism is to set
   `landscape.Nanite.LiveRebuildOnModification` so that the property change
   itself triggers a rebuild. That was the only route available when UE 5.8
   exposes no UFUNCTION for `ULandscapeSubsystem::BuildNanite` — and it cannot
   report whether the build finished, only that a modification happened.

   `LandscapeLabEditor` now exposes BuildNanite directly. This calls it.
   The side-effect route is superseded for new work; it is left in place for
   /Game/Alpine, where it is proven.

=====================================================================
WHAT IT SETS, AND WHY THE SKIRT
=====================================================================
    enable_nanite          True on the ALandscape and every streaming proxy
    nanite_skirt_enabled   True
    nanite_skirt_depth     from --skirt-depth

Epic's own guidance: Nanite landscape "does not improve landscape resolution"
-- it buys GPU culling, streaming and LODs, and "generally boosts runtime
performance, especially for demanding features such as VSM". The quality win
comes from tessellation/displacement ON TOP of it, which is why R2's checklist
puts the material first: enabling Nanite before the material buys NO
silhouette, because it renders the same geometry as a Nanite mesh.

THE SKIRT IS NOT COSMETIC HERE. Skirt depth moves additional edge vertices
down to hide gaps between proxy tiles. This landscape has 256 proxies, so it
has an unusually large amount of tile boundary; Epic says seams are "usually
small enough to be corrected by temporal anti-aliasing", which is a statement
about a typical proxy count, not this one.

MEMORY: Epic is explicit that Nanite landscapes stream "twice the amount of
data", because both the Nanite and non-Nanite representations must be
resident. At 1024 components that is the cost to watch, and it is why this
logs free RAM before and after.

Exit codes:
  0  enabled, built, and read back
  1  could not look
  2  refused before touching anything
  3  rule 7: no verified editor node
  5  a property did not read back, or the build reported failure
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_NANITE__"

PAYLOAD = r'''
import json as _json
import unreal as _unreal

_enable = __ENABLE__
_skirt = __SKIRT__
_skirt_depth = __SKIRT_DEPTH__
_do_build = __BUILD__

_out = {"error": None, "level": None, "touched": 0, "unreadable": 0,
        "enabled_after": 0, "skirt_after": 0, "build_called": False,
        "build_ok": None, "build_error": None, "with_mesh": 0}
try:
    _out["level"] = _unreal.EditorLevelLibrary.get_editor_world().get_path_name()
    _actors = [a for a in _unreal.EditorLevelLibrary.get_all_level_actors()
               if isinstance(a, _unreal.LandscapeProxy)]
    for _a in _actors:
        try:
            _a.set_editor_property("enable_nanite", _enable)
            if _skirt:
                _a.set_editor_property("nanite_skirt_enabled", True)
                _a.set_editor_property("nanite_skirt_depth", _skirt_depth)
            _out["touched"] += 1
        except Exception:
            _out["unreadable"] += 1

    # READ BACK before building. A build over actors whose flag did not land
    # would report success and produce nothing.
    for _a in _actors:
        try:
            if bool(_a.get_editor_property("enable_nanite")):
                _out["enabled_after"] += 1
            if bool(_a.get_editor_property("nanite_skirt_enabled")):
                _out["skirt_after"] += 1
        except Exception:
            _out["unreadable"] += 1

    if _do_build and _enable:
        # THE SANCTIONED ROUTE. ULandscapeSubsystem::BuildNanite is
        # LANDSCAPE_API with no UFUNCTION in 5.8; LandscapeLabEditor wraps it.
        _ok, _err = _unreal.LandscapeLabTools.build_landscape_nanite(True)
        _out["build_called"] = True
        _out["build_ok"] = bool(_ok)
        _out["build_error"] = _err or None

        # Did a mesh actually appear? A different question than "did the call
        # return" -- non-negotiable 8.
        #
        # ACCESSOR CORRECTED 2026-08-13, and the old one did not raise -- it
        # returned a confident ZERO. The singular
        # get_component_by_class(LandscapeNaniteComponent) + get_static_mesh()
        # read 0 of 256 on a world whose SAVED PACKAGES held 256 Nanite meshes
        # (3.03 GB across 256 external actor packages). The plural form plus the
        # reflected `static_mesh` property -- which verify_cold_boot.py:52-61 has
        # used correctly all along -- reads 256/256 on the same world in the same
        # state. Non-negotiable 23: an API remembered is an API guessed, and the
        # dangerous case is the guess that ANSWERS.
        #
        # This mattered: the exit-5 gate below reads "the build returned success
        # and NO proxy has a built Nanite mesh ... treat the build as NOT done",
        # so the wrong accessor turns a COMPLETED build into a reported failure.
        for _a in _actors:
            try:
                for _c in list(_a.get_components_by_class(
                        _unreal.LandscapeNaniteComponent)):
                    if _c.get_editor_property("static_mesh") is not None:
                        _out["with_mesh"] += 1
                        break
            except Exception:
                pass
    del _actors
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_NANITE__" + _json.dumps(_out))
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--off", action="store_true", help="disable Nanite instead")
    ap.add_argument("--no-skirt", action="store_true")
    ap.add_argument("--skirt-depth", type=float, default=1.0,
                    help="metres of skirt. Default 1.0; the engine default is 0.1, "
                         "which is thin for a landscape with 256 proxy boundaries.")
    ap.add_argument("--no-build", action="store_true",
                    help="set the flags but do not build the Nanite meshes")
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and changes nothing")
    args = ap.parse_args(argv)

    enable = not args.off
    print("=== PLAN ===")
    print("  enable_nanite       %s" % enable)
    print("  nanite_skirt        %s  depth %.2f" % (not args.no_skirt, args.skirt_depth))
    print("  build               %s" % (enable and not args.no_build))
    print("  scope               every LandscapeProxy in the CURRENT level")
    print()
    if not args.go:
        print("DRY RUN. Nothing was contacted. Re-run with --go.")
        return 0

    payload = (PAYLOAD
               .replace("__ENABLE__", repr(bool(enable)))
               .replace("__SKIRT__", repr(bool(not args.no_skirt)))
               .replace("__SKIRT_DEPTH__", repr(float(args.skirt_depth)))
               .replace("__BUILD__", repr(bool(not args.no_build))))

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
            print("NO MARKER — could not look. The build may or may not have run.")
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

    print("=== RESULT ===")
    print("  level               %s" % d.get("level"))
    print("  actors touched      %d" % d.get("touched", 0))
    print("  enable_nanite after %d" % d.get("enabled_after", 0))
    print("  skirt enabled after %d" % d.get("skirt_after", 0))
    print("  unreadable          %d" % d.get("unreadable", 0))
    if d.get("build_called"):
        print("  build called        %s" % d.get("build_ok"))
        if d.get("build_error"):
            print("  build said          %s" % d["build_error"])
        print("  proxies with a BUILT Nanite mesh: %d" % d.get("with_mesh", 0))
    print()

    want = d.get("touched", 0)
    if enable and d.get("enabled_after", 0) != want:
        print("enable_nanite did not read back on every actor (%d of %d)."
              % (d.get("enabled_after", 0), want))
        return 5
    if d.get("build_called") and not d.get("build_ok"):
        print("The build call reported failure.")
        return 5
    if d.get("build_called") and d.get("with_mesh", 0) == 0:
        print("The build returned success and NO proxy has a built Nanite mesh.")
        print("That is the silent-no-op shape; treat the build as NOT done.")
        return 5

    print("Nanite enabled and built. The LEVEL is not saved — run save_level.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
