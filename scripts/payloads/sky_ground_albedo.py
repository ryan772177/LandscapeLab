"""Read, set or restore the SkyAtmosphere's GroundAlbedo. Brief 2, Task 0.

WHAT THIS IS FOR
    The elevated bench stations show a flat pale band with a razor-sharp top
    edge. Two candidates: exponential height fog, or the SkyAtmosphere's
    VIRTUAL PLANET SURFACE showing wherever no geometry is rendered -- i.e.
    world that is not loaded. Painting that surface magenta for one capture
    decides it, because fog cannot turn magenta.

WHY THE VISIBLE SURFACE ACTUALLY TAKES THIS VALUE (verified, not assumed)
    SkyAtmosphereComponent.h:64 says GroundAlbedo "will tint the atmosphere
    when the sun light will bounce on it. Only taken into account when
    MultiScattering>0.0" -- which describes the LUT contribution and would
    suggest this test cannot work. The RAY-MARCH path is what draws the
    surface you can see, and it is NOT gated on multi-scattering:

        SkyAtmosphere.usf:815   if (Ground && tMax == tBottom)
        SkyAtmosphere.usf:826   L += Light0Illuminance * TransmittanceToLight0
                                     * Throughput * NdotL0
                                     * Atmosphere.GroundAlbedo.rgb / PI

    So a ray that reaches the planet sphere is shaded with GroundAlbedo.

    NOTE THE SCALING, because it is the trap: NdotL0 is the sun's cosine at
    that point and this recipe's sun sits at 12 deg elevation, so the term is
    ~0.21, then divided by PI, then tonemapped at -1.923 EV. The magenta can
    land DIM. A hue test with absolute floors (void_mask.py wants r>0.2 and
    b>0.2) could therefore report 0.000 on a frame that IS void -- a false
    zero, and Brief 2 gates every later atmosphere number on this reading.
    That is why Task 0 here captures a BASELINE at the original albedo too:
    the differential between the two captures needs no absolute threshold.

MODE is one of:
    read     report the current value and the multi-scattering factor
    set      set to __R__,__G__,__B__ and read back
    restore  set to __R__,__G__,__B__ (the recorded original) and read back

NEVER SAVES. The component is a level actor; leaving the package dirty is
fine and the editor is closed without saving (R-EDITOR-CLOSE, census first).
"""
import json as _json
import traceback as _tb

import unreal as _u

MODE = r"__MODE__"
R = int("__R__")
G = int("__G__")
B = int("__B__")

_out = {"ok": False, "error": None, "mode": MODE}
try:
    _ues = _u.get_editor_subsystem(_u.UnrealEditorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _out["level_path"] = _ues.get_editor_world().get_path_name()

    # Identify by CLASS, not by label -- standing rule 8. Labels collide and
    # this level has carried duplicates before.
    _comps = []
    for _a in _eas.get_all_level_actors():
        try:
            _c = _a.get_component_by_class(_u.SkyAtmosphereComponent)
        except Exception:
            _c = None
        if _c:
            _comps.append((_a, _c))
    _out["skyatmosphere_actors"] = [a.get_actor_label() for a, _ in _comps]
    if len(_comps) != 1:
        raise RuntimeError("expected exactly 1 SkyAtmosphere component, found "
                           "%d: %s" % (len(_comps), _out["skyatmosphere_actors"]))
    _actor, _comp = _comps[0]

    def _albedo():
        _c = _comp.get_editor_property("ground_albedo")
        return [int(_c.r), int(_c.g), int(_c.b), int(_c.a)]

    _out["multi_scattering"] = float(
        _comp.get_editor_property("multi_scattering_factor"))
    _out["before"] = _albedo()

    if MODE in ("set", "restore"):
        _comp.set_editor_property("ground_albedo", _u.Color(r=R, g=G, b=B, a=255))
        # The component caches atmosphere state; nudge it so the change is
        # live for the very next render rather than the one after.
        try:
            _comp.mark_render_state_dirty()
        except Exception as _e:
            _out["mark_dirty_error"] = str(_e)
        _out["after"] = _albedo()
        _out["applied"] = (_out["after"][:3] == [R, G, B])
        # RULE 12: the read-back comes from the engine, not from the value I
        # just wrote. If these disagree, the set did not take.
        if not _out["applied"]:
            raise RuntimeError("read-back %s != requested %s"
                               % (_out["after"][:3], [R, G, B]))
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-900:]

print("__LL__" + _json.dumps(_out, default=str))
