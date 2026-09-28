"""probe_texture_dims.py -- the THREE-GETTER texture dimension read-back.

Run as a COMMANDLET. It loads textures and reads them. It NEVER saves.

    UnrealEditor-Cmd.exe <uproject> -run=pythonscript
        -script="scripts/probe_texture_dims.py"
        -unattended -nosplash -nopause -abslog=<abs>

Targets come from `_verify/hlod/cap4096_2026-09-14/sixcell_targets.json`.

⭐ WHY THREE GETTERS AND NOT ONE. On 2026-09-14 a single read-back
(`blueprint_get_size_x`) reported 32x32 for a cell whose source was
1024x1024, then reported 1024 for the same object minutes later, and two
sessions were spent attributing a build behaviour that never happened
(LESSONS 2026-09-14). A texture has more than one size:

    imported_size                    the SOURCE dimensions. What the build
                                     wrote. Immutable, DDC-independent.
    blueprint_get_built_texture_size the PLATFORM DATA dimensions, after the
                                     DDC build and any LOD bias.
    blueprint_get_size_x/y           also platform data, and the accessor
                                     that misreported.

Reading all three IN THE SAME PAYLOAD is the point: a disagreement between
them is the finding, and no single one of them can report it. This is
non-negotiable 8 applied to an instrument that has already impeached itself.

⛔ THIS SCRIPT MUST NEVER SAVE. The 2026-09-14 incident that destroyed the
evidence was a payload whose save step ran even though its write had
raised. There is no save call here, and no mutation of any kind.
"""
import json
import os

import unreal

MARK = "__LANDSCAPELAB_TEXDIM__"
TARGETS = os.path.join(
    unreal.Paths.project_dir(), "..", "_verify", "hlod",
    "cap4096_2026-09-14", "sixcell_targets.json")


def read_one(path):
    row = {"path": path}
    tex = unreal.load_object(None, path)
    if tex is None:
        row["error"] = "load_object returned None"
        return row

    # Each getter is reported with its own raise. A getter that could not be
    # called must not be indistinguishable from one that returned a number.
    # ⛔ THE SNAKE_CASE NAME IS NOT ALWAYS THE NAME. `hlod_max_texture_size`
    # raises on ULandscapeSettings while the exact C++ `HLODMaxTextureSize`
    # reads fine (measured 2026-09-14, same session). Try both spellings and
    # record which one answered, rather than concluding "not exposed" from
    # one guess at the casing.
    for attempt in ("imported_size", "ImportedSize"):
        try:
            s = tex.get_editor_property(attempt)
            row["imported_size"] = [int(s.x), int(s.y)]
            row["imported_size_via"] = attempt
            break
        except Exception as exc:                        # noqa: BLE001
            row.setdefault("imported_size_errors", {})[attempt] = \
                f"{type(exc).__name__}: {exc}"

    try:
        b = tex.blueprint_get_built_texture_size()
        row["built_texture_size"] = [int(b.x), int(b.y)]
    except Exception as exc:                            # noqa: BLE001
        row["built_texture_size_error"] = f"{type(exc).__name__}: {exc}"

    try:
        row["blueprint_get_size_xy"] = [int(tex.blueprint_get_size_x()),
                                        int(tex.blueprint_get_size_y())]
    except Exception as exc:                            # noqa: BLE001
        row["blueprint_get_size_error"] = f"{type(exc).__name__}: {exc}"

    return row


def main():
    unreal.log(f"{MARK} BEGIN")
    with open(os.path.normpath(TARGETS), "r", encoding="utf-8") as fh:
        cells = json.load(fh)

    results = []
    for cell in cells:
        for path in cell["textures"]:
            row = read_one(path)
            row["cell"] = cell["label"]
            row["cap"] = cell["cap"]
            row["offdisk"] = cell["offdisk_dims"]
            results.append(row)
            unreal.log(f"{MARK} ROW {json.dumps(row)}")

    # Agreement is only meaningful with its sample count beside it (rule 13).
    read = [r for r in results
            if "imported_size" in r and "built_texture_size" in r]
    agree = [r for r in read if r["imported_size"] == r["built_texture_size"]]
    unreal.log(f"{MARK} SUMMARY textures={len(results)} "
               f"both_getters_read={len(read)} agree={len(agree)} "
               f"disagree={len(read) - len(agree)}")
    if not read:
        unreal.log_error(f"{MARK} REFUSING: 0 textures read both getters. "
                         f"Silence is not agreement.")
    unreal.log(f"{MARK} END")


main()
