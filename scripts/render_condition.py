"""render_condition.py — set a RENDER condition and PROVE it landed.

Render-state only: sets console variables, reads every one of them back,
and REFUSES if a value did not move. Touches no asset, no actor, no
config file, and saves nothing. Everything it changes dies with the
editor process, which is the point — this is for taking a comparison
under a stated condition, not for changing what the project is.

WHY THIS EXISTS
---------------
Two separate findings made it necessary on the same day.

1. **A/B COMPARISON IS UNUSABLE WHILE CLOUDS ARE ON** (B-CLOUD-NOISE,
   2026-08-09). Two `forest_floor` captures thirty minutes apart with
   identical settings differed by mae 0.06469 in the SKY and only
   0.02853 in the near ground: the region that should be the control
   moved MORE than the region under test, because volumetric clouds
   ANIMATE. The 2026-08-08 noise floor of mean mae 0.00298 was measured
   on CLOUD-FREE frames and does not transfer. So any look comparison on
   this world must turn clouds off FIRST or its noise floor is larger
   than the effect it is looking for.

2. **THE CLIP RENDERS UNDER LUMEN AND THE LOOK WAS TUNED WITHOUT IT.**
   `DefaultEngine.ini` sets `r.DynamicGlobalIlluminationMethod=0` and
   `r.ReflectionMethod=0` for editing on the iGPU, with the comment
   "RE-ENABLE FOR FINAL RENDERS". The exposure solve, the sun and the
   forest-floor tint were all set with Lumen off. Judging look under the
   editing condition is judging the wrong world — but Lumen is only
   needed for the STILLS, so a cvar for the duration of a capture beats
   a project-config change that also affects cooked builds.

THE READ-BACK IS NOT OPTIONAL, AND THIS PROJECT HAS THE SCAR
------------------------------------------------------------
CURRENT STATE records three landscape mutations that "returned ok and
moved nothing", and specifically:
`SystemLibrary.execute_console_command(world, "r.LandscapeLODBias 3")`
returned clean while the cvar still read 0.0, from a fresh connection, in
the same payload. A capture taken after that silent failure would have
been at the OLD value and would have read as a null result.

So: every set is followed by a get, the get is compared to what was
asked, and a mismatch is a REFUSAL with exit 5 — never a warning. A
condition that cannot be proven is not a condition.

Exit codes:
  0  every requested cvar was set AND read back at the requested value
  2  editor gate refused (conduct rule 7), or bad arguments
  5  a cvar did not move — DO NOT capture against this
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_RENDERCOND__"

# name -> (off_value, on_value). Both cvars are already present in this
# project's DefaultEngine.ini and are read by read_cloud_state.py, so
# they are proven to exist on THIS install rather than remembered.
GROUPS = {
    "clouds": (("r.VolumetricCloud", 0.0, 1.0),),
    "lumen": (("r.DynamicGlobalIlluminationMethod", 0.0, 1.0),
              ("r.ReflectionMethod", 0.0, 1.0)),
}

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"ok": False, "rows": [], "error": None}}
try:
    _sl = _unreal.SystemLibrary
    _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
    _w = _ues.get_editor_world()
    for _name, _want in {pairs!r}:
        _row = {{"name": _name, "want": _want,
                "before": None, "after": None, "error": None}}
        try:
            _row["before"] = _sl.get_console_variable_float_value(_name)
        except Exception as _e:
            _row["error"] = "read-before failed: " + type(_e).__name__
        try:
            # Format an INTEGRAL value as an int and anything else as a
            # float. The original wrote int(_want) unconditionally, which
            # is correct for the on/off GROUPS (every value is 0.0/1.0)
            # and would SILENTLY TRUNCATE a fractional --cvar to zero --
            # i.e. set the opposite of a small value like 0.5. Integral
            # values still render exactly as before, so the proven
            # clouds/lumen path is unchanged.
            _txt = (str(int(_want)) if float(_want).is_integer()
                    else repr(float(_want)))
            _sl.execute_console_command(
                _w, "{{0}} {{1}}".format(_name, _txt))
        except Exception as _e:
            _row["error"] = "set failed: " + type(_e).__name__
        try:
            _row["after"] = _sl.get_console_variable_float_value(_name)
        except Exception as _e:
            _row["error"] = "read-after failed: " + type(_e).__name__
        _out["rows"].append(_row)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)
print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def parse_cvar_specs(specs):
    """NAME=VALUE strings -> ([(name, float), ...], error_or_None).

    Split out of main() so the refusals can be PROVEN OFFLINE. Testing
    them through main() is not equivalent: a well-formed spec makes main
    go on to contact the editor, so the positive control -- the case that
    proves the gate does not simply refuse everything -- could not run in
    a suite that must work with no editor open.
    """
    out = []
    for spec in (specs or []):
        if "=" not in spec:
            return None, "--cvar wants NAME=VALUE, got {0!r}".format(spec)
        name, _, raw = spec.partition("=")
        name, raw = name.strip(), raw.strip()
        if not name:
            return None, "--cvar has an empty name in {0!r}".format(spec)
        try:
            value = float(raw)
        except ValueError:
            return None, (
                "--cvar value {0!r} is not a number. This tool reads back "
                "with get_console_variable_float_value, so a non-numeric "
                "cvar could not be PROVEN to have landed and is refused "
                "rather than set blind.".format(raw))
        out.append((name, value))
    return out, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--clouds", choices=("on", "off"), default=None)
    ap.add_argument("--lumen", choices=("on", "off"), default=None)
    ap.add_argument("--cvar", action="append", default=None, metavar="NAME=VALUE",
                    help="set an arbitrary float cvar, repeatable. Same "
                         "read-back proof as the named groups. Exists so a "
                         "quality re-derivation on new hardware does not "
                         "spawn a SECOND cvar-setting implementation "
                         "(non-negotiable 4a); this is the one.")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)

    pairs = []
    for group, want in (("clouds", args.clouds), ("lumen", args.lumen)):
        if want is None:
            continue
        for name, off, on in GROUPS[group]:
            pairs.append((name, on if want == "on" else off))

    extra, err = parse_cvar_specs(args.cvar)
    if err:
        print("REFUSE: {0}".format(err))
        return 2
    pairs.extend(extra)

    if not pairs:
        print("REFUSE: nothing requested. Pass --clouds, --lumen or --cvar.")
        return 2

    # THE DISPLAY MUST NOT ROUND. The payload already sends fractional
    # values correctly (it writes str(int(v)) only when v.is_integer()),
    # but every print here used "{:.0f}", so setting
    # r.Shadow.Virtual.ResolutionLodBiasDirectional to -0.5 reported
    #     asked -0   after -0   ok
    # A reader cannot tell that from a genuine truncation to zero, and
    # this tool exists specifically because a fractional cvar was once
    # silently truncated by int(). A verdict rendered at lower precision
    # than the value it is judging is not a verdict (NN5 in miniature:
    # a check that discards the thing it is verifying).
    def _fmt(v):
        if v is None:
            return "?"
        return str(int(v)) if float(v).is_integer() else repr(float(v))

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("RENDER STATE ONLY: no asset, no actor, no config file, no save.")
    print("requested:")
    for name, want in pairs:
        print("  {0:<38s} -> {1}".format(name, _fmt(want)))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            25)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(PAYLOAD.format(pairs=pairs, marker=MARKER),
                               unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r) if r else ""
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    got = _parse(text)
    if got is None:
        print("REFUSE: no parseable result. This is 'I could not look', "
              "NOT 'the condition is set'. Do not capture against it.")
        return 5
    if got.get("error"):
        print("REFUSE: payload error: {0}".format(got["error"]))
        return 5

    print("{0:<38s} {1:>8s} {2:>8s} {3:>8s}  {4}"
          .format("cvar", "before", "asked", "after", "verdict"))
    bad = 0
    for row in got["rows"]:
        after, want = row.get("after"), row.get("want")
        ok = (after is not None and abs(float(after) - float(want)) < 1e-6
              and not row.get("error"))
        if not ok:
            bad += 1
        print("{0:<38s} {1:>8} {2:>8} {3:>8}  {4}".format(
            row["name"],
            _fmt(row.get("before")),
            _fmt(want),
            _fmt(after),
            "ok" if ok else "DID NOT MOVE" + (
                " ({0})".format(row["error"]) if row.get("error") else "")))

    print("")
    if bad:
        print("REFUSE: {0} cvar(s) did not reach the requested value. "
              "execute_console_command can return cleanly and change "
              "nothing — CURRENT STATE records exactly that for "
              "r.LandscapeLODBias. DO NOT capture against this; the run "
              "would be at the OLD value and would read as a null result."
              .format(bad))
        return 5

    print("CONDITION SET and READ BACK on every cvar.")
    print("Render state only — it dies with the editor process. Nothing "
          "was saved and no config file was touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
