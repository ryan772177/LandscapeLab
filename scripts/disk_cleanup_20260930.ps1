# disk_cleanup_20260930.ps1 -- operator-run deletion of regenerable caches after
# the Brief 7 P4 HLOD rebuild left 2.5 GB free (2026-09-30 04:30).
# Standing rule 2 forbids recursive/forced deletes from the agent, so this runs
# from the operator's prompt:   ! powershell -File scripts/disk_cleanup_20260930.ps1
#
# INSIDE THE REPO (always): LandscapeLab/DerivedDataCache (14.5 GB, regenerated
# on load; the shared C:\UnrealDDC still holds the derived data), Intermediate
# (0.7 GB), Saved/Profiling, Saved/Autosaves, Saved/Logs older than today (1.9 GB).
#
# OUTSIDE THE REPO (operator's call, off by default -- standing rule 1):
#   -IncludeSharedDDC   deletes C:\UnrealDDC (58 GB; every derived asset rebuilds
#                       on next load -- the HLOD commandlet rebuilt ~27 GB of it
#                       this week; expect a slow first editor launch).
# NOT touched by any flag: C:\pagefile.sys (206 GB, system-managed; it grew with
# the 25 GB editor sessions). A reboot lets Windows shrink it; a fixed size is
# set under System > Advanced > Performance > Virtual memory. Both yours.
# Refuses if an editor or commandlet is running.
param([switch]$IncludeSharedDDC)
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Get-Process UnrealEditor*,UnrealEditor-Cmd* -ErrorAction SilentlyContinue) { Write-Output "REFUSE: editor or commandlet running"; exit 1 }
$before = (Get-PSDrive C).Free/1GB
$targets = @("LandscapeLab\DerivedDataCache", "LandscapeLab\Intermediate",
             "LandscapeLab\Saved\Profiling", "LandscapeLab\Saved\Autosaves",
             "LandscapeLab\Saved\ShaderDebugInfo")
foreach ($t in $targets) {
    if (Test-Path $t) {
        $gb = [math]::Round((Get-ChildItem $t -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB, 2)
        Remove-Item $t -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue
        Write-Output "deleted $t ($gb GB)"
    }
}
$logs = Get-ChildItem "LandscapeLab\Saved\Logs" -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).Date }
$lgb = [math]::Round(($logs | Measure-Object Length -Sum).Sum/1GB, 2)
$logs | Remove-Item -Force -Confirm:$false -ErrorAction SilentlyContinue
Write-Output "deleted $($logs.Count) log files older than today ($lgb GB)"
if ($IncludeSharedDDC -and (Test-Path "C:\UnrealDDC")) {
    $gb = [math]::Round((Get-ChildItem "C:\UnrealDDC" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB, 2)
    Remove-Item "C:\UnrealDDC" -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue
    Write-Output "deleted C:\UnrealDDC ($gb GB) -- OUTSIDE the repo, by your flag"
}
$after = (Get-PSDrive C).Free/1GB
Write-Output ("free: {0:N1} GB -> {1:N1} GB" -f $before, $after)
Write-Output ("pagefile.sys: {0:N0} GB (not touched; reboot or set a fixed size)" -f ((Get-Item C:\pagefile.sys -Force).Length/1GB))
