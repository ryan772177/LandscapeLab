"""Force the landscape to LOD0 for a diagnostic capture, or restore it.

    MODE=force    -> max_lod_level = 0
    MODE=restore  -> max_lod_level = __HOME__

⛔ NEITHER CVAR THE RULING NAMED EXISTS IN 5.8. Enumerated on the running
editor: `r.LandscapeLODBias` and `landscape.ForcedLOD` both read back ""
from `get_console_variable_string_value`, which is how an UNSET cvar
answers -- so this is "I looked and they are absent", not "I could not
look". `r.ForceLOD` does exist (value -1) but it is the STATIC MESH
override; the landscape has its own LOD chain.

What IS reflected on the Landscape actor, and is therefore the honoured
lever here:

    max_lod_level              -1 (no cap)  -> 0 forces LOD0
    lod_distribution_setting   3.0          (read, not changed)

`max_lod_level` CAPS the LOD index, so 0 means "never coarser than
LOD0". Read back after the write, and a disagreement raises. NOTE this
confirms the CAP PROPERTY reads back as 0 -- it does not by itself prove
the renderer is displaying LOD0 (no component recreate/flush is observed);
a setter that silently did nothing is caught, a stale render is not.

RESTORE IS TO THE RECORDED VALUE, passed in, not to a guessed default --
and one HOME value cannot restore MULTIPLE landscapes whose originals may
differ, so restore refuses when more than one landscape is present.
"""
import json as _json
import traceback as _tb

import unreal as _u

MODE = "__MODE__"
# Parsed inside the try (and only when restoring) so a bad/absent __HOME__ fails
# into the __LL__ JSON rather than crashing at import with no marker -- and a
# force run, which does not use HOME, is not blocked by a bad HOME.
HOME_RAW = "__HOME__"
_out = {"ok": False, "mode": MODE}
try:
    if MODE not in ("force", "restore"):
        raise RuntimeError("MODE must be 'force' or 'restore', got %r" % MODE)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _ls = [a for a in _eas.get_all_level_actors()
           if type(a).__name__ == "Landscape"]
    if not _ls:
        _kinds = sorted(set(type(a).__name__ for a in
                            _eas.get_all_level_actors()
                            if "Landscape" in type(a).__name__))
        raise RuntimeError("no Landscape actor; Landscape-ish classes "
                           "present: %r" % _kinds)
    _out["landscape_count"] = len(_ls)
    HOME = None
    if MODE == "restore":
        HOME = int(HOME_RAW)
        if len(_ls) > 1:
            raise RuntimeError(
                "%d landscapes present but restore was given ONE HOME (%d); "
                "per-landscape originals may differ -- refusing to restore all "
                "to one value" % (len(_ls), HOME))
    _rows = []
    for _a in _ls:
        _before = int(_a.get_editor_property("max_lod_level"))
        _want = 0 if MODE == "force" else HOME
        _a.set_editor_property("max_lod_level", _want)
        _after = int(_a.get_editor_property("max_lod_level"))
        _rows.append({"label": _a.get_actor_label(),
                      "max_lod_level_before": _before,
                      "max_lod_level_after": _after,
                      "requested": _want,
                      "lod_distribution_setting": float(
                          _a.get_editor_property(
                              "lod_distribution_setting"))})
        if _after != _want:
            raise RuntimeError(
                "max_lod_level read back as %d after asking for %d on %r "
                "-- the setter did not take, so a capture now would look "
                "like a control and would not be one"
                % (_after, _want, _a.get_actor_label()))
    _out["landscapes"] = _rows
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]
print("__LL__" + _json.dumps(_out))
