"""TEMPORARY DIAGNOSTIC: set grade color_gamma's effective product.

    --set G=0.797     apply to EVERY PostProcessVolume, override on
    --set G<=0        restore: override OFF, value back to (1,1,1,1), all volumes

⚠ BULK: this touches every PostProcessVolume in the level (there is one
baseline unbound volume in Alpine8K); restore forces ALL of them to
(1,1,1,1)/override-off, which assumes that baseline. G<=0 (not just 0)
takes the restore branch, since the apply exponent 1/G needs G>0.

⭐ WHAT IT TESTS. Q12's residual, after the grade contrast is accounted
for, is ~0.797 and is PIVOT-1 rather than pivot-0.18: the PPI0 card at
0.180 lands at 0.2509 on FinalImage, where a pivot-0.18 op would map
0.18 to itself. Pivot 1 is a GAMMA, not a contrast.

The shader's gamma is the RECIPROCAL of the product
(PostProcessCombineLUTs.usf:99):

    WorkingColor = pow( WorkingColor, 1.0 / (ColorGamma.xyz*ColorGamma.w) )

so setting the product to the residual R contributes an exponent 1/R and
CANCELS it. If the residual really is gamma-shaped, the card's delivered
step should then be the contrast alone.

⛔ NOT WRITTEN TO ALL FOUR COMPONENTS. The shader uses xyz*w, so writing
G to all four would give G squared -- the exact defect found in
color_contrast the same day. xyz = 1, the value in w, and the PRODUCT is
read back.
"""
import json as _json
import traceback as _tb

import unreal as _u

G = float("__G__")

_out = {"ok": False, "requested_product": G}
try:
    _sub = _u.get_editor_subsystem(_u.EditorActorSubsystem)
    _eas = _u.get_editor_subsystem(_u.EditorAssetSubsystem)
    _touched = []
    for _a in _sub.get_all_level_actors():
        if type(_a).__name__ != "PostProcessVolume":
            continue
        _s = _a.get_editor_property("settings")
        if G <= 0.0:
            _s.set_editor_property("override_color_gamma", False)
            _s.set_editor_property("color_gamma",
                                   _u.Vector4(1.0, 1.0, 1.0, 1.0))
        else:
            _s.set_editor_property("override_color_gamma", True)
            _s.set_editor_property("color_gamma",
                                   _u.Vector4(1.0, 1.0, 1.0, G))
        _a.set_editor_property("settings", _s)
        _touched.append(_a)

    # READ BACK from the volume, and report the PRODUCT -- the components
    # individually would each be exactly what was written while the
    # product was wrong.
    _rb = []
    for _a in _touched:
        _s2 = _a.get_editor_property("settings")
        _cg = _s2.get_editor_property("color_gamma")
        _rb.append({
            "label": _a.get_actor_label(),
            "override_color_gamma": bool(
                _s2.get_editor_property("override_color_gamma")),
            "color_gamma": [round(float(_cg.x), 5), round(float(_cg.y), 5),
                            round(float(_cg.z), 5), round(float(_cg.w), 5)],
            "effective_xyz_times_w": [
                round(float(_cg.x) * float(_cg.w), 6),
                round(float(_cg.y) * float(_cg.w), 6),
                round(float(_cg.z) * float(_cg.w), 6)],
        })
    _out["volumes"] = _rb
    _mod_errs = []
    for _a in _touched:
        try:
            _a.modify()
            _eas.set_dirty_flag(_a, True)
        except Exception as _me:
            # F4: a failed modify/dirty can mean the save does not persist --
            # record it rather than swallow it.
            _mod_errs.append({"label": _a.get_actor_label(),
                              "error": type(_me).__name__})
    if _mod_errs:
        _out["modify_errors"] = _mod_errs
    if _touched:
        _out["saved"] = bool(_eas.save_loaded_assets(_touched, False))

    # F2/NN12: verify each volume DELIVERED the requested product, not merely
    # that the setter ran. The product is xyz*w and xyz==1, so it equals w.
    # Restore (G<=0) expects product 1.0 with override OFF.
    _want_product = G if G > 0.0 else 1.0
    _want_override = G > 0.0
    _mismatch = []
    for _r in _rb:
        _prod = _r["effective_xyz_times_w"][0]
        if (abs(_prod - _want_product) > 1e-4
                or _r["override_color_gamma"] != _want_override):
            _mismatch.append({"label": _r["label"], "product": _prod,
                              "override": _r["override_color_gamma"]})
    _out["mismatches"] = _mismatch

    # F1/F3: mutated zero volumes, a delivered-value mismatch, or a save that did
    # not persist are each failures, not success.
    _out["ok"] = (bool(_touched) and not _mismatch and bool(_out.get("saved")))
    if not _out["ok"]:
        _out["refused"] = (
            "touched=%d, mismatches=%d, saved=%s -- gamma not applied, verified "
            "and persisted on all PostProcessVolumes"
            % (len(_touched), len(_mismatch), _out.get("saved")))
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["trace"] = _tb.format_exc()[-700:]

print("__LL__" + _json.dumps(_out))
