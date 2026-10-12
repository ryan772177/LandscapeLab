"""make_roof_grades.py -- the town roofs' weathering-grade material instances (2026-10-11 roof variety, lever B).

    python scripts/make_roof_grades.py [--dry-run]

Reads recipes/town_kit.json style.roof_variety (grades, grade_dir) and the usable roofs. For every usable roof
mesh, its slot-0 material is read LIVE (never assumed). For each non-base grade, one MaterialInstanceConstant
grade_dir/<roof MI asset name>_<grade> (e.g. MI_Roof_aged; town_kit_plan.grade_mic_path) is found or created. Its parent is that roof MI; it overrides ONLY the grade's
scalar/vector keys, each of which must already be a parameter of the parent (refused otherwise). It is saved
(save_asset must return True) and every value is READ BACK from the saved asset object, along with the parent.
That object is the in-memory one just written, NOT a cold reload (review S4): the save succeeding plus the
read-back are the evidence, and the stills are the independent check.

No vendor byte is written: grade_dir must lie outside /Game/Meshes and /Game/Megascans. Idempotent: a rerun
re-sets the same values. Design + review: research/town_kit/ROOF_VARIETY.md.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import town_kit_plan as tkp  # noqa: E402

MARKER = "__LL__"


grade_mic_path = tkp.grade_mic_path    # THE one naming rule lives in town_kit_plan (stamped as the manifest's _roof_fit)


def config():
    rv = (tkp._R.get("style") or {}).get("roof_variety") or {}
    return rv


def validate(rv):
    e = []
    gd = str(rv.get("grade_dir", ""))
    if not gd.startswith("/Game/Materials/") or gd.startswith(("/Game/Meshes", "/Game/Megascans")):
        e.append("grade_dir must be under /Game/Materials/ (ours), got %r" % gd)
    gs = rv.get("grades")
    if not isinstance(gs, list) or not gs:
        return e + ["grades must be a non-empty list"]
    names = [g.get("name") for g in gs]
    if "base" not in names or len(set(names)) != len(names):
        e.append("grades need exactly one 'base' and unique names: %s" % names)
    for g in gs:
        n = str(g.get("name"))
        if not n.replace("_", "").isalnum():
            e.append("grade name %r must be alphanumeric/underscore" % n)
        extra = [k for k in g if k not in ("name", "scalars", "vectors") and not k.startswith("_")]
        if extra:
            e.append("grade %s: unknown keys %s" % (n, extra))
        if n == "base" and (g.get("scalars") or g.get("vectors")):
            e.append("grade base must override nothing")
        if n != "base" and not (g.get("scalars") or g.get("vectors")):
            e.append("grade %s overrides nothing (it would equal base)" % n)
        for k, v in (g.get("scalars") or {}).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v:
                e.append("grade %s scalar %s = %r is not a number" % (n, k, v))
        for k, v in (g.get("vectors") or {}).items():
            if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)):
                e.append("grade %s vector %s must be 4 numbers" % (n, k))
    return e


PAYLOAD = r'''
import json as _json
import unreal as _u
_C = _json.loads(__CFG__)
_eal = _u.EditorAssetLibrary
_mel = _u.MaterialEditingLibrary
_at = _u.AssetToolsHelpers.get_asset_tools()
_out = {"ok": False, "mics": [], "roof_mis": {}}
def _p(o):
    return o.get_path_name().split(".")[0] if o is not None else None
try:
    _parents = {}
    for _rp in _C["roofs"]:
        _m = _eal.load_asset(_rp)
        if _m is None or not isinstance(_m, _u.StaticMesh):
            raise RuntimeError("roof mesh does not load: " + _rp)
        _sm = _m.static_materials
        if len(_sm) != 1 or _sm[0].material_interface is None:
            raise RuntimeError("%s has %d slots (need exactly 1 with a material)" % (_rp, len(_sm)))
        _mi = _sm[0].material_interface
        if not isinstance(_mi, _u.MaterialInstance):
            raise RuntimeError("%s slot 0 is not a MaterialInstance: %s" % (_rp, _p(_mi)))
        _out["roof_mis"][_rp] = _p(_mi)
        if _p(_mi) != _C["recorded_mi"][_rp]:
            raise RuntimeError("%s slot 0 is %s live, recipe records %s" % (_rp, _p(_mi), _C["recorded_mi"][_rp]))
        _parents[_p(_mi)] = _mi
    for _pp, _par in sorted(_parents.items()):
        _sn = set(str(n) for n in _mel.get_scalar_parameter_names(_par))
        _vn = set(str(n) for n in _mel.get_vector_parameter_names(_par))
        for _g in _C["grades"]:
            if _g["name"] == "base":
                continue
            _miss = [k for k in _g.get("scalars", {}) if k not in _sn] + [k for k in _g.get("vectors", {}) if k not in _vn]
            if _miss:
                raise RuntimeError("grade %s: %s are not parameters of %s" % (_g["name"], _miss, _pp))
            _path = _C["mic_paths"][_pp][_g["name"]]
            if _eal.does_asset_exist(_path):
                _mic = _eal.load_asset(_path)
                if not isinstance(_mic, _u.MaterialInstanceConstant):
                    raise RuntimeError(_path + " exists and is not a MaterialInstanceConstant")
                _made = False
            else:
                _mic = _at.create_asset(_path.rsplit("/", 1)[1], _C["grade_dir"], _u.MaterialInstanceConstant,
                                        _u.MaterialInstanceConstantFactoryNew())
                if _mic is None:
                    raise RuntimeError("create_asset failed: " + _path)
                _made = True
            _mel.set_material_instance_parent(_mic, _par)
            # a rerun with FEWER keys must not keep the old ones: clear every override first
            _mel.clear_all_material_instance_parameters(_mic)
            # the setters' bool is a CONSTANT false in 5.8 (MaterialEditingLibrary.cpp:1485-1494, 1573-1582:
            # bResult never assigned) -- design review 2026-10-11 M1. The read-back below is the check.
            for _k, _v in _g.get("scalars", {}).items():
                _mel.set_material_instance_scalar_parameter_value(_mic, _k, float(_v))
            for _k, _v in _g.get("vectors", {}).items():
                _mel.set_material_instance_vector_parameter_value(_mic, _k, _u.LinearColor(*[float(x) for x in _v]))
            _mel.update_material_instance(_mic)
            if not _eal.save_asset(_path, only_if_is_dirty=False):
                raise RuntimeError("save_asset returned False: " + _path)
            _c = _eal.load_asset(_path)
            _rb = {"parent": _p(_c.get_editor_property("parent")), "scalars": {}, "vectors": {}}
            _ok = _rb["parent"] == _pp
            for _k, _v in _g.get("scalars", {}).items():
                _r = _mel.get_material_instance_scalar_parameter_value(_c, _k)
                _rb["scalars"][_k] = _r
                _ok = _ok and abs(_r - float(_v)) <= 1e-5
            for _k, _v in _g.get("vectors", {}).items():
                _r = _mel.get_material_instance_vector_parameter_value(_c, _k)
                _rb["vectors"][_k] = [_r.r, _r.g, _r.b, _r.a]
                _ok = _ok and all(abs(a - float(b)) <= 1e-5 for a, b in zip(_rb["vectors"][_k], _v))
            # the textures must be the PARENT's (inherited, not overridden)
            _tx = _mel.get_material_instance_texture_parameter_value(_c, "ALBEDO")
            _tp = _mel.get_material_instance_texture_parameter_value(_par, "ALBEDO")
            _rb["albedo_inherited"] = _p(_tx) == _p(_tp) and _tx is not None
            _ok = _ok and _rb["albedo_inherited"]
            _out["mics"].append({"path": _path, "grade": _g["name"], "created": _made, "readback": _rb, "ok": bool(_ok)})
    _out["ok"] = bool(_out["mics"]) and all(x["ok"] for x in _out["mics"])
except Exception:
    import traceback as _tb
    _out["error"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out, default=str))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args(argv)
    rv = config()
    errs = validate(rv)
    if errs:
        print("REFUSE:\n  " + "\n  ".join(errs))
        return 2
    mis = sorted(set(tkp.ROOF_MATERIAL[n] for n in tkp.ROOFS if tkp.ROOF_MATERIAL.get(n)))
    if len(set(m.rsplit("/", 1)[1] for m in mis)) != len(mis):
        print("REFUSE: two roof MIs share an asset name -- grade_mic_path would collide in grade_dir: %s" % mis)
        return 2
    missing = [n for n in tkp.ROOFS if not tkp.ROOF_MATERIAL.get(n)]
    if missing:
        print("REFUSE: usable roofs with no recorded 'material' in recipes/town_kit.json: %s" % missing)
        return 2
    cfg = {"roofs": sorted(p for p, _ in tkp.ROOFS.values()), "grade_dir": rv["grade_dir"],
           "recorded_mi": dict((p, tkp.ROOF_MATERIAL[n]) for n, (p, _) in tkp.ROOFS.items()),
           # the MIC paths the manifest will reference, from the ONE naming rule (never re-derived in the payload)
           "mic_paths": dict((mi, dict((g["name"], grade_mic_path(rv["grade_dir"], mi, g["name"]))
                                       for g in rv["grades"] if g["name"] != "base"))
                             for mi in set(tkp.ROOF_MATERIAL[n] for n in tkp.ROOFS)),
           "grades": [dict((k, v) for k, v in g.items() if not k.startswith("_")) for g in rv["grades"]]}
    src = PAYLOAD.replace("__CFG__", repr(json.dumps(cfg)))
    if a.dry_run:
        print("dry run: %d roofs x %d non-base grades; payload %d bytes"
              % (len(cfg["roofs"]), sum(1 for g in cfg["grades"] if g["name"] != "base"), len(src)))
        return 0
    import ue_exec
    out_dir = os.path.join(bootstrap.REPO_ROOT, "_verify", "roof_variety")
    os.makedirs(out_dir, exist_ok=True)
    io.open(os.path.join(out_dir, "grades_payload.txt"), "w", encoding="utf-8").write(src)
    _code, out, raw = ue_exec.run(src, marker=MARKER, timeout=a.timeout, stage_name="roof_grades")
    if not isinstance(out, dict):
        print("FAIL (code %s): payload returned nothing -- COULD NOT LOOK\n%s" % (_code, (raw or "")[-1500:]))
        return 4
    io.open(os.path.join(out_dir, "grades_result.json"), "w", encoding="utf-8").write(json.dumps(out, indent=1))
    print(json.dumps({k: out.get(k) for k in ("ok", "error", "roof_mis")}, indent=1))
    print("mics: %d, all ok: %s" % (len(out.get("mics", [])), out.get("ok")))
    return 0 if out.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
