"""fix_camera_z.py — lift buried capture cameras to eye height. Z ONLY.

WHY THIS EXISTS, AND WHY IT IS NOT `site_ground_cameras.py`
-----------------------------------------------------------
Four ground stations in `recipes/alpine_8k.json` are measured to be INSIDE
the terrain — `sweep_0060` -4.38 m, `sweep_0350` -3.30 m, `trunk_base`
-2.71 m, `lod_far` -1.19 m. 19 of the 20 cameras were inherited
byte-identical from `recipes/alpine.json`, which described a 4 m/vertex
terrain; this one is 1 m/vertex and a different surface.

`site_ground_cameras.py` cannot fix them. It CHOOSES stations by mask and
writes only cameras named `ground_*` (the write is at `:224`); none of the
four is. Running
it would site five new stations and leave all four buried ones exactly where
they are.

**Z ONLY, and that is the whole design.** Keeping XY and rotation preserves
each station's SUBJECT — what it photographs — which is the minimal-variable
repair, because the defect is BURIAL, not siting. `lod_far` in particular
pairs with `lod_near` 13 m away and that pair geometry is the station's
entire purpose; a mask re-site would destroy it.

Ruled 2026-08-15 by the fable model under Ryan's delegation. The stations
that measure fine are NOT touched — above all `forest_floor` at +1.93 m,
which carries the 8.14 -> 7.76 ms GPU series and both canopy A/Bs. Moving it
would orphan every number on the board.

THE TRACE IS THE AUTHORITY, NOT THE HEIGHTMAP
---------------------------------------------
Z comes from an engine line trace down the station's own XY, for the reason
`site_ground_cameras.py` gives at length: predicting Z from the PNG assumes
a row/column-to-world mapping this project has not verified for this
landscape. This tool does NOT read the PNG or predict a heightmap Z at all --
the trace is the sole authority, and (unlike site_ground_cameras) it prints no
heightmap-vs-trace comparison.

A station whose trace MISSES is REFUSED, never guessed. Writing a height the
measurement failed to produce is exactly the defect this project names as
reporting the number a broken instrument produced.

The trace payload is IMPORTED from site_ground_cameras rather than copied:
it carries hard-won knowledge about FHitResult's fields being protected in
5.8, and two copies would need that fixed twice.

Exit codes:
  0  dry run completed, or Z written and read back
  2  bad arguments, a named camera is not in the recipe, OR the landscape
     declares neither z_scale_cm nor scale_z
  3  editor gate refused (conduct rule 7)
  4  a trace MISSED — nothing written
  5  no parseable result / a hits-count mismatch ("I could not look"), OR a
     read-back DISAGREED after the write (the file was already written)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap                 # noqa: E402
import site_ground_cameras as sgc  # noqa: E402  payload reused, not copied
import verify_landscape          # noqa: E402

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = os.path.join(REPO_ROOT, "recipes", "alpine_8k.json")

# Eye height above the traced surface. 1.7 m is this project's standing
# ground-station convention (BACKLOG's sweep design, "each at 1.7 m eye
# height above LOCAL terrain").
EYE_HEIGHT_M = 1.7

# The four measured as buried. Named explicitly rather than discovered by a
# threshold, so this tool cannot quietly widen its own blast radius on a
# later run: adding a station is an edit someone makes deliberately.
DEFAULT_STATIONS = ["sweep_0060", "sweep_0350", "trunk_base", "lod_far"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recipe", default=DEFAULT_RECIPE)
    ap.add_argument("--station", action="append", default=None,
                    help="camera name (repeatable). Default: the four "
                         "measured as buried.")
    ap.add_argument("--eye-height-m", type=float, default=EYE_HEIGHT_M)
    ap.add_argument("--write-recipe", action="store_true",
                    help="Write the new Z. Without this it is a dry run.")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args(argv)

    with open(args.recipe, encoding="utf-8") as fh:
        recipe = json.load(fh)
    cams = (recipe.get("capture") or {}).get("cameras") or []
    by_name = {c.get("name"): c for c in cams if isinstance(c, dict)}

    wanted = args.station or DEFAULT_STATIONS
    missing = [n for n in wanted if n not in by_name]
    if missing:
        print("REFUSE: not in {0}: {1}".format(
            os.path.relpath(args.recipe, REPO_ROOT), ", ".join(missing)))
        return 2

    targets = [by_name[n] for n in wanted]
    pts = [[float(c["location_cm"][0]), float(c["location_cm"][1])]
           for c in targets]

    print("REPO_ROOT : {0}".format(REPO_ROOT))
    print("recipe    : {0}".format(os.path.relpath(args.recipe, REPO_ROOT)))
    print("eye height: {0:.2f} m above the traced surface".format(
        args.eye_height_m))
    print("mode      : {0}".format(
        "WRITE" if args.write_recipe else "DRY RUN (writes nothing)"))
    print("")
    print("XY and ROTATION are preserved exactly. Only Z changes.")
    print("")

    # Trace envelope. TWO RECIPE SPELLINGS EXIST and neither is wrong:
    # recipes/alpine.json carries `scale_z`, recipes/alpine_8k.json carries
    # `z_scale_cm` (256000.0). site_ground_cameras.py:169 reads `scale_z`
    # only, which is why it would ALSO fail on this recipe — corroborating
    # that it has never been run against the 8K world, which is exactly how
    # 19 of 20 cameras came to be inherited unchecked.
    #
    # The envelope only has to BRACKET the terrain, so it is generous rather
    # than exact: a trace that starts too high costs nothing, and one that
    # starts too low silently misses. Alpine8K spans 0..1552.5 m in world Z.
    land = recipe["landscape"]
    z_scale = land.get("z_scale_cm", land.get("scale_z"))
    if z_scale is None:
        print("REFUSE: landscape declares neither z_scale_cm nor scale_z, "
              "so the trace envelope cannot be derived. Refusing rather "
              "than guessing a height range.")
        return 2
    span_cm = max(float(z_scale) * 2.0, 400000.0)

    payload = (sgc.PAYLOAD
               .replace("__PTS__", json.dumps(pts))
               .replace("__TOP__", repr(float(span_cm)))
               .replace("__BOTTOM__", repr(float(-span_cm))))

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 3
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(payload, unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r) if r else ""
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    i = (text or "").find(sgc.MARKER)
    if i < 0:
        print("REFUSE: no marker — I could not look. Nothing written.")
        return 5
    try:
        got, _ = json.JSONDecoder().raw_decode(text[i + len(sgc.MARKER):]
                                               .lstrip())
    except ValueError:
        print("REFUSE: unparseable result. Nothing written.")
        return 5

    hits = got.get("hits") or []
    if len(hits) != len(targets):
        print("REFUSE: asked for {0} traces, got {1}. Nothing written."
              .format(len(targets), len(hits)))
        return 5

    print("  {0:<14} {1:>12} {2:>12} {3:>12} {4:>10}".format(
        "station", "old z m", "ground m", "new z m", "lift m"))
    rows, missed = [], []
    for cam, hit in zip(targets, hits):
        name = cam["name"]
        old_z_cm = float(cam["location_cm"][2])
        if hit.get("z") is None:
            missed.append("{0}: {1}".format(name, hit.get("why")))
            print("  {0:<14} {1:>12.2f} {2:>12} {3:>12} {4:>10}".format(
                name, old_z_cm / 100.0, "MISS", "-", "-"))
            continue
        ground_cm = float(hit["z"])
        new_z_cm = ground_cm + args.eye_height_m * 100.0
        rows.append((cam, new_z_cm))
        print("  {0:<14} {1:>12.2f} {2:>12.2f} {3:>12.2f} {4:>+10.2f}".format(
            name, old_z_cm / 100.0, ground_cm / 100.0, new_z_cm / 100.0,
            (new_z_cm - old_z_cm) / 100.0))

    if missed:
        print("")
        print("REFUSE: {0} trace(s) missed. NOTHING WRITTEN — a camera "
              "placed at a guessed height because the trace failed is the "
              "defect this tool exists to avoid.".format(len(missed)))
        for m in missed:
            print("  {0}".format(m))
        return 4

    if not args.write_recipe:
        print("")
        print("DRY RUN. Nothing written. Re-run with --write-recipe.")
        return 0

    for cam, new_z_cm in rows:
        cam["location_cm"][2] = round(new_z_cm, 1)
    with open(args.recipe, "w", encoding="utf-8") as fh:
        json.dump(recipe, fh, indent=2)
        fh.write("\n")

    # READ BACK from the file, not from the dict we just wrote.
    with open(args.recipe, encoding="utf-8") as fh:
        after = json.load(fh)
    back = {c["name"]: c["location_cm"][2]
            for c in after["capture"]["cameras"] if isinstance(c, dict)}
    bad = [cam["name"] for cam, z in rows
           if abs(back.get(cam["name"], 1e9) - round(z, 1)) > 0.05]
    if bad:
        print("REFUSE: read-back disagrees for {0}".format(", ".join(bad)))
        return 5

    print("")
    print("WROTE and READ BACK {0} station(s). XY and rotation untouched."
          .format(len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
