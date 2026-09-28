"""brief5_r1_probe_autoname.py -- READ-ONLY. Find the reflected Python name for
UStaticMesh::bAutoComputeLODScreenSize (StaticMesh.h:719-722) so R1 can read it
back cold, and confirm the two meshes are currently at their reverted (pre-hold)
ScreenSizes. Enumerates dir(mesh) for auto/compute/screen/lod attributes and
tries get_editor_property on each candidate. Changes nothing."""
import json as _json
import unreal as _u

assert "LandscapeLab" in _u.Paths.project_dir(), "wrong project (rule 7)"
PATHS = {"ConiferPine": "/Game/KiteDemo/Environments/Trees/ScotsPineTall_01/ScotsPineTall_01",
         "SpruceSub": "/Game/PN_interactiveSpruceForest/Meshes/half/high/spruce_half_01"}
out = {"ok": False, "meshes": {}}
try:
    ss = _u.get_editor_subsystem(_u.StaticMeshEditorSubsystem)
    eal = _u.EditorAssetLibrary
    for sp, p in PATHS.items():
        m = eal.load_asset(p)
        attrs = [n for n in dir(m) if any(k in n.lower()
                 for k in ("auto", "compute", "screen"))]
        vals = {}
        for n in attrs:
            try:
                vals[n] = repr(m.get_editor_property(n))
            except Exception as e:
                vals[n] = "get_editor_property ERR: %s" % type(e).__name__
        # also try the plain-attribute read (reflected props are attributes)
        attr_reads = {}
        for n in attrs:
            try:
                attr_reads[n] = repr(getattr(m, n))
            except Exception as e:
                attr_reads[n] = "getattr ERR: %s" % type(e).__name__
        out["meshes"][sp] = {
            "candidate_attrs": attrs,
            "get_editor_property": vals,
            "getattr": attr_reads,
            "screen_sizes_now": [round(float(x), 6)
                                 for x in ss.get_lod_screen_sizes(m)]}
    out["ok"] = True
except Exception as e:
    import traceback
    out["error"] = "%s: %s" % (type(e).__name__, e)
    out["traceback"] = traceback.format_exc()[-1000:]
print("__LL__" + _json.dumps(out, default=str))
