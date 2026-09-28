"""bench_capture.py -- render the benchmark through Movie Render Queue.

    python scripts/bench_capture.py --profile dev [--dolly]
    python scripts/bench_capture.py --profile target
    python scripts/bench_capture.py --selftest        (offline, no editor)

Renders the three station stills, and with --dolly the 180-frame walk, into
_verify/bench/<date>/<profile>/, then writes bench_run_<profile>[_<tag>].json
beside them (NOT plain "bench_run.json" — globbing that name finds nothing)
carrying git sha, recipe sha, the profile, and READ-BACKS rather than requests.

WHY READ-BACK AND NOT REQUEST. On 2026-09-05 this project found a perf station
whose FOV was never declared, a `viewport_size` field that had been null for
weeks because the function behind it does not exist, and an MRQ property
(`CVars`) that looks settable from Python and is not. A recorded REQUEST proves
only that the script asked. Every field in the sidecar that can be read back
is read back, and the ones that CANNOT are labelled as requests in the file
itself rather than left to look like measurements.

THE ONE THING THAT IS NOT A TRUE READ-BACK, stated plainly: the console
variables. MRQ applies them when the shot starts and restores them when it
ends, so their during-render values are not observable from this channel. What
IS recorded is (a) the MRQ config read-back, which proves the setter took and
that the ScriptNoExport trap was avoided, and (b) the engine's surrounding
values before the render. Closing this properly means parsing the MRQ log,
which is not done here and is named in the sidecar as an open gap.

RESOLUTION IS READ BACK FROM THE ARTEFACT. The output setting's resolution is
recorded, and then the PNG's own pixel dimensions are measured off disk -- a
file that is 2560x1440 is the strongest possible evidence of what was rendered.

================================================================================
WHAT "TRUTH" MEANS HERE, AND THERE ARE TWO OF THEM
================================================================================
⛔ `--instrument truth` AND `--truth` ARE DIFFERENT INSTRUMENTS. Conflating
them is how a frame gets compared against the wrong reference.

  --instrument truth   EDITOR + HighResShot, every region force-loaded.
                       NO MoviePipeline at all, so NO GameOverride, so none
                       of the forcing below. Returns before the MRQ path.
  --truth              MRQ render WITH MoviePipelineGameOverrideSetting.
                       This is the one that forces LOD, HLOD and distance.

THE --truth INSTRUMENT IS NOT "THE SAME FRAME WITH EVERYTHING LOADED".
All 20 GameOverride properties, read back off the setting object 2026-09-13
under `--profile target --truth` (rule 12 -- this list is a READ-BACK, not the
three values the script sets):

    cinematic_quality_settings            True     <- class default
    use_lod_zero                          True     <- class default
    disable_hlods                         True     <- class default
    disable_hlo_ds                        True     <- deprecated alias, same field
    texture_streaming                     DISABLED <- class default
    use_high_quality_shadows              True     <- class default
    shadow_distance_scale                 10       <- class default
    shadow_radius_threshold               0.001    <- class default
    flush_grass_streaming                 True     <- class default
    override_grass_cull_distance_scale    True     <- class default
    grass_cull_distance_scale             50.0     <- class default
    override_grass_density_scale          False    <- class default
    grass_density_scale                   1.0      <- class default
    override_virtual_texture_feedback_factor True  <- class default
    virtual_texture_feedback_factor       1        <- class default
    soft_game_mode_override    MoviePipelineGameMode <- class default
    game_mode_override                    None     <- deprecated
    override_view_distance_scale          True     <- SET by --truth
    view_distance_scale                   100      <- SET by --truth
                                                   (benchmark.json residency.truth)
    flush_streaming_managers              True     <- SET by --truth

⭐ ONLY THE LAST THREE ARE CHOSEN. The other seventeen arrive as MRQ class
defaults the moment the setting is added, and before 2026-09-13 none of them
was ever read back or written down -- the ruling text said "all regions
force-loaded" and stopped there. A truth frame is therefore ALSO: LOD 0 on
every mesh, HLOD off, texture streaming off, high-quality shadows, grass cull
x50, and draw distance x100.

CONSEQUENCE FOR ACCEPTANCES. An acceptance about LOD, HLOD, cull or draw
distance taken on `--truth` measures the OVERRIDE, not the world. Audited
2026-09-13 over every sidecar in _verify/: six MRQ-truth captures exist
(09-06 dev diag, dev truth; 09-09 target mrqtruth, mrqtruth2, truth_task5;
09-10 truth_t5r) plus one editor-truth (09-07). All six measured residency and
featureless/luma content; NONE measured LOD, HLOD, cull or draw distance as its
subject. Clean -- but the definition above is now the record, so the next one
is checkable rather than assumed.

Plus `--game-override KEY=VALUE`, which installs the same setting outside
--truth and carries the same seventeen defaults. It is for diagnostics; a
capture using it is not a truth capture and is not comparable to one.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import ue_exec  # noqa: E402

# A render is a LONG job whose only progress signal is this script's stdout,
# and Python block-buffers stdout the moment it is redirected to a file or a
# pipe. That turns "still going" and "hung" into the same observation.
# LESSONS 2026-09-05 records this defect twice in one session -- a 686-camera
# search that ran 25 minutes against an empty file, and then THIS script,
# launched without -u an hour after that lesson was written. Fixing it at the
# source so no caller has to remember a flag.
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

REPO = bootstrap.REPO_ROOT
BENCH = os.path.join(REPO, "research", "brief", "brief1_distance_as_angle",
                     "brief1", "benchmark.json")
PAYLOADS = os.path.join(REPO, "scripts", "payloads")
STATIONS = ["near_ground", "mid_slope", "vista"]
# OPT-IN ONLY -- named with --stations or it does not render. The three
# above are the RATIFIED COMPARISON SET and a default run must keep
# producing exactly them, or frames stop being comparable across
# sessions. `ground` (Bench_ground, derived 2026-09-11) answers a
# different question -- the surface metrics -- and joining the default
# set would quietly redefine what "the bench" means.
EXTRA_STATIONS = ["ground"]
# Mutable one-element box so stage_probe can bake the declared radius into the
# probe without a global rebind.
NEAR_RADIUS_M = [600.0]

# The sky colour band is DECLARED in benchmark.json, never sampled from the
# frame under test -- see featureless_split. Loaded lazily so --selftest can
# override it, and defaulted rather than crashing if an older benchmark.json
# has no `scores.sky_colour_band`.
def _sky_band():
    # BENCH *is* the benchmark.json path — joining "benchmark.json" onto
    # it built ...\benchmark.json\benchmark.json, so the open ALWAYS
    # raised and the fallback ALWAYS won; the declared band was never
    # read (right numbers for the wrong reason — they happened to match;
    # Pass 3 2026-09-16). The selftest now asserts declared == loaded.
    try:
        b = json.load(open(BENCH, encoding="utf-8"))
        return b["scores"]["sky_colour_band"]
    except Exception:
        return {"min_blue_minus_red": 0.06, "require_monotonic_bgr": True}


SKY_BAND = _sky_band()
DEPTH_MATERIAL = "/Game/Bench/M_SceneDepth"

# R-GATE / AUDIT S-11 (closure A-8): the fraction of canopy rays that pass
# through alpha-tested foliage to sky. DERIVED, not fitted: the occlusion
# trace missed 17.25 sky-points at near_ground and they came out of its
# 81.33% canopy, so 17.25/81.33 = 0.212. The same 0.21 predicts mid_slope
# (0.21x28.93 = 6.1 pts) and vista (1.5 pts), both inside their observed
# spread on stations it was NOT derived from -- a testable number, and it
# held. See research/audit/inputs/CONTENT_GATE_S11.md.
CANOPY_POROSITY = 0.21


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def git_sha():
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                             capture_output=True)
        sha = out.stdout.decode().strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                               capture_output=True).stdout.decode().strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return None


def split_profile(profile_block):
    """Separate true console variables from the MRQ settings that merely LIVE
    in the same JSON block. mrq.temporal_samples is not a cvar."""
    cvars, mrq = {}, {}
    for k, v in profile_block.items():
        if k.startswith("_"):
            continue
        if k.startswith("mrq."):
            mrq[k] = v
        else:
            cvars[k] = v
    return cvars, mrq


def png_size(path):
    """Width/height straight out of the PNG IHDR. No image library needed, and
    it reads the FILE rather than asking the thing that wrote it."""
    with open(path, "rb") as f:
        head = f.read(33)
    if len(head) < 33 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if head[12:16] != b"IHDR":
        return None
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    return [w, h]


def featureless_fraction(path, tile=16, var_thresh=1e-5):
    """Fraction of the frame carrying NO detail at all.

    WHY THIS GATE EXISTS. On 2026-09-05 this script reported OK on a capture in
    which two of three frames contained no world: 2560x1440 confirmed off the
    file, 11/11 cvars confirmed from the engine's own log, mean luma a
    perfectly ordinary 0.77 -- and mid_slope was a white void because the World
    Partition cells around a station 2 km from the town never streamed in.

    Every check in this tool passed, because not one of them looked at CONTENT.
    Resolution, cvars, file size and mean luma are all satisfied by a blank
    frame. This measures the thing they cannot: how much of the image has no
    structure. Sky is legitimately featureless, so a high number is not
    automatically a failure -- it is compared against what the station was
    DERIVED to frame, which is the whole point of having a prediction.
    """
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("L")
    a = np.asarray(im).astype("float32") / 255.0
    h, w = a.shape
    h2, w2 = h // tile * tile, w // tile * tile
    t = a[:h2, :w2].reshape(h2 // tile, tile, w2 // tile, tile)
    var = t.var(axis=(1, 3))
    return float((var < var_thresh).mean())


def sky_mask_from_depth(depth_path, tile=16, ceiling_frac=0.999):
    """Tile-grid sky mask from the scene-depth pass (RULED 2026-09-10).

    Sky is decided GEOMETRICALLY: a tile whose median depth sits at or
    beyond the encoding ceiling (10.49 km) is sky or beyond the world.
    Colour never enters, which is the whole point -- LESSONS 2026-09-09e:
    the colour band keys on the property Brief 2 changes by design, so
    the more the sky desaturates the less of it the mask sees, and four
    metrics degrade together in the direction of the work.

    PREMISE (verification practice: state it, check it transfers): the
    depth pass and the beauty frame share camera, station and geometry.
    Depth is invariant to every Brief-2 change (lighting only), so ONE
    depth frame per station serves every task's frames at that station --
    but NOT a frame from a different station or resolution, and the tile
    grids are shape-checked by the caller for exactly that reason.

    CAVEAT stated, not hidden: terrain beyond the 10.49 km ceiling would
    also read as sky. The decode and ceiling are haze_metrics.py's,
    imported rather than re-implemented (one declaration).

    Median, not mean: a skyline-straddling tile's mean is dragged toward
    the ceiling by its sky half, while its median stays on whichever side
    holds more pixels -- the conservative edge behaviour.
    """
    import numpy as np
    from haze_metrics import decode_depth_m, CEILING_M
    dm = decode_depth_m(depth_path)
    h, w = dm.shape
    h2, w2 = h // tile * tile, w // tile * tile
    tiles = dm[:h2, :w2].reshape(h2 // tile, tile, w2 // tile, tile)
    med = np.median(tiles, axis=(1, 3))
    return med >= CEILING_M * ceiling_frac


def _tile_exclusion(rect, tile, nty, ntx):
    """Boolean tile grid: True where a tile overlaps the excluded rect.

    The grey card (R-GREYCARD, ruled 2026-09-10) is a MEASUREMENT TARGET,
    not scene content; leaving it in would count a synthetic 18% plane as
    featureless non-sky and pollute the very metrics it exists beside.
    """
    import numpy as np
    m = np.zeros((nty, ntx), dtype=bool)
    if rect:
        x0, y0, x1, y1 = rect
        tx0, ty0 = max(0, x0 // tile), max(0, y0 // tile)
        tx1 = min(ntx, (x1 + tile - 1) // tile)
        ty1 = min(nty, (y1 + tile - 1) // tile)
        m[ty0:ty1, tx0:tx1] = True
    return m


def featureless_split(path, band, tile=16, var_thresh=1e-5, depth_path=None,
                      exclude_rect_px=None):
    """featureless_fraction, split into SKY and NON-SKY (ruled 2026-09-09;
    sky mask REPLACED by depth, ruled 2026-09-10).

    Sky is legitimately featureless. A flat NON-sky region is a void, an
    untextured surface, or a blow-out -- and those are the failures worth
    catching. The single number could not tell them apart.

    THE MASK. With `depth_path` given, sky comes from the scene-depth pass
    (sky_mask_from_depth) -- geometric, colour-blind, immune to the Brief-2
    erosion in LESSONS 2026-09-09e. A tile-grid shape mismatch RAISES
    ValueError rather than falling back to colour: a wrong-station depth
    frame silently producing a plausible number is the failure mode, and a
    failed measurement reports that it failed.

    Without a depth frame the COLOUR band still applies (declared in
    benchmark.json, never sampled from the frame under test -- a blown
    white frame must not define white as sky; pure white has B - R = 0 and
    is NON-SKY, asserted in selftest). The caller records WHICH mask
    produced the number; colour-mask figures from Brief-2-era frames are
    not comparable across tasks (LESSONS 2026-09-09e).

    Returns (total, sky, non_sky) as fractions of the whole frame; the two
    parts sum to the total, so the existing number is unchanged and
    comparable with every prior run.
    """
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im).astype("float32") / 255.0
    g = np.asarray(im.convert("L")).astype("float32") / 255.0
    h, w = g.shape
    h2, w2 = h // tile * tile, w // tile * tile
    nty, ntx = h2 // tile, w2 // tile
    var = g[:h2, :w2].reshape(nty, tile, ntx, tile).var(axis=(1, 3))
    flat = var < var_thresh
    # Excluded tiles (the grey card's region) leave BOTH the numerator and
    # the denominator: they are not scene content in either direction.
    excl = _tile_exclusion(exclude_rect_px, tile, nty, ntx)
    flat = flat & ~excl
    total_tiles = float(var.size - excl.sum()) or 1.0
    if depth_path is not None:
        is_sky = sky_mask_from_depth(depth_path, tile)
        if is_sky.shape != (nty, ntx):
            raise ValueError(
                "depth tile grid %s does not match beauty tile grid %s "
                "(%s vs %s) -- wrong station or resolution; refusing to "
                "classify" % (is_sky.shape, (nty, ntx), depth_path, path))
    if not flat.any():
        return 0.0, 0.0, 0.0
    if depth_path is None:
        tc = rgb[:h2, :w2].reshape(nty, tile, ntx, tile, 3).mean(axis=(1, 3))
        r, gg, b = tc[..., 0], tc[..., 1], tc[..., 2]
        is_sky = (b - r) >= float(band["min_blue_minus_red"])
        if band.get("require_monotonic_bgr", True):
            is_sky = is_sky & (b >= gg) & (gg >= r)
    sky = float((flat & is_sky).sum()) / total_tiles
    non_sky = float((flat & ~is_sky).sum()) / total_tiles
    return float(flat.sum()) / total_tiles, sky, non_sky


def mean_luma(path):
    """Mean luma of a PNG, for the determinism check. Pillow only."""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype("float64") / 255.0
    return float((0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]).mean())


MRQ_LOG = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "Logs",
                       "LandscapeLab.log")
_CVAR_RE = None


def read_mrq_applied_cvars(since_byte=0):
    """The REAL during-render cvar read-back, from the engine's own log.

    MRQ writes one line per variable as it applies them:

        LogMovieRenderPipeline: Applying CVar "sg.ShadowQuality"
            PreviousValue: 1.000000 NewValue: 1.000000

    This is the channel the Python API cannot give us -- the setting restores
    its values when the shot ends, so anything read afterwards is the
    surrounding state, not the render's. Parsing the log turns a stated-open
    gap into an actual measurement of what the frames were rendered with.

    Also captures the engine's own resolution line, which is a second
    independent witness to the PNG's IHDR.
    """
    global _CVAR_RE
    import re
    if _CVAR_RE is None:
        _CVAR_RE = re.compile(
            r'Applying CVar "([^"]+)"\s+PreviousValue:\s*(-?[\d.]+)\s+'
            r'NewValue:\s*(-?[\d.]+)')
    res_re = re.compile(r"Total resolution: \((\d+)x(\d+)\)")
    applied, resolutions = {}, []
    if not os.path.isfile(MRQ_LOG):
        return {"_error": "no log at %s" % MRQ_LOG}, [], since_byte
    with open(MRQ_LOG, "r", encoding="utf-8", errors="replace") as f:
        f.seek(since_byte)
        text = f.read()
        end = f.tell()
    for m in _CVAR_RE.finditer(text):
        applied[m.group(1)] = {"previous": float(m.group(2)),
                               "applied": float(m.group(3))}
    for m in res_re.finditer(text):
        r = [int(m.group(1)), int(m.group(2))]
        if r not in resolutions:
            resolutions.append(r)
    return applied, resolutions, end


def log_size():
    return os.path.getsize(MRQ_LOG) if os.path.isfile(MRQ_LOG) else 0


def stage_probe(src, out_path):
    """Write the residency probe with its output path baked in.

    The probe runs via `py "<file>"` from MRQ, which passes no arguments, so
    the destination has to be IN the file. Staged under the UE project's
    Saved/ (the same place ue_exec stages payloads) rather than edited in
    place, so scripts/ stays a source tree and not a scratch pad."""
    text = open(src, encoding="utf-8").read()
    text = text.replace("__OUT_PATH__", repr(out_path.replace("\\", "/")))
    text = text.replace("__NEAR_M__", repr(float(NEAR_RADIUS_M[0])))
    d = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "LLPython")
    if not os.path.isdir(d):
        os.makedirs(d)
    # ⛔ THE STAGED NAME DERIVES FROM THE SOURCE. It was a fixed
    # "bench_residency_probe_staged.py", which was fine while there was
    # exactly one probe and silently destructive the moment there were
    # two: the second staging would overwrite the first, and MRQ would
    # then run the same probe twice under two names and the missing one
    # would simply produce no file. Caught before it ran (2026-09-13c).
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(d, "%s_staged.py" % base)
    open(dst, "w", encoding="utf-8").write(text)
    return dst


def read_residency(path):
    """One dict per shot, in the order MRQ ran them."""
    if not os.path.isfile(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def judge_residency(lines, jobs, expect_components, require_probe,
                    key="components"):
    """Verdict per shot. NO VERDICT is never PASS."""
    rows, worst = [], "PASS"
    for i, job in enumerate(jobs):
        rec = lines[i] if i < len(lines) else None
        if rec is None:
            rows.append({"job": job["name"], "verdict": "NO VERDICT",
                         "why": "no probe line for this shot -- 'I could not "
                                "look' is not 'it was there'"})
            worst = "NO VERDICT" if require_probe else worst
            continue
        if rec.get("error"):
            rows.append({"job": job["name"], "verdict": "NO VERDICT",
                         "why": "probe errored: %s" % rec["error"]})
            worst = "NO VERDICT"
            continue
        comps = int(rec.get(key, 0) or 0)
        unread = int(rec.get("components_unreadable", 0))
        row = {"job": job["name"], "components": comps, "counted": key,
               "components_whole_world": rec.get("components"),
               "near_radius_m": rec.get("near_radius_m"),
               "components_unreadable": unread,
               "proxies": rec.get("proxies"),
               "landscape_actors": rec.get("landscape_actors"),
               "foliage_instances": rec.get("foliage_instances"),
               "is_pie": rec.get("is_pie"),
               "view_target": rec.get("view_target")}
        if unread and comps == 0:
            row["verdict"] = "NO VERDICT"
            row["why"] = ("%d actors would not report components. That is 'I "
                          "could not count', NOT 'it was not there' "
                          "(R-FRAMECOST REJECTED)." % unread)
            worst = "NO VERDICT"
        elif comps < expect_components:
            row["verdict"] = "FAIL"
            row["why"] = ("%d of %d landscape components resident (%.1f%%)"
                          % (comps, expect_components,
                             100.0 * comps / max(expect_components, 1)))
            if worst != "NO VERDICT":
                worst = "FAIL"
        else:
            row["verdict"] = "PASS"
        rows.append(row)
    return worst, rows


def capture_truth(bm, stations, outroot, res, expect_components, date):
    """TRUTH INSTRUMENT: the editor, force-loaded, via HighResShot.

    ⛔⛔ RETIRED 2026-09-13 AND NO LONGER CALLED FROM ANYWHERE. Its only
    caller was the `--instrument truth` branch, which now refuses. Kept,
    not deleted, because two other files cite it by name as the lesson
    about a capture reporting success over a frame that never landed
    (census_project.py:123, lod_silhouette_capture.py:239) and because
    the recipe discipline is to record a superseded route rather than
    remove it. **It is dead code: do not call it, and do not read its
    survival as endorsement.**

    ⛔ SUPERSEDED 2026-09-09 -- PREFER `--truth --load-all-regions`, WHICH
    RUNS THROUGH MRQ. This editor route does not work: HighResShot will not
    complete above roughly 960x540 against a force-loaded world (measured
    2026-09-09 -- 960x540 landed in 296 s, 1920x1080 and 3840x2160 produced
    nothing in 26 and 15 minutes, with no error in the engine log). It is
    kept for the census it performs and for history.

    WHY NOT PIE -- AND THE ANSWER WAS WRONG. Three levers were tried on
    2026-09-06 to make PIE hold the whole world; none moved residency off
    16/1024, so the truth frame was moved here. ONE OF THOSE LEVERS WAS NEVER
    CONNECTED: `residency.truth.grid` said "MainGrid", a SpatialHash name,
    while this world's UWorldPartitionRuntimeHashSet names its default
    partition "MainPartition" (WorldPartitionRuntimeHashSet.cpp:269), and
    wp.Runtime.OverrideRuntimeLoadingRange is an exact FName lookup with no
    wildcard (WorldPartitionSubsystem.cpp:563-571). A wrong name does not
    warn; it silently does nothing.

    With the name corrected, PIE reaches FULL residency -- near_ground
    expected 808 resident 3477 missing 0, mid_slope expected 20 resident 3420
    missing 0, the first residency PASS this project has recorded.

    A null result from a disconnected lever is not evidence about the lever.

    The instrument SPLIT is still right and is unaffected: the player
    instrument measures what a player sees, the truth instrument measures what
    is there, and conflating them is what produced a "confirmed" station
    rendered on 1.2% of a world. Only the mechanism moved.

    Capture goes through scripts/shoot.py, which already owns HighResShot, the
    camera read-back and -- the part that matters -- waits for the file ON THE
    HOST rather than sleeping on the game thread it needs to tick.
    """
    import subprocess as _sp
    stills, census = {}, None

    # 25, not 900 -- see the note on the --load-all-regions call site. The
    # window bounds NODE DISCOVERY; execution is unbounded either way, and
    # 900 was 15 minutes of idle editor before every truth capture.
    code, loaded, _raw = run_payload("bench_load_regions.py", timeout=25.0)
    if not loaded or loaded.get("error"):
        return None, None, ("region load failed: %s"
                            % (loaded.get("error") if loaded else "no marker"))
    census = loaded.get("editor_census") or {}
    got = int(census.get("components", 0))
    print("  editor census after force-load: %s proxies, %s/%s components, "
          "%s foliage instances" % (census.get("proxies"), got,
                                    expect_components,
                                    census.get("foliage_instances")))
    if got < expect_components:
        return stills, census, ("truth frame REFUSED: editor holds %d of %d "
                                "components after force-load" % (got, expect_components))

    derived = _load_derivation(date)
    for st in stations:
        d = derived["derived_stations"][st]
        loc = d["location_cm"]
        pitch, yaw, roll = d["rotation_deg_pitch_yaw_roll"]
        # `--loc=<v>`, NOT `--loc <v>`. This world spans -406400..406400 cm, so
        # every station's location string starts with a minus sign, and
        # argparse's negative-number matcher only exempts tokens that are
        # ENTIRELY a number -- "-406400.0,-406400.0,13000.0" has commas, so it
        # is read as an option flag and `--loc` reports "expected one
        # argument". The equals form has no such ambiguity.
        # Measured 2026-09-09: this is why capture_truth had never produced a
        # frame; shoot.py exited 2 every time and the exit code was not tested.
        cmd = [sys.executable, os.path.join(REPO, "scripts", "shoot.py"),
               "--name", st,
               "--loc=%.1f,%.1f,%.1f" % (loc[0], loc[1], loc[2]),
               "--rot=%.4f,%.4f,%.4f" % (roll, pitch, yaw),
               "--fov=%.1f" % bm["declared_camera"]["fov_h_deg"],
               "--res=%dx%d" % (res[0], res[1]),
               "--outdir", outroot,
               "--deadline", "1800"]
        print("  shoot %s ..." % st)
        # SAME TRAP AS THE MRQ POLL, AND IT COST A FALSE "OK" ON 2026-09-09.
        # This globbed <station>*.png, found the PLAYER run's file already in
        # outroot, marked exists=True and measured it -- while shoot.py had
        # produced nothing and the engine log carried no HighResShot line at
        # all. `shoot_exit` was recorded and never TESTED, so shoot.py's
        # stdout was printed only in the branch that could no longer be
        # reached. The run then printed "OK -- truth frames captured at full
        # residency." Two independent guards now, because either alone was
        # enough to be fooled: the exit code, and the file's own age.
        shot_t0 = time.time() - 1.0
        r = _sp.run(cmd, cwd=REPO, capture_output=True)
        out = r.stdout.decode(errors="replace")
        err = r.stderr.decode(errors="replace")
        # AUDIT 2026-09-10 F2: a SceneDepth pass or a _diff frame must
        # never be promoted to beauty when the true beauty is missing.
        hits = sorted(p for p in glob.glob(os.path.join(outroot, st + "*.png"))
                      if os.path.getmtime(p) >= shot_t0
                      and "SceneDepth" not in os.path.basename(p)
                      and not os.path.basename(p).endswith("_diff.png"))
        if r.returncode != 0 or not hits:
            why = ("shoot.py exited %d" % r.returncode if r.returncode
                   else "shoot.py exited 0 but wrote no NEW %s*.png into %s"
                        % (st, outroot))
            print("  TRUTH SHOT FAILED: %s" % why)
            print(out[-1200:])
            if err.strip():
                print("  stderr: %s" % err[-600:])
            stills[st] = {"exists": False, "shoot_exit": r.returncode,
                          "failure": why}
            continue
        p = hits[0]
        if os.path.basename(p) != st + ".png":
            os.replace(p, os.path.join(outroot, st + ".png"))
            p = os.path.join(outroot, st + ".png")
        _dp = _station_depth(outroot, st)
        _gc = _greycard_rect(st)
        _fl = featureless_split(p, SKY_BAND, depth_path=_dp,
                                exclude_rect_px=_gc)
        stills[st] = {"exists": True,
                      "path": os.path.relpath(p, REPO).replace("\\", "/"),
                      "bytes": os.path.getsize(p),
                      "png_size_from_file": png_size(p),
                      "mean_luma": round(mean_luma(p), 6),
                      "featureless_fraction": round(_fl[0], 4),
                      "featureless_sky_fraction": round(_fl[1], 4),
                      "featureless_non_sky_fraction": round(_fl[2], 4),
                      "sky_mask": "depth" if _dp else "colour",
                      "greycard_excluded_rect_px": _gc,
                      "shoot_exit": r.returncode}
    return stills, census, None


def _greycard_rect(st):
    """The station's grey-card pixel region (R-GREYCARD), or None. Absent
    file or station means no card was ever placed there -- nothing to
    exclude, and the sidecar records which it was."""
    try:
        import greycard
        return greycard.region_for(st)
    except Exception:
        return None


def _station_depth(outroot, st):
    """The station's SceneDepth pass beside its beauty frame, if this run
    produced one (--depth). Sky masks prefer it (ruled 2026-09-10); the
    sidecar records WHICH mask produced the number either way, because a
    colour-mask figure on a Brief-2-era frame is not comparable across
    tasks (LESSONS 2026-09-09e)."""
    hits = sorted(glob.glob(os.path.join(outroot, st + "*SceneDepth*.png")))
    return hits[0] if hits else None


def _load_derivation(date):
    dpath = os.path.join(REPO, "_verify", "bench", date,
                         "bench_stations_derived.json")
    if not os.path.isfile(dpath):
        cands = sorted(glob.glob(os.path.join(
            REPO, "_verify", "bench", "*", "bench_stations_derived.json")))
        if not cands:
            raise IOError("no bench_stations_derived.json under _verify/bench/")
        dpath = cands[-1]
    return json.load(open(dpath, encoding="utf-8"))


def run_payload(name, subs=None, timeout=25.0):
    # `timeout` is ue_exec's NODE DISCOVERY WINDOW and is spent in full; it
    # does NOT bound execution (ue_exec.run passes it only to
    # _select_verified_node, and remote.run_command takes no timeout). Every
    # caller here used to pass 120-900 "to be safe", which bought nothing and
    # cost that many seconds of an idle editor on every single call.
    text = open(os.path.join(PAYLOADS, name), encoding="utf-8").read()
    for k, v in (subs or {}).items():
        text = text.replace(k, v)
    code, parsed, raw = ue_exec.run(text, timeout=timeout,
                                    stage_name=os.path.splitext(name)[0],
                                    quiet=True)
    return code, parsed, raw


def selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %-56s %s" % (label, "PASS" if cond else "FAIL"))

    bm = json.load(open(BENCH, encoding="utf-8"))
    # SKY_BAND must be the DECLARED band, not the fallback (Pass 3
    # 2026-09-16: _sky_band silently fell back for months because it
    # joined "benchmark.json" onto a path that already was the file —
    # undetectable while fallback == declared; this catches the drift).
    check("SKY_BAND is the band benchmark.json declares",
          SKY_BAND == bm["scores"]["sky_colour_band"])
    dev, _ = split_profile(bm["profiles"]["dev"])
    tgt, tgt_mrq = split_profile(bm["profiles"]["target"])
    check("dev profile yields cvars, no mrq.* leaks in", "mrq.temporal_samples" not in dev)
    check("target's mrq.temporal_samples is separated out",
          tgt_mrq.get("mrq.temporal_samples") == 8)
    check("target cvars still contain r.ScreenPercentage",
          "r.ScreenPercentage" in tgt)
    check("no underscore keys survive", not any(k.startswith("_") for k in tgt))
    check("declared camera is the RULED 4K", bm["declared_camera"]["res"] == [3840, 2160])
    check("floor is 1440p", bm["declared_camera"]["floor_res"] == [2560, 1440])

    # png_size must read a real file and refuse a non-PNG
    import tempfile
    from PIL import Image
    d = tempfile.mkdtemp(prefix="benchcap_")
    p = os.path.join(d, "t.png")
    Image.new("RGB", (37, 11), (10, 20, 30)).save(p)
    check("png_size reads IHDR off disk (37x11)", png_size(p) == [37, 11])
    q = os.path.join(d, "notpng.png")
    open(q, "wb").write(b"not a png at all, really not")
    check("png_size refuses a non-PNG rather than guessing", png_size(q) is None)
    lum = mean_luma(p)
    check("mean_luma in range for a dark grey (%.4f)" % lum, 0.0 < lum < 0.15)

    # THE SKY SPLIT. The property the whole design rests on is that a BLOWN
    # WHITE frame counts as NON-sky: a per-frame reference would call it all
    # sky and excuse the 2026-09-05 white void, which passed every other check.
    band = SKY_BAND
    wp_ = os.path.join(d, "white.png")
    Image.new("RGB", (256, 256), (255, 255, 255)).save(wp_)
    t, s, n = featureless_split(wp_, band)
    check("a blown WHITE frame is featureless (%.2f)" % t, t > 0.99)
    check("...and is scored NON-SKY, not sky (sky=%.2f non_sky=%.2f)" % (s, n),
          s == 0.0 and n > 0.99)

    sp_ = os.path.join(d, "sky.png")
    Image.new("RGB", (256, 256), (126, 160, 192)).save(sp_)   # 0.494/0.627/0.753
    t2, s2, n2 = featureless_split(sp_, band)
    check("a flat SKY-BLUE frame is scored SKY (sky=%.2f)" % s2,
          s2 > 0.99 and n2 == 0.0)

    gp_ = os.path.join(d, "grey.png")
    Image.new("RGB", (256, 256), (128, 128, 128)).save(gp_)
    _t3, s3, n3 = featureless_split(gp_, band)
    check("a flat NEUTRAL GREY frame is NON-sky (non_sky=%.2f)" % n3,
          s3 == 0.0 and n3 > 0.99)

    check("the split sums to the total", abs((s2 + n2) - t2) < 1e-9)

    # GREY-CARD EXCLUSION (R-GREYCARD; audit 2026-09-10 F7). A 256x256
    # frame at tile 16 is a 16x16 grid; excluding a 64x64 rect removes
    # exactly 16 tiles from BOTH sides of the fraction, so a fully flat
    # frame still reads 1.0 -- the card leaves the metric, it does not
    # dent it. And the excluded region's content must not matter: paint
    # the rect a wild colour and the numbers stay identical.
    ep_ = os.path.join(d, "excl.png")
    im_ = Image.new("RGB", (256, 256), (128, 128, 128))
    for _y in range(0, 64):
        for _x in range(0, 64):
            im_.putpixel((_x, _y), (255, 0, 255))
    im_.save(ep_)
    t4, s4, n4 = featureless_split(ep_, band, exclude_rect_px=(0, 0, 64, 64))
    check("excluded rect leaves numerator AND denominator (total=%.2f)" % t4,
          abs(t4 - 1.0) < 1e-9 and s4 == 0.0 and abs(n4 - 1.0) < 1e-9)
    t5_, _, n5_ = featureless_split(gp_, band, exclude_rect_px=(0, 0, 64, 64))
    check("exclusion changes the denominator, not the verdict",
          abs(t5_ - 1.0) < 1e-9 and abs(n5_ - 1.0) < 1e-9)
    import shutil
    shutil.rmtree(d, ignore_errors=True)

    # ---- the residency judge, in three directions ------------------------
    J = [{"name": "j0"}, {"name": "j1"}]
    full = {"components": 1024, "components_unreadable": 0, "proxies": 4}
    short = {"components": 96, "components_unreadable": 0, "proxies": 4}
    blind = {"components": 0, "components_unreadable": 7, "proxies": 4}
    check("full residency on both shots -> PASS",
          judge_residency([full, full], J, 1024, True)[0] == "PASS")
    check("a short shot -> FAIL, not PASS",
          judge_residency([full, short], J, 1024, True)[0] == "FAIL")
    check("a missing probe line -> NO VERDICT, not PASS",
          judge_residency([full], J, 1024, True)[0] == "NO VERDICT")
    check("a probe that errored -> NO VERDICT",
          judge_residency([full, {"error": "boom"}], J, 1024, True)[0] == "NO VERDICT")
    check("unreadable components -> NO VERDICT, NOT 'it was not there'",
          judge_residency([full, blind], J, 1024, True)[0] == "NO VERDICT")
    v, rows = judge_residency([full, blind], J, 1024, True)
    check("...and its reason says 'could not count', not 'absent'",
          "could not count" in rows[1]["why"])
    check("probe optional -> a missing line does not force NO VERDICT",
          judge_residency([full], J, 1024, False)[0] == "PASS")
    check("residency block is declared in benchmark.json",
          isinstance(bm.get("residency"), dict)
          and bm["residency"]["expect_landscape_components"] == 1024)
    check("bench and perf agree on how big the world is",
          bm["residency"]["expect_landscape_components"]
          == json.load(open(os.path.join(REPO, "recipes", "perf_budgets.json"),
                            encoding="utf-8"))["spline"].get("expect_components",
                                                             1024))

    print()
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["dev", "target"])
    ap.add_argument("--dolly", action="store_true")
    ap.add_argument("--dolly-seconds", type=float, default=0.0,
                    help="duration the dolly SEQUENCE was built with. Only "
                         "used to know how many frames completion must wait "
                         "for; it does not change the sequence. Defaults to "
                         "benchmark.json dolly.seconds.")
    ap.add_argument("--dolly-only", action="store_true",
                    help="render ONLY the dolly. The station jobs overwrite "
                         "_verify/bench/<date>/<profile>/<station>.png, and "
                         "that directory holds the Phase C stills the "
                         "research send-back cites.")
    ap.add_argument("--dolly-seq", default="Bench_Dolly",
                    help="Level Sequence NAME under /Game/Bench (not a path: "
                         "R-UEEXEC -- a /Game/ path through Git Bash is "
                         "rewritten). E4 uses Bench_Dolly_Sunlit, a 3 s "
                         "variant, so the ratified 6 s Bench_Dolly is left "
                         "alone.")
    ap.add_argument("--date", default=None)
    ap.add_argument("--timeout-s", type=float, default=3600.0)
    ap.add_argument("--poll-s", type=float, default=15.0)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--drop-cvar", action="append", default=[],
                    metavar="NAME",
                    help="omit this cvar from the profile for a diagnostic "
                         "run; benchmark.json is left untouched")
    ap.add_argument("--pp-pass", action="append", default=[],
                    metavar="NAME=/Game/Path/M_Mat",
                    help="render an ADDITIONAL post-process pass through "
                         "this material and write it as its own file. For "
                         "splitting the post chain: a material at "
                         "BL_SCENE_COLOR_AFTER_DOF (what 5.8 calls the "
                         "location the UI names Before Tonemapping) "
                         "emitting PostProcessInput0 writes the buffer as "
                         "it stands before the tonemap pass.")
    ap.add_argument("--add-cvar", action="append", default=[],
                    metavar="NAME=VALUE",
                    help="add or override a cvar for a diagnostic run; "
                         "benchmark.json is left untouched. Applied through "
                         "MRQ like every other cvar, so it is read back into "
                         "the sidecar.")
    ap.add_argument("--temporal-samples", type=int, default=None,
                    help="override mrq.temporal_samples for a diagnostic "
                         "run; benchmark.json is left untouched")
    ap.add_argument("--tag", default=None,
                    help="suffix the output dir, for a determinism re-run")
    ap.add_argument("--no-render-warm-up", dest="render_warm_up",
                    action="store_false",
                    help="leave RenderWarmUpFrames OFF, i.e. zero RENDERED "
                         "warm-up frames. That was the engine default and "
                         "therefore what every capture before 2026-09-12 "
                         "silently used; kept only to reproduce that state "
                         "for a controlled comparison.")
    ap.add_argument("--render-warm-up-count", type=int, default=40,
                    help="rendered frames discarded before the measured "
                         "one. 40 is MEASURED, not the engine default: a "
                         "settle sweep at 32/64/128 held the PPI0 grey "
                         "card to 0.006%% and 0.031%% and a 300 m-1 km "
                         "depth crop to 0.059%% and 0.020%%, so the bench "
                         "settles by 32; 40 is that plus 25%% headroom. "
                         "See scripts/warmup_settle.py and "
                         "_verify/bench/2026-09-13/warmup_settle.json.")
    ap.add_argument("--stations", nargs="+", default=None,
                    help="subset of stations, for a fast diagnostic run")
    ap.add_argument("--instrument",
                    choices=["editor_player", "player", "player_streaming", "truth"],
                    default="editor_player",
                    help="EDITOR_PLAYER (default; `player` is the retained alias): "
                         "MRQ RUNNING INSIDE THE EDITOR renders the EDITOR WORLD. "
                         "Runtime WORLD-PARTITION STREAMING and the HLOD PROXY SWAP "
                         "happen only in PIE / a -game process, NOT in the editor "
                         "world MRQ renders -- so this instrument shows the "
                         "editor's resident cells, never the proxy band a player "
                         "sees. It applies the DERIVED loading range via "
                         "wp.Runtime.OverrideRuntimeLoadingRange so the visible "
                         "cells are resident (no voids). RENAMED from `player` "
                         "2026-09-16 (D-2 item 1) to say WHICH world it is. "
                         "PLAYER_STREAMING: no override; must run in a -game "
                         "process to show the proxy band (D-2 item 1b) -- in the "
                         "editor it still renders real cells (D-1 item 1). "
                         "[RETIRED] `--instrument truth` (2026-09-13) ERRORS -- "
                         "use --truth; the choice is kept so the refusal can "
                         "explain itself.")
    ap.add_argument("--near-field", action="store_true",
                    help="judge residency AROUND THE CAMERA rather than over "
                         "the whole world: correct for a near-field shot such "
                         "as the dolly, wrong for a truth frame.")
    ap.add_argument("--load-all-regions", action="store_true",
                    help="force-load every World Partition region in the EDITOR "
                         "before rendering, so PIE duplicates a loaded world. "
                         "Same flag name and same underlying call as "
                         "measure_frame_cost --load-all-regions.")
    ap.add_argument("--linear", action="store_true",
                    help="SCENE-LINEAR EXR: disable the filmic tone curve "
                         "(MoviePipelineColorSetting.bDisableToneCurve) so "
                         "the EXR carries unbounded scene-referred values. "
                         "RULED 2026-09-11 for card measurement -- the "
                         "display-referred EXRs clamp at exactly 1.0, which "
                         # ESCAPED. argparse formats help as `help % params`
                         # with params a DICT, so a bare percent raises
                         # "TypeError: %o format: an integer is required,
                         # not dict" and --help dies -- which it had been
                         # doing, so the tool could not document itself.
                         "is why a ruled exposure step delivered 65%% of "
                         "itself. Not the default: the bench's comparison "
                         "frames are display-referred on purpose.")
    ap.add_argument("--depth", action="store_true",
                    help="also render a SCENE-DEPTH pass via the authored "
                         "post-process material /Game/Bench/M_SceneDepth. "
                         "The material emits LOG2-ENCODED depth -- "
                         "log2(max(depth_cm,1))/20, ceiling ~10.49 km -- NOT "
                         "raw centimetres (make_depth_material.py); decode "
                         "via haze_metrics.decode_depth_m. It lands through "
                         "both output classes and the sky mask consumes the "
                         "PNG. There is no "
                         "depth pass class in 5.8 (MoviePipelineDeferredPasses"
                         ".h ships Lit/Unlit/DetailLighting/LightingOnly/"
                         "ReflectionsOnly/PathTracer only), so depth arrives "
                         "as an AdditionalPostProcessMaterial. Forces "
                         "temporal samples to 1: depth cannot be "
                         "multisampled and still line up with the beauty "
                         "frame.")
    ap.add_argument("--game-override", action="append", default=[],
                    metavar="KEY=VALUE",
                    help="Set a property on MoviePipelineGameOverrideSetting, "
                         "e.g. --game-override cinematic_quality_settings=true. "
                         "Repeatable. Names are the snake_case bindings of "
                         "MoviePipelineGameOverrideSetting.h:79-151. "
                         "NOTE: before this flag existed a DEV capture "
                         "carried NO GameOverride setting at all -- only "
                         "--truth added one -- so dev-profile questions "
                         "about disable_hlods / use_lod_zero / "
                         "cinematic_quality_settings were being asked "
                         "about a setting absent from the config.")
    ap.add_argument("--exr-compression", default="ZIP",
                    choices=["None", "RLE", "ZIPS", "ZIP", "PIZ", "PXR24"],
                    help="EEXRCompressionFormat for the EXR output "
                         "(MoviePipelineEXROutput.h:53-67). Default ZIP = "
                         "ZIP(16 scanlines), lossless. The ENGINE default "
                         "is PIZ, and until 2026-09-14 this class was "
                         "added by --linear and never configured, so the "
                         "format of the file every look acceptance is "
                         "measured from was undeclared. Applies with "
                         "--linear.")
    ap.add_argument("--exr-multilayer", action="store_true",
                    help="write every render pass into ONE exr. Default "
                         "off: the reader here (OpenEXR 3.3.2 via "
                         "exr_card) addresses files, not layers.")
    ap.add_argument("--echo-scalability", action="store_true",
                    help="Append Scalability + sg.* queries to BOTH the "
                         "start and end console command lists, so the "
                         "levels the frames actually rendered at appear in "
                         "the engine log. Read from outside the render they "
                         "would be the surrounding state, not the state "
                         "under test.")
    ap.add_argument("--dump-config", action="store_true",
                    help="Build the MRQ config exactly as a render would, "
                         "dump every setting and property as the ENGINE "
                         "holds it, and STOP without rendering. The dump "
                         "comes from the same construction the render uses, "
                         "so it cannot drift from it.")
    ap.add_argument("--truth", action="store_true",
                    help="TRUTH FRAME: force World Partition to load every cell "
                         "and take distance culling out, so a later HLOD or "
                         "imposter result has a reference. Slow, and NOT a "
                         "benchmark frame.")
    a = ap.parse_args(argv)
    # `player` is the retained alias for `editor_player` (D-2 item 1): every
    # existing caller keeps working, and the sidecar/checks see one canonical
    # name that says which world MRQ rendered.
    if a.instrument == "player":
        a.instrument = "editor_player"

    if a.selftest:
        return selftest()
    if not a.profile:
        ap.error("--profile is required")

    bm = json.load(open(BENCH, encoding="utf-8"))
    date = a.date or datetime.date.today().isoformat()
    prof_dir = a.profile + ("_" + a.tag if a.tag else "")
    outroot = os.path.join(REPO, "_verify", "bench", date, prof_dir)
    os.makedirs(outroot, exist_ok=True)

    cvars, mrq = split_profile(bm["profiles"][a.profile])
    # DIAGNOSTIC, 2026-09-09. The two exposure cvars below were added to BOTH
    # profiles by 535dba3c, AFTER the last good capture, to kill the
    # auto-exposure drift the dolly showed. The 2026-09-06 sidecar records
    # them as never applied; today's records 1.0->0.0 and 2.0->0.0 -- and
    # today's frames are 4-5 stops hot. Dropping one lets that be tested
    # without editing benchmark.json, which is the research desk's contract.
    for _name in a.drop_cvar:
        if cvars.pop(_name, None) is not None:
            print("  DIAGNOSTIC: dropped %s from the %s profile"
                  % (_name, a.profile))
        else:
            print("  DIAGNOSTIC: %s was not in the %s profile"
                  % (_name, a.profile))
    # ADD, the mirror of drop. Same contract: benchmark.json is the research
    # desk's file and is left untouched, so a one-capture probe cannot leak
    # into the ratified profile. The value goes through MRQ's console
    # variable setting like every other cvar, which means it is READ BACK
    # into the sidecar by the same path -- a probe whose setting is not
    # proven to have landed measures nothing (rule 12).
    for _pair in a.add_cvar:
        if "=" not in _pair:
            print("REFUSE: --add-cvar wants NAME=VALUE, got %r" % _pair)
            return 1
        _n, _v = _pair.split("=", 1)
        _n, _v = _n.strip(), _v.strip()
        try:
            _val = float(_v)
        except ValueError:
            print("REFUSE: --add-cvar value %r is not a number" % _v)
            return 1
        _had = _n in cvars
        cvars[_n] = _val
        print("  DIAGNOSTIC: %s %s = %s"
              % ("overrode" if _had else "added", _n, _val))
    _pp_passes = []
    for _spec in a.pp_pass:
        if "=" not in _spec:
            print("REFUSE: --pp-pass wants NAME=/Game/Path, got %r" % _spec)
            return 1
        _nm, _path = _spec.split("=", 1)
        _nm, _path = _nm.strip(), _path.strip()
        if not _path.startswith("/Game/"):
            print("REFUSE: --pp-pass material must be a /Game/ path, got %r"
                  % _path)
            return 1
        _pp_passes.append({"name": _nm, "material": _path})
        print("  DIAGNOSTIC: extra post-process pass %s -> %s"
              % (_nm, _path))

    res = bm["declared_camera"]["floor_res"] if a.profile == "dev" \
        else bm["declared_camera"]["res"]
    temporal = int(mrq.get("mrq.temporal_samples", 1))
    # DIAGNOSTIC OVERRIDE, 2026-09-09. The first ever `target` run came back
    # 4-5 stops over-exposed (near_ground luma 0.95, mid_slope 1.0 with EVERY
    # pixel at 255) while every `dev` run before it sat at 0.35/0.77/0.71 --
    # and dev and target declare the SAME exposure cvars, so exposure config
    # is not the difference. `mrq.temporal_samples` (dev 1, target 8) is, and
    # 8x is about 3 stops. This flag exists to bisect that WITHOUT editing
    # benchmark.json, which is the research desk's contract and not ours to
    # mutate for a test. The value used is recorded in the sidecar either way.
    if a.temporal_samples is not None:
        temporal = int(a.temporal_samples)

    # ---- RESIDENCY: declared, applied, read back -------------------------
    resi = bm.get("residency")
    if not resi:
        print("REFUSE: benchmark.json declares no `residency` block. A "
              "precondition that is not declared cannot be read back, and an "
              "undeclared precondition is how a capture reports OK over an "
              "empty frame (2026-09-05). See R-BENCHCAPTURE.")
        return 6
    expect_components = int(resi["expect_landscape_components"])
    warm_up = int(resi["engine_warm_up_frames"])

    # NEAR-FIELD MODE. Measured 2026-09-06: PIE streams roughly 4 landscape
    # proxies (16 of 1024 components) around the camera and NOTHING further,
    # and neither the editor region loader nor
    # wp.Runtime.OverrideRuntimeLoadingRange changes that. Demanding all 1024
    # is therefore correct for a TRUTH frame and wrong for a near-field shot --
    # a dolly through the town does not need cells 4 km away, and a gate that
    # refuses correct work is a gate that gets switched off.
    # ---- DERIVED RESIDENCY (ruled 2026-09-09) ---------------------------
    # Replaces the typed expectations. `expect_landscape_components: 1024` and
    # the near-field `16 within 600 m` were both wrong in the SAME direction:
    # they demanded content from outside the loading range. The engine's own
    # default range is 25600 cm (RuntimePartition.cpp:27) -- 256 m -- so a gate
    # asking for 600 m, let alone the whole 8 km world, could never pass. That
    # is why every bench run this project has taken failed residency.
    derived = resi.get("derived") if a.instrument == "editor_player" else None
    derived_expected = {}
    if derived:
        print("  residency mode: DERIVED — grid %s, loading range %d cm "
              "(%.0f m); expectation comes from the engine, not the file"
              % (str(derived["grid"]), int(derived["loading_range_cm"]),
                 int(derived["loading_range_cm"]) / 100.0))

    near = resi.get("near_field") or {}
    if a.instrument in ("editor_player", "player_streaming") and not a.near_field:
        # The player instrument judges what the player sees. World Partition
        # streams ~1 km around the camera and three separate levers failed to
        # change that, so whole-world residency is the wrong question here and
        # asking it only produces a gate that refuses correct work.
        a.near_field = True
    if a.near_field and a.instrument != "truth":
        NEAR_RADIUS_M[0] = float(near.get("radius_m", 600.0))
        expect_components = int(near.get("expect_components_within_radius", 16))
        expect_key = "near_components"
        print("  residency mode: NEAR-FIELD — %d components within %.0f m of "
              "the camera" % (expect_components, NEAR_RADIUS_M[0]))
    else:
        expect_key = "components"
    resi_path = os.path.join(REPO, "_verify", "bench", date,
                             "residency_%s.jsonl" % prof_dir)
    if os.path.isfile(resi_path):
        os.remove(resi_path)          # this run's lines only
    probe = os.path.join(PAYLOADS, "bench_residency_probe.py")
    staged_probe = stage_probe(probe, resi_path)
    end_commands = ['py "%s"' % staged_probe.replace("\\", "/")]

    # TONE-CURVE READ-BACK, from INSIDE the render (2026-09-13c). A second
    # staged probe rather than an addition to the residency one: that probe
    # has a contract bench_capture parses, and widening it to carry an
    # unrelated reading is how a file grows two jobs and answers neither
    # cleanly. `disable_tone_curve` is what the setter wrote; this records
    # what the VIEW and the VOLUME actually hold while the frame renders.
    tc_path = os.path.join(REPO, "_verify", "bench", date,
                           "tonecurve_%s.jsonl" % prof_dir)
    if os.path.isfile(tc_path):
        os.remove(tc_path)
    staged_tc = stage_probe(
        os.path.join(PAYLOADS, "bench_tonecurve_probe.py"), tc_path)
    end_commands.append('py "%s"' % staged_tc.replace("\\", "/"))

    start_commands = []
    truth = None
    if a.truth:
        truth = resi["truth"]
        if not truth.get("grid"):
            print("REFUSE: --truth needs residency.truth.grid, and it is null. "
                  "The grid name is DISCOVERED, not guessed: run "
                  "scripts/payloads/bench_grid_derive.py through ue_exec "
                  "(it reads the runtime grid from the WORLD; "
                  "bench_grid_probe.py answers the spatial-hash case only) "
                  "and record the name in benchmark.json residency.truth.grid. "
                  "(A --discover-grid flag was cited here for months and "
                  "never existed.)")
            return 6
        start_commands = [
            "wp.Runtime.OverrideRuntimeLoadingRange -grid=%s -range=%d"
            % (truth["grid"], int(truth["loading_range_cm"])),
            "wp.Runtime.MaxLoadingStreamingCells %d"
            % int(truth["max_loading_streaming_cells"]),
        ]
        warm_up = max(warm_up, int(resi.get("truth_warm_up_frames", warm_up * 2)))

    if derived:
        # APPLY the loading range rather than assume it. The value cannot be
        # READ from the world -- RuntimePartitions is private -- so it is
        # declared, applied here, and its effect read back through the
        # expected/resident sets. Standing rule 12: a parameter that is not
        # read back is prose. FRuntimePartitionStreamingData::GetLoadingRange
        # (WorldPartitionRuntimeHashSet.cpp:125-135) consults the override
        # first, keyed on the PARTITION name.
        # NOT WHEN --truth. Both blocks name the SAME grid now that
        # truth.grid is corrected to MainPartition, and this append lands
        # AFTER the truth command, so the last writer wins: a 12 km truth
        # range was being overwritten by the 256 m derived range on the same
        # grid, in the same start_console_commands list. Measured 2026-09-09
        # in bench_run_target_mrqtruth.json's start_console_commands_readback:
        #     -grid=MainGrid       -range=1200000    (no-op, wrong grid name)
        #     -grid=MainPartition  -range=25600      (this one, and it won)
        # so the "truth" frames came out byte-comparable to player frames.
        if not a.truth:
            start_commands.append(
                "wp.Runtime.OverrideRuntimeLoadingRange -grid=%s -range=%d"
                % (str(derived["grid"]), int(derived["loading_range_cm"])))
        else:
            print("  --truth: NOT applying the derived %d cm range; the truth "
                  "range owns the grid for this run"
                  % int(derived["loading_range_cm"]))
        # Let the warm-up actually settle. The default cap is 4 concurrent
        # cell loads (WorldPartitionSubsystem.cpp:202-206), which leaves the
        # sparse low-priority tail still in flight at shot end -- measured as
        # 7 missing foliage actors, all in range, all non-empty.
        # `not a.truth` for the same last-writer-wins reason as the range
        # command above: the truth block already appended its own cells
        # value, and a divergent derived value landing after it would win
        # silently (Pass 3 2026-09-16; harmless today, both are 512).
        if not a.truth and derived.get("max_loading_streaming_cells"):
            start_commands.append(
                "wp.Runtime.MaxLoadingStreamingCells %d"
                % int(derived["max_loading_streaming_cells"]))

    # --echo-scalability: read the sg.* levels FROM INSIDE the render.
    #
    # Why an echo and not a read from outside: MRQ applies its scalability
    # and cvar overrides at pipeline setup and restores them at teardown,
    # so anything read from the editor before or after the render is the
    # SURROUNDING state, not the state the frames were rendered at. The
    # only channel that reports from inside is a console command MRQ
    # itself executes.
    #
    # Both hooks, deliberately. MoviePipelineConsoleVariableSetting.cpp:
    # StartConsoleCommands run at :271 -- inside ApplyCVarSettings(true),
    # AFTER that setting's own cvar writes at :253; EndConsoleCommands run
    # at :279 during teardown. Reading at both ends is what distinguishes
    # "GameOverride applied before the cvars and lost" from "applied after
    # and won", which is precisely the precedence question and cannot be
    # answered from one sample.
    if a.echo_scalability:
        _echo = ["Scalability", "sg.ShadowQuality", "sg.FoliageQuality",
                 "sg.ViewDistanceQuality", "sg.TextureQuality",
                 "sg.GlobalIlluminationQuality", "sg.EffectsQuality"]
        start_commands = list(start_commands) + _echo
        end_commands = list(end_commands) + _echo

    stations = [s for s in STATIONS if not a.stations or s in a.stations]
    stations += [s for s in EXTRA_STATIONS if a.stations and s in a.stations]
    if not stations:
        ap.error("--stations matched none of %s"
                 % (STATIONS + EXTRA_STATIONS))

    # The expected set, per station, BEFORE the render. This must come after
    # `stations` exists -- it was written above it first and died on an
    # UnboundLocalError, which is what the run at 17:07 was.
    if derived:
        # The expected-set radius is the range ACTUALLY APPLIED this run
        # (Pass 3 2026-09-16): on --truth the truth range owns the grid
        # (the derived range is deliberately not applied, see above), so
        # judging truth frames against the 512 m derived radius let cells
        # at 1-8 km be absent from a "fully resident" truth PASS.
        rng = int(truth["loading_range_cm"] if a.truth
                  else derived["loading_range_cm"])
        _deriv = _load_derivation(date)["derived_stations"]
        # THE THIRD PLACE --dolly-only has to reach. It gated the JOBS and the
        # completion check; this loop still queried all three stations, and a
        # transient remote failure on mid_slope -- a station this run does not
        # capture -- refused the whole run.
        #
        # The dolly stands at ONE place: its origin station. That is the only
        # residency expectation this run can be judged against, so it is the
        # only one queried.
        _resi_stations = ([(bm.get("dolly") or {}).get("from_station")]
                          if a.dolly_only else list(stations))
        _resi_stations = [s for s in _resi_stations if s]
        if not _resi_stations:
            # A filtered-empty list here would flow to _judged = [] and
            # a zero-comparison residency PASS — the same rule-13 hole
            # the judging fix closed, reachable through a CONFIG gap
            # (dolly.from_station missing) instead of a flag (auditor
            # FIX, Pass 3 2026-09-16). Zero stations to judge REFUSES.
            print("  REFUSE: no station to judge residency against "
                  "(--dolly-only with no dolly.from_station in "
                  "benchmark.json?). A zero-station residency judgement "
                  "would PASS on nothing.")
            return 6
        for st in _resi_stations:
            if st not in _deriv:
                print("  REFUSE: no derivation for station %s" % st)
                return 6
            loc = _deriv[st]["location_cm"]
            _c, got, _raw = run_payload(
                "bench_expected_set.py",
                {"__LOC_X__": "%.1f" % loc[0], "__LOC_Y__": "%.1f" % loc[1],
                 "__LOC_Z__": "%.1f" % loc[2], "__RADIUS_CM__": "%.1f" % rng},
                timeout=25.0)
            if not got or got.get("error"):
                print("  REFUSE: expected-set query failed for %s: %s"
                      % (st, (got or {}).get("error")))
                return 6
            derived_expected[st] = got
            print("    %-12s expected %d actors (%d in box, skipped %s)"
                  % (st, got["expected_count"], got["descs_in_box"],
                     got["skipped"]))
    jobs = []
    # --dolly-only exists to PROTECT EVIDENCE, not to save time. The station
    # jobs write to _verify/bench/<date>/<profile>/<station>.png, and today's
    # directory already holds the Phase C stills that the research send-back
    # cites. Re-rendering them for a dolly run would overwrite measured
    # artefacts with fresh ones nobody asked for.
    for st in ([] if a.dolly_only else stations):
        jobs.append({"name": "Bench_%s_%s" % (a.profile, st),
                     "sequence": "/Game/Bench/Bench_Still_" + st,
                     "output_dir": outroot.replace("\\", "/"),
                     "file_name_format": st})
    if a.dolly:
        jobs.append({"name": "Bench_%s_dolly" % a.profile,
                     "sequence": "/Game/Bench/" + a.dolly_seq,
                     "output_dir": os.path.join(outroot, "dolly").replace("\\", "/"),
                     "file_name_format": "frame_{frame_number}"})

    # --depth forces temporal_samples 1. FMoviePipelinePostProcessPass's own
    # doc says an additional PP material "will need bDisableMultisampleEffects
    # enabled for pixels to line up (ie: no DoF, MotionBlur, TAA)", so a depth
    # buffer cannot be aligned with a temporal x8 beauty frame. Averaging a
    # geometric quantity across jittered samples would be wrong anyway.
    if a.depth and temporal != 1:
        print("  --depth: temporal_samples %d -> 1 (depth cannot be "
              "multisampled and still line up with the beauty frame)"
              % temporal)
        temporal = 1

    # RENDER warm-up, R-METER retest 2026-09-12c. `warm_up_frames` above is
    # the ENGINE count; it ticks the game thread and renders nothing, so it
    # cannot advance anything held in the render thread's frame history.
    # The engine's own default leaves `render_warm_up_frames` FALSE, which
    # makes its count of 32 inert -- so every capture before this one ran
    # with ZERO rendered warm-up while its sidecar recorded "warm-up 300".
    # Declared here rather than defaulted in the payload: a value the
    # caller cannot see is a value nobody chose.
    # --game-override KEY=VALUE. Typed here rather than in the payload:
    # set_editor_property is type-strict, and "true" as a STRING against
    # a bool property raises inside the editor where the message is one
    # line in a JSON blob. Parsed and refused here, where the caller can
    # see it.
    _game_override = {}
    for _kv in a.game_override:
        if "=" not in _kv:
            print("REFUSE: --game-override needs KEY=VALUE, got %r" % _kv)
            return 2
        _k, _v = _kv.split("=", 1)
        _k, _v = _k.strip(), _v.strip()
        _lv = _v.lower()
        if _lv in ("true", "false"):
            _game_override[_k] = (_lv == "true")
        else:
            try:
                _game_override[_k] = int(_v)
            except ValueError:
                try:
                    _game_override[_k] = float(_v)
                except ValueError:
                    _game_override[_k] = _v

    cfg = {"map": bm["level"], "res": res, "temporal_samples": temporal,
           "spatial_samples": 1, "cvars": cvars, "jobs": jobs,
           "warm_up_frames": warm_up, "truth": truth,
           "render_warm_up_frames": bool(a.render_warm_up),
           "render_warm_up_count": int(a.render_warm_up_count),
           "extra_pp_passes": _pp_passes,
           "start_commands": start_commands, "end_commands": end_commands,
           "depth_material": (DEPTH_MATERIAL if a.depth else None),
           "linear": bool(a.linear),
           "exr_compression": a.exr_compression,
           "exr_multilayer": bool(a.exr_multilayer),
           "game_override": _game_override,
           "dump_only": bool(a.dump_config)}

    print("bench_capture — profile %s%s, %d job(s), %dx%d, temporal x%d"
          % (a.profile, " TRUTH" if a.truth else "", len(jobs),
             res[0], res[1], temporal))
    print("  out: %s" % outroot)
    print("  residency: expect %d landscape components, %d warm-up frames, "
          "probe %s" % (expect_components, warm_up,
                        "REQUIRED" if resi.get("require_probe") else "optional"))

    # ---- ONE TRUTH INSTRUMENT, NOT TWO -----------------------------------
    # RULED 2026-09-13. `--instrument truth` and `--truth` were two
    # different instruments wearing one word: the first is editor +
    # HighResShot with NO MoviePipeline and therefore NO GameOverride;
    # the second is an MRQ render that installs all 20 GameOverride
    # properties (LOD0 everywhere, HLOD off, streaming off, draw
    # distance x100). A frame from one is not comparable to a frame from
    # the other, and nothing in a sidecar said which you had.
    #
    # `--truth` survives because it is the one that installs the
    # override set. This branch refuses rather than being deleted, so an
    # old command line gets an explanation instead of a silently
    # different frame.
    if a.instrument == "truth":
        print("REFUSE: `--instrument truth` is retired (2026-09-13).")
        print("  It was the EDITOR + HighResShot path: no MoviePipeline, so")
        print("  no GameOverride -- none of LOD0 / HLOD-off / streaming-off /")
        print("  draw-distance x100 that `--truth` installs. Two instruments")
        print("  shared one word and their frames are not comparable.")
        print("  Use:  --truth   (MRQ, installs and reads back all 20)")
        print("  See research/audit/inputs/TRUTH_INSTRUMENT_REGISTER_2026-09-13.md")
        return 2


    editor_census = None
    if a.load_all_regions:
        print("  force-loading every World Partition region in the EDITOR "
              "(PIE duplicates the editor world) ...")
        # DISCOVERY WINDOW, NOT A DEADLINE -- 25, not 600. ue_exec.run passes
        # `timeout` to _select_verified_node ONLY; remote.run_command takes no
        # timeout, so payload EXECUTION is unbounded and a long force-load is
        # in no danger from a short window here. 600 bought nothing and was
        # spent in full on every run (measured 2026-09-09: 10 minutes of a
        # completely idle editor before the load even started).
        # ue_exec's own help says 12-25 is right, and it prints a warning --
        # but only on the CLI path, which a library caller never reaches.
        _c, loaded, _raw = run_payload("bench_load_regions.py", timeout=25.0)
        if not loaded or loaded.get("error"):
            print("REFUSE: the region load did not report success: %s"
                  % (loaded.get("error") if loaded else "no marker"))
            return 6
        editor_census = loaded.get("editor_census")
        print("    editor now holds %s proxies, %s/%s components, %s foliage "
              "instances" % (editor_census.get("proxies"),
                             editor_census.get("components"), expect_components,
                             editor_census.get("foliage_instances")))
        if int(editor_census.get("components", 0)) < expect_components:
            print("REFUSE: even after --load-all-regions the EDITOR holds only "
                  "%s of %s components. Nothing rendered from this world could "
                  "be a measurement."
                  % (editor_census.get("components"), expect_components))
            return 6

    log_mark = log_size()          # so the log parse sees only THIS render
    # Anchor for artefact freshness, taken BEFORE the render is triggered so
    # nothing this render writes can predate it. The 1 s slack absorbs
    # filesystem timestamp granularity, not a slow render.
    render_t0 = time.time() - 1.0
    code, started, raw = run_payload("bench_render.py",
                                     {"__CONFIG_JSON__": json.dumps(cfg)},
                                     timeout=25.0)
    if not started:
        print("COULD NOT LOOK: no marker from the render payload")
        print(raw[-1500:] if raw else "(no output)")
        return 1
    if started.get("error"):
        print("PAYLOAD ERROR: %s" % started["error"])
        print(started.get("trace", ""))
        return 1

    if cfg.get("dump_only"):
        # Nothing was rendered, so none of the artefact checks below apply.
        # Write the dump and stop -- and say plainly that no frame exists,
        # rather than returning 0 next to a "capture" that did not happen.
        dump = started.get("config_dump")
        if not dump:
            print("REFUSE: --dump-config produced no dump")
            return 4
        dp = os.path.join(REPO, "research", "audit", "inputs",
                          "mrq_config_dump.json")
        if not os.path.isdir(os.path.dirname(dp)):
            os.makedirs(os.path.dirname(dp))
        dump["_what"] = ("the bench MRQ config as the ENGINE holds it, "
                         "dumped from the same construction a render uses")
        dump["_profile"] = a.profile
        dump["_temporal_samples"] = temporal
        dump["_game_override_requested"] = _game_override
        dump["_jobs"] = [j for j in started.get("jobs", [])]
        dump["_git_sha"] = git_sha()
        # Keyed by profile and MERGED, so `--profile dev --dump-config`
        # followed by `--profile target --dump-config` leaves one file
        # holding both rather than the second silently replacing the
        # first with a file of the same name and half the content.
        key = "%s%s" % (a.profile, "+truth" if a.truth else "")
        # Closure A-5 (AUDIT V-6): the acceptance constructions are added
        # by flags, so the dump key must carry them or the --linear /
        # PPI0 / depth dumps silently overwrite the standard one and the
        # file claims one construction was all there ever was.
        if a.linear:
            key += "+linear"
        for _pp in _pp_passes:
            key += "+pp:%s" % _pp["name"]
        if a.depth:
            key += "+depth"
        if _game_override:
            key += "+" + ",".join("%s=%s" % kv
                                  for kv in sorted(_game_override.items()))
        doc = {}
        if os.path.isfile(dp):
            try:
                with open(dp, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except Exception:
                doc = {}
        doc[key] = dump
        with open(dp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        print("  profile key: %s  (file now holds: %s)"
              % (key, ", ".join(sorted(k for k in doc if not k.startswith("_")))))
        print("  DUMP ONLY — no render was started, no frame exists.")
        print("  %d setting classes" % len(dump.get("settings", [])))
        for s in dump.get("settings", []):
            print("    %-46s %d props" % (s["class"], len(s["properties"])))
        print("  wrote %s (%d bytes)" % (dp, os.path.getsize(dp)))
        return 0

    # ---- a truth capture RECORDS ALL 20 GameOverride PROPERTIES ----------
    # RULED 2026-09-13. Before now the sidecar carried four of them, which
    # is how use_lod_zero / disable_hlods / texture_streaming DISABLED went
    # unrecorded for the life of the instrument -- a truth frame was LOD0
    # everywhere with HLOD off and nothing said so. Twenty is the count in
    # MoviePipelineGameOverrideSetting.h:79-151, and the refusal names the
    # missing keys rather than reporting a bare number (rule 13: the
    # sample count travels with the verdict).
    if cfg.get("truth"):
        _GO_EXPECTED = 20
        for j in started["jobs"]:
            g = j.get("game_overrides_readback") or {}
            got = [k for k in g if not k.startswith("_")]
            if len(got) < _GO_EXPECTED:
                print("REFUSE: truth capture recorded %d of %d GameOverride "
                      "properties on job %s" % (len(got), _GO_EXPECTED,
                                                j.get("name")))
                print("  recorded: %s" % ", ".join(sorted(got)))
                print("  A truth frame is LOD0 everywhere, HLOD off, texture")
                print("  streaming off and draw distance x100. A sidecar that")
                print("  does not say so is not evidence about a truth frame.")
                return 4
        print("  truth: all %d GameOverride properties read back on every job"
              % _GO_EXPECTED)

    for j in started["jobs"]:
        if not j.get("cvars_match"):
            print("REFUSE: cvar config read-back does not match the request for "
                  "job %s" % j["name"])
            print("  requested: %s" % j["cvars_requested"])
            print("  read back: %s" % j["cvars_config_readback"])
            return 4
    print("  cvar config read-back matches request on every job")

    # PROGRESS IS WATCHED FROM OUTSIDE THE EDITOR, AND HERE IS WHY.
    # The first version polled MoviePipelineQueueSubsystem.is_rendering()
    # through remote exec. That CANNOT WORK: remote-exec Python runs on the
    # GAME THREAD, and while MRQ is rendering it owns the game thread, so the
    # polls never execute -- on 2026-09-05 not one LogPython line appeared in
    # the engine log for the entire render. A poll that cannot run is not a
    # poll; it is a timeout with extra steps.
    # Three out-of-process instruments, none of which need the game thread:
    #   1. the engine log's mtime and its MRQ lines
    #   2. the frames arriving on disk
    #   3. the editor's own window title, which MRQ updates with
    #      "[Job n/N Total] Current Job: P% Completed."
    # THE FRAMES MUST BE FROM *THIS* RENDER, NOT JUST PRESENT.
    # Measured 2026-09-09: a re-run into a directory that already held the
    # previous run's stills saw them on its FIRST poll, 15 s in, while MRQ was
    # still opening -- so the window title did not yet say "Movie Pipeline
    # Render" either. The loop broke, the script exited, and it then reported
    # the OLD PNGs' luma as this run's numbers, byte-identical to the run
    # before. MRQ was in fact still going and took 5:15 more.
    # `glob` answers "does a file exist", never "is it the one we just made".
    def fresh(paths):
        return [p for p in paths if os.path.getmtime(p) >= render_t0]

    # How many dolly frames this run must see before it is complete. Derived
    # from the SEQUENCE's own declaration (seconds x fps), not guessed: MRQ
    # renders playback [0, N), so N frames numbered 0..N-1.
    _dcfg = bm.get("dolly") or {}
    dolly_expected_frames = int(round(float(a.dolly_seconds or
                                            _dcfg.get("seconds", 0))
                                      * float(_dcfg.get("fps", 30)))) or 1

    def artefacts_present():
        # --dolly-only removes the station JOBS, so it must also remove them
        # from what completion WAITS FOR. Without this the run blocks until
        # its timeout on three PNGs that were never scheduled -- measured
        # 2026-09-09: 13 minutes of an idle editor and an empty log, which
        # reads exactly like a hung render.
        #
        # A flag that changes what is PRODUCED must change what is CHECKED.
        need = [] if a.dolly_only else list(stations)
        ok = all(fresh(glob.glob(os.path.join(outroot, s + "*.png")))
                 for s in need)
        if a.dolly:
            # `> 0` IS NOT COMPLETION. MRQ writes frames lazily and keeps
            # flushing after the window title clears, so this returned True on
            # the FIRST frame: the run printed "dolly 17 frames" and OK while
            # 73 more were still being written. Nothing errored. A check run
            # at that moment would have read frame_0016 as the LAST frame of
            # the walk and answered the shadow question against the wrong
            # image.
            #
            # The expected count is known -- the sequence declares it -- so
            # wait for it rather than for evidence that rendering began.
            got = len(fresh(glob.glob(
                os.path.join(outroot, "dolly", "*.png"))))
            return ok and got >= dolly_expected_frames
        return ok

    def window_title():
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue"
                 " | Select-Object -First 1).MainWindowTitle"],
                capture_output=True, timeout=30)
            return out.stdout.decode(errors="replace").strip()
        except Exception:
            return ""

    t0 = time.time()
    last_log_size = log_mark
    last_change = time.time()
    STALL_S = 600.0
    while time.time() - t0 < a.timeout_s:
        time.sleep(a.poll_s)
        title = window_title()
        sz = log_size()
        if sz != last_log_size:
            last_log_size, last_change = sz, time.time()
        if artefacts_present() and "Movie Pipeline Render" not in title:
            break
        idle = time.time() - last_change
        print("  ... %.0f s | %s | log idle %.0f s"
              % (time.time() - t0, title or "(no title)", idle))
        if idle > STALL_S:
            print()
            print("REFUSE: the engine log has not moved for %.0f s and the "
                  "render is not finished. This is a STALL, not slowness -- "
                  "reporting it rather than waiting out the timeout." % idle)
            print("  last window title: %s" % title)
            return 6
    else:
        print("TIMEOUT after %.0f s; the render may still be running" % a.timeout_s)
        return 5
    last = {"final_window_title": window_title()}
    elapsed = time.time() - t0
    print("  render finished in %.0f s (poll: %s)" % (elapsed, last))

    resi_lines = read_residency(resi_path)
    derived_rows = []
    if derived:
        # THE DERIVED GATE: nothing the ENGINE said is in range may be absent
        # from the world when the shot finished. Subset, not equality -- see
        # residency.derived._verdict in benchmark.json.
        # PAIR BY INDEX, not by a `job` field -- the probe records DO NOT HAVE
        # ONE. `judge_residency` above pairs `lines[i]` with `jobs[i]`, and it
        # is right: MRQ runs the shots in job order and the probe appends one
        # line per shot. Keying on ln.get("job") returned None for every line,
        # so every station came back NO VERDICT with resident=None while the
        # probe had in fact recorded 1502/321/309 resident actors. Measured
        # 2026-09-09.
        # THE FOURTH PLACE --dolly-only has to reach: the JUDGING. Gating the
        # jobs, the completion check and the residency pre-check still left
        # this loop iterating all three stations, and it died on
        # KeyError: 'mid_slope' -- AFTER a successful 107 s render, so the
        # frames existed and the run reported failure.
        #
        # One flag, four places, discovered one at a time. The lesson is not
        # "check four places"; it is that a run should derive WHAT IT JUDGES
        # from WHAT IT CAPTURED, rather than from a list written before either
        # was decided.
        # Judge WHAT WAS CAPTURED (Pass 3 2026-09-16): this was
        # `[] if a.dolly_only else list(stations)`, so a --dolly-only run
        # judged NOTHING and resi_verdict kept its "PASS" initialisation
        # — a zero-comparison PASS (rule 13's shape) on the gate that
        # exists to catch 2026-09-05-class voids. _resi_stations is
        # already "the stations this run captured" (the dolly's origin
        # for --dolly-only, all stations otherwise).
        _judged = list(_resi_stations)
        by_job = {st: (resi_lines[i] if i < len(resi_lines) else None)
                  for i, st in enumerate(_judged)}
        resi_verdict = "PASS"
        for st in _judged:
            # NAMED expected_set/resident_set, NOT exp/res. `res` is the
            # DECLARED RENDER RESOLUTION from line 635, and this loop used to
            # rebind it to a set of actor names -- after which the final gate
            #     bad = [s for s,v in stills.items() if v[...] != res]
            # compared every still's pixel size against a set of ~250 actor
            # labels, so it could never match. Measured 2026-09-09: two 4K
            # stills, the engine's own 'resolution lines [[3840, 2160]]' in
            # the same run, and "REFUSE: ['mid_slope','vista'] rendered at a
            # resolution other than {'Alpine8K_HLODLayer_...'}".
            #
            # It stayed hidden because a set in the sidecar killed the run at
            # json.dump a few lines earlier; fixing that exposed this. Two
            # bugs in one path, the first masking the second.
            expected_set = set(derived_expected[st]["expected_actors"])
            ln = by_job.get(st)
            if ln is None or ln.get("resident_actors") is None:
                row = {"station": st, "verdict": "NO VERDICT",
                       "why": "no resident_actors line for this shot -- "
                              "'I could not look' is not 'it was there'",
                       "expected": len(expected_set), "resident": None,
                       "missing": None}
                resi_verdict = "NO VERDICT"
            else:
                resident_set = set(ln["resident_actors"])
                miss = sorted(expected_set - resident_set)
                row = {"station": st,
                       "verdict": "PASS" if not miss else "FAIL",
                       "expected": len(expected_set),
                       "resident": len(resident_set),
                       "missing": len(miss), "missing_sample": miss[:12]}
                if miss and resi_verdict != "NO VERDICT":
                    resi_verdict = "FAIL"
            derived_rows.append(row)
        print("  DERIVED residency (%d probe line(s)):" % len(resi_lines))
        for r in derived_rows:
            print("    %-12s %-10s expected %s resident %s missing %s"
                  % (r["station"], r["verdict"], r["expected"],
                     r["resident"], r["missing"]))
        resi_rows = derived_rows
    else:
        resi_verdict, resi_rows = judge_residency(
            resi_lines, jobs, expect_components, bool(resi.get("require_probe")),
            expect_key)
    if not derived:
        print("  residency read-back (%d probe line(s)):" % len(resi_lines))
        for r in resi_rows:
            print("    %-24s %-10s %s"
                  % (r["job"], r["verdict"],
                     r.get("why", "%s/%s components, %s foliage instances"
                           % (r.get("components"), expect_components,
                              r.get("foliage_instances")))))

    applied_cvars, log_resolutions, _ = read_mrq_applied_cvars(log_mark)
    if isinstance(applied_cvars, dict) and "_error" not in applied_cvars:
        missing_cv = [k for k in cvars if k not in applied_cvars]
        mismatched = [k for k in cvars if k in applied_cvars
                      and abs(applied_cvars[k]["applied"] - float(cvars[k])) > 1e-6]
        print("  engine applied %d/%d cvars; resolution lines %s"
              % (len(applied_cvars), len(cvars), log_resolutions))
        if missing_cv:
            print("  WARNING: not seen in the engine log: %s" % missing_cv)
        if mismatched:
            print("  WARNING: engine applied a different value for: %s" % mismatched)

    # ---- verify the artefacts, and read resolution off the FILES ----------
    found = {}
    for st in ([] if a.dolly_only else stations):
        # AUDIT 2026-09-10 F2: a SceneDepth pass or a _diff frame must
        # never be promoted to beauty when the true beauty is missing.
        hits = sorted(p for p in glob.glob(os.path.join(outroot,
                                                        st + "*.png"))
                      if "SceneDepth" not in os.path.basename(p)
                      and not os.path.basename(p).endswith("_diff.png"))
        if len(hits) == 1 and os.path.basename(hits[0]) != st + ".png":
            os.replace(hits[0], os.path.join(outroot, st + ".png"))
            hits = [os.path.join(outroot, st + ".png")]
        found[st] = hits[0] if hits else None
    dolly_frames = sorted(glob.glob(os.path.join(outroot, "dolly", "*.png"))) \
        if a.dolly else []

    stills = {}
    for st, p in found.items():
        if not p or not os.path.isfile(p):
            stills[st] = {"exists": False}
            continue
        _dp = _station_depth(outroot, st)
        _gc = _greycard_rect(st)
        _fl = featureless_split(p, SKY_BAND, depth_path=_dp,
                                exclude_rect_px=_gc)
        stills[st] = {"exists": True,
                      "path": os.path.relpath(p, REPO).replace("\\", "/"),
                      "bytes": os.path.getsize(p),
                      "png_size_from_file": png_size(p),
                      "mean_luma": round(mean_luma(p), 6),
                      "featureless_fraction": round(_fl[0], 4),
                      "featureless_sky_fraction": round(_fl[1], 4),
                      "featureless_non_sky_fraction": round(_fl[2], 4),
                      "sky_mask": "depth" if _dp else "colour",
                      "greycard_excluded_rect_px": _gc}

    # ---- INSTRUMENT NAMING (closure A-5, AUDIT S-5) ----------------------
    # Every reading names its buffer from now on. The RGBA channels of a
    # --linear EXR are the tone-curve-DISABLED FinalImage -- post-grade, it
    # carries the WB stage -- so a card read there is finalimage_linear,
    # NEVER ppi0. The PPI0 tap is the SEPARATE channel group written by
    # --pp-pass (FinalImagePPI0), named per still below. --truth is its own
    # instrument. The 2026-09-14 WB solve was mislabelled "PPI0" exactly
    # because nothing in the sidecar said which buffer the read came from.
    _instrument = ("truth" if a.truth else
                   "finalimage_linear" if a.linear else
                   "finalimage_look")
    # LOADING instrument (closure D-1 item 1): orthogonal to the buffer.
    # player = derived OverrideRuntimeLoadingRange applied; player_streaming =
    # no override, grid keeps its recipe range so proxies render beyond it.
    _loading_instrument = a.instrument
    _ppi0_names = [p["name"] for p in _pp_passes
                   if str(p.get("name", "")).upper().startswith("PPI0")]
    for _row in stills.values():
        _row["instrument"] = _instrument
        if _ppi0_names:
            _row["ppi0_channel"] = "FinalImage%s" % _ppi0_names[0]
    sidecar = {
        "instrument": _instrument,
        "loading_instrument": _loading_instrument,
        "_what": ("Benchmark capture sidecar. Fields ending _readback were read "
                  "back from the engine or measured off the artefact; fields "
                  "ending _requested are what was asked for and are NOT "
                  "evidence."),
        "date": date,
        "profile": a.profile,
        "tag": a.tag,
        "git_sha": git_sha(),
        "recipe_sha256": sha256(os.path.join(REPO, "recipes", "alpine_8k.json")),
        "benchmark_json_sha256": sha256(BENCH),
        "level_requested": bm["level"],
        "resolution_requested": res,
        "temporal_samples_requested": temporal,
        "elapsed_s": round(elapsed, 1),
        "jobs": started["jobs"],
        # THE LINEAR READ-BACK MUST REACH THE SIDECAR. The payload
        # collected it and the sidecar dropped it on the first run, which
        # is rule 12's exact shape: a read-back that is taken and then
        # discarded answers "is this controlled?" with a false yes.
        "linear_readback": started.get("linear"),
        "depth_readback": started.get("depth"),
        "engine_cvars_before_render": started.get("engine_cvars_before_render"),
        "cvars_applied_readback": applied_cvars,
        "engine_resolution_readback": log_resolutions,
        "_cvar_provenance": (
            "cvars_applied_readback is the ENGINE'S OWN record of what it "
            "applied for this render, parsed from LogMovieRenderPipeline's "
            "'Applying CVar \"X\" PreviousValue: A NewValue: B' lines in "
            "Saved/Logs/LandscapeLab.log, read from a byte offset taken "
            "immediately before the render started so it cannot pick up an "
            "earlier run. This is the during-render value, which the Python "
            "API cannot give: the MRQ setting restores its variables when the "
            "shot ends, so anything read afterwards is the surrounding state. "
            "cvars_config_readback proves the setter took (and that "
            "UMoviePipelineConsoleVariableSetting::CVars being ScriptNoExport "
            "was avoided). engine_resolution_readback is the engine's own "
            "'Total resolution' line, a second independent witness to the "
            "PNG's IHDR."),
        "stills": stills,
        "dolly_frame_count": len(dolly_frames),
        "dolly_first_frame_size": png_size(dolly_frames[0]) if dolly_frames else None,
        "residency_declared": {"expect_landscape_components": expect_components,
                               "engine_warm_up_frames": warm_up,
                               # DECLARED beside the engine count so a reader
                               # can tell the two apart. They are not the
                               # same warm-up and only one of them renders.
                               "render_warm_up_frames": bool(a.render_warm_up),
                               "render_warm_up_count": int(
                                   a.render_warm_up_count),
                               "require_probe": bool(resi.get("require_probe")),
                               "truth": truth,
                               "derived": derived},
        # BOTH SETS, as ruled. The expected set is what the engine said was in
        # range; the resident set is what was actually there when the shot
        # ended. Full lists, not just counts -- a count cannot be re-checked
        # and the missing NAMES are what a diagnosis starts from.
        "residency_derived": ({
            "grid": str(derived["grid"]),
            "loading_range_cm": int(derived["loading_range_cm"]),
            # The range APPLIED, which on --truth is NOT the derived one
            # (the run prints that it does not apply it) — the sidecar
            # used to assert "APPLIED" unconditionally, rule 12's shape
            # in the evidence file (Pass 3 2026-09-16).
            "range_applied_cm": int(truth["loading_range_cm"] if a.truth
                                    else derived["loading_range_cm"]),
            "_range_provenance": (
                "--truth run: the TRUTH range %d cm owns the grid; the "
                "derived %d cm range was deliberately NOT applied. Applied "
                "via wp.Runtime.OverrideRuntimeLoadingRange in "
                "start_console_commands; not readable from the world "
                "(RuntimePartitions is private)"
                % (int(truth["loading_range_cm"]),
                   int(derived["loading_range_cm"]))
                if a.truth else
                "APPLIED via wp.Runtime.OverrideRuntimeLoadingRange in "
                "start_console_commands; not readable from the world "
                "(RuntimePartitions is private)"),
            "per_station": {
                st: {"expected_count": derived_expected[st]["expected_count"],
                     "descs_in_box": derived_expected[st]["descs_in_box"],
                     "skipped": derived_expected[st]["skipped"],
                     "expected_actors": derived_expected[st]["expected_actors"]}
                for st in derived_expected},
            "resident_counts": {
                (ln.get("job") or "?"): ln.get("resident_actor_count")
                for ln in resi_lines},
        } if derived else None),
        "editor_census_after_load_all_regions": editor_census,
        "residency_readback": resi_rows,
        "residency_verdict": resi_verdict,
        "_residency_provenance": (
            "residency_readback comes from scripts/payloads/bench_residency_probe.py "
            "run INSIDE PIE by MRQ's end_console_commands, not from remote exec "
            "(which cannot reach the game thread while MRQ owns it). The census "
            "is measure_frame_cost's: LandscapeStreamingProxy/Landscape actors, "
            "components via get_components_by_class -- never the "
            "landscape_components UPROPERTY, which reads 0 on a loaded world "
            "(R-FRAMECOST REJECTED)."),
    }
    sp = os.path.join(REPO, "_verify", "bench", date, "bench_run_%s.json" % prof_dir)
    # A set anywhere in here used to kill the run AFTER a completed render:
    # 2026-09-09, both stations on disk at 4K and no sidecar, because
    # json.dump raised "Object of type set is not JSON serializable" at the
    # very last step. The frames survive that, but the EVIDENCE does not --
    # cvar read-backs, residency and provenance all live in the sidecar, and
    # a 20-minute render then has to be repeated to get them.
    #
    # So coerce rather than raise, and SAY which keys needed it: a silent
    # coercion would hide a field that is the wrong type at its source.
    _coerced = []

    def _jsonable(o, _seen=_coerced):
        if isinstance(o, (set, frozenset)):
            _seen.append(sorted(str(x) for x in o))
            return sorted(o)
        raise TypeError("sidecar holds a %s, which is not JSON"
                        % type(o).__name__)

    with open(sp, "w", encoding="utf-8") as _fh:
        json.dump(sidecar, _fh, indent=1, default=_jsonable)
    if _coerced:
        print("  note: coerced %d set(s) to sorted lists in the sidecar"
              % len(_coerced))

    missing = [s for s, v in stills.items() if not v.get("exists")]
    print()
    for st, v in stills.items():
        print("  %-12s %s" % (st, "MISSING" if not v.get("exists")
                              else "%s  %s  luma %.4f"
                              % (v["png_size_from_file"], v["path"], v["mean_luma"])))
    if a.dolly:
        print("  dolly        %d frames, first %s"
              % (len(dolly_frames), sidecar["dolly_first_frame_size"]))
    print("  sidecar: %s" % os.path.relpath(sp, REPO))
    if missing:
        print("INCOMPLETE: %s did not land on disk" % ", ".join(missing))
        return 3
    bad = [s for s, v in stills.items() if v["png_size_from_file"] != res]
    if bad:
        print("REFUSE: %s rendered at a resolution other than %s" % (bad, res))
        return 4

    # THE CONTENT GATE. Resolution, cvars, file size and mean luma are all
    # satisfied by a frame with no world in it -- proven on 2026-09-05, when
    # this tool printed OK over a mid_slope still that was 93.8% blank because
    # the World Partition cells around a station 2 km from the town never
    # streamed in. Compare what the frame actually contains against what the
    # station was DERIVED to frame.
    voids = []
    try:
        # The derivation is not produced per run, so look in this run's dated
        # folder first and fall back to the most recent one. The first version
        # only looked in the dated folder and silently skipped the content gate
        # on the first capture of a new day -- a gate that quietly does not run
        # is worse than no gate, because the OK line still prints.
        dpath = os.path.join(REPO, "_verify", "bench", date,
                             "bench_stations_derived.json")
        if not os.path.isfile(dpath):
            cands = sorted(glob.glob(os.path.join(
                REPO, "_verify", "bench", "*", "bench_stations_derived.json")))
            if not cands:
                raise IOError("no bench_stations_derived.json anywhere under "
                              "_verify/bench/ -- the content gate has nothing "
                              "to compare against")
            dpath = cands[-1]
            print("  content gate: using derivation from %s"
                  % os.path.relpath(dpath, REPO))
        pred = json.load(open(dpath, encoding="utf-8"))["derived_stations"]
        for st, v in stills.items():
            occ = pred[st]["traced_occlusion"]
            pct_sky = occ["pct_sky"]
            pct_canopy = occ.get("pct_canopy")
            # R-GATE / AUDIT S-11 (closure A-8): the occlusion trace counts
            # a canopy hit as OPAQUE, but foliage is alpha-tested -- leaves
            # have gaps and sky renders through. So the raw pct_sky
            # under-predicts sky exactly in proportion to canopy fraction
            # (measured 17.8x-25.4x low at near_ground, 81% canopy; accurate
            # where canopy is small). The porosity term corrects it. Threshold
            # UNCHANGED -- the comparand was wrong, not the bound.
            if pct_canopy is None:
                # NN6 degrade: no canopy datum (e.g. the ground station).
                # Fall back to the raw sky prediction and NAME the gap
                # rather than inventing a canopy term.
                sky = pct_sky / 100.0
                v["content_gate_canopy_model"] = "absent (pct_canopy None)"
            else:
                sky = (pct_sky + CANOPY_POROSITY * pct_canopy) / 100.0
                v["content_gate_canopy_model"] = (
                    "porosity %.2f x pct_canopy %.2f" % (CANOPY_POROSITY,
                                                         pct_canopy))
            slack = v["featureless_fraction"] - sky
            v["predicted_sky_fraction_raw"] = round(pct_sky / 100.0, 4)
            v["predicted_sky_fraction"] = round(sky, 4)
            v["featureless_over_prediction"] = round(slack, 4)
            if slack > 0.20:
                voids.append((st, v["featureless_fraction"], sky))
        sidecar["stills"] = stills
        # SERIALISE FIRST, TRUNCATE ONLY ON SUCCESS (Pass 3 2026-09-16):
        # this rewrite used open(sp,"w") + json.dump WITHOUT the
        # default=_jsonable the first write carries — a non-JSON value
        # would truncate the guarded sidecar mid-write and the except
        # below would print "content gate skipped" over half a file.
        _txt = json.dumps(sidecar, indent=1, default=_jsonable)
        with open(sp, "w", encoding="utf-8") as _fh:
            _fh.write(_txt)
    except Exception as e:
        print("  (content gate skipped: %s)" % e)

    # RESIDENCY IS A PRECONDITION, so it is judged BEFORE the content gate.
    # A void frame on a non-resident world has a known cause and should say so,
    # rather than being reported as a mysterious blank.
    if resi_verdict != "PASS":
        print()
        print("REFUSE (%s): residency. The frames exist and may even look "
              "plausible, but the world was not established to be there when "
              "they were taken, so they are not measurements." % resi_verdict)
        for r in resi_rows:
            if r["verdict"] != "PASS":
                # DERIVED rows key by "station", judge_residency rows by
                # "job" (fixed 2026-09-10: the derived path crashed HERE
                # with KeyError on every refused run, truncating exactly
                # the detail a refusal exists to print -- the task5 log
                # ends at this line).
                print("  %-24s %s — %s"
                      % (r.get("job") or r.get("station") or "<unnamed>",
                         r["verdict"],
                         r.get("why",
                               "expected %s resident %s missing %s"
                               % (r.get("expected"), r.get("resident"),
                                  r.get("missing")))))
        print("  Sidecar written anyway: %s" % os.path.relpath(sp, REPO))
        return 6

    if voids:
        print()
        for st, f, sky in voids:
            print("REFUSE: %s is %.1f%% featureless against %.1f%% predicted sky. "
                  "Residency PASSED, so this is not a streaming failure — look "
                  "at the station before the pipeline." % (st, f * 100, sky * 100))
        return 7

    print("OK — every still exists, measures %dx%d off the file, and carries "
          "content consistent with its derivation." % (res[0], res[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
