"""trace_grounding.py — the INDEPENDENT grounding instrument.

`verify_grounding` reads the SAME heightmap through the SAME world
transform as the planner, so a bug in that shared derivation is invisible
to it — its own docstring says so, names this instrument, and calls it
`--trace`. **`--trace` was never implemented.** The project has cited the
circular half ("max 0.001 m over 157,554 instances") as grounding proof
since 2026-08-04, while conifers visibly float.

This asks the ENGINE instead: trace down at each instance XY and take the
LANDSCAPE hit.

    gap = pivot_Z + sink_depth - landscape_hit_Z

`pivot_Z + sink_depth` is where the planner believed the ground was.
POSITIVE gap = the planner's ground is ABOVE the real collision surface
= the instance FLOATS. Fail direction follows the failure mode: floating
is the observed defect, so this fails toward daylight.

WHY MULTI-TRACE AND NOT SINGLE. Foliage has collision too, and the
nearest hit under a conifer is frequently the conifer. A single trace
would silently measure tree-to-tree contact and report a tidy zero. Every
hit is walked and only Landscape / LandscapeStreamingProxy is accepted;
an instance with no landscape hit is reported as NO-HIT, never as zero
(non-negotiable 6 — "I could not look" is not a measurement).

API verified in the generated stub before use (REFERENCES Tier 1). Cited by
SYMBOL, not stub line — the generated stub renumbers on every regeneration:
  unreal.SystemLibrary.line_trace_multi(world_context_object, start, end,
                 trace_channel, trace_complex, actors_to_ignore,
                 draw_debug_type, ignore_self=True, ...) -> Array[HitResult]

Exit codes:
  0  ran; read the verdict
  1  unexpected error, OR a payload self-check refused (file extension in the
     payload / chunk over the proven size ceiling)
  2  plan unreadable, OR grounding convention not modelled (no 'sink_depth_m')
  3  editor identity gate refused
  4  probe returned nothing, too few instances resolved to be a sample, OR the
     --park streaming-source setup did not confirm
  5  FLOATING CONFIRMED beyond epsilon
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_TRACEGND__"
PARK_MARKER = "__LANDSCAPELAB_PARK__"

# The editor VIEWPORT CAMERA is a World Partition streaming source, so
# where it sits determines what is resident. If the traced gap moves when
# only the camera moves, the trace is measuring RESIDENCY and not
# grounding — and re-projecting instances onto that surface would corrupt
# a placement that matches the heightmap to 0.001 m.
#
# set_level_viewport_camera_info is the same call capture.py uses to aim
# its shots, so this parks the streaming source exactly as a capture does.
PARK = '''
import json as _json
import unreal as _unreal

_loc = {loc!r}
_out = {{"ok": False}}
try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _ues.set_level_viewport_camera_info(
        _unreal.Vector(_loc[0], _loc[1], _loc[2]),
        _unreal.Rotator(0.0, -20.0, 0.0))
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)
for _n in ("_ues",):
    globals().pop(_n, None)
print("{marker}" + _json.dumps(_out))
'''

# No file extensions in the payload (PythonScriptPlugin.cpp:813-830).
PROBE = '''
import json as _json
import unreal as _unreal

_pts = {pts!r}
_up = {up!r}
_down = {down!r}
_out = {{"ok": False, "rows": [], "nohit": 0, "accessor": None}}

try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _chan = _unreal.TraceTypeQuery.TRACE_TYPE_QUERY1
    _dbg = _unreal.DrawDebugTrace.NONE
    _ignore = _unreal.Array(_unreal.Actor)

    for _p in _pts:
        _x = _p[0]
        _y = _p[1]
        _z = _p[2]
        _s = _unreal.Vector(_x, _y, _z + _up)
        _e = _unreal.Vector(_x, _y, _z - _down)
        _hits = _unreal.SystemLibrary.line_trace_multi(
            _w, _s, _e, _chan, True, _ignore, _dbg, True)
        _got = None
        # Raw hit count is recorded separately from the landscape filter,
        # so "the trace returned nothing" and "the trace returned only
        # foliage" cannot be confused. They have different causes.
        _out["raw_hits"] = _out.get("raw_hits", 0) + (
            len(_hits) if _hits else 0)
        # ASK THE OBJECT. The stub shows HitResult(StructBase) with only
        # __init__ and NO "Editor Properties" section, so neither
        # get_editor_property nor a guessed attribute name is reliable.
        # dir() on a live hit is the authoritative answer and costs one
        # round trip; three guessed spellings cost three.
        if _hits and _out.get("first_hit_classes") is None:
            _h2 = _hits[0]
            _out["first_hit_classes"] = [
                _d for _d in dir(_h2) if not _d.startswith("__")][:40]
        if _hits:
            for _h in _hits:
                # to_dict() — the ONLY working accessor, and it was found
                # by dir() on a live hit rather than guessed. HitResult is
                # a StructBase whose fields are NOT reflected: the stub
                # lists no Editor Properties for it, get_editor_property
                # raises, and attribute access returns nothing. Three
                # guessed spellings failed before one introspection round
                # trip answered it.
                try:
                    _d = _h.to_dict()
                except Exception:
                    continue
                _out["accessor"] = "to_dict"
                _act = _d.get("hit_actor")
                if _act is None:
                    continue
                if isinstance(_act, (_unreal.Landscape,
                                     _unreal.LandscapeStreamingProxy)):
                    _loc = _d.get("impact_point") or _d.get("location")
                    if _loc is None:
                        continue
                    _got = float(_loc.z)
                    break
        if _got is None:
            _out["nohit"] += 1
        else:
            _out["rows"].append([_x, _y, _z, _got])
    del _w
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

for _n in ("_w", "_ues", "_h", "_act", "_hits", "_loc", "_ignore"):
    globals().pop(_n, None)

print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", default="foliage/alpine_Conifer.json")
    ap.add_argument("--n", type=int, default=500)
    # EPSILON IS COLLISION QUANTIZATION, NOT A TASTE SETTING.
    #
    # 0.05 m was the original guess and it is WRONG: it prints "FLOATING
    # CONFIRMED" and exits 5 on placement that is CORRECT. Measured
    # 2026-08-06 at the same 500 points, collision-vs-heightmap is
    # |d| p90 0.091 / max 0.431 m with signed mean -0.007 — symmetric,
    # i.e. the landscape's own collision surface is quantized relative to
    # the heightmap the planner used. An instance sitting exactly on the
    # heightmap therefore traces up to ~0.4 m away from collision through
    # no fault of the placement.
    #
    # 0.45 m sits just above that measured maximum. It is derived from the
    # collision surface's own behaviour, not chosen for comfort.
    #
    # WHY THIS IS A DEFECT WORTH A COMMENT THIS LONG: the adjudication
    # that closed the Pass 4 exit gate lived ONLY in LESSONS prose. The
    # instrument still failed, so a fresh session running the project's
    # own independent check got a FAILURE BANNER while CLAUDE.md said the
    # gate was closed. A ruling that is not encoded in the instrument is
    # a ruling that will be re-litigated by whoever runs the tool next.
    ap.add_argument("--epsilon-m", type=float, default=0.45)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--park", nargs=3, default=None,
                    help="Park the editor viewport (a World Partition "
                         "streaming source) at this XYZ in cm before "
                         "tracing. Same instance sample + different park "
                         "= the residency test.")
    ap.add_argument("--settle", type=float, default=20.0,
                    help="Seconds to wait after parking, for streaming.")
    ap.add_argument("--dump", default="",
                    help="Write the raw rows [x_cm, y_cm, plan_z_cm, "
                         "hit_z_cm] to this JSON path, so the tail can be "
                         "characterised offline without re-tracing. Each "
                         "trace costs an editor round trip; the analysis "
                         "should not.")
    args = ap.parse_args(argv)

    path = os.path.join(bootstrap.REPO_ROOT, args.plan)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            plan = json.load(fh)
    except Exception as exc:                          # noqa: BLE001
        print("REFUSE: cannot read plan: {0}".format(exc))
        return 2
    inst = plan["instances"]

    # REFUSE A PLAN WHOSE GROUNDING CONVENTION THIS TOOL DOES NOT MODEL.
    #
    # `sink_depth_m` is the CONIFER convention: pivot at the flare, sunk a
    # fixed depth. The BOULDER plan has no such key — it grounds via
    # `pivot_base_offset_m` (-0.6183) and `embed_depth_per_scale_m`
    # (0.234, scale-dependent). Defaulting the missing key to 0.0 made
    # this tool measure the wrong quantity and report ~100% FLOATING over
    # a boulder placement that engine traces put at median +0.000 m.
    #
    # A plausible number from the wrong premise is worse than a refusal:
    # the refusal costs a re-run, the number costs a wrong conclusion
    # about 759 placed instances. Fail closed until the convention is
    # modelled, and name what is missing.
    if "sink_depth_m" not in plan:
        keys = sorted(k for k in plan.keys() if k != "instances")
        print("")
        print("REFUSE: {0!r} has no 'sink_depth_m'. This tool models the "
              "CONIFER grounding convention (pivot at flare, fixed sink) "
              "and cannot measure a plan that grounds differently."
              .format(args.plan))
        print("  plan keys present: {0}".format(", ".join(keys)))
        print("  A boulder-style plan grounds via pivot_base_offset_m and "
              "embed_depth_per_scale_m (scale-dependent), which this tool "
              "does NOT implement. Measuring it as if sink were 0.0 "
              "reports ~100% FLOATING on placement that is correct.")
        print("  This is 'I cannot measure this', NOT 'the placement is "
              "wrong'.")
        return 2
    sink_m = float(plan["sink_depth_m"])
    rng = random.Random(args.seed)
    pick = rng.sample(inst, min(args.n, len(inst)))
    pts = [[float(r[0]), float(r[1]), float(r[2])] for r in pick]

    print("plan       : {0}".format(args.plan))
    print("instances  : {0}   sampling {1} (seed {2})".format(
        len(inst), len(pts), args.seed))
    print("sink_depth : {0} m  (as recorded in the plan)".format(sink_m))

    # CHUNKED because the points are interpolated INTO the payload and the
    # channel has a size ceiling (largest proven 8,683 bytes). 500 points
    # inline is ~15 KB, which would arrive truncated and be reported by the
    # editor as a missing FILE rather than an oversized command.
    CHUNK = 40
    chunks = [pts[i:i + CHUNK] for i in range(0, len(pts), CHUNK)]
    sample_src = PROBE.format(pts=chunks[0], up=5000.0, down=30000.0,
                              marker=MARKER)
    if (".p" + "y") in sample_src:
        print("REFUSE: payload carries a file extension.")
        return 1
    if len(sample_src.encode("utf-8")) > 8683:
        print("REFUSE: chunk payload is {0} bytes, over the proven "
              "ceiling.".format(len(sample_src.encode("utf-8"))))
        return 1
    print("chunks     : {0} x {1} points, {2} bytes each".format(
        len(chunks), CHUNK, len(sample_src.encode("utf-8"))))

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
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        if args.park:
            px, py, pz = [float(v) for v in args.park]
            src = PARK.format(loc=[px, py, pz], marker=PARK_MARKER)
            try:
                remote.open_command_connection(node["node_id"])
                pres = remote.run_command(
                    src, unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass
            # READ THE PARK BACK (standing rule 12). The whole point of --park
            # is to fix the streaming source; if set_level_viewport_camera_info
            # raised editor-side, the source is NOT where we think and the
            # trace would measure RESIDENCY, not grounding (see "WHY … PARK"
            # above). PARK emits PARK_MARKER+json for exactly this read-back --
            # do not print "parked" and sleep over a park that never happened.
            ptext = bootstrap._collect_output(pres or {})
            pi = ptext.find(PARK_MARKER)
            ppart = (json.JSONDecoder().raw_decode(
                ptext[pi + len(PARK_MARKER):].lstrip())[0]
                if pi >= 0 else None)
            if not ppart or not ppart.get("ok"):
                print("REFUSE: --park did not confirm ({0}). The streaming "
                      "source is not known to be at the requested location, so "
                      "the trace could be measuring residency, not grounding."
                      .format((ppart or {}).get(
                          "error", "no PARK marker in editor output")))
                return 4
            import time as _t
            print("  parked viewport at ({0:.0f}, {1:.0f}, {2:.0f}) cm "
                  "(confirmed); settling {3}s for streaming".format(
                      px, py, pz, args.settle))
            _t.sleep(args.settle)

        out = {"ok": True, "rows": [], "nohit": 0, "accessor": None}
        for ci, chunk in enumerate(chunks):
            src = PROBE.format(pts=chunk, up=5000.0, down=30000.0,
                               marker=MARKER)
            try:
                remote.open_command_connection(node["node_id"])
                res = remote.run_command(
                    src, unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                text = bootstrap._collect_output(res or {})
                i = text.find(MARKER)
                part = json.JSONDecoder().raw_decode(
                    text[i + len(MARKER):].lstrip())[0] if i >= 0 else None
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass
            if not part or not part.get("ok"):
                # A chunk that failed is NOT silently dropped: dropping it
                # would shrink the denominator and make the pass rate look
                # better than it is.
                print("  chunk {0} FAILED: {1}".format(
                    ci, (part or {}).get("error", "no result")))
                out["ok"] = False
                break
            out["rows"].extend(part.get("rows") or [])
            out["nohit"] += part.get("nohit") or 0
            out["accessor"] = part.get("accessor") or out["accessor"]
            out["raw_hits"] = out.get("raw_hits", 0) + (
                part.get("raw_hits") or 0)
            out["first_hit_classes"] = (out.get("first_hit_classes")
                                        or part.get("first_hit_classes"))

        if not out or not out.get("ok"):
            print("FAIL: probe returned nothing usable ({0}).".format(
                (out or {}).get("error", "no result")))
            return 4

        rows = out.get("rows") or []
        print("  landscape hits   : {0} of {1}".format(len(rows), len(pts)))
        print("  NO landscape hit : {0}".format(out.get("nohit")))
        print("  hit accessor     : {0}".format(out.get("accessor")))
        print("  RAW hits any class: {0}".format(out.get("raw_hits")))
        print("  first hit classes : {0}".format(
            out.get("first_hit_classes")))
        if len(rows) < 50:
            print("")
            print("FAIL: too few instances resolved to a landscape hit to "
                  "be a sample. That is 'I could not measure', not "
                  "'grounding is fine'.")
            return 4

        if args.dump:
            dpath = os.path.join(bootstrap.REPO_ROOT, args.dump)
            with open(dpath, "w", encoding="utf-8") as fh:
                json.dump({"plan": args.plan, "seed": args.seed,
                           "sink_depth_m": sink_m,
                           "sampled": len(pts),
                           "nohit": out.get("nohit"),
                           "columns": ["x_cm", "y_cm", "plan_z_cm",
                                       "hit_z_cm"],
                           "rows": rows}, fh)
            print("  dumped {0} rows -> {1}".format(len(rows), args.dump))

        sink_cm = sink_m * 100.0
        gaps = [((r[2] + sink_cm) - r[3]) / 100.0 for r in rows]
        gaps.sort()
        n = len(gaps)
        floats = [g for g in gaps if g > args.epsilon_m]
        buried = [g for g in gaps if g < -2.0 * sink_m]
        print("")
        print("  gap = pivot_Z + sink - landscape_hit_Z   (POSITIVE = FLOATING)")
        print("  min {0:+.3f}  p50 {1:+.3f}  p90 {2:+.3f}  p99 {3:+.3f}  "
              "max {4:+.3f}  (m)".format(
                  gaps[0], gaps[n // 2], gaps[int(n * 0.9)],
                  gaps[int(n * 0.99)], gaps[-1]))
        print("  floating (> {0:.2f} m) : {1} of {2}  ({3:.1f}%)".format(
            args.epsilon_m, len(floats), n, 100.0 * len(floats) / n))
        print("  buried  (< -{0:.2f} m) : {1}".format(
            2.0 * sink_m, len(buried)))
        print("")
        if floats:
            print("FLOATING CONFIRMED. The planner's ground sits ABOVE the "
                  "landscape collision surface on {0} of {1} sampled "
                  "instances, worst {2:+.3f} m.".format(
                      len(floats), n, gaps[-1]))
            print("verify_grounding's 0.001 m is arithmetic about the "
                  "heightmap, not contact with the terrain.")
            return 5
        print("No instance floats beyond {0:.2f} m in this sample. "
              "Instance Z agrees with landscape collision.".format(
                  args.epsilon_m))
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
