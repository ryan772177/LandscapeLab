<#
lookdev_blendcheck.ps1 -- IS THE LAYER COMPOSITE THE WEIGHTED SUM OF ITS LAYERS?

    pwsh -File scripts/lookdev_blendcheck.ps1 -Iter iter13_alphas

Shoots the buffer overview straight down on three BLENDED patches of
/Game/LookDevMtn (three layers at roughly a third each, no snow) and prints
the Base Color tile against two predictions made from textures/lookdev_weights.png:

    weighted sum   sum(m_i * c_i)                 -- what a partition must render
    raw lerp chain the same + prod(1 - m_i) * 1.0 -- the white background constant
                                                     leaking (LESSONS 2026-10-01)

The layer colours c_i are the in-engine pure-patch readings of
lookdev_basecolor.ps1 (Rock 0.204, Scree 0.220, Grass 0.047 linear), so a
texture's local variation is the instrument's noise floor: read the verdict as
"which prediction is it near", not to three figures. The two predictions differ
by ~0.28 here, more than the largest layer colour.

lookdev_basecolor.ps1 measures PURE patches, where prod(1 - m_i) is zero, and
so cannot see this defect -- that is why this script exists beside it.
#>
param([Parameter(Mandatory=$true)][string]$Iter)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$t0 = Get-Date
while (@(Get-Process ShaderCompileWorker* -ErrorAction SilentlyContinue).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 900) { Start-Sleep 5 }
Start-Sleep 5
$spots = @(@("blend_a",-20400,84800), @("blend_b",-73200,-17600), @("blend_c",-90500,66700))
$on = python scripts/ue_exec.py scripts/brief7_console_exec_payload.txt --timeout 25 --set 'CMDS=["ShowFlag.VisualizeBuffer 1"]' 2>&1 | Out-String
if ($on -notmatch '"ok":\s*true') { throw "could not enable buffer visualisation: $on" }
try {
    foreach ($s in $spots) {
        pwsh -NoProfile -File scripts/lookdev_shot.ps1 -Iter $Iter -Name ("bc_" + $s[0]) -X $s[1] -Y $s[2] -Pitch -89 -Yaw 0 -Eye 400 -Settle 5 | Out-Null
    }
} finally {
    python scripts/ue_exec.py scripts/brief7_console_exec_payload.txt --timeout 25 --set 'CMDS=["ShowFlag.VisualizeBuffer 0"]' 2>&1 | Out-Null
}
$py = @'
import sys, os, numpy as np
from PIL import Image
it = sys.argv[1]
LUM = np.array([0.2126, 0.7152, 0.0722])
COL = np.array([0.839, 0.204, 0.220, 0.14, 0.047])     # Snow Rock Scree ForestFloor Grass, linear lum in engine
dec = lambda a: np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
w = np.asarray(Image.open("textures/lookdev_weights.png")).astype(np.float64) / 255
n = w.shape[0]
org = -(n - 1) / 2 * 100.0
n_ok = 0
spots = [("blend_a", -20400, 84800), ("blend_b", -73200, -17600), ("blend_c", -90500, 66700)]
for name, x, y in spots:
    p = "_verify/lookdev/%s/bc_%s.png" % (it, name)
    if not os.path.exists(p):
        print("%-8s NO FRAME" % name); continue
    px, py = int(round((x - org) / 100)), int(round((y - org) / 100))
    t = w[py - 4:py + 5, px - 4:px + 5].reshape(-1, 4)
    m = np.concatenate([t, np.clip(1 - t.sum(1, keepdims=True), 0, 1)], axis=1)
    wsum = float((m * COL).sum(1).mean())
    leak = float(np.prod(1 - m, axis=1).mean())
    chain = float(((m * COL) * np.stack([np.prod(1 - m[:, :i], axis=1) for i in range(5)], axis=1)).sum(1).mean()) + leak
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255
    h, ww = a.shape[:2]
    tile = a[int(h * 0.03):int(h * 0.21), int(ww * 0.02):int(ww * 0.235)].reshape(-1, 3)
    lum = float(dec(tile).mean(0) @ LUM)
    near = "WEIGHTED SUM" if abs(lum - wsum) < abs(lum - chain) else "RAW LERP CHAIN (background leaks)"
    n_ok += 1
    print("%-8s base colour %.3f   weighted sum %.3f   raw chain %.3f (background share %.3f)   -> %s   texels %d"
          % (name, lum, wsum, chain, leak, near, len(m)))
print("frames read: %d of %d" % (n_ok, len(spots)))
sys.exit(0 if n_ok == len(spots) else 1)
'@
$tmp = Join-Path $repo ("_verify\lookdev\" + $Iter + "\_blendcheck.py")
Set-Content -Path $tmp -Value $py -Encoding utf8
python $tmp $Iter
