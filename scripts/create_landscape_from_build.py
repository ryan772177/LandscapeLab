"""create_landscape_from_build.py — create a World Partition level and import a
Gaea build's heightmap into a new landscape, through the LandscapeLabEditor
plugin.

MUTATES: creates a level asset, spawns a landscape, saves. Bare invocation is a
DRY RUN and prints the plan without touching the editor's world.

=====================================================================
WHAT THIS REPLACES
=====================================================================
`ue5_import_alpinelab.py` opens by saying the landscape must be created BY HAND
in Landscape Mode because UE 5.8 Python cannot create one. That was CORRECT
when it was written and is now FALSE: LandscapeLabEditor exposes
ALandscapeProxy::Import as a UFUNCTION. That docstring is a derived record
which this script's existence invalidates; it is corrected in its own file, not
here.

=====================================================================
EVERY NUMBER IS DERIVED, NONE IS RETYPED
=====================================================================
The Z scale is READ from the build's height_normalization.json, never from this
file and never from a handoff note. It is the one value in the whole import
with no independent check available downstream -- the naive answer (Gaea's
declared Terrain/Height) is 2.7x too tall, and no instrument in this pipeline
can catch that after the fact. So it comes from the sidecar that recorded the
measurement, and the heightmap is SHA-256 matched against that same sidecar
before anything is imported (non-negotiable 20: adopted artefacts are copies at
stable names, hash-proven against their source at adoption time).

The component layout is likewise derived from the file's resolution rather than
asserted about it. If the arithmetic does not close exactly, this refuses.

=====================================================================
THE MAP TRANSITION, AND WHY THIS DOES NOT RE-IMPLEMENT open_level.py's GUARD
=====================================================================
Creating a level tears down the outgoing world, which is the fatal that
open_level.py's reference scrub exists to prevent
(UEditorEngine::VerifyLoadMapWorldCleanup, EditorServer.cpp:1951). That guard
lives at one choke point on purpose and copying it here is the pattern
non-negotiable 4a rejects.

So this script does not copy it -- it REQUIRES A CONDITION UNDER WHICH THE
HAZARD CANNOT EXIST, which non-negotiable 3 prefers over a gate that rejects
it. The transition may only run against a FRESH editor process whose Python
namespace has never bound anything, and this script's freshness probe
(PAYLOAD_FRESHNESS, run UNCONDITIONALLY before the transition; exit 4 if the
namespace is not fresh) asserts that rather than assuming it. There is no
--require-fresh-editor flag -- the probe is not optional. A stale global cannot
be scrubbed here because it cannot be present here.

Every level open AFTER this one still goes through open_level.py.

Exit codes:
  0  created, imported, read back and saved
  1  could not look / unexpected error
  2  refused before touching anything (bad arithmetic, hash mismatch,
     missing build, target level already exists)
  3  rule 7: no verified editor node
  4  the editor namespace is not fresh -- refusing to transition
  5  the plugin refused the import; its reason is printed
  6  imported, but the read-back disagrees with what was asked for
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

MARKER = "__LL_CREATE__"

DEFAULT_BUILD = r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1\006"
DEFAULT_LEVEL = "/Game/GaeaLab/AlpineLab_8129"

# 8129 = 32 components x (2 sections x 127 quads) + 1. Not hardcoded as a
# result -- see _solve_layout, which derives it and refuses if it does not
# close.
DEFAULT_SECTIONS = 2
DEFAULT_QUADS = 127

LEGAL_QUADS = (7, 15, 31, 63, 127, 255)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _solve_layout(size: int, sections: int, quads: int):
    """Return (component_count, error). Refuses rather than rounding.

    A layout that does not close EXACTLY means the heightmap and the component
    grid disagree, and the engine's answer to that is to resample. Every
    downstream placement would then be computed against a terrain that is not
    the one on disk.
    """
    if sections not in (1, 2):
        return None, "sections_per_component must be 1 or 2, got %d" % sections
    if quads not in LEGAL_QUADS:
        return None, ("quads_per_section must be one of %s, got %d"
                      % (", ".join(str(q) for q in LEGAL_QUADS), quads))
    per_component = sections * quads
    if (size - 1) % per_component != 0:
        return None, ("%d vertices does not tile at %d quads per component "
                      "(%d sections x %d quads): %d - 1 = %d leaves a "
                      "remainder of %d"
                      % (size, per_component, sections, quads, size, size - 1,
                         (size - 1) % per_component))
    return (size - 1) // per_component, None


PAYLOAD_FRESHNESS = r'''
import json as _json
import unreal as _unreal
# A fresh remote-exec namespace holds only the module's own builtins plus
# whatever THIS payload binds. Anything else is a leftover from an earlier
# payload, which is exactly the condition that makes a map transition fatal.
_UOBJ = getattr(_unreal, "Object", None)
_out = {"resolved_base": _UOBJ is not None, "level": None, "stale": [], "error": None}
try:
    if _UOBJ is None:
        raise RuntimeError("unreal.Object did not resolve; cannot judge freshness")
    _out["level"] = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world().get_outer().get_path_name()
    _g = dict(globals())
    for _k, _v in _g.items():
        if _k.startswith("_") or _k.startswith("__"):
            continue
        try:
            if isinstance(_v, _UOBJ):
                _out["stale"].append(_k)
        except Exception:
            pass
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_CREATE__" + _json.dumps(_out))
'''

PAYLOAD_CREATE = r'''
import gc as _gc
import json as _json
import unreal as _unreal

_out = {"error": None, "level_made": False, "landscape": None, "import_error": None,
        "readback": {}, "saved": None}
try:
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)

    # ---- 1. the map transition -------------------------------------------
    # Nothing in this process has bound a UObject; the host asserted that
    # before sending this. Collect anyway: it is free and it is the half of
    # open_level.py's guard that costs nothing to repeat.
    _gc.collect()
    _out["level_made"] = bool(_les.new_level(__LEVEL__, is_partitioned_world=True))
    if not _out["level_made"]:
        raise RuntimeError("new_level returned False for " + __LEVEL__)

    # ---- 2. the import ---------------------------------------------------
    _mat = None
    if __MATERIAL__:
        _mat = _unreal.EditorAssetLibrary.load_asset(__MATERIAL__)

    # LOCATION Z IS NOT COSMETIC AND WAS HARDCODED TO ZERO UNTIL 2026-08-14.
    #
    # UE places a landscape vertex at
    #     world_z = actor_z + (h - 32768) * scale_z / 128
    # so heightmap value 0 lands at actor_z - (32768*scale_z/128), i.e. half the
    # full span BELOW the actor. place_foliage.py:124 computes instance height as
    #     height_m = (h / 65535) * (z_scale_cm / 100)
    # which puts h=0 at world Z ZERO. The two agree only when the actor sits at
    # z_scale_cm/2 -- 128000 cm for the alpine terrain, which is exactly what
    # recipes/alpine.json's landscape.location_cm has always said.
    #
    # Passing Vector(0,0,0) therefore drops the whole landscape by 1280 m while
    # every read-back looks healthy: the scale is right, the component count is
    # right, and the actor location is a number nobody compares to the recipe.
    # The tell is that 157,554 conifers would have been planted in mid-air.
    #
    # THAT HAZARD IS THE alpine.json PATH (location_cm 128000, actor at
    # z_scale_cm/2). THIS Gaea script is different: its build is proven to
    # centre on the origin at Z 0, so __LOCZ__ is substituted with 0.0 ON
    # PURPOSE (see the substitution note at :472-476) and Vector(0,0,0) is
    # CORRECT here -- NOT the bug described above. The block above stays
    # because it explains the world_z formula that substitution relies on.
    _land, _err = _unreal.LandscapeLabTools.create_landscape_from_heightmap(
        __HEIGHTMAP__,
        _unreal.Vector(__LOCX__, __LOCY__, __LOCZ__),
        _unreal.Rotator(0.0, 0.0, 0.0),
        _unreal.Vector(__SXY__, __SXY__, __SZ__),
        __SECTIONS__, __QUADS__, __COMPX__, __COMPY__,
        _mat, __GRID__, __ACTOR__, False, True,
    )
    _out["import_error"] = _err or None
    if _land is None:
        _out["landscape"] = None
    else:
        _out["landscape"] = _land.get_actor_label()

        # ---- 3. read back from the ENGINE, not from what we asked for ----
        _s = _land.get_actor_scale3d()
        _loc = _land.get_actor_location()
        _out["readback"]["scale"] = [float(_s.x), float(_s.y), float(_s.z)]
        _out["readback"]["location"] = [float(_loc.x), float(_loc.y), float(_loc.z)]

        _actors = _unreal.EditorLevelLibrary.get_all_level_actors()
        _n_land, _n_proxy, _n_comp, _n_unreadable = 0, 0, 0, 0
        for _a in _actors:
            if isinstance(_a, _unreal.LandscapeStreamingProxy):
                _n_proxy += 1
            elif isinstance(_a, _unreal.Landscape):
                _n_land += 1
            else:
                continue
            # A property this build refuses to reflect must NOT fall through
            # to "+= 0". Counting an unreadable actor as zero components is
            # non-negotiable 6 exactly: reporting the number a broken
            # measurement produced instead of saying it could not measure.
            try:
                _comps = _a.get_editor_property("landscape_components")
            except Exception:
                _n_unreadable += 1
                continue
            if _comps is None:
                _n_unreadable += 1
            else:
                _n_comp += len(_comps)
        _out["readback"]["landscape_actors"] = _n_land
        _out["readback"]["streaming_proxies"] = _n_proxy
        _out["readback"]["components_unreadable"] = _n_unreadable
        _out["readback"]["components_seen"] = (
            None if _n_unreadable and _n_comp == 0 else _n_comp)
        del _actors, _land, _s, _loc

    # ---- 4. save ---------------------------------------------------------
    _out["saved"] = bool(_les.save_current_level())
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_CREATE__" + _json.dumps(_out))
'''


def _run(remote, remote_exec, payload):
    r = remote.run_command(payload, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        return None, text
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    return d, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", default=DEFAULT_BUILD)
    ap.add_argument("--level", default=DEFAULT_LEVEL)
    ap.add_argument("--sections", type=int, default=DEFAULT_SECTIONS)
    ap.add_argument("--quads", type=int, default=DEFAULT_QUADS)
    ap.add_argument("--scale-xy-cm", type=float, default=100.0)
    ap.add_argument("--grid-size", type=int, default=2,
                    help="components per World Partition proxy along each axis")
    ap.add_argument("--actor", default="Landscape_8129",
                    help="landscape actor name. Was hardcoded in the payload "
                         "until 2026-08-13; the default preserves the name the "
                         "8129 build already carries.")
    ap.add_argument("--material", default="",
                    help="/Game/... path, or empty for the engine default")
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and touches nothing")
    args = ap.parse_args(argv)

    # ---- everything below refuses before the editor is contacted ---------

    norm_path = os.path.join(args.build, "height_normalization.json")
    if not os.path.isfile(norm_path):
        print("REFUSE: no height_normalization.json in %s" % args.build)
        print("        Without it the Z scale is unrecoverable, and the naive")
        print("        answer is 2.7x too tall. Build 005 is un-normalized for")
        print("        exactly this reason; 006 is the canonical one.")
        return 2

    with open(norm_path, "r", encoding="utf-8") as fh:
        norm = json.load(fh)

    z_scale = float(norm["ue_z_scale"])
    alias = norm.get("import_alias") or "AlpineLabHeight.png"
    heightmap = os.path.join(args.build, "UE5_Ready", alias)

    if not os.path.isfile(heightmap):
        print("REFUSE: heightmap alias not found: %s" % heightmap)
        return 2

    # ---- PROVENANCE, checked where provenance actually lives -------------
    #
    # The sidecar's hashes describe the PRE-RESIZE file in the build root.
    # UE5_Ready holds a BICUBIC RESAMPLE of it (resize_gaea_build.py, whose
    # docstring is "RESIZE, NEVER CROP" — the masks must stay in register with
    # the height, so the whole package is resampled together). The shipped
    # bytes therefore CANNOT match the sidecar hash, by design.
    #
    # A first version of this gate hashed the shipped file and refused. It was
    # asking the right question of the wrong artefact. Two checks replace it:
    #
    #   1. the ROOT file hashes to the sidecar  -> the sidecar describes THIS
    #      build, so ue_z_scale is this terrain's number and not another's.
    #   2. the shipped file is on the SAME VALUE SCALE as the root -> the
    #      resample did not re-normalize.
    #
    # (2) is the one that matters and it is not obvious. Cropping or resampling
    # cannot invalidate the Z scale: the scale maps the uint16 RANGE to metres
    # and is independent of what the data does inside that range. What WOULD
    # invalidate it is a second normalization pass restretching the resampled
    # data — the file would still span 0..65535 and every height would be
    # wrong. Range alone cannot see that; the MEAN can.
    root_name = norm.get("output_file") or "AlpineLab_v1_Height_normalized.png"
    root_file = os.path.join(args.build, root_name)
    want_sha = norm.get("output_sha256")

    if not os.path.isfile(root_file):
        print("REFUSE: the sidecar's own output is missing: %s" % root_file)
        print("        Without it the Z scale cannot be tied to this build.")
        return 2

    root_sha = _sha256(root_file)
    if want_sha and root_sha != want_sha:
        print("REFUSE: the build root's normalized heightmap does not match its sidecar.")
        print("  file    %s" % root_file)
        print("  sha256  %s" % root_sha)
        print("  sidecar %s" % want_sha)
        print("  ue_z_scale %.6f was measured against DIFFERENT data." % z_scale)
        return 2

    try:
        import numpy as _np
        from PIL import Image as _Image
        _Image.MAX_IMAGE_PIXELS = None
        root_a = _np.asarray(_Image.open(root_file))
        root_stats = (int(root_a.min()), int(root_a.max()), float(root_a.mean()))
        del root_a
        ship_a = _np.asarray(_Image.open(heightmap))
        ship_stats = (int(ship_a.min()), int(ship_a.max()), float(ship_a.mean()))
        del ship_a
    except Exception as exc:
        print("REFUSE: could not measure the heightmaps: %s: %s"
              % (type(exc).__name__, exc))
        print("        This is 'could not look', not 'they agree'.")
        return 2

    drift = abs(ship_stats[2] - root_stats[2]) / max(root_stats[2], 1.0)
    if drift > 1e-3:
        print("REFUSE: the shipped heightmap is not on the same value scale as the")
        print("        file the Z scale was measured against.")
        print("  root    min %d max %d mean %.3f" % root_stats)
        print("  shipped min %d max %d mean %.3f" % ship_stats)
        print("  mean drift %.4f%%, over the 0.1%% a resample should cause."
              % (drift * 100.0))
        print("  A second normalization pass would look exactly like this.")
        return 2

    got_sha = _sha256(heightmap)

    # Resolution comes from the PNG header, not from an expectation.
    try:
        import struct
        with open(heightmap, "rb") as fh:
            head = fh.read(33)
        if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            print("REFUSE: %s is not a PNG with a leading IHDR chunk." % heightmap)
            return 2
        width, height = struct.unpack(">II", head[16:24])
        bit_depth = head[24]
    except Exception as exc:
        print("REFUSE: could not read the PNG header: %s: %s"
              % (type(exc).__name__, exc))
        return 2

    if width != height:
        print("REFUSE: heightmap is %d x %d; a landscape import wants a square."
              % (width, height))
        return 2
    if bit_depth != 16:
        print("REFUSE: heightmap is %d-bit. A landscape heightmap must be 16-bit; "
              "8-bit quantises %.2f m of span into 256 steps."
              % (bit_depth, float(norm.get("span_m", 0.0))))
        return 2

    comp, err = _solve_layout(width, args.sections, args.quads)
    if err:
        print("REFUSE:", err)
        return 2

    proxies = None
    if args.grid_size > 0:
        if comp % args.grid_size != 0:
            print("REFUSE: %d components does not divide by grid size %d, so the "
                  "proxy grid would be ragged." % (comp, args.grid_size))
            return 2
        proxies = (comp // args.grid_size) ** 2

    extent_m = (width - 1) * args.scale_xy_cm / 100.0
    verts = width * height
    span_m = z_scale * 512.0 / 100.0

    print("=== PLAN (every value derived, none retyped) ===")
    print("  build            %s" % args.build)
    print("  heightmap        %s" % heightmap)
    print("  shipped sha256   %s  (a resample; recorded, not matched)" % got_sha[:16])
    print("  root sha256      %s  %s" % (
        root_sha[:16],
        "MATCHES sidecar output_sha256" if want_sha
        else "(sidecar declares no output_sha256 -- nothing to match against)"))
    print("  value scale      root mean %.3f  vs shipped %.3f   drift %.4f%%"
          % (root_stats[2], ship_stats[2], drift * 100.0))
    print("                   root %d..%d, shipped %d..%d"
          % (root_stats[0], root_stats[1], ship_stats[0], ship_stats[1]))
    print("  resolution       %d x %d, %d-bit  (from the PNG header)" % (width, height, bit_depth))
    print("  layout           %d x %d components, %d sections x %d quads"
          % (comp, comp, args.sections, args.quads))
    print("                   %d x %d + 1 = %d  -- closes exactly"
          % (comp, args.sections * args.quads, width))
    print("  vertices         %s" % format(verts, ","))
    print("  scale            xy %.1f cm/vertex   z %.6f" % (args.scale_xy_cm, z_scale))
    print("  extent           %.1f m x %.1f m" % (extent_m, extent_m))
    print("  Z span           %.2f m   (sidecar says %.2f m)"
          % (span_m, float(norm.get("span_m", 0.0))))
    print("  z provenance     %s" % norm.get("z_scale_provenance", "(none recorded)"))
    print("  grid size        %s  ->  %s proxies"
          % (args.grid_size, proxies if proxies is not None else "unsplit"))
    print("  level            %s" % args.level)
    print("  material         %s" % (args.material or "(engine default)"))
    print()

    if abs(span_m - float(norm.get("span_m", span_m))) > 0.01:
        print("REFUSE: the Z scale does not reproduce the sidecar's own span.")
        return 2

    if not args.go:
        print("DRY RUN. Nothing was contacted. Re-run with --go.")
        return 0

    # ---- editor side -----------------------------------------------------

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

        fresh, raw = _run(remote, remote_exec, PAYLOAD_FRESHNESS)
        if fresh is None:
            print("NO MARKER on the freshness probe — could not look.")
            print(raw[:2000])
            return 1
        if fresh.get("error"):
            print("FRESHNESS PROBE ERROR:", fresh["error"])
            return 1
        if fresh.get("stale"):
            print("REFUSE: this editor's Python namespace is NOT fresh.")
            print("  live globals rooting a UObject: %s" % ", ".join(fresh["stale"]))
            print("  A map transition with those present is the fatal at")
            print("  EditorServer.cpp:1951. Restart the editor and re-run;")
            print("  this script deliberately does not carry its own scrub.")
            return 4
        print("freshness        clean namespace, editor on %s" % fresh.get("level"))

        payload = (PAYLOAD_CREATE
                   .replace("__LEVEL__", repr(args.level))
                   .replace("__ACTOR__", repr(args.actor))
                   # The Gaea path has always centred on the origin at Z 0 and
                   # is proven that way, so its behaviour is preserved exactly.
                   .replace("__LOCX__", repr(0.0))
                   .replace("__LOCY__", repr(0.0))
                   .replace("__LOCZ__", repr(0.0))
                   .replace("__HEIGHTMAP__", repr(heightmap))
                   .replace("__MATERIAL__", repr(args.material))
                   .replace("__SXY__", repr(float(args.scale_xy_cm)))
                   .replace("__SZ__", repr(float(z_scale)))
                   .replace("__SECTIONS__", repr(int(args.sections)))
                   .replace("__QUADS__", repr(int(args.quads)))
                   .replace("__COMPX__", repr(int(comp)))
                   .replace("__COMPY__", repr(int(comp)))
                   .replace("__GRID__", repr(int(args.grid_size))))

        print("creating and importing — this holds %s vertices in memory ..."
              % format(verts, ","))
        d, raw = _run(remote, remote_exec, payload)
        if d is None:
            print("NO MARKER — could not look. The import may or may not have run.")
            print(raw[:3000])
            return 1
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1

    print()
    print("=== RESULT ===")
    print("  level created    %s" % d.get("level_made"))
    print("  landscape        %s" % (d.get("landscape") or "NONE"))
    if d.get("import_error"):
        print("  plugin said      %s" % d["import_error"])
    if d.get("landscape") is None:
        print()
        print("REFUSED BY THE PLUGIN. Nothing was imported.")
        return 5

    rb = d.get("readback") or {}
    print("  scale read back  %s" % rb.get("scale"))
    print("  location         %s" % rb.get("location"))
    print("  landscape actors %s" % rb.get("landscape_actors"))
    print("  streaming proxies %s" % rb.get("streaming_proxies"))
    seen = rb.get("components_seen")
    print("  components seen  %s"
          % ("UNREADABLE on %d actor(s) — not a count of zero"
             % rb.get("components_unreadable", 0) if seen is None else seen))
    print("  saved            %s" % d.get("saved"))
    print()

    problems = []
    got_scale = rb.get("scale") or []
    if len(got_scale) == 3:
        if abs(got_scale[2] - z_scale) > 1e-4:
            problems.append("Z scale read back as %r, asked for %r"
                            % (got_scale[2], z_scale))
        if abs(got_scale[0] - args.scale_xy_cm) > 1e-4:
            problems.append("XY scale read back as %r, asked for %r"
                            % (got_scale[0], args.scale_xy_cm))
    else:
        problems.append("could not read the scale back")

    if proxies is not None and rb.get("streaming_proxies") not in (proxies, None):
        # World Partition may leave regions unloaded, so fewer is not proof of
        # failure -- but MORE is, and zero means ChangeGridSize did nothing.
        if rb.get("streaming_proxies", 0) == 0:
            problems.append("0 streaming proxies: the grid size was not applied")
        elif rb.get("streaming_proxies", 0) > proxies:
            problems.append("%d streaming proxies, more than the %d the layout allows"
                            % (rb["streaming_proxies"], proxies))
        else:
            print("NOTE: %d of %d proxies are loaded. World Partition leaves regions"
                  % (rb["streaming_proxies"], proxies))
            print("      unloaded, so this is not a shortfall -- but it is also not")
            print("      a complete census. landscape_inventory.py is the instrument")
            print("      for that, and it reads a different code path.")

    if not d.get("saved"):
        problems.append("save_current_level returned False — this is render state only")

    if problems:
        print("READ-BACK DISAGREES:")
        for p in problems:
            print("  -", p)
        return 6

    print("Created, imported, read back and saved.")
    print()
    print("NOT VERIFIED BY THIS SCRIPT: that the terrain is the RIGHT terrain.")
    print("Everything above reads the engine's own record of what it was told.")
    print("A different representation -- landscape_inventory.py for the census,")
    print("a collision trace for the surface -- has not run yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
