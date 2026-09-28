"""The forge CLI: one concept image in, a walkable UE landscape out.

    python -m forge_tool.cli author                       # visual editor
    python -m forge_tool.cli build <image> --layout <l.json> --name <run>
    python -m forge_tool.cli init --dest <dir> [--compile]  # emit UE project
    (build <image> --name <run> alone = EXPERIMENTAL vision auto-read;
     needs ANTHROPIC_API_KEY, untested — ruled optional 2026-09-04)

`build` chains the PROVEN scripts, fail-stop per leg (the 2026-09-01
driver lesson: a multi-leg loop that ignores a leg's exit code renders
the wrong world and reports success):

    author/gate -> assemble -> base gen -> brief_loop (composite+probe)
    -> adopt (hash-proven) -> concept2level (offline+editor+shoot)
    -> water plane (if the brief declares one)

Every artefact lands in forge_runs/<name>/ plus the shared terrain/ and
textures/ paths the recipe names. Re-running a build with the same name
REFUSES rather than overwriting a finished run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)

from brief_loop import Refuse  # noqa: E402
from forge_tool import assemble_recipe, check_brief  # noqa: E402

import re as _re

BASE_RELIEF = 0.18  # the spike's subdued rolling base


def biome_for(name):
    """Per-run biome id: forge_<name>, lowercased, [a-z0-9_] only —
    it names files (schema: biome_id must match the recipe filename
    stem), the level (/Game/Forge_<biome>), and the material."""
    clean = _re.sub(r"[^a-z0-9_]", "_", name.lower())
    if not clean.strip("_"):
        raise Refuse("run name %r reduces to nothing usable as a "
                     "biome id" % name)
    return "forge_" + clean


def base_seed_for(layout):
    """Deterministic per-world base seed from the PLACEMENTS only.

    A fixed constant gave every forge world the same underlying base
    terrain (v0.1.0). Hashing the whole layout fixed that but coupled
    the seed to the CAMERA: raising the camera 140 m rebuilt a
    different world whose carve no longer converged (measured
    2026-09-04, uistarter). The seed hashes only what shapes terrain —
    the placements — so camera/lighting/water edits iterate on the SAME
    world. 31 bits for numpy's seed range."""
    canon = json.dumps(layout["placements"],
                       sort_keys=True).encode("utf-8")
    return int.from_bytes(
        hashlib.sha256(canon).digest()[:4], "big") & 0x7FFFFFFF


def run(label, script, args, timeout=1800, ok_exits=(0,)):
    """One leg: run a scripts/ tool with cwd=scripts, fail-stop."""
    cmd = [sys.executable, os.path.join(SCRIPTS, script)] + args
    print("== %s" % label)
    r = subprocess.run(cmd, cwd=SCRIPTS, timeout=timeout)
    if r.returncode not in ok_exits:
        raise Refuse("leg %r exited %d — stopping (fail-stop per leg)"
                     % (label, r.returncode))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def adopt(recipe):
    """R-STAMP adoption: copy the compositor output to the stable
    heightmap source and prove the copy against the sidecar hash."""
    out = os.path.join(REPO, recipe["stamps"]["output"])
    side = out + ".stamps.json"
    src_rel = recipe["heightmap"]["source"]
    dst = os.path.join(REPO, src_rel)
    with open(side, encoding="utf-8") as f:
        want = json.load(f)["output_sha256"]
    got = sha256_file(out)
    if got != want:
        raise Refuse("compositor output %s does not match its own sidecar "
                     "(%s vs %s) — refusing to adopt"
                     % (out, got[:12], want[:12]))
    shutil.copy2(out, dst)
    if sha256_file(dst) != want:
        raise Refuse("adopted copy does not hash-match the sidecar")
    print("== adopted %s  (%s)" % (src_rel, want[:16]))


