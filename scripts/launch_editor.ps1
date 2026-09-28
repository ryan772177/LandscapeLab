<#
launch_editor.ps1 -- start the editor with a working directory inside the repo.

    powershell -File scripts/launch_editor.ps1 [-Map /Game/Alpine8K]

WHY THIS EXISTS, AND IT IS STANDING RULE 1.
Every capture tool in this project builds a RELATIVE output path
(`_verify/<date>/<name>.png`) and the editor resolves it against ITS OWN
working directory. Launched with `Start-Process` and no `-WorkingDirectory`,
that directory is wherever the caller happened to be -- and on 2026-08-21 it
was `C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64`. Ten frames,
including a whole presence-gate set, were written INTO THE ENGINE INSTALL,
outside both roots.

The tools caught it, which is the part that worked: `world_shot.py` refused
with "the payload reported a frame that is not on disk" and `groom_presence.py`
with "frames never landed on disk". Neither said WHERE they had gone, because
neither could know -- the write succeeded from the editor's point of view.

⚠ AND `-WorkingDirectory` DOES NOT FIX THAT. It is passed below and it is
INERT for this purpose: Unreal sets its own working directory to the engine
binaries folder during startup, so whatever the launcher asked for is gone by
the time a payload resolves a path. Measured 2026-08-21 -- the editor was
relaunched through this script and the very next render landed in the engine
folder again.

**THE FIX IS AT THE CALL SITE: PASS AN ABSOLUTE `--out-dir`.** Verified in the
same session; the identical command with an absolute path wrote into the repo.

This script is kept for its OTHER job, which is real -- see the restore-data
handling below -- and the flag is left in place so nobody re-adds it thinking
it was overlooked. It is not a defence and must not be read as one.

ALSO HANDLED: `Saved/Autosaves/PackageRestoreData.json` is moved aside before
launching. If it is present the editor raises a Restore modal on start, and a
modal blocks the game thread -- which is the only channel that could report
that it is blocked.

⭐ OFFSCREEN BY DEFAULT, ADDED 2026-09-13. On 2026-09-12 this editor died
with `DXGI_ERROR_DEVICE_REMOVED` at `D3D12Viewport.cpp:537`, 36 s after
load, in the VIEWPORT PRESENT path -- and I had already misdiagnosed the
process as "wedged idle" from outside before the operator said "got a gpu
crash error". Relaunching with `-RenderOffScreen` removed the crash site
and every capture since has been clean.

That fix was written up in LESSONS and in R-EDITOR-CLOSE and NEVER REACHED
THIS SCRIPT, so every launch through it kept the crash site. A lesson that
exists and does not fire is a defect in the lesson (operating loop (e)),
and the landing site for this one is the launcher, not the prose.

⛔ IT COSTS A GATE INSTRUMENT, so this is not free: `CloseMainWindow()`
returns False on an offscreen editor because there is NO main window.
Plan to end on R-EDITOR-CLOSE's kill path and prove safety the other three
ways (clean census, quiet RSS, empty PackageRestoreData). Do NOT read a
False return as an unresponsive editor. Pass `-Windowed` when a human
needs to look at the viewport.
#>
param(
    [string]$Map = "/Game/Alpine8K",
    [string]$Engine = "C:\Program Files\Epic Games\UE_5.8",
    [switch]$Windowed
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$uproject = Join-Path $repo "LandscapeLab\LandscapeLab.uproject"
$exe = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor.exe"

if (-not (Test-Path $uproject)) { throw "no uproject at $uproject" }
if (-not (Test-Path $exe))      { throw "no editor at $exe" }

$restore = Join-Path $repo "LandscapeLab\Saved\Autosaves\PackageRestoreData.json"
if (Test-Path $restore) {
    $dest = Join-Path $repo ("_trash\autosaves_launch_" + (Get-Date -Format "yyyyMMddHHmmss"))
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Move-Item $restore $dest
    Write-Output "moved PackageRestoreData.json -> $dest (no Restore modal)"
}

$extra = @()
if (-not $Windowed) { $extra += "-RenderOffScreen" }

Write-Output "working directory : $repo"
Write-Output "map               : $Map"
Write-Output ("mode              : " + $(if ($Windowed) { "WINDOWED -- the viewport Present path that took the GPU on 2026-09-12 is live" } else { "OFFSCREEN (no main window; end on R-EDITOR-CLOSE's kill path)" }))
Start-Process -FilePath $exe -WorkingDirectory $repo `
    -ArgumentList (@($uproject, $Map, "-log") + $extra)
Write-Output "launched. Confirm with scripts/bootstrap.py before any remote work."
