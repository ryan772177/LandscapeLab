<#
lookdev_iter.ps1 -- ONE look iteration on /Game/LookDevMtn: apply recipe edits,
validate, rebuild M_LookDev, wait for shaders, shoot the standard cameras.

    pwsh -File scripts/lookdev_iter.ps1 -Iter iter08_x -Set 'material.layers:Rock.tiling_m=9.0','material.displacement.per_layer.Rock=1.5'

-Set takes dotted paths into recipes/lookdev.json; `layers:Name` selects a
material layer by name; the value is parsed as JSON (falls back to a string).
With no -Set it rebuilds and shoots the recipe as it stands. Frames:
_verify/lookdev/<Iter>/{mtn_wide,mtn_face,ground_rock}.png, plus recipe_diff.txt
recording exactly what this iteration changed (rule 12: the change is written
beside the frame it produced).
#>
param(
    [Parameter(Mandatory=$true)][string]$Iter,
    [string[]]$Set = @(),
    [switch]$NoBuild,
    [switch]$ImportTextures
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$out = Join-Path $repo ("_verify\lookdev\" + $Iter)
New-Item -ItemType Directory -Force -Path $out | Out-Null

if ($Set.Count -gt 0) {
    $py = @'
import io, json, re, sys
p = "recipes/lookdev.json"
r = json.load(io.open(p, encoding="utf-8"))
log = []
for item in sys.argv[2:]:
    path, _, raw = item.partition("=")
    # REFUSE a path whose ROOT is not already a recipe key. Two -Set values
    # passed through `pwsh -File` arrive as ONE string ("a=1','b=2"), and
    # this setter used to create the junk key "'material" from it (hero
    # rounds 1 and 11, LESSONS 2026-10-03f). Pass several values as
    # separate -Set flags in one in-process call, or one value per run.
    if path.split(".")[0].split(":")[0] not in r or "'" in item:
        raise SystemExit("REFUSED -Set item %r: unknown recipe root or a "
                         "quote in it -- two values collapsed into one "
                         "string? Pass one value per -Set." % item)
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    node = r
    parts = path.split(".")
    for i, part in enumerate(parts):
        m = re.match(r"^(\w+):(\w+)$", part)
        last = i == len(parts) - 1
        if m:
            lst = node[m.group(1)]
            node = next(x for x in lst if x.get("name") == m.group(2))
            if last:
                raise SystemExit("path ends on a list selector: " + path)
            continue
        if last:
            old = node.get(part, "<absent>")
            if val == "__DELETE__":
                node.pop(part, None)
            else:
                node[part] = val
            log.append("%s: %r -> %r" % (path, old, val))
        else:
            node = node.setdefault(part, {})
json.dump(r, io.open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
io.open(sys.argv[1], "w", encoding="utf-8").write("\n".join(log) + "\n")
print("\n".join(log))
'@
    $tmp = Join-Path $out "_set.py"
    Set-Content -Path $tmp -Value $py -Encoding utf8
    python $tmp (Join-Path $out "recipe_diff.txt") @Set
    if ($LASTEXITCODE -ne 0) { throw "recipe edit failed" }
}
$v = python scripts/import_heightmap.py --recipe recipes/lookdev.json --offline 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "recipe INVALID:`n$v" }
if ($ImportTextures) {
    $i = python scripts/import_layer_textures.py --recipe recipes/lookdev.json --timeout 25 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "import_layer_textures failed:`n$($i.Substring([math]::Max(0,$i.Length-1500)))" }
}
if (-not $NoBuild) {
    $b = python scripts/make_landscape_material.py --recipe recipes/lookdev.json --assign --timeout 25 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "material build failed:`n$($b.Substring([math]::Max(0,$b.Length-1800)))" }
    # SAVE THE LANDSCAPE PROXIES after every build (LESSONS 2026-09-27 item 4, 2026-10-03i):
    # each ULandscapeComponent SAVES its own grass-type list, a game world never re-derives
    # it, so without this the editor shows the new grass and -game shows the OLD list.
    $s = python scripts/ue_exec.py scripts/brief7_save_landscape_proxies_payload.txt --set BATCH=32 --set APPLY=True 2>&1 | Out-String
    # Gate on dirty packages EXCLUDING the push tool's transient staging texture
    # (/Game/Debug/T_PushHeight_Source, dirty after any heightmap push, never saved).
    if ($LASTEXITCODE -ne 0 -or $s -notmatch '"dirty_after_excluding_push_staging": 0' -or $s -notmatch '"batch_failures": \[\]') {
        throw "landscape proxy save failed or left dirty packages:`n$($s.Substring([math]::Max(0,$s.Length-1500)))" }
    Start-Sleep 6
    $t0 = Get-Date
    while (@(Get-Process ShaderCompileWorker* -ErrorAction SilentlyContinue).Count -gt 0 -and ((Get-Date) - $t0).TotalSeconds -lt 900) { Start-Sleep 4 }
    Start-Sleep 6
}
pwsh -NoProfile -File scripts/lookdev_shot.ps1 -Iter $Iter -Name mtn_wide -X 0 -Y 60000 -Pitch 2 -Yaw 270 -Eye 3000 -Settle 8 | Out-Null
pwsh -NoProfile -File scripts/lookdev_shot.ps1 -Iter $Iter -Name mtn_face -X -20000 -Y 5000 -Pitch 6 -Yaw 262 -Eye 400 -Settle 6 | Out-Null
pwsh -NoProfile -File scripts/lookdev_shot.ps1 -Iter $Iter -Name ground_rock -X 20000 -Y -20000 -Pitch -25 -Yaw 250 -Eye 175 -Settle 6 | Out-Null
$n = @(Get-ChildItem $out -Filter *.png).Count
Write-Output "$Iter : $n frame(s) in $out"
