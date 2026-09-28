"""read_cloud_state.py — is the undeclared VolumetricCloud actor ACTIVE?

READ-ONLY. Mutates nothing, saves nothing.

WHY THIS EXISTS
---------------
The pass audit (2026-08-06) found a `VolumetricCloud` actor in
/Game/Alpine that no recipe declares, no script disables, and
`apply_lighting`'s foreign-actor census does not cover. The GPU
measurement behind the clouds ruling (R13 ADDENDUM: sweep_2000 94.45 ms
/ sweep_0060 75.71 ms) was taken WITH IT PRESENT, and its visibility was
never read. So the board asserts a negative — "clouds NOT enabled" —
that no instrument in this pipeline can enforce.

`PROJECT_STATE.json` records `scene.VolumetricCloud` count 1 at the
origin. That is a CENSUS, not a state: it says the actor exists, and
says nothing about whether it renders.

THE THREE OUTCOMES, ruled in the handoff before the measurement (so the
verdict cannot be chosen to suit the answer):

  ACTIVE  -> clouds are already inside the 75-95 ms figures, interactive
             headroom is BETTER than believed, and the ruling should be
             re-taken on a clean baseline.
  INERT   -> bookkeeping defect only; the ruling stands; declare the
             actor.
  UNREAD  -> say so. DO NOT ASSUME INERT.

WHAT "ACTIVE" MEANS HERE, and why three reads and not one
---------------------------------------------------------
Rendering is gated in more than one place, and any one of them alone can
make the cloud invisible while the others say it is fine (non-negotiable
17: a config records overrides, not effect). This reads all of:

  1. the ACTOR's editor and game hidden flags;
  2. the COMPONENT's own visibility and active state — the component is
     what renders, not the actor;
  3. the engine's `r.VolumetricCloud` cvar — the global switch, which
     can be 0 while a perfectly visible actor sits in the level.

A cloud renders only if ALL THREE permit it. The verdict is therefore
ACTIVE only when every read succeeded and every one permits rendering;
any failed read yields UNREAD, never INERT (non-negotiable 6 — "I could
not look" is not "it is off").

Every field is read in its own try/except and reported as either a value
or the exception, so one unreflected property cannot silently become a
False that reads as "disabled" — the exact shape of the
`camera_aperture_f_stop` gap this same audit recorded.

Exit codes:
  0  measured; INERT (present, cannot be rendering)
  2  editor gate refused (rule 7), or no parseable result
  3  measured; ACTIVE (is or can be rendering) — the ruling needs re-take
  4  COULD NOT READ — never a pass, never an assumed INERT
  5  measured; NO VolumetricCloud actor found at all
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_CLOUDSTATE__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"actors": [], "cvars": {{}}, "error": None}}


def _try(fn):
    """Value, or the exception text. NEVER a default that reads as data."""
    try:
        return {{"ok": True, "value": fn()}}
    except Exception as _e:
        return {{"ok": False, "error": str(_e)[:200]}}


try:
    _sub = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _all = _sub.get_all_level_actors()
    for _a in _all:
        if not isinstance(_a, _unreal.VolumetricCloud):
            continue
        _row = {{"label": None, "path": None, "class": type(_a).__name__,
                 "actor": {{}}, "components": []}}
        _row["label"] = _try(lambda a=_a: a.get_actor_label())
        _row["path"] = _try(lambda a=_a: a.get_path_name())
        _row["actor"]["is_hidden_ed"] = _try(lambda a=_a: bool(
            a.is_hidden_ed()))
        _row["actor"]["temporarily_hidden"] = _try(lambda a=_a: bool(
            a.is_temporarily_hidden_in_editor()))
        _row["actor"]["hidden_in_game"] = _try(lambda a=_a: bool(
            a.get_editor_property("hidden")))
        try:
            _comps = _a.get_components_by_class(
                _unreal.VolumetricCloudComponent)
        except Exception as _e:
            _comps = []
            _row["components_error"] = str(_e)[:200]
        for _c in _comps:
            _crow = {{"class": type(_c).__name__}}
            _crow["is_visible"] = _try(lambda c=_c: bool(c.is_visible()))
            _crow["visible_prop"] = _try(lambda c=_c: bool(
                c.get_editor_property("visible")))
            _crow["is_active"] = _try(lambda c=_c: bool(c.is_active()))
            _crow["is_registered"] = _try(lambda c=_c: bool(
                c.get_editor_property("is_active")))
            _crow["layer_bottom_km"] = _try(lambda c=_c: float(
                c.get_editor_property("layer_bottom_altitude")))
            _crow["layer_height_km"] = _try(lambda c=_c: float(
                c.get_editor_property("layer_height")))
            _crow["material"] = _try(
                lambda c=_c: str(c.get_editor_property("material")))
            _row["components"].append(_crow)
        _out["actors"].append(_row)

    for _cv in ("r.VolumetricCloud", "r.VolumetricRenderTarget"):
        _out["cvars"][_cv] = _try(
            lambda v=_cv: int(
                _unreal.SystemLibrary.get_console_variable_int_value(v)))
except Exception as _exc:
    _out["error"] = str(_exc)[:400]

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


def _show(name, cell, indent="    "):
    """Print a read as a value or as an explicit could-not-read."""
    if not isinstance(cell, dict):
        print("{0}{1:<24s} (absent)".format(indent, name))
        return None
    if cell.get("ok"):
        print("{0}{1:<24s} {2}".format(indent, name, cell["value"]))
        return cell["value"]
    print("{0}{1:<24s} COULD NOT READ: {2}".format(
        indent, name, cell.get("error")))
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("READ-ONLY: this script mutates nothing and saves nothing.")
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(PAYLOAD.format(marker=MARKER),
                                   unattended=True,
                                   exec_mode=remote_exec.MODE_EXEC_FILE)
            if not r or not r.get("success"):
                print("command failed: {0}".format((r or {}).get("result")))
                return 2
            data = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None:
        print("COULD NOT READ: no parseable result from the editor.")
        return 4
    if data.get("error"):
        print("COULD NOT READ: editor-side error: {0}".format(data["error"]))
        return 4

    actors = data.get("actors") or []
    print("VolumetricCloud actors found: {0}".format(len(actors)))
    if not actors:
        print("")
        print("VERDICT: NO VolumetricCloud actor in the loaded world.")
        print("NOTE: World Partition — an actor in an UNLOADED cell is")
        print("invisible to this read. That is 'none among the loaded")
        print("actors', not 'none in the level'.")
        return 5

    unread, permits = [], []
    for row in actors:
        print("")
        print("  actor: {0}".format(
            (row.get("label") or {}).get("value", "<unread>")))
        print("    path                     {0}".format(
            (row.get("path") or {}).get("value", "<unread>")))
        a = row.get("actor") or {}
        hid_ed = _show("is_hidden_ed", a.get("is_hidden_ed"))
        hid_tmp = _show("temporarily_hidden", a.get("temporarily_hidden"))
        hid_game = _show("hidden_in_game", a.get("hidden_in_game"))
        for k, v in (("is_hidden_ed", hid_ed),
                     ("temporarily_hidden", hid_tmp),
                     ("hidden_in_game", hid_game)):
            if v is None:
                unread.append("actor.{0}".format(k))
        # An actor permits rendering when it is not hidden by any flag.
        permits.append(hid_ed is False)
        permits.append(hid_tmp is False)

        if row.get("components_error"):
            print("    components               COULD NOT READ: {0}"
                  .format(row["components_error"]))
            unread.append("components")
        comps = row.get("components") or []
        print("    VolumetricCloudComponent count: {0}".format(len(comps)))
        if not comps:
            unread.append("no component read")
        for c in comps:
            vis = _show("is_visible", c.get("is_visible"), "      ")
            _show("visible (property)", c.get("visible_prop"), "      ")
            _show("is_active", c.get("is_active"), "      ")
            _show("layer_bottom_km", c.get("layer_bottom_km"), "      ")
            _show("layer_height_km", c.get("layer_height_km"), "      ")
            _show("material", c.get("material"), "      ")
            if vis is None:
                unread.append("component.is_visible")
            permits.append(vis is True)

    print("")
    print("  engine switches (the global gate — non-negotiable 17: the")
    print("  actor can be perfectly visible while this is 0)")
    cv_ok = True
    for name, cell in (data.get("cvars") or {}).items():
        val = _show(name, cell, "    ")
        if val is None:
            unread.append("cvar {0}".format(name))
            cv_ok = False
        else:
            permits.append(val != 0)

    print("")
    if unread:
        print("VERDICT: COULD NOT READ — {0} field(s) did not read:"
              .format(len(unread)))
        for u in unread:
            print("  - {0}".format(u))
        print("")
        print("This is NOT 'inert'. The handoff ruled that a failed read")
        print("is reported as a failed read (non-negotiable 6). The GPU")
        print("baseline stays contaminated until every gate is read.")
        return 4

    if all(permits):
        print("VERDICT: ACTIVE — every gate permits rendering.")
        print("")
        print("CONSEQUENCE, ruled in advance: the 94.45 / 75.71 ms figures")
        print("were measured WITH clouds rendering, so they are not a")
        print("clouds-off baseline. Interactive headroom is BETTER than")
        print("R13 ADDENDUM believes, and the clouds ruling should be")
        print("re-taken against a clean baseline. That re-measure is")
        print("ATTENDED (viewport overlay reading) — not this script.")
        return 3

    print("VERDICT: INERT — at least one gate blocks rendering, and every")
    print("gate was read successfully.")
    print("")
    print("CONSEQUENCE: bookkeeping defect only. The R13 ADDENDUM clouds")
    print("ruling stands on its measured numbers. The actor must still be")
    print("DECLARED — an undeclared actor that no census covers is how")
    print("this was missed for three days.")
    if not cv_ok:
        print("(cvar reads failed — see above)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
