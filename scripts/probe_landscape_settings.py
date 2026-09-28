"""probe_landscape_settings.py -- read ULandscapeSettings back FROM THE ENGINE.

Run as a COMMANDLET so the read-back lands in a commandlet log, with no
editor and no level loaded:

    UnrealEditor-Cmd.exe <uproject> -run=pythonscript
        -script="scripts/probe_landscape_settings.py"
        -unattended -nosplash -nopause -abslog=<abs path>

⭐ WHY A READ-BACK AT ALL. Standing rule 12: a declared value that is not
read back from the engine is prose. `HLODMaxTextureSize` is written in
`LandscapeLab/Config/DefaultEngine.ini` under
`[/Script/Landscape.LandscapeSettings]`; whether the engine LOADED it is a
separate question from whether it is typed in the file, and the ini is
silent about typos -- an unrecognised key is simply ignored.

`ULandscapeSettings` is `UCLASS(config = Engine, defaultconfig)`
(`LandscapeSettings.h:45`), so DefaultEngine.ini is the right file and
`[/Script/Landscape.LandscapeSettings]` the right section.

The value that governs the bake is read at
`LandscapeHLODBuilder.cpp:233-234` as
`GetDefault<ULandscapeSettings>()->GetHLODMaxTextureSize()` -- the CDO,
which is what this reads.
"""
import unreal

MARK = "__LANDSCAPELAB_LSSETTINGS__"


def main():
    unreal.log(f"{MARK} BEGIN")

    # ⛔ `unreal.LandscapeSettings` DOES NOT EXIST in the Python surface --
    # the class is UCLASS(..., MinimalAPI) (LandscapeSettings.h:45) and is not
    # exported. Measured 2026-09-14, this probe's first run.
    # The CDO is still a real UObject with a known path, so load it directly.
    cdo = None
    cls = getattr(unreal, "LandscapeSettings", None)
    if cls is not None:
        cdo = unreal.get_default_object(cls)
        unreal.log(f"{MARK} route=exported_class cdo={cdo}")
    else:
        unreal.log(f"{MARK} note unreal.LandscapeSettings is NOT exported "
                   f"(MinimalAPI); falling back to the CDO object path")
        for path in ("/Script/Landscape.Default__LandscapeSettings",
                     "/Script/Landscape.LandscapeSettings"):
            try:
                obj = unreal.find_object(None, path)
                if obj is None:
                    obj = unreal.load_object(None, path)
            except Exception as exc:                   # noqa: BLE001
                unreal.log_warning(f"{MARK} path {path} RAISED "
                                   f"{type(exc).__name__}: {exc}")
                continue
            unreal.log(f"{MARK} path {path} -> {obj!r}")
            if obj is not None and "Default__" in path:
                cdo = obj

    if cdo is None:
        unreal.log_error(f"{MARK} FAIL could not reach the ULandscapeSettings CDO")
        unreal.log(f"{MARK} END")
        return
    unreal.log(f"{MARK} cdo={cdo}")

    # Read the fields that decide the landscape HLOD texture size. Each is
    # reported with its raise, if any, rather than defaulted -- a property
    # that could not be read must not be indistinguishable from one that read 0.
    # Enumerate what the reflection layer actually exposes, so "not found" is
    # a measured absence rather than a guess about naming.
    try:
        props = [n for n in dir(cdo) if not n.startswith("_")]
        unreal.log(f"{MARK} dir(cdo) n={len(props)}")
        hits = [n for n in props if "hlod" in n.lower() or "texture" in n.lower()]
        unreal.log(f"{MARK} dir(cdo) hlod/texture names: {hits}")
    except Exception as exc:                           # noqa: BLE001
        unreal.log_warning(f"{MARK} dir RAISED {exc}")

    for prop in ("hlod_max_texture_size", "HLODMaxTextureSize",
                 "side_resolution_limit", "SideResolutionLimit"):
        try:
            unreal.log(f"{MARK} {prop} = {cdo.get_editor_property(prop)!r}")
        except Exception as exc:                       # noqa: BLE001
            unreal.log_warning(f"{MARK} {prop} RAISED {type(exc).__name__}: {exc}")

    # Where the engine thinks it read it from.
    try:
        unreal.log(f"{MARK} config_class={cls.__name__} "
                   f"section=/Script/Landscape.LandscapeSettings")
    except Exception as exc:                           # noqa: BLE001
        unreal.log_warning(f"{MARK} config info RAISED {exc}")

    unreal.log(f"{MARK} END")


main()
