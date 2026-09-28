"""Emit a fresh, minimal UE 5.8 project for a forge run.

The dev LandscapeLab project carries Fab content, MetaHuman plugins and
20+ GB of kit; a forge user gets NONE of that. This emits a clean project
whose Content/ starts empty (the proven scripts create everything) and
whose only C++ is a TRIMMED copy of the LandscapeLabEditor plugin: the
six landscape UFUNCTIONs survive, the MetaHuman DNA and Groom categories
— and their RigLogic/DNACalib/HairStrandsCore dependencies — are cut.

The trim is textual, against markers verified in the source (the DNA
section banner in both LandscapeLabTools.h/.cpp), and is proven by TWO
gates: a symbol self-check here (no DNA/Groom identifier may survive)
and the UBT compile the caller runs afterwards. The project name stays
"LandscapeLab" so bootstrap.py's UE_PROJECT_ROOT join and every payload's
class references resolve untouched.

Usage:
    python -m forge_tool.emit_project --dest <dir> [--compile]
Exit: 0 emitted (and compiled if asked), 2 refusal, 3 compile failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from engine_paths import resolve_engine_root  # noqa: E402

DEV_PROJECT = os.path.join(REPO, "LandscapeLab")
PLUGIN_REL = os.path.join("Plugins", "LandscapeLabEditor")
SRC_REL = os.path.join(PLUGIN_REL, "Source", "LandscapeLabEditor")

DNA_BANNER = "MetaHuman DNA"
# include lines to drop from the trimmed .cpp (everything the cut
# sections needed and the landscape sections do not)
_DROP_INCLUDE = re.compile(
    r'^#include ".*(DNACalib|DNACommon|DNAReader|DNAToSkelMeshMap|DNAUtils'
    r'|SkelMeshDNAUtils|Groom|HairStrands|Engine/SkeletalMesh)')
_DROP_COMMENT = re.compile(r"^// --- MetaHuman DNA|^// remembered;")
# symbols that must NOT survive the trim (self-check direction)
_FORBIDDEN = re.compile(
    r"IDNAReader|FDNACalib|LoadDNAFromFile|UGroomBindingAsset::Build"
    r"|ReadDNAJoints|ReadDNAMeshes|WriteDNA|ApplyDNAToSkeletalMesh"
    r"|BuildGroom|BuildFreshGroomBinding|UGroomAsset|FHairStrandsCore"
    r"|LandscapeLab\|DNA|LandscapeLab\|Groom")

UPLUGIN = {
    "FileVersion": 3,
    "Version": 1,
    "VersionName": "0.1.0-forge",
    "FriendlyName": "LandscapeLab Editor Tools (forge trim)",
    "Description": "Exposes the landscape editor operations UE 5.8 "
                   "declares LANDSCAPE_API but never marks UFUNCTION. "
                   "Trimmed for the forge: MetaHuman DNA and Groom "
                   "categories removed with their plugin dependencies.",
    "Category": "Editor",
    "CreatedBy": "LandscapeLab",
    "CanContainContent": False,
    "IsBetaVersion": False,
    "IsExperimentalVersion": False,
    "Installed": False,
    "EnabledByDefault": True,
    "Modules": [{"Name": "LandscapeLabEditor", "Type": "Editor",
                 "LoadingPhase": "Default"}],
}

UPROJECT = {
    "FileVersion": 3,
    "EngineAssociation": "5.8",
    "Category": "",
    "Description": "Emitted by the forge; Content is created by the "
                   "pipeline scripts, not copied.",
    "Plugins": [
        {"Name": "PythonScriptPlugin", "Enabled": True},
        {"Name": "LandscapePatch", "Enabled": True},
    ],
}

BUILD_CS = '''// Emitted by forge_tool/emit_project.py — the forge trim of
// LandscapeLabEditor.Build.cs: landscape dependencies only. The DNA and
// Groom module dependencies of the dev plugin are deliberately absent,
// matching the trimmed sources beside this file.

using UnrealBuildTool;

public class LandscapeLabEditor : ModuleRules
{
\tpublic LandscapeLabEditor(ReadOnlyTargetRules Target) : base(Target)
\t{
\t\tPCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

\t\tPublicDependencyModuleNames.AddRange(new string[]
\t\t{
\t\t\t"Core",
\t\t\t"CoreUObject",
\t\t\t"Engine",
\t\t});

\t\tPrivateDependencyModuleNames.AddRange(new string[]
\t\t{
\t\t\t"Landscape",
\t\t\t"LandscapeEditor",
\t\t\t"UnrealEd",
\t\t\t"Slate",
\t\t\t"SlateCore",
\t\t});
\t}
}
'''


class Refuse(Exception):
    pass


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise Refuse(
            "emission source missing: %s. The emitter reads the DEV "
            "project's sources — in a packaged dist the project skeleton "
            "is pre-emitted at package time, and `init` only compiles."
            % path)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _trim_at_banner(text, close_class):
    """Cut everything from the DNA section banner onward. The banner is a
    '// ====' line whose NEXT line names MetaHuman DNA; refuse if the
    marker is not found (a moved marker must fail loudly, not ship the
    whole file)."""
    lines = text.splitlines(keepends=True)
    cut = None
    for i in range(len(lines) - 1):
        if lines[i].lstrip().startswith("// ====") and \
                DNA_BANNER in lines[i + 1]:
            cut = i
            break
    if cut is None:
        raise Refuse("DNA section banner not found — the plugin source "
                     "moved; update emit_project's markers")
    head = "".join(lines[:cut]).rstrip() + "\n"
    if close_class:
        head += "};\n"
    return head


def _trim_header(text):
    return _trim_at_banner(text, close_class=True)


def _trim_cpp(text):
    kept = []
    for ln in text.splitlines(keepends=True):
        if _DROP_INCLUDE.match(ln) or _DROP_COMMENT.match(ln):
            continue
        kept.append(ln)
    return _trim_at_banner("".join(kept), close_class=False)


def emit(dest_root):
    """Create <dest_root>/LandscapeLab. Refuses if it already exists,
    if dest_root is relative (cwd is resettable — an ambiguous target is
    a wrong target), or if it lands inside the dev project."""
    if not os.path.isabs(dest_root):
        raise Refuse("dest must be an absolute path, got %r" % dest_root)
    proj = os.path.join(os.path.abspath(dest_root), "LandscapeLab")
    dev = os.path.abspath(DEV_PROJECT)
    try:
        nested = os.path.commonpath(
            [os.path.abspath(dest_root), dev]) == dev
    except ValueError:  # different drives cannot nest
        nested = False
    if nested:
        raise Refuse("dest is inside the dev project: %s" % dest_root)
    if os.path.exists(proj):
        raise Refuse("destination already exists: %s (the emitter never "
                     "overwrites a project)" % proj)
    # UBT appends ~150 chars of Intermediate/... to the project path and
    # fails opaquely past MAX_PATH (measured 2026-09-02: a deep dest died
    # in 0.7 s printing only "[276 characters] <path>" lines).
    if len(proj) > 110:
        raise Refuse("project path is %d chars; UBT intermediate paths "
                     "would exceed Windows MAX_PATH. Use a shorter dest "
                     "(<= 110 chars for the project dir)." % len(proj))
    # --- trimmed plugin sources (trim BEFORE any write, so a marker
    # failure emits nothing) -------------------------------------------
    h_src = _read(os.path.join(DEV_PROJECT, SRC_REL, "Public",
                               "LandscapeLabTools.h"))
    cpp_src = _read(os.path.join(DEV_PROJECT, SRC_REL, "Private",
                                 "LandscapeLabTools.cpp"))
    module_cpp = _read(os.path.join(DEV_PROJECT, SRC_REL, "Private",
                                    "LandscapeLabEditorModule.cpp"))
    h_out = _trim_header(h_src)
    cpp_out = _trim_cpp(cpp_src)
    for name, text in (("LandscapeLabTools.h", h_out),
                       ("LandscapeLabTools.cpp", cpp_out)):
        m = _FORBIDDEN.search(text)
        if m:
            raise Refuse("trim self-check: %r survived in trimmed %s"
                         % (m.group(0), name))

    # --- config transforms --------------------------------------------
    # Renderer/perf values copy VERBATIM, including
    # ManualScreenPercentage=70: measured 2026-09-02, the dev per-user
    # layer does NOT shadow it, so every calibrated dev render was made
    # under it — dropping it here would silently change the instrument
    # the acceptance numbers were measured on. Only project-IDENTITY
    # keys are transformed.
    cfg_dir = os.path.join(DEV_PROJECT, "Config")
    engine_ini = _read(os.path.join(cfg_dir, "DefaultEngine.ini"))
    engine_ini = re.sub(r"(?m)^(GameDefaultMap|EditorStartupMap)=.*$",
                        r"\1=/Engine/Maps/Entry", engine_ini)
    # identity/dev-only keys: the game mode class lives in a plugin the
    # emitted project never receives; redirects and the Android token are
    # dev-project identity.
    engine_ini = re.sub(
        r"(?m)^(GlobalDefaultGameMode=|\+ActiveGameNameRedirects="
        r"|SecurityToken=).*\n", "", engine_ini)
    game_ini = re.sub(r"(?m)^ProjectID=.*\n", "",
                      _read(os.path.join(cfg_dir, "DefaultGame.ini")))
    # dead character section: exports dev MetaHuman asset paths that do
    # not exist in the emitted project
    game_ini = re.sub(
        r"(?ms)^\[/Script/LandscapeLabGameplay\.LandscapeLabCharacter\]"
        r".*?(?=^\[|\Z)", "", game_ini)

    # --- write everything ---------------------------------------------
    _write(os.path.join(proj, "LandscapeLab.uproject"),
           json.dumps(UPROJECT, indent=1) + "\n")
    for tgt in ("LandscapeLab.Target.cs", "LandscapeLabEditor.Target.cs"):
        _write(os.path.join(proj, "Source", tgt),
               _read(os.path.join(DEV_PROJECT, "Source", tgt)))
    _write(os.path.join(proj, "Config", "DefaultEngine.ini"), engine_ini)
    _write(os.path.join(proj, "Config", "DefaultGame.ini"), game_ini)
    for ini in ("DefaultEditor.ini", "DefaultEditorSettings.ini",
                "DefaultEditorPerProjectUserSettings.ini",
                "DefaultInput.ini"):
        _write(os.path.join(proj, "Config", ini),
               _read(os.path.join(cfg_dir, ini)))
    plug = os.path.join(proj, PLUGIN_REL)
    _write(os.path.join(plug, "LandscapeLabEditor.uplugin"),
           json.dumps(UPLUGIN, indent=1) + "\n")
    src = os.path.join(proj, SRC_REL)
    _write(os.path.join(src, "LandscapeLabEditor.Build.cs"), BUILD_CS)
    _write(os.path.join(src, "Public", "LandscapeLabTools.h"), h_out)
    _write(os.path.join(src, "Private", "LandscapeLabTools.cpp"), cpp_out)
    _write(os.path.join(src, "Private", "LandscapeLabEditorModule.cpp"),
           module_cpp)
    os.makedirs(os.path.join(proj, "Content"), exist_ok=True)
    return proj


def compile_plugin(proj):
    """UBT compile of the trimmed plugin; the real proof of the trim.
    Returns the subprocess returncode (0 = built)."""
    engine = resolve_engine_root()
    bat = os.path.join(engine, "Engine", "Build", "BatchFiles", "Build.bat")
    uproject = os.path.join(proj, "LandscapeLab.uproject")
    cmd = [bat, "LandscapeLabEditor", "Win64", "Development",
           "-Project=%s" % uproject, "-WaitMutex"]
    print("compiling: %s" % " ".join(cmd))
    try:
        # 30 min ceiling: Build.bat has two unbounded prompt-free waits
        # (mutex spin, first-run UBT self-build); a hang must land as a
        # refusal, not a stuck process (audit F3).
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=1800)
    except subprocess.TimeoutExpired:
        print("REFUSE: compile exceeded 30 min ceiling")
        return 124
    tail = (r.stdout or "").splitlines()[-25:]
    print("\n".join(tail))
    if r.returncode != 0 and r.stderr:
        print(r.stderr[-2000:])
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True,
                    help="directory that will CONTAIN LandscapeLab/")
    ap.add_argument("--compile", action="store_true")
    a = ap.parse_args(argv)
    try:
        proj = emit(a.dest)
    except Refuse as e:
        print("REFUSE: %s" % e)
        return 2
    print("emitted: %s" % proj)
    if a.compile:
        rc = compile_plugin(proj)
        if rc != 0:
            print("COMPILE FAILED (exit %d)" % rc)
            return 3
        print("plugin compiled clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
