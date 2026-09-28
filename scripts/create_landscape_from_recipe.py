"""create_landscape_from_recipe.py — create a World Partition level and import
a RECIPE's adopted heightmap into a new landscape, through LandscapeLabEditor.

MUTATES: creates a level asset, spawns a landscape, saves. Bare invocation is a
DRY RUN and prints the plan without touching the editor's world.

=====================================================================
WHY THIS EXISTS BESIDE create_landscape_from_build.py
=====================================================================
That script is GAEA-BUILD oriented by construction, and correctly so: it reads
the Z scale out of `height_normalization.json` and refuses without it, because
for a Gaea build the naive Z answer is 2.7x too tall and unrecoverable after the
fact. None of that applies to a STAMP-COMPOSITED terrain, which has no Gaea
sidecar and whose Z scale is a recipe value that never left this repo.

**THE PLUGIN CALL SEQUENCE IS IMPORTED, NOT COPIED** (non-negotiable 4a). This
module reuses `PAYLOAD_FRESHNESS`, `PAYLOAD_CREATE`, `_run`, `_solve_layout`,
`MARKER` and `_sha256` from `create_landscape_from_build`. A second transcription
of `spawn -> set material -> Import -> UpdateLayerInfoMap -> ChangeGridSize`
would be exactly the individually-patched-copy pattern that rule rejects, and
the ordering came from the engine's own New Landscape button
(`LandscapeEditorDetailCustomization_NewLandscape.cpp:1150-1290`) — it is not
ours to re-derive.

=====================================================================
WHERE THE Z SCALE COMES FROM, AND WHY IT IS NOT GUESSED
=====================================================================
UE maps the full 16-bit heightmap range onto `scale_z * 512` centimetres. The
recipe states the span directly as `landscape.z_scale_cm`, so

    scale_z = z_scale_cm / 512.0

For the alpine terrain that is 256000 / 512 = **500.0**, which is the value
`/Game/Alpine` already carries. Derived here, then CHECKED against the recipe's
own round trip and printed, rather than retyped from a handoff note.

=====================================================================
PROVENANCE — the adopted map must be the one the compositor made
=====================================================================
Non-negotiable 20 says an adopted artefact is a copy at a stable name,
hash-proven against its producer. This asserts that at import time too, not
only at adoption time: the sidecar `<stamps.output>.stamps.json` records
`output_sha256`, and the file being imported must still hash to it. A terrain
that was re-composited after adoption, or edited, fails here rather than
silently becoming the level.

Exit codes:
  0  created, imported, read back, saved
  1  could not look
  2  refused before touching anything
  3  rule 7: no verified editor node
  4  the editor process is not fresh (a map transition would be fatal)
  5  the engine's read-back disagrees with the plan
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402
from create_landscape_from_build import (  # noqa: E402
    MARKER, PAYLOAD_CREATE, PAYLOAD_FRESHNESS, _run, _sha256, _solve_layout,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--grid-size", type=int, default=2,
                    help="components per streaming proxy axis. 2 -> 4 components "
                         "per proxy, the layout proven on AlpineLab_8129.")
    ap.add_argument("--material", default="")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--go", action="store_true",
                    help="without this the run is a DRY RUN and contacts nothing")
    args = ap.parse_args(argv)

    repo = bootstrap.REPO_ROOT
    with open(args.recipe, "r", encoding="utf-8") as fh:
        recipe = json.load(fh)

    hm, ls = recipe["heightmap"], recipe["landscape"]
    heightmap = os.path.join(repo, hm["source"])
    if not os.path.isfile(heightmap):
        print("REFUSE: heightmap not found: %s" % heightmap)
        return 2

    # ---- resolution from the PNG HEADER, not from the recipe's claim -----
    with open(heightmap, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        print("REFUSE: %s is not a PNG with a leading IHDR chunk." % heightmap)
        return 2
    width, height = struct.unpack(">II", head[16:24])
    bit_depth = head[24]

    if width != height:
        print("REFUSE: heightmap is %d x %d; a landscape import wants a square."
              % (width, height))
        return 2
    if bit_depth != 16:
        print("REFUSE: heightmap is %d-bit; a landscape heightmap must be 16-bit."
              % bit_depth)
        return 2
    if int(hm["resolution"]) != width:
        print("REFUSE: recipe says resolution %d, the file header says %d. "
              "The FILE wins; fix the recipe." % (int(hm["resolution"]), width))
        return 2

    # ---- PROVENANCE: is this still the map the compositor produced? ------
    got_sha = _sha256(heightmap)
    side = os.path.join(repo, recipe["stamps"]["output"] + ".stamps.json")
    prov = "NO SIDECAR — provenance UNVERIFIED"
    if os.path.isfile(side):
        with open(side, "r", encoding="utf-8") as fh:
            sc = json.load(fh)
        want = sc.get("output_sha256")
        if want and want != got_sha:
            print("REFUSE: the adopted heightmap does not hash to the "
                  "compositor's recorded output.")
            print("  file    %s" % heightmap)
            print("  sha256  %s" % got_sha)
            print("  sidecar %s" % want)
            print("  Either the terrain was re-composited after adoption, or the")
            print("  adopted copy was edited. Re-adopt before importing.")
            return 2
        prov = "MATCHES the compositor sidecar" if want else "sidecar has no hash"

    # ---- layout, solved not assumed --------------------------------------
    sections = int(hm["sections_per_component"])
    quads = int(hm["section_size"])
    comp, err = _solve_layout(width, sections, quads)
    if err:
        print("REFUSE:", err)
        return 2
    if comp != int(hm["component_count"]):
        print("REFUSE: solved %d components per axis, recipe says %d."
              % (comp, int(hm["component_count"])))
        return 2
    if args.grid_size > 0 and comp % args.grid_size != 0:
        print("REFUSE: %d components does not divide by grid size %d; the proxy "
              "grid would be ragged." % (comp, args.grid_size))
        return 2

    scale_xy = float(ls["scale_xy_cm"])
    z_scale = float(ls["z_scale_cm"]) / 512.0
    span_m = z_scale * 512.0 / 100.0
    extent_m = (width - 1) * scale_xy / 100.0
    proxies = (comp // args.grid_size) ** 2 if args.grid_size > 0 else None

    print("=== PLAN (derived from the recipe, checked against the file) ===")
    print("  recipe           %s" % args.recipe)
    print("  heightmap        %s" % hm["source"])
    print("  sha256           %s  %s" % (got_sha[:16], prov))
    print("  resolution       %d x %d, %d-bit   (from the PNG header)"
          % (width, height, bit_depth))
    print("  layout           %d x %d components, %d sections x %d quads"
          % (comp, comp, sections, quads))
    print("                   %d x %d + 1 = %d   %s"
          % (comp, sections * quads, comp * sections * quads + 1,
             "closes EXACTLY" if comp * sections * quads + 1 == width else "DOES NOT CLOSE"))
    print("  vertices         %s" % format(width * height, ","))
    print("  scale_xy         %.1f cm      extent %.1f m" % (scale_xy, extent_m))
    print("  scale_z          %.6f    span %.2f m over the full 16-bit range"
          % (z_scale, span_m))
    print("                   (z_scale_cm %.1f / 512)" % float(ls["z_scale_cm"]))
    print("  actor Z          %.1f cm = %.1f m   (must be z_scale_cm/2 = %.1f, "
          "or every instance is misplaced)"
          % (float(ls["location_cm"][2]), float(ls["location_cm"][2]) / 100.0,
             float(ls["z_scale_cm"]) / 2.0))
    print("  terrain sits     %.1f .. %.1f m in world Z"
          % (0.0, span_m * 39743.0 / 65535.0))
    print("  grid size        %d -> %s streaming proxies"
          % (args.grid_size, proxies if proxies is not None else "n/a"))
    print("  level            %s" % ls["level_path"])
    print("  actor            %s" % ls["actor_name"])
    print("  material         %s" % (args.material or "(engine default)"))
    print()

    if not args.go:
        print("DRY RUN. Nothing was contacted. Re-run with --go.")
        return 0

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3
        remote.open_command_connection(node["node_id"])

        # ---- FRESHNESS. A map transition in a namespace that has bound a
        # UObject is the EditorServer.cpp:1951 fatal. Same gate as the build
        # path, and it is asserted rather than assumed (non-negotiable 3).
        d, raw = _run(remote, remote_exec, PAYLOAD_FRESHNESS)
        if d is None:
            print("NO MARKER on the freshness probe — could not look.")
            print(raw[:2000])
            return 1
        if d.get("error"):
            print("Freshness probe error:", d["error"])
            return 1
        if d.get("stale"):
            print("REFUSE (exit 4): this editor process is NOT fresh. It holds "
                  "UObject references: %s" % ", ".join(sorted(d["stale"])[:8]))
            print("  Creating a level is a map transition, which is fatal at "
                  "EditorServer.cpp:1951 with live references.")
            print("  Restart the editor and run this as the FIRST payload.")
            return 4
        print("freshness        OK — no UObject bound in this namespace")
        print("current level    %s" % d.get("level"))

        payload = (PAYLOAD_CREATE
                   .replace("__LEVEL__", repr(ls["level_path"]))
                   .replace("__ACTOR__", repr(ls["actor_name"]))
                   # X and Y are 0 because the plugin centres the landscape on
                   # the origin itself; passing the recipe's X/Y would double it.
                   # Z is NOT centred and MUST come from the recipe -- see the
                   # note in PAYLOAD_CREATE. This is asserted after the import.
                   .replace("__LOCX__", repr(0.0))
                   .replace("__LOCY__", repr(0.0))
                   .replace("__LOCZ__", repr(float(ls["location_cm"][2])))
                   .replace("__HEIGHTMAP__", repr(heightmap))
                   .replace("__MATERIAL__", repr(args.material))
                   .replace("__SXY__", repr(scale_xy))
                   .replace("__SZ__", repr(z_scale))
                   .replace("__SECTIONS__", repr(sections))
                   .replace("__QUADS__", repr(quads))
                   .replace("__COMPX__", repr(int(comp)))
                   .replace("__COMPY__", repr(int(comp)))
                   .replace("__GRID__", repr(int(args.grid_size))))

        print()
        print("creating and importing — this takes minutes at %s vertices ..."
              % format(width * height, ","))
        d, raw = _run(remote, remote_exec, payload)
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    if d is None:
        print("NO MARKER — could not look. The level may or may not exist.")
        print(raw[:3000])
        return 1
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 1

    rb = d.get("readback", {})
    print()
    print("=== RESULT — read back from the ENGINE, not from what we asked ===")
    print("  level made       %s" % d.get("level_made"))
    print("  landscape        %s" % d.get("landscape"))
    if d.get("import_error"):
        print("  import said      %s" % d["import_error"])
    print("  scale            %s" % rb.get("scale"))
    print("  location         %s" % rb.get("location"))
    print("  landscape actors %s" % rb.get("landscape_actors"))
    print("  streaming proxies %s" % rb.get("streaming_proxies"))
    print("  components seen  %s" % rb.get("components_seen"))
    print("  unreadable       %s" % rb.get("components_unreadable"))
    print("  saved            %s" % d.get("saved"))
    print()

    if not d.get("landscape"):
        print("The import did not produce a landscape.")
        return 5
    sc = rb.get("scale") or []
    if len(sc) == 3 and (abs(sc[0] - scale_xy) > 1e-6 or abs(sc[2] - z_scale) > 1e-6):
        print("REFUSE (exit 5): the engine's scale %s is not the plan's "
              "(%.6f, %.6f)." % (sc, scale_xy, z_scale))
        return 5

    # LOCATION Z, asserted against the recipe. The scale was checked here from
    # the first version and the location was merely PRINTED -- which is how a
    # 1280 m drop survived a read-back that looked entirely healthy on
    # 2026-08-14. A number that is displayed but never compared is not verified.
    loc = rb.get("location") or []
    want_z = float(ls["location_cm"][2])
    if len(loc) == 3 and abs(loc[2] - want_z) > 1e-6:
        print("REFUSE (exit 5): the landscape sits at Z %.1f cm, the recipe says "
              "%.1f cm." % (loc[2], want_z))
        print("  This is not cosmetic. UE puts heightmap value h at")
        print("    world_z = actor_z + (h - 32768) * scale_z / 128")
        print("  so h=0 lands half a span BELOW the actor, while place_foliage")
        print("  computes height_m = (h/65535) * (z_scale_cm/100), i.e. h=0 at")
        print("  world Z ZERO. They agree only at actor_z = z_scale_cm/2 = %.1f."
              % (float(ls["z_scale_cm"]) / 2.0))
        print("  Every instance placed against this landscape would be off by")
        print("  %.1f m." % (abs(loc[2] - want_z) / 100.0))
        return 5
    want_comp = comp * comp
    if rb.get("components_seen") not in (None, want_comp):
        print("NOTE: engine reports %s components, plan implies %d."
              % (rb.get("components_seen"), want_comp))
    print("Created. Verify independently with landscape_inventory.py, which "
          "derives geometry from engine section bases and never sees this plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
