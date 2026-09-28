"""read_exposure.py — read the LIVE exposure state. Read-only.

WHY THIS EXISTS
The 2026-08-06 sweep measured ground at linear 0.556-0.622 against
`atmosphere_solve`'s solved target of 0.3201 — about 0.9 stop over, on
front-lit horizontal ground that is 80-90% Grass layer. That is not the
accepted pale-verticals ruling (R13 2d), which concerns VERTICAL
surfaces. The report named one check to separate the two candidates:
is the solved -1.786 EV actually in effect, or is the solver's terrain
albedo assumption too dark?

This is that check, and it answers a question no existing tool asks.
`apply_lighting` WRITES exposure and has no read-only mode; running it to
find out what is set would mutate the thing being measured — a check that
consumes the value it is verifying (non-negotiable 5).

WHAT IT ENUMERATES, AND WHY ALL OF THEM
EVERY PostProcessVolume in the world, not just the recipe's. That is the
load-bearing part. `apply_lighting` deliberately leaves PostProcessVolume
out of its foreign-actor census, and says why (apply_lighting:103-108):
multiple BOUNDED volumes are legitimate and blend by priority, but a
second UNBOUND volume "overrides exposure exactly as a second fog
overrides fog". So a scene can carry the recipe's -1.786 and still expose
at something else entirely, with nothing anywhere reporting a conflict.
Reporting only the recipe's own volume would return a correct number that
answers the wrong question.

Per volume it reports: label, unbound, enabled, priority, blend weight,
and whether each exposure field is OVERRIDDEN as well as its value — an
un-overridden value is inert and reads exactly like a set one
(non-negotiable 17: a config records differences from a default; reading
one tells you what was overridden, never what is in effect).

WHAT IT CANNOT TELL YOU, STATED PLAINLY
The engine's final exposure also depends on viewport show flags and on
`r.DefaultFeature.AutoExposure*` cvars, which this does not read. A clean
report here is therefore NOT proof that the render used -1.786; it is
proof that the VOLUMES agree on it. Said out loud because "I checked the
exposure" would otherwise read as more than it is.

Exit codes:
  0  read completed (agreement or not — see the verdict line)
  1  unexpected error
  2  recipe missing / unparseable
  3  editor identity gate refused (conduct rule 7)
  4  the probe returned nothing — could not look
  6  level gate refused: the editor has a different level open
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import landscape_spec     # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_EXPOSURE__"

# NOTE: no file extensions anywhere in the payload below. A '.p'+'y'
# substring makes UE treat the whole script as a FILENAME instead of
# running it (PythonScriptPlugin.cpp:813-830), and the resulting error
# reads as a missing file rather than a bad payload.
PROBE = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "volumes": [], "error": None}}

_FIELDS = (
    "auto_exposure_method",
    "auto_exposure_bias",
    "auto_exposure_min_brightness",
    "auto_exposure_max_brightness",
    "auto_exposure_speed_up",
    "auto_exposure_speed_down",
    # AEM_MANUAL derives exposure from the PHYSICAL CAMERA fields, so
    # these are not incidental - they are the other half of the manual
    # exposure. atmosphere_solve assumes f/4, 1/60 s, ISO 100 to reach
    # EV100 9.9069; if the live values differ, the solved bias is
    # correct and the EXPOSURE STILL DIFFERS, which is exactly the shape
    # of the 0.9-stop discrepancy being chased. Read, never assumed:
    # engine defaults are a claim about a default, not about this level.
    "camera_shutter_speed",
    "camera_iso",
    "camera_aperture_f_stop",
    "depth_of_field_fstop",
)

try:
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _world = _ues.get_editor_world()
    for _v in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.PostProcessVolume):
        _rec = {{"label": _v.get_actor_label(), "fields": {{}}}}
        for _prop, _key in (("unbound", "unbound"),
                            ("enabled", "enabled"),
                            ("priority", "priority"),
                            ("blend_weight", "blend_weight"),
                            ("blend_radius", "blend_radius")):
            try:
                _rec[_key] = _v.get_editor_property(_prop)
            except Exception as _e:
                _rec[_key] = "UNREADABLE: " + type(_e).__name__
        try:
            _s = _v.get_editor_property("settings")
        except Exception as _e:
            _rec["settings_error"] = "%s: %s" % (type(_e).__name__, _e)
            _out["volumes"].append(_rec)
            continue
        for _f in _FIELDS:
            _entry = {{}}
            try:
                _entry["value"] = str(_s.get_editor_property(_f))
            except Exception as _e:
                _entry["value"] = "UNREADABLE: " + type(_e).__name__
            try:
                _entry["overridden"] = bool(
                    _s.get_editor_property("override_" + _f))
            except Exception as _e:
                _entry["overridden"] = "UNREADABLE: " + type(_e).__name__
            _rec["fields"][_f] = _entry
        _out["volumes"].append(_rec)
    _out["ok"] = True
    del _world
except Exception as _exc:
    _out["error"] = "%s: %s" % (type(_exc).__name__, _exc)

for _n in ("_v", "_s", "_world", "_ues"):
    globals().pop(_n, None)

print("{marker}" + _json.dumps(_out))
'''.format(marker=MARKER)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--recipe", default=landscape_spec.DEFAULT_RECIPE)
    ap.add_argument("--timeout", type=float, default=25.0)
    args = ap.parse_args(argv)

    recipe, err = landscape_spec.load_recipe(os.path.abspath(args.recipe))
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    want_ev = ((recipe.get("lighting") or {}).get("exposure") or {}).get(
        "compensation_ev")
    want_method = ((recipe.get("lighting") or {}).get("exposure") or {}).get(
        "method")

    for token in (".p" + "y",):
        if token in PROBE:
            print("REFUSE: probe carries {0!r}; UE would treat it as a "
                  "filename.".format(token))
            return 1

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("recipe    : exposure {0!r}, compensation_ev {1}".format(
        want_method, want_ev))
    print("")

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

        def _runner(source, marker):
            try:
                remote.open_command_connection(node["node_id"])
            except Exception as exc:
                print("  connection failed: {0}".format(exc))
                return None
            try:
                res = remote.run_command(
                    source, unattended=True,
                    exec_mode=remote_exec.MODE_EXEC_FILE)
                if not res or not res.get("success"):
                    print("  command did not succeed: {0}".format(
                        (res or {}).get("result")))
                    return None
                text = bootstrap._collect_output(res)
                idx = text.find(marker)
                if idx < 0:
                    return None
                payload, _ = json.JSONDecoder().raw_decode(
                    text[idx + len(marker):].lstrip())
                return payload
            except Exception as exc:
                print("  command errored: {0}".format(exc))
                return None
            finally:
                try:
                    remote.close_command_connection()
                except Exception:
                    pass

        ok_level, detail = verify_landscape.gate_level(
            remote_exec, remote, node["node_id"],
            (recipe.get("landscape") or {}).get("level_path"), _runner)
        if not ok_level:
            print("REFUSE: {0}".format(detail))
            return 6
        print("  level {0}".format(detail))
        print("")

        out = _runner(PROBE, MARKER)
        if out is None or not out.get("ok"):
            print("FAIL: the exposure probe returned nothing usable "
                  "({0}). This is 'I could not look', NOT 'nothing is "
                  "set'.".format((out or {}).get("error", "no result")))
            return 4

        vols = out.get("volumes") or []
        print("--- PostProcessVolumes in the level: {0} ---".format(
            len(vols)))
        unbound_live = []
        for v in vols:
            print("")
            print("  {0!r}".format(v.get("label")))
            print("    unbound={0}  enabled={1}  priority={2}  "
                  "blend_weight={3}".format(
                      v.get("unbound"), v.get("enabled"),
                      v.get("priority"), v.get("blend_weight")))
            if v.get("settings_error"):
                print("    settings UNREADABLE: {0}".format(
                    v["settings_error"]))
                continue
            for f, e in (v.get("fields") or {}).items():
                mark = "OVERRIDDEN" if e.get("overridden") is True else \
                    ("inert" if e.get("overridden") is False else "?")
                print("    {0:<32} {1:<28} {2}".format(
                    f, e.get("value"), mark))
            if v.get("unbound") is True and v.get("enabled") is not False:
                unbound_live.append(v)

        print("")
        print("=" * 68)
        # The discriminating question, asked explicitly.
        print("  UNBOUND + enabled volumes affecting the whole level: "
              "{0}".format(len(unbound_live)))
        if len(unbound_live) > 1:
            print("  *** MORE THAN ONE. A second unbound volume overrides")
            print("      exposure exactly as a second fog overrides fog")
            print("      (apply_lighting:103-108). The recipe's value can")
            print("      be set and still not be what the camera used.")
        for v in unbound_live:
            e = (v.get("fields") or {}).get("auto_exposure_bias") or {}
            print("  {0!r}: bias {1} ({2})".format(
                v.get("label"), e.get("value"),
                "OVERRIDDEN" if e.get("overridden") is True else
                "NOT overridden — INERT, the project default applies"))
        print("=" * 68)
        print("")
        print("NOTE: this reads VOLUMES only. Viewport show flags and")
        print("r.DefaultFeature.AutoExposure* cvars also govern the final")
        print("exposure and are NOT read here, so agreement below is not")
        print("proof the render used it.")
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
