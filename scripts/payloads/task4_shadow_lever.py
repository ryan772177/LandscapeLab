"""Task 4 stage 2 discriminators: turn ONE shadow candidate on, or restore.

    MODE = cards_on | cards_off | contact_on | contact_off

⭐ THE TWO CANDIDATES, and why these two. Stage 1 established that the
Task 4 metric is dominated by LIGHTING structure, not card colour. The
read-backs then found two things that would put shadow between the
blades and are currently OFF:

    grass varieties  cast_dynamic_shadow = False  (all four)
    sun              contact_shadow_length = 0.0  (all four lights)

Virtual shadow maps ARE on (r.Shadow.Virtual.Enable 1) and
r.ContactShadows is 1 globally -- so neither candidate is blocked by the
renderer; both are switched off at the object.

⛔ THE THIRD CANDIDATE DOES NOT APPLY AND IS NOT RUN. The ruling offered
"a blended-up normal if the cards use a flat one". They do not: the card
material's MP_NORMAL is fed by an AppendVector off the scan's tangent
normal map. Blending toward up would REDUCE per-blade N.L variation,
which is the opposite of what this task needs, so running it would be a
capture whose direction is known in advance.

CONTACT SHADOW LENGTH is set in WORLD SPACE at 20 cm. Stated because the
units matter: `contact_shadow_length_in_ws` is False by default, in
which case the number is a fraction of screen depth and 20 would be
absurd. This sets the flag AND the length, and reads both back.

⛔ THE OFF MODES RESET TO THE STAGE-1 BASELINE, not to a passed-in value.
Stage 1 measured a HOMOGENEOUS original (all varieties cast_dynamic_shadow
False, all lights contact_shadow_length 0.0), so cards_off/contact_off
write those literals. The pre-change value is CAPTURED in `before` /
`varieties` for the caller to verify or adopt; a heterogeneous original
would need the caller to restore per-object.
"""
import json as _json
import traceback as _tb

import unreal as _u

MODE = "__MODE__"
GT = "/Game/Foliage/GT_alpine_8k_Meadow"
SUN_LABEL = "Lighting_alpine_8k_Sun"
CONTACT_LENGTH_CM = 20.0

_out = {"ok": False, "mode": MODE}
try:
    _eal = _u.EditorAssetLibrary

    if MODE in ("cards_on", "cards_off"):
        want = (MODE == "cards_on")
        a = _eal.load_asset(GT)
        # ⛔ `list(...)`, NOT the returned Array. `grass_varieties` hands
        # out COPIES of the structs, so mutating an element changes
        # nothing on the asset -- and writing the SAME Array object back
        # is a silent no-op: it neither raises nor takes. Measured
        # 2026-09-13: per-element read-back said True, the asset said
        # False, and save+reload confirmed False. Rebuilding as a plain
        # Python list and assigning THAT takes.
        vs = list(a.get_editor_property("grass_varieties"))
        if not vs:
            # F1/NN13: zero varieties means nothing was switched; the empty-list
            # `any([])` below is False and would let ok:True through.
            raise RuntimeError(
                "grass type %s has zero varieties -- nothing to switch; a "
                "zero-count mutation must not report success" % GT)
        rows = []
        for v in (vs or []):
            before = bool(v.get_editor_property("cast_dynamic_shadow"))
            v.set_editor_property("cast_dynamic_shadow", want)
            after = bool(v.get_editor_property("cast_dynamic_shadow"))
            m = v.get_editor_property("grass_mesh")
            rows.append({"mesh": m.get_name() if m else None,
                         "before": before, "after": after})
            if after != want:
                raise RuntimeError(
                    "cast_dynamic_shadow read back as %r after asking for "
                    "%r -- the setter did not take, so a capture now would "
                    "look like a control and would not be one"
                    % (after, want))
        # The struct array must be written BACK: get_editor_property on an
        # array of structs can hand out copies, and a change to a copy is
        # a change to nothing. Written, then re-read from the asset.
        a.set_editor_property("grass_varieties", vs)
        # F4: save_asset's return is the DISK-persistence signal -- capture and
        # require it (it was discarded).
        _saved = bool(_eal.save_asset(GT, only_if_is_dirty=False))
        _out["saved"] = _saved
        if not _saved:
            raise RuntimeError("save_asset returned False for " + GT)
        # load_asset returns the RESIDENT object; re-reading grass_varieties
        # hands out FRESH struct copies, which verifies the write-back-up-the-
        # chain took (the copy-semantics hazard noted above) -- it is NOT a disk
        # reload, so _saved above is the disk evidence.
        re_a = _eal.load_asset(GT)
        re_rows = [bool(v.get_editor_property("cast_dynamic_shadow"))
                   for v in (re_a.get_editor_property("grass_varieties")
                             or [])]
        _out["varieties"] = rows
        _out["reread_from_asset"] = re_rows
        if not re_rows or any(r != want for r in re_rows):
            raise RuntimeError(
                "after write-back the asset reports %r, not all %r"
                % (re_rows, want))

    elif MODE in ("contact_on", "contact_off"):
        on = (MODE == "contact_on")
        eas = _u.get_editor_subsystem(_u.EditorActorSubsystem)
        _matches = [act for act in eas.get_all_level_actors()
                    if act.get_actor_label() == SUN_LABEL]
        if not _matches:
            labels = sorted(a.get_actor_label()
                            for a in eas.get_all_level_actors()
                            if type(a).__name__ == "DirectionalLight")
            raise RuntimeError("no actor %r; directional lights: %r"
                               % (SUN_LABEL, labels))
        if len(_matches) > 1:
            # F3/rule 8: labels collide in this project; mutating "the first"
            # would change an arbitrary light. Refuse the ambiguity.
            raise RuntimeError(
                "%d actors share the label %r; refusing to mutate an ambiguous "
                "one" % (len(_matches), SUN_LABEL))
        hit = _matches[0]
        comp = hit.get_component_by_class(_u.DirectionalLightComponent)
        if comp is None:
            raise RuntimeError("%r has no DirectionalLightComponent" % SUN_LABEL)
        before = {
            "contact_shadow_length": float(
                comp.get_editor_property("contact_shadow_length")),
            "contact_shadow_length_in_ws": bool(
                comp.get_editor_property("contact_shadow_length_in_ws"))}
        comp.set_editor_property("contact_shadow_length_in_ws", bool(on))
        comp.set_editor_property(
            "contact_shadow_length", CONTACT_LENGTH_CM if on else 0.0)
        after = {
            "contact_shadow_length": float(
                comp.get_editor_property("contact_shadow_length")),
            "contact_shadow_length_in_ws": bool(
                comp.get_editor_property("contact_shadow_length_in_ws"))}
        _out["sun"] = {"label": SUN_LABEL, "before": before, "after": after}
        want_len = CONTACT_LENGTH_CM if on else 0.0
        if abs(after["contact_shadow_length"] - want_len) > 1e-6:
            raise RuntimeError(
                "contact_shadow_length read back %r, asked %r"
                % (after["contact_shadow_length"], want_len))
        if after["contact_shadow_length_in_ws"] != bool(on):
            raise RuntimeError("contact_shadow_length_in_ws did not take")
    else:
        raise RuntimeError("unknown MODE %r" % MODE)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1000:]

print("__LL__" + _json.dumps(_out))