def build(a):
    # RULED 2026-09-04 (operator): the product is FINAL without an API
    # key — the Layout Author is the standard path, and the vision leg
    # is an optional, UNTESTED extra. Refuse image-only invocations
    # BEFORE touching the filesystem, with the standard path spelled
    # out.
    if not a.image and not a.layout:
        raise Refuse("give an image plus --layout <layout.json> "
                     "(run 'forge author' to make one)")
    if a.image and not a.layout and not (
            os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise Refuse(
            "no API key set — that's fine: the standard path is the "
            "Layout Author.\n"
            "  1. forge author        (visual editor; export "
            "<world>.layout.json)\n"
            "  2. forge build %s --layout <world>.layout.json "
            "--name %s\n"
            "(Auto-reading the image with a vision model is an "
            "optional, EXPERIMENTAL extra needing ANTHROPIC_API_KEY; "
            "it is untested in this build.)" % (a.image, a.name))

    run_dir = os.path.join(REPO, "forge_runs", a.name)
    if os.path.isdir(run_dir) and os.listdir(run_dir):
        raise Refuse("forge_runs/%s already exists and is non-empty — "
                     "pick a new --name (runs are never overwritten)"
                     % a.name)
    os.makedirs(run_dir, exist_ok=True)

    catalogue = json.load(open(
        os.path.join(REPO, "recipes", "forge_stamps_catalogue.json"),
        encoding="utf-8"))

    # 1. layout: author from the image, or gate a supplied one. A
    # Layout Author export (schema forge-layout/1, the operator's
    # three.js UI) is converted first — same gate either way.
    layout_path = os.path.join(run_dir, "layout.json")
    if a.layout:
        layout = json.load(open(a.layout, encoding="utf-8"))
        if layout.get("schema") == "forge-layout/1":
            if not a.image:
                raise Refuse("a Layout Author export needs the concept "
                             "image too (its lighting is MEASURED, and "
                             "the UI does not export the image): "
                             "build <image> --layout <ui.layout.json>")
            from forge_tool.import_layout import convert
            layout, notes = convert(layout, a.image)
            for n in notes:
                print("import note: %s" % n)
        else:
            layout = check_brief.check(layout, catalogue)
        if "lighting_measured" not in layout["brief"] \
                or "source_image" not in layout["brief"]:
            raise Refuse("--layout must carry brief.lighting_measured and "
                         "brief.source_image (author briefs do; add them "
                         "or author from the image instead)")
        with open(layout_path, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=1)
    elif a.image:
        # key presence was gated at the top of build(); reaching here
        # means the EXPERIMENTAL vision leg was explicitly chosen
        from forge_tool.brief_author import author as vision_author
        layout = vision_author(a.image, layout_path)
    else:  # unreachable: the top-of-build() guard already refused
        raise Refuse("give an image plus --layout <layout.json> "
                     "(run 'forge author' to make one)")

    # 2. recipe assembly (per-run biome: files, level and material all
    # carry the run's identity, so worlds never overwrite each other)
    recipe_path, brief_path = assemble_recipe.assemble(
        layout, run_dir, biome_id=biome_for(a.name))
    recipe = json.load(open(recipe_path, encoding="utf-8"))
    print("== assembled %s" % os.path.relpath(recipe_path, REPO))

    # 3. procedural base (deterministic: fixed seed + relief).
    # --recipe here is an INPUT the generator READS for its relief
    # report (audit: it is not an output record) — hand it the
    # assembled recipe so the report speaks this world's frame.
    seed = base_seed_for(layout)
    print("== base seed %d (from layout content hash)" % seed)
    run("base terrain", "make_alpine_terrain.py", [
        "--resolution", "1009",
        "--seed", str(seed),
        "--relief", str(BASE_RELIEF),
        "--output", os.path.join(REPO, recipe["stamps"]["base"]),
        "--recipe", recipe_path,
    ], timeout=3600)

    # 4. composite + probe + adjust until the brief's acceptance passes.
    # brief_loop resolves --recipe against ITS cwd (scripts/), so these
    # legs get ABSOLUTE paths (audit: repo-relative here lands on
    # scripts/forge_runs/...).
    rel = lambda p: os.path.relpath(p, REPO)  # noqa: E731
    # --max-iters passes through untouched: the cap stays a REFUSAL
    # (scoutproof 2026-09-03: the 15%-per-step anchor-planing knob was
    # still converging, 7.1 -> 4.2 deg, when the default cap of 6 hit —
    # a geometric-decay knob needs runway the multiplicative knobs
    # never did; more iterations is not a widened tolerance)
    bl_args = ["--recipe", recipe_path, "--brief", brief_path]
    if a.max_brief_iters:
        bl_args += ["--max-iters", str(a.max_brief_iters)]
    run("brief loop", "brief_loop.py", bl_args, timeout=3600)

    # 5. adoption (hash-proven)
    adopt(recipe)

    # 5b. camera sightline over the ADOPTED terrain — a blocked vista is
    # detectable in seconds here; the editor phase costs twenty minutes
    # (the first duskhighland render framed a ridge instead of the lake)
    from forge_tool import check_sightline
    brief_obj = json.load(open(brief_path, encoding="utf-8"))
    blocked = check_sightline.check(recipe, brief_obj, REPO)
    # The refusal carries its own prescription when the problem is pure
    # height (ray blockages all report camera_height_to_clear_m). Apply
    # it and re-check TO A FIXPOINT, bounded — mechanizing the fix that
    # was done by hand on three builds. One application is not enough:
    # raising the camera changes the ray geometry, and scoutproof v2
    # measured a fresh 0.8 m-marginal blocker appearing after the first
    # raise (2026-09-03). Height only ever goes UP toward the 500 m
    # bound, so the loop cannot cycle. Aiming problems (frustum) and
    # off-map entries are never auto-fixed: they mean the layout, not
    # the height.
    raises = []
    for _attempt in range(4):
        if not (blocked
                and all("camera_height_to_clear_m" in b for b in blocked)):
            break
        need = max(b["camera_height_to_clear_m"] for b in blocked) + 10.0
        if need > 500.0:
            break
        cam = brief_obj["render_camera"]
        raises.append(cam["height_above_ground_m"])
        cam["height_above_ground_m"] = round(need, 1)
        print("== sightline: camera auto-raised %s -> %s m (gate "
              "prescription)" % (raises[-1], cam["height_above_ground_m"]))
        blocked = check_sightline.check(recipe, brief_obj, REPO)
    if raises:
        cam = brief_obj["render_camera"]
        cam["_height_provenance"] = (
            "auto-raised %s -> %s by the sightline gate's own "
            "prescription (%d application(s); base terrain blocked "
            "the original)" % (raises[0], cam["height_above_ground_m"],
                               len(raises)))
        with open(brief_path, "w", encoding="utf-8") as f:
            json.dump(brief_obj, f, indent=1)
    if blocked:
        lines = ["render_camera cannot see its subjects on the built "
                 "terrain:"]
        for b in blocked:
            if "camera_height_to_clear_m" in b:
                lines.append(
                    "  %(check)s blocked %(dist_from_cam_m)s m out at "
                    "%(blocked_at_m)s — terrain %(terrain_m)s m over a "
                    "%(ray_m)s m ray; camera height_above_ground_m "
                    ">= %(camera_height_to_clear_m)s would clear it" % b)
            else:  # off-map camera/target entries carry check+reason only
                lines.append("  %s: %s" % (b.get("check", "?"),
                                           b.get("reason", "blocked")))
        raise Refuse("\n".join(lines))
    print("== sightline: all acceptance subjects visible")

    # 6. the editor phases: landscape, textures, material, lighting, shot
    outdir = os.path.join(run_dir, "renders")
    os.makedirs(outdir, exist_ok=True)
    run("concept2level", "concept2level.py", [
        "--recipe", rel(recipe_path), "--brief", rel(brief_path),
        "--name", a.name, "--outdir", outdir], timeout=5400)

    # 7. water plane, when the brief read one off the image. GO=0 first:
    # the dry run reports the world path it WOULD touch (rule 11
    # in-band), then the same payload commits.
    water = layout["brief"].get("water")
    if water:
        # NOTE: __LL__ in these payloads is ue_exec's result MARKER, not
        # a parameter — substituting it erases the marker and turns a
        # successful payload into "COULD NOT LOOK" exit 1 (measured
        # 2026-09-03, build 6). Never --set LL.
        run("water material", "ue_exec.py", [
            os.path.join(SCRIPTS, "make_water_material_payload.txt"),
            "--set", "WR=%s" % water["color_linear"][0],
            "--set", "WG=%s" % water["color_linear"][1],
            "--set", "WB=%s" % water["color_linear"][2],
            "--set", "ROUGH=%s" % water["roughness"],
            "--set", "OPAC=%s" % water["opacity"],
            "--timeout", "25"], timeout=300)
        spawn_args = [
            os.path.join(SCRIPTS, "spawn_water_plane_payload.txt"),
            "--set", "LABEL=WaterPlane_%s" % a.name,
            "--set", "NAME=WaterPlane_%s" % a.name,
            "--set", "CX=%s" % water["centre_cm"][0],
            "--set", "CY=%s" % water["centre_cm"][1],
            "--set", "CZ=%s" % water["level_cm"],
            "--set", "SX=%s" % water["scale_xy"][0],
            "--set", "SY=%s" % water["scale_xy"][1]]
        run("water plane (dry run)", "ue_exec.py",
            spawn_args + ["--set", "GO=0", "--timeout", "25"], timeout=300)
        run("water plane", "ue_exec.py",
            spawn_args + ["--set", "GO=1", "--timeout", "25"], timeout=300)
        # save_level resolves --recipe against its cwd: absolute path
        run("save level", "save_level.py", [
            "--recipe", recipe_path, "--timeout", "25", "--save"],
            timeout=900, ok_exits=(0, 6))
        # the phase-all shot predates the water; relight reshoots the
        # SAME camera over the finished scene
        run("reshoot with water", "concept2level.py", [
            "--recipe", rel(recipe_path), "--brief", rel(brief_path),
            "--name", a.name, "--outdir", outdir, "--phase", "relight"],
            timeout=1800)

    # 8. closed-loop fidelity measurement (report, not gate)
    render_path = os.path.join(outdir, a.name + ".png")
    concept_path = os.path.join(REPO, layout["brief"]["source_image"])
    if os.path.isfile(render_path) and os.path.isfile(concept_path):
        from forge_tool import verify_render
        verify_render.main([concept_path, render_path, "--out",
                            os.path.join(run_dir, "fidelity.json")])

    print("\nFORGED: %s" % run_dir)
    print("render: %s" % render_path)
    return 0


def polish(a):
    """Mechanized exposure matching: measure the render against the
    concept, push the EV override through the measured transfer slope,
    relight, re-measure — the loop that converged coastforge to
    -0.010 EV by hand (2026-09-03), productized. Requires the editor
    open on the run's world (it naturally follows a build; every
    editor-side gate still applies)."""
    from forge_tool import verify_render
    run_dir = os.path.join(REPO, "forge_runs", a.name)
    if not os.path.isdir(run_dir):
        raise Refuse("no run at forge_runs/%s — build it first" % a.name)
    biome = biome_for(a.name)
    recipe_path = os.path.join(run_dir, "%s.json" % biome)
    brief_path = os.path.join(run_dir, "%s_brief.json" % biome)
    render = os.path.join(run_dir, "renders", a.name + ".png")
    for p, what in ((recipe_path, "recipe"), (brief_path, "brief"),
                    (render, "render")):
        if not os.path.isfile(p):
            raise Refuse("run is missing its %s (%s)" % (what, p))
    brief = json.load(open(brief_path, encoding="utf-8"))
    concept = os.path.join(REPO, brief["source_image"])
    recipe = json.load(open(recipe_path, encoding="utf-8"))
    geo = brief["lighting_geometry"]

    slope = geo.get("_ev_slope")  # measured on a prior iteration
    rel = lambda p: os.path.relpath(p, REPO)  # noqa: E731
    outdir = os.path.join(run_dir, "renders")
    for it in range(1, a.max_iters + 1):
        rep = verify_render.report(concept, render)
        delta = rep["delta"]["exposure_ev"]
        print("== polish iter %d: render is %+.3f EV vs concept"
              % (it, delta))
        if abs(delta) <= a.target_ev:
            print("CONVERGED: |%.3f| <= %.2f EV" % (delta, a.target_ev))
            break
        cur = geo.get("exposure_compensation_ev_override",
                      recipe["lighting"]["exposure"]["compensation_ev"])
        step = -delta / (slope if slope else 0.6)
        # bound each step: a huge measured delta is often framing/fog,
        # not pure exposure — walk, don't leap
        step = max(-3.0, min(3.0, step))
        new_ev = round(cur + step, 2)
        geo["exposure_compensation_ev_override"] = new_ev
        geo["_ev_provenance"] = (
            "forge polish iter %d: measured %+.3f EV, slope %s -> "
            "EV %s -> %s" % (it, delta, slope or "0.6 (default)",
                             cur, new_ev))
        with open(brief_path, "w", encoding="utf-8") as f:
            json.dump(brief, f, indent=1)
        run("relight (polish %d)" % it, "concept2level.py", [
            "--recipe", rel(recipe_path), "--brief", rel(brief_path),
            "--name", a.name, "--outdir", outdir, "--phase", "relight"],
            timeout=1800)
        rep2 = verify_render.report(concept, render)
        moved = rep2["delta"]["exposure_ev"] - delta
        if abs(step) > 0.05 and abs(moved) > 0.02:
            if moved / step < 0:
                # the render moved OPPOSITE to the push: the residual is
                # not exposure (fog/framing). Clamping this into a
                # plausible slope would drive the next step further
                # wrong (audit 2026-09-03) — stop and say so.
                with open(brief_path, "w", encoding="utf-8") as f:
                    json.dump(brief, f, indent=1)
                print("response INVERTED (%+.3f for %+.2f EV) — the "
                      "residual is not exposure; stopping. See the "
                      "fidelity report's instrument caveat."
                      % (moved, step))
                break
            slope = round(max(0.2, min(1.5, moved / step)), 3)
            geo["_ev_slope"] = slope
            print("   measured slope %.3f (moved %+.3f for %+.2f)"
                  % (slope, moved, step))
        with open(brief_path, "w", encoding="utf-8") as f:
            json.dump(brief, f, indent=1)
    else:
        rep = verify_render.report(concept, render)
        final = rep["delta"]["exposure_ev"]
        if abs(final) <= a.target_ev:
            print("CONVERGED on the final iteration: |%.3f| <= %.2f EV"
                  % (final, a.target_ev))
        else:
            print("iteration cap %d reached at %+.3f EV — the residual "
                  "is likely framing/content, not exposure (see the "
                  "fidelity report's instrument caveat)"
                  % (a.max_iters, final))
    verify_render.main([concept, render, "--out",
                        os.path.join(run_dir, "fidelity.json")])
    return 0


def author():
    """Open the Layout Author page and print the two steps that follow.

    This IS the keyless path's front door: the page carries the real
    stamp catalogue baked in (export_digest --inject), so there is
    nothing to configure — author, export, build.
    """
    ui = os.path.join(REPO, "examples", "forge_layout_author.html")
    if not os.path.isfile(ui):
        raise Refuse("Layout Author page missing (%s) — this "
                     "distribution is incomplete" % ui)
    import webbrowser
    from pathlib import Path
    # as_uri() percent-encodes: a dist under "C:\Users\My Name\#forge"
    # still opens (audit F2 — hand-built file:// URLs break on # and %)
    opened = webbrowser.open(Path(ui).as_uri())
    print("Layout Author%s: %s" % (
        " opened in your browser" if opened else
        " (open this file in a browser)", ui))
    print("")
    print("  1. Drop your concept image on the page, place stamps on")
    print("     the 3D preview until it matches the image, then")
    print("     'Export' — you get <world>.layout.json.")
    print("  2. Build it (no API key needed):")
    print("       forge build your_concept.jpg "
          "--layout <world>.layout.json --name <world>")
    print("")
    print("  Then optionally: forge polish --name <world>")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="image -> landscape, end to end")
    b.add_argument("image", nargs="?", help="concept image path")
    b.add_argument("--layout", help="pre-authored layout.json (no-key path)")
    b.add_argument("--name", required=True, help="run name (forge_runs/<name>)")
    b.add_argument("--max-brief-iters", type=int, default=None,
                   help="terrain repair iteration cap (default: brief_loop's "
                        "own; raise for slow-converging carves — the cap is "
                        "a refusal, not a tolerance)")

    p = sub.add_parser("polish", help="converge render exposure to the "
                       "concept (editor must hold the run's world)")
    p.add_argument("--name", required=True)
    p.add_argument("--target-ev", type=float, default=0.15)
    p.add_argument("--max-iters", type=int, default=3)

    i = sub.add_parser("init", help="emit the minimal UE project")
    i.add_argument("--dest", required=True)
    i.add_argument("--compile", action="store_true")

    sub.add_parser("doctor", help="check this machine is ready")

    sub.add_parser("author", help="open the visual Layout Author "
                   "(keyless path: no API key needed)")

    s = sub.add_parser("serve", help="the whole forge as one local web "
                       "page: author, build, download the project")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            return build(a)
        if a.cmd == "polish":
            return polish(a)
        if a.cmd == "author":
            return author()
        if a.cmd == "serve":
            from forge_tool import serve
            sv = ["--port", str(a.port)]
            if a.no_browser:
                sv.append("--no-browser")
            return serve.main(sv)
        if a.cmd == "doctor":
            from forge_tool import doctor
            return doctor.main([])
        if a.cmd == "init":
            from forge_tool import emit_project
            existing = os.path.join(os.path.abspath(a.dest), "LandscapeLab")
            if os.path.isdir(existing):
                # packaged dist: skeleton pre-emitted at package time —
                # init only compiles
                print("project already emitted: %s" % existing)
                if a.compile:
                    rc = emit_project.compile_plugin(existing)
                    if rc != 0:
                        print("COMPILE FAILED (exit %d)" % rc)
                        return 3
                    print("plugin compiled clean")
                return 0
            return emit_project.main(
                ["--dest", a.dest] + (["--compile"] if a.compile else []))
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    except subprocess.TimeoutExpired as e:
        print("REFUSE: leg timed out: %r" % e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
