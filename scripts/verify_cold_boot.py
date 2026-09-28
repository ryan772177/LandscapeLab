"""COLD-BOOT VERIFICATION. Read-only.

Two claims that only a fresh process can settle, and they are different
claims from anything checked so far:

1. THE WORLD LOADS FROM THE SAVED BYTES. `verify_saved_nanite.py` proved
   the .uasset files CONTAIN the Nanite state. A name-table token says the
   data was serialised; it does not say a cold open reconstructs a working
   Nanite landscape. This process never saw the in-memory state.

2. THE CONFIG DELIVERS. Every quality cvar was verified as live RENDER
   STATE on the old process, and then pinned in DefaultEngine.ini. An ini
   records an OVERRIDE, not the state in effect (NN17) — three instances
   of that trap are already recorded in this project, one of them being
   `[SystemSettings]` setting an sg.* VALUE without running the GROUP.
   So this reads the DOWNSTREAM cvars the group expands to, not sg.*.
"""
import json, os, sys
sys.path.insert(0, r"C:\Users\Admin\UE5LandscapePipeline\scripts")
import bootstrap, verify_landscape

MARKER = "__LL_COLD__"

PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {"level": None, "total": 0, "enabled": 0, "with_component": 0,
        "with_mesh": 0, "unreadable": 0, "cvars": {}, "material": {},
        "error": None}
try:
    _sl = _unreal.SystemLibrary
    _les = _unreal.get_editor_subsystem(_unreal.LevelEditorSubsystem)
    try:
        _out["level"] = str(_les.get_current_level().get_outer().get_path_name())
    except Exception:
        _w = _unreal.EditorLevelLibrary.get_editor_world()
        _out["level"] = str(_w.get_path_name()) if _w else None

    _eas = _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _px = [_a for _a in _eas.get_all_level_actors()
           if isinstance(_a, _unreal.LandscapeProxy)]
    _out["total"] = len(_px)
    for _a in _px:
        try:
            if bool(_a.get_editor_property("enable_nanite")):
                _out["enabled"] += 1
        except Exception:
            _out["unreadable"] += 1
            continue
        try:
            _nc = list(_a.get_components_by_class(
                _unreal.LandscapeNaniteComponent))
        except Exception:
            _out["unreadable"] += 1
            continue
        if _nc:
            _out["with_component"] += 1
        for _c in _nc:
            try:
                if _c.get_editor_property("static_mesh") is not None:
                    _out["with_mesh"] += 1
                    break
            except Exception:
                pass

    for _n in ["r.Nanite.MaxPixelsPerEdge",
               "r.Nanite.Tessellation",
               "r.DynamicGlobalIlluminationMethod",
               "r.ReflectionMethod",
               "r.Lumen.HardwareRayTracing",
               "r.Lumen.HardwareRayTracing.LightingMode",
               "r.Shadow.Virtual.ResolutionLodBiasDirectional",
               "r.ScreenPercentage",
               "sg.GlobalIlluminationQuality",
               "sg.ReflectionQuality",
               "r.Lumen.DiffuseIndirect.Allow",
               "r.Lumen.FinalGatherMethod",
               "r.LumenScene.SurfaceCache.AtlasSize",
               "r.Lumen.Reflections.Allow",
               "r.Lumen.Reflections.DownsampleFactor",
               "r.SSR.Quality",
               "grass.DensityScale",
               "foliage.DensityScale",
               "r.ViewDistanceScale"]:
        try:
            _out["cvars"][_n] = _sl.get_console_variable_float_value(_n)
        except Exception:
            _out["cvars"][_n] = "ERR"

    _m = _unreal.EditorAssetLibrary.load_asset(
        "/Game/Materials/M_AutoLandscape")
    if _m is not None:
        _ds = _m.get_editor_property("displacement_scaling")
        _out["material"] = {
            "use_material_attributes": bool(
                _m.get_editor_property("use_material_attributes")),
            "enable_tessellation": bool(
                _m.get_editor_property("enable_tessellation")),
            "magnitude": float(_ds.get_editor_property("magnitude")),
            "center": float(_ds.get_editor_property("center")),
        }
except Exception as _e:
    _out["error"] = type(_e).__name__ + ": " + str(_e)
