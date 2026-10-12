<#
lookdev_basecolor.ps1 -- THE CALIBRATED BASE-COLOUR INSTRUMENT for the look rig.

    powershell -File scripts/lookdev_basecolor.ps1 -Iter iter04_dispoff

Turns the buffer-visualisation overview on, shoots straight down on four
near-pure-layer patches of /Game/LookDevMtn, turns it off, and prints the
"Base Color" tile of each frame against the source albedo of that layer.

CALIBRATION (2026-09-30): Snow reads 0.839 linear against a source of 0.836
(ratio 1.00), so the tile is trusted as linear base colour. `viewmode unlit`
and ShowFlag.Lighting 0 + PostProcessing 0 are NOT instruments (LESSONS
2026-09-30d/f): the first does nothing, the second reads every layer too
bright by a different factor.

The patches are from textures/lookdev_weights.png (40 px block maxima).
THE STATIONS GO STALE WHEN THE RIG TERRAIN CHANGES -- re-derive them (41 px
uniform-filter maxima per layer) after any lookdev_terrain run.
#>
param([Parameter(Mandatory=$true)][string]$Iter)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$t0 = Get-Date
while (@(Get-Process ShaderCompileWorker* -ErrorAction SilentlyContinue).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 900) { Start-Sleep 5 }
Start-Sleep 5
$on = python scripts/ue_exec.py scripts/brief7_console_exec_payload.txt --timeout 25 --set 'CMDS=["ShowFlag.VisualizeBuffer 1"]' 2>&1 | Out-String
if ($on -notmatch '"ok":\s*true') { throw "could not enable buffer visualisation: $on" }
try {
    # RE-DERIVED 2026-10-01 from the t09 weightmap. The Scree and Grass stations
    # predated terrain t09: the old Grass station (49200, 49200) had become 0.92
    # Snow and read 0.771, the old Scree station 0.45 Rock / 0.42 Scree. Scree's
    # best 41 px block is only 0.68 Scree now, so it is reported and NOT judged.
    foreach ($s in @(@("Rock",-78800,-86800), @("Scree",-37500,77900), @("Snow",29200,-78800), @("Grass",82100,82800))) {
        # pwsh (7), not powershell (5.1): 5.1 strips the inner double quotes of a
        # native argument, and CMDS=["..."] arrives as invalid Python (2026-09-30).
        pwsh -NoProfile -File scripts/lookdev_shot.ps1 -Iter $Iter -Name ("bc_" + $s[0]) -X $s[1] -Y $s[2] -Pitch -89 -Yaw 0 -Eye 400 -Settle 5 | Out-Null
    }
} finally {
    python scripts/ue_exec.py scripts/brief7_console_exec_payload.txt --timeout 25 --set 'CMDS=["ShowFlag.VisualizeBuffer 0"]' 2>&1 | Out-Null
}
$py = @'
import sys, os, numpy as np
from PIL import Image
it = sys.argv[1]
# Rock: None since 2026-09-30 -- the layer is Rock026 * tint and 0.175 was gray_rocks.
# Grass: Free/_intake/megascans_grass/unpacked/WildGrass_C.png, linear mean 0.0385 (2026-10-01).
exp = {"Snow": 0.836, "Rock": None, "Scree": None, "Grass": 0.0385}
dec = lambda a: np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
n_ok = 0
for n, e in exp.items():
    p = "_verify/lookdev/%s/bc_%s.png" % (it, n)
    if not os.path.exists(p):
        print("%-6s NO FRAME" % n); continue
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255
    h, w = a.shape[:2]
    t = a[int(h * 0.03):int(h * 0.21), int(w * 0.02):int(w * 0.235)].reshape(-1, 3)
    lum = float(dec(t).mean(0) @ np.array([0.2126, 0.7152, 0.0722]))
    n_ok += 1
    if e is None:
        print("%-6s base colour linear %.3f   (not judged)" % (n, lum))
    else:
        print("%-6s base colour linear %.3f   source %.3f   ratio %.2fx   linear RGB %s" % (n, lum, e, lum / e, [round(float(v), 3) for v in dec(t).mean(0)]))
print("frames read: %d of %d" % (n_ok, len(exp)))
sys.exit(0 if n_ok == len(exp) else 1)
'@
$tmp = Join-Path $repo ("_verify\lookdev\" + $Iter + "\_measure.py")
Set-Content -Path $tmp -Value $py -Encoding utf8
python $tmp $Iter

