"""landscape_lod_probe.py — test whether landscape LOD strands foliage.

THE QUESTION
Conifers render floating in open sky with their trunk bases exposed
(_verify/20260806_resite_sweep_0060.png). `verify_grounding` proves
PLACEMENT to max 0.001 m over all 157,554 instances, so the disagreement
is render-side. The leading candidate is landscape section LOD: distant
terrain is drawn from decimated vertices, below the true surface the
instances were placed on.

Decimating this heightmap by hand gives the right ORDER of magnitude —
at 64 m vertex spacing the true surface sits 67 m above the decimated one
at p99, 258 m at worst — but that is a MODEL of decimation, not the
engine, and a plausible magnitude is not a cause. Today already produced
one confident wrong diagnosis; this exists so the next one is settled by
experiment.

THE EXPERIMENT, AND WHY IT PUSHES THE CHEAP WAY
`r.LandscapeLODBias` is raised, making the landscape COARSER, and the
same cameras are re-captured. If LOD is the mechanism the floating gets
WORSE and by more than noise; if it is unchanged, LOD is not the cause
and streaming/HLOD or a cull mismatch is.

Pushing toward COARSER is deliberate. Forcing full detail would be the
other half of the experiment and it costs GPU: this host has already lost
its GPU to a driver timeout once, and frame cost is a correctness concern
here, not a polish concern. A coarser landscape is strictly cheaper to
draw, so the falsification runs in the safe direction.

RENDER STATE, NOT SCENE STATE. A console variable is not saved, touches
no actor or asset, and `--restore` puts it back. Nothing here needs a
level save, and this is not a scene change under pipeline rule 4.

Exit codes:
  0  read/applied
  1  unexpected error
  2  bad arguments
  3  editor identity gate refused (conduct rule 7)
  4  the probe returned nothing — could not look
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_LODPROBE__"

# Read alongside the bias so a surprising result can be attributed. All
# of these move landscape or foliage draw distance.
WATCH = (
    "r.LandscapeLODBias",
    "r.LandscapeLOD0DistributionScale",
    "r.LandscapeLODDistributionScale",
    "r.ViewDistanceScale",
    "foliage.LODDistanceScale",
    "foliage.DensityScale",
    "sg.ViewDistanceQuality",
    "sg.FoliageQuality",
)

# NOTE: no file extensions in the payload — a '.p'+'y' substring makes UE
# treat the whole script as a filename (PythonScriptPlugin.cpp:813-830).
# Per-component LOD. VERIFIED IN ENGINE SOURCE before being called
# (UE 5.8 resolution protocol - an accessor remembered is an accessor
# guessed):
#   LandscapeComponent.h:643  int32 ForcedLOD   UPROPERTY(EditAnywhere,
#                                                BlueprintReadOnly)
#   LandscapeComponent.h:647  int32 LODBias     same flags
#   LandscapeComponent.h:1300 SetForcedLOD(int32)  UFUNCTION(BlueprintCallable)
#   LandscapeComponent.h:1303 SetLODBias(int32)    UFUNCTION(BlueprintCallable)
# The SETTERS are used rather than set_editor_property: they are the
# reflected surface, and a bare property write is not guaranteed to
# re-register the component's render state.
#
# ForcedLOD is the STRONGER test. r.LandscapeLODBias only shifts where
# distance-based transitions happen; ForcedLOD decimates at EVERY
# distance, so if this mechanism is what strands foliage the effect
# appears near the camera too — far above the measured 26% noise floor.
# -1 is "automatic" and is the restore value.
#
# THIS MUTATES ACTOR PROPERTIES, not just render state. It dirties the
# landscape proxy packages. NOTHING HERE SAVES, and --restore-lod puts
# every component back to -1 / 0.
COMPONENT_PROBE = '''
import json as _json
import unreal as _unreal

_forced = {forced!r}
_bias = {bias!r}
_out = {{"ok": False, "components": 0, "set_ok": 0, "verified": 0,
        "before": {{}}, "after": {{}}, "errors": []}}

try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    _comps = []
    for _cls in (_unreal.Landscape, _unreal.LandscapeStreamingProxy):
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(_w, _cls):
            try:
                for _c in _a.get_components_by_class(
                        _unreal.LandscapeComponent):
                    _comps.append(_c)
            except Exception as _e:
                _out["errors"].append(type(_e).__name__)
    _out["components"] = len(_comps)

    # WHY NANITE IS READ HERE. ForcedLOD verified as set on all 1024
    # components and the render did not change by more than the noise
    # between two identical captures. A Nanite landscape bypasses the
    # classic LOD path entirely, which would make BOTH r.LandscapeLODBias
    # and ForcedLOD inert - one explanation for two silent no-ops.
    # LandscapeProxy.h:491 bEnableNanite -> reflected as enable_nanite.
    _nan = {{}}
    for _cls in (_unreal.Landscape, _unreal.LandscapeStreamingProxy):
        for _a in _unreal.GameplayStatics.get_all_actors_of_class(_w, _cls):
            # collision_mip_level is read alongside because a DECIMATED
            # collision heightfield is the leading explanation for a line
            # trace disagreeing with the render surface by 25 m at p90
            # and 273 m at worst, while the placement plan matches the
            # heightmap to 0.001 m.
            _bits = []
            for _pn in ("enable_nanite", "collision_mip_level",
                        "simple_collision_mip_level"):
                try:
                    _bits.append(_pn + "=" + str(
                        _a.get_editor_property(_pn)))
                except Exception as _e:
                    _bits.append(_pn + "=UNREADABLE:" + type(_e).__name__)
            _v = " ".join(_bits)
            _nan[_v] = _nan.get(_v, 0) + 1
    _out["nanite"] = _nan

    for _c in _comps[:1]:
        for _p in ("forced_lod", "lod_bias"):
            try:
                _out["before"][_p] = _c.get_editor_property(_p)
            except Exception as _e:
                _out["before"][_p] = "UNREADABLE: " + type(_e).__name__

    for _c in _comps:
        try:
            if _forced is not None:
                _c.set_forced_lod(int(_forced))
            if _bias is not None:
                _c.set_lod_bias(int(_bias))
            _out["set_ok"] += 1
        except Exception as _e:
            if len(_out["errors"]) < 4:
                _out["errors"].append("%s: %s" % (type(_e).__name__, _e))

    _want = _forced if _forced is not None else None
    for _c in _comps:
        try:
            if _want is not None and int(
                    _c.get_editor_property("forced_lod")) == int(_want):
                _out["verified"] += 1
        except Exception:
            pass
    for _c in _comps[:1]:
        for _p in ("forced_lod", "lod_bias"):
            try:
                _out["after"][_p] = _c.get_editor_property(_p)
            except Exception as _e:
                _out["after"][_p] = "UNREADABLE: " + type(_e).__name__

    del _w
    del _ues
    del _comps
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

for _n in ("_c", "_a", "_w", "_ues", "_comps"):
    globals().pop(_n, None)

print("{marker}" + _json.dumps(_out))
'''


PROBE = '''
import json as _json
import unreal as _unreal

_watch = {watch!r}
_set_to = {set_to!r}
_out = {{"ok": False, "before": {{}}, "after": {{}}, "applied": None}}

try:
    _sl = _unreal.SystemLibrary
    for _n in _watch:
        try:
            _out["before"][_n] = _sl.get_console_variable_float_value(_n)
        except Exception as _e:
            _out["before"][_n] = "UNREADABLE: " + type(_e).__name__
    if _set_to is not None:
        _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
        _w = _ues.get_editor_world()
        _sl.execute_console_command(
            _w, "r.LandscapeLODBias " + str(_set_to))
        _out["applied"] = _set_to
        del _w
        del _ues
        for _n in _watch:
            try:
                _out["after"][_n] = _sl.get_console_variable_float_value(_n)
            except Exception as _e:
                _out["after"][_n] = "UNREADABLE: " + type(_e).__name__
    _out["ok"] = True
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''


def main(argv=None):
    # ⛔ RETIRED 2026-09-14 (AUDIT P1-4). `r.LandscapeLODBias` DOES NOT
    # EXIST in 5.8 -- confirmed twice, by the string getter and by the
    # engine's own 11,073-entry `Help` enumeration, with both controls
    # passing. Every write this tool made set nothing and reported
    # nothing, and its own read-back at :330 could only ever have read
    # the value it failed to change.
    #
    # The honoured lever is ALandscapeProxy.max_lod_level, which
    # scripts/payloads/landscape_force_lod.py already uses (0 = never
    # coarser than LOD0; -1 = no cap).
    #
    # The file is kept, not deleted: its docstring is the record of why
    # the classic LOD path was investigated and what was learned. It
    # refuses rather than running, so an old command line gets the
    # reason instead of a silent no-op.
    print("REFUSE: landscape_lod_probe is retired (2026-09-14).")
    print("  r.LandscapeLODBias does not exist in UE 5.8. Every write")
    print("  this tool made was a no-op that reported success.")
    print("  Use scripts/payloads/landscape_force_lod.py, which sets")
    print("  ALandscapeProxy.max_lod_level -- the lever the engine honours.")
    print("  AUDIT P1-4; live enumeration 2026-09-13, both controls passed.")
    return 2


def _retired_main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", type=float, default=None,
                    help="Value for r.LandscapeLODBias. Higher = COARSER "
                         "= cheaper. Omit to read only.")
    ap.add_argument("--restore", action="store_true",
                    help="Set r.LandscapeLODBias back to 0.")
    ap.add_argument("--forced-lod", type=int, default=None,
                    help="Per-component ForcedLOD. Decimates at EVERY "
                         "distance, so the effect shows near the camera "
                         "too. -1 restores automatic.")
    ap.add_argument("--restore-lod", action="store_true",
                    help="Put every component back to ForcedLOD -1 and "
                         "LODBias 0.")
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    component_mode = args.forced_lod is not None or args.restore_lod
    if component_mode:
        forced = -1 if args.restore_lod else args.forced_lod
        bias = 0 if args.restore_lod else None
        source = COMPONENT_PROBE.format(forced=forced, bias=bias,
                                        marker=MARKER)
    else:
        set_to = 0.0 if args.restore else args.set
        source = PROBE.format(watch=list(WATCH), set_to=set_to,
                              marker=MARKER)
    if (".p" + "y") in source:
        print("REFUSE: payload carries a file extension.")
        return 1

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

        try:
            remote.open_command_connection(node["node_id"])
            res = remote.run_command(source, unattended=True,
                                     exec_mode=remote_exec.MODE_EXEC_FILE)
            text = bootstrap._collect_output(res or {})
            idx = text.find(MARKER)
            out = None
            if idx >= 0:
                out, _ = json.JSONDecoder().raw_decode(
                    text[idx + len(MARKER):].lstrip())
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass

        if not out or not out.get("ok"):
            print("FAIL: the probe returned nothing usable ({0}). That is "
                  "'I could not look', not 'the value is default'.".format(
                      (out or {}).get("error", "no result")))
            return 4

        if component_mode:
            print("")
            print("  components found : {0}".format(out.get("components")))
            print("  set calls ok     : {0}".format(out.get("set_ok")))
            print("  ForcedLOD before : {0}".format(
                out.get("before", {}).get("forced_lod")))
            print("  ForcedLOD after  : {0}".format(
                out.get("after", {}).get("forced_lod")))
            print("  landscape Nanite : {0}".format(out.get("nanite")))
            for e in (out.get("errors") or [])[:4]:
                print("  error: {0}".format(e))
            want = -1 if args.restore_lod else args.forced_lod
            n = out.get("components") or 0
            ok = out.get("verified") or 0
            print("")
            # READ-BACK IS THE VERDICT, not the call returning. This is the
            # check the cvar path lacked, which cost a whole capture run.
            if n and ok == n:
                print("VERIFIED: all {0} components report ForcedLOD "
                      "{1}.".format(n, want))
                print("MUTATES ACTOR PROPERTIES — the proxy packages are "
                      "now dirty. NOTHING WAS SAVED. Re-run with "
                      "--restore-lod.")
                return 0
            print("FAILED: {0} of {1} components report ForcedLOD {2}. "
                  "The setter returned without changing the value — do "
                  "NOT capture against this and call it an "
                  "experiment.".format(ok, n, want))
            return 4

        print("")
        print("{0:<38} {1:>12} {2:>12}".format("cvar", "before", "after"))
        for n in WATCH:
            print("{0:<38} {1:>12} {2:>12}".format(
                n, str(out["before"].get(n)),
                str(out["after"].get(n, "-"))))
        if out.get("applied") is not None:
            # READ BACK, AND REFUSE TO REPORT SUCCESS FROM A CALL THAT
            # MERELY RETURNED. On 2026-08-06 this printed "APPLIED
            # r.LandscapeLODBias = 3.0" while the value stayed 0.0, so a
            # whole capture ran at the baseline and was analysed as the
            # experiment. The call returning is not the knob moving.
            got = out["after"].get("r.LandscapeLODBias")
            print("")
            if isinstance(got, (int, float)) and abs(
                    float(got) - float(out["applied"])) < 1e-6:
                print("APPLIED and VERIFIED r.LandscapeLODBias = {0} "
                      "(read back). RENDER state only: not saved, no "
                      "actor or asset touched. Re-run with "
                      "--restore.".format(got))
                return 0
            print("FAILED: asked for r.LandscapeLODBias = {0}, read back "
                  "{1!r}. execute_console_command returned without error "
                  "and the value DID NOT CHANGE.".format(
                      out["applied"], got))
            print("  Do NOT capture against this and call it an "
                  "experiment — the run would be at the OLD value and "
                  "would read as a null result.")
            print("  Try a mechanism that actually moves landscape LOD: "
                  "per-component LODBias, or the scalability path "
                  "(sg.ViewDistanceQuality).")
            return 4
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