print("__LL_COLD__" + _json.dumps(_out))
'''

def _target_profile_cvars():
    """The target profile's cvars, read from benchmark.json.

    ⛔ WHY THIS IS NOT A LITERAL HERE. Until 2026-09-14 this table
    carried `r.Shadow.Virtual.ResolutionLodBiasDirectional: -0.5` while
    the target profile set **-1.5**. Two values for one lever, in two
    files, with nothing comparing them -- AUDIT P1-6, and the live
    engine default is -0.5, so the stale copy looked perfectly
    plausible.

    A gate that carries its own copy of the value it is checking is not
    checking anything: it is comparing the engine against a number that
    can drift from the profile silently. The profile is the source; this
    reads it. Two lists that must agree are one list badly stored
    (NN24).

    Fails CLOSED: if benchmark.json cannot be read or the key is absent,
    the caller is told and the entry is left out of WANT rather than
    defaulted to a guess -- a missing expectation is visible, a wrong
    one is not (NN6).
    """
    path = os.path.join(bootstrap.REPO_ROOT, "research", "brief",
                        "brief1_distance_as_angle", "brief1",
                        "benchmark.json")
    try:
        with open(path, encoding="utf-8") as fh:
            bm = json.load(fh)
    except Exception as exc:
        print("WARN: could not read the target profile from %s (%s: %s).\n"
              "      Profile-sourced expectations are OMITTED from WANT "
              "rather than guessed." % (path, type(exc).__name__, exc))
        return {}
    prof = ((bm.get("profiles") or {}).get("target")
            or (bm.get("profile") or {}).get("target") or {})
    cvars = prof.get("cvars") or prof
    out = {}
    for name in ("r.Shadow.Virtual.ResolutionLodBiasDirectional",):
        if isinstance(cvars, dict) and name in cvars:
            try:
                out[name] = float(cvars[name])
            except (TypeError, ValueError):
                print("WARN: %s in benchmark.json is not a number: %r"
                      % (name, cvars[name]))
        else:
            print("WARN: %s is not in benchmark.json's target profile; "
                  "it is OMITTED from WANT rather than defaulted." % name)
    return out


WANT = {
    "r.Nanite.MaxPixelsPerEdge": 1.0,
    "r.Nanite.Tessellation": 1.0,
    "r.DynamicGlobalIlluminationMethod": 1.0,
    "r.ReflectionMethod": 1.0,
    "r.Lumen.HardwareRayTracing": 1.0,
    "r.Lumen.HardwareRayTracing.LightingMode": 1.0,
    # r.Shadow.Virtual.ResolutionLodBiasDirectional is NOT listed here.
    # It comes from the target profile below -- see _target_profile_cvars.
    "r.ScreenPercentage": 100.0,
    "sg.GlobalIlluminationQuality": 3.0,
    "sg.ReflectionQuality": 3.0,
    "r.Lumen.DiffuseIndirect.Allow": 1.0,
    "r.Lumen.FinalGatherMethod": 1.0,
    "r.LumenScene.SurfaceCache.AtlasSize": 4096.0,
    "r.Lumen.Reflections.Allow": 1.0,
    "r.Lumen.Reflections.DownsampleFactor": 1.0,
    "r.SSR.Quality": 3.0,
    "grass.DensityScale": 1.0,
    "foliage.DensityScale": 1.0,
    "r.ViewDistanceScale": 1.0,
}
# Profile-sourced expectations, merged in at import. Anything this adds
# is a value the TARGET PROFILE declares, so the gate and the render can
# never disagree about it.
WANT.update(_target_profile_cvars())

remote_exec = bootstrap._load_remote_execution()
remote = remote_exec.RemoteExecution()
remote.start()
try:
    node, reason = verify_landscape._select_verified_node(
        remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT), 30)
    if node is None:
        print("REFUSE (rule 7):", reason); sys.exit(3)
    remote.open_command_connection(node["node_id"])
    r = remote.run_command(PAYLOAD, unattended=True,
                           exec_mode=remote_exec.MODE_EXEC_FILE)
    text = bootstrap._collect_output(r)
    i = text.find(MARKER)
    if i < 0:
        print("NO MARKER — could not look:"); print(text[:2000]); sys.exit(1)
    d, _ = json.JSONDecoder().raw_decode(text[i + len(MARKER):].lstrip())
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"]); sys.exit(1)

    print("level                :", d["level"])
    print()
    print("=== 1. DOES THE WORLD LOAD FROM THE SAVED BYTES? ===")
    print("  landscape actors     : %d" % d["total"])
    print("  enable_nanite        : %d" % d["enabled"])
    print("  with Nanite component: %d" % d["with_component"])
    print("  with a BUILT mesh    : %d" % d["with_mesh"])
    print("  unreadable           : %d" % d["unreadable"])
    print()
    print("=== 2. DOES THE PINNED CONFIG DELIVER ON A COLD BOOT? ===")
    bad = []
    for k, want in WANT.items():
        got = d["cvars"].get(k)
        ok = isinstance(got, float) and abs(got - want) < 1e-6
        if not ok:
            bad.append((k, got, want))
        print("  %-48s %-10s want %-8s %s"
              % (k, got, want, "ok" if ok else "MISMATCH"))
    print()
    print("=== 3. THE MATERIAL, RELOADED FROM DISK ===")
    for k, v in (d.get("material") or {}).items():
        print("  %-28s %s" % (k, v))
    print()
    if bad:
        print("CONFIG MISMATCHES: %d" % len(bad))
        for k, got, want in bad:
            print("   %s  got %r want %r" % (k, got, want))
    else:
        print("CONFIG: every pinned value is in effect on a cold boot.")
finally:
    try:
        remote.close_command_connection()
    except Exception:
        pass
    remote.stop()
