<#
    migrate_to_drive.ps1 — copy the migration set to an external drive,
    verify it by hash, and write a manifest.

        pwsh scripts\migrate_to_drive.ps1 -Drive E:            # dry run
        pwsh scripts\migrate_to_drive.ps1 -Drive E: -Go        # copy
        pwsh scripts\migrate_to_drive.ps1 -Drive E: -VerifyOnly

    WHY EACH SOURCE GETS ITS OWN DESTINATION SUBFOLDER
    --------------------------------------------------
    The brief said robocopy /MIR into <Drive>\Migration\. /MIR MIRRORS:
    it deletes anything at the destination that is not in the current
    source. Pointing three sources at one destination root means the
    second copy deletes the first and the third deletes the second, and
    robocopy reports success every time. Each source therefore lands in
    its own subfolder, where /MIR is safe and does what it is for --
    making a re-run converge instead of accumulate.

    WHAT IS EXCLUDED, AND WHY
    -------------------------
    _trash        17.8 GB. It is the project's undo buffer for removed
                  files; anything ever committed is in .git, which IS
                  copied. Ryan's call.
    DerivedDataCache / Intermediate
                  regenerate on first editor launch. Already moved to
                  _trash by the clean step.
    Saved         everything except Config and Screenshots, same reason.

    THE VERIFY IS A DIFFERENT INSTRUMENT FROM THE COPY
    --------------------------------------------------
    robocopy's own exit code says whether IT thinks it succeeded. This
    hashes both trees with SHA256 and compares, which is a different
    representation of the same claim -- non-negotiable 8. A file that
    copied truncated passes robocopy's count and fails here.
#>

[CmdletBinding()]
param(
    # Either a drive letter (E:) or a UNC destination
    # (\\LEGION\Migration). The network case pushes FROM this laptop,
    # which is the direction that works: inbound SMB here needs three
    # elevated changes (a share, LocalAccountTokenFilterPolicy for C$,
    # and File-and-Printer-Sharing firewall rules, of which 0 are
    # enabled). Outbound needs none.
    [Parameter(Mandatory = $true)][Alias('Drive')][string]$Dest,
    [switch]$Go,
    [switch]$VerifyOnly,
    [switch]$IncludeTrash
)

$ErrorActionPreference = 'Stop'
$repo = "C:\Users\ryanb\UE5LandscapePipeline"

# CHECK THE DESTINATION BEFORE BUILDING ANY PATH FROM IT. Join-Path
# RESOLVES a drive, so composing first makes the failure come out as
# "Cannot find drive. A drive with the name 'E' does not exist" from
# inside a path helper, instead of from the preflight that is supposed
# to own this refusal. Same outcome, worse message.
$Dest = $Dest.TrimEnd('\')
$isUnc = $Dest -match '^\\\\[^\\]+\\[^\\]+'
if (-not $isUnc -and $Dest -notmatch '^[A-Za-z]:$') {
    throw "REFUSE: -Dest must be a drive like 'E:' or a UNC path like '\\LEGION\Migration', got '$Dest'."
}

# THIS GUARD RUNS BEFORE ANY CIM QUERY, and that ordering is the whole
# point. It used to sit after Get-CimInstance, which throws "Invalid
# query" on some inputs -- so the run died with a WMI error instead of
# the refusal that was written for exactly this case. A gate placed
# downstream of something that can fail first is not a gate.
# The source drive is DERIVED from the repo path rather than hardcoded,
# so moving the repo cannot silently retire the check.
$srcDrive = (Split-Path $repo -Qualifier)
if (-not $isUnc -and $Dest -ieq $srcDrive) {
    throw "REFUSE: $Dest is the SOURCE drive ($repo lives there). A migration copy onto the source is not a backup."
}
if ($isUnc) {
    if (-not (Test-Path $Dest)) {
        throw "REFUSE: $Dest is not reachable. Check the Legion is on the LAN, the share exists and is WRITABLE, and that you are authenticated (net use $Dest /user:<legion>\<user>)."
    }
    # A UNC target IS the container -- the share the user made for this.
    # Appending \Migration to \\host\Migration gives \\host\Migration\
    # Migration, which is just noise: each source already lands in its
    # own named subfolder below.
    $destDir = $Dest
} else {
    if (-not (Test-Path "$Dest\")) {
        throw "REFUSE: $Dest is not mounted. Connect the external drive and re-run."
    }
    $destDir = "$Dest\Migration"
}

# name -> source. The name is also the destination subfolder.
$sets = [ordered]@{
    'LandscapeLab_repo' = $repo
    'Gaea_TerrainData'  = 'C:\Dev\LandscapeLab'
    'Gaea_Autosaves'    = 'C:\Users\ryanb\AppData\Roaming\QuadSpinner'
    'Asset_Sources'     = 'C:\Users\ryanb\Downloads'
}

# PROJECTTITAN IS DELIBERATELY ABSENT, and it is not a judgement call:
#   * its .uproject declares "Category": "Samples" -- an Epic sample,
#     not authored work
#   * VaultCache\Titan_5.8 holds 61.14 GB / 208,727 files against the
#     project's 61.11 GB / 208,726, so the launcher can restore it
#   * BACKLOG.md:244 already classified it "Large community art project.
#     Very large on disk; audit what is actually wanted before creating
#     it at all."
#   * nothing in this repo references Titan and nothing in Titan
#     references this pipeline. The single "Gaea" match inside it is
#     XH9GAEA8PCP8AX49BDZE4M.uasset, a World Partition GUID filename
#     that happens to contain those four letters.
# Re-download it from the Epic launcher on the new machine instead of
# carrying 61 GB across.

# Excluded directories, per source.
$excl = @{
    'LandscapeLab_repo' = @(
        (Join-Path $repo '_trash'),
        (Join-Path $repo 'LandscapeLab\DerivedDataCache'),
        (Join-Path $repo 'LandscapeLab\Intermediate')
    )
}
if ($IncludeTrash) { $excl['LandscapeLab_repo'] = $excl['LandscapeLab_repo'] | Where-Object { $_ -notmatch '_trash$' } }

function Get-TreeSize($path, $exclude) {
    $f = Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue
    if ($exclude) { foreach ($e in $exclude) { $f = $f | Where-Object { $_.FullName -notlike "$e*" } } }
    [pscustomobject]@{ Bytes = ($f | Measure-Object Length -Sum).Sum; Count = $f.Count }
}

# ---------- PREFLIGHT ----------------------------------------------------
Write-Host "=== PREFLIGHT ===" -ForegroundColor Cyan
if ($isUnc) {
    # GetDiskFreeSpaceEx, NOT Get-PSDrive. Get-PSDrive reported 0.0 GB
    # free for a share with 817 GB behind it -- and 0 is falsy, so the
    # headroom check would have been SKIPPED with a warning rather than
    # enforced. A capacity check that quietly disables itself on the one
    # path it was added for is worse than no check.
    Add-Type -ErrorAction SilentlyContinue @"
using System;
using System.Runtime.InteropServices;
public class LLDisk {
  [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
  public static extern bool GetDiskFreeSpaceEx(string dir, out ulong freeForCaller, out ulong total, out ulong totalFree);
}
"@
    [ulong]$avail = 0; [ulong]$tot = 0; [ulong]$tfree = 0
    if (-not [LLDisk]::GetDiskFreeSpaceEx("$Dest\", [ref]$avail, [ref]$tot, [ref]$tfree)) {
        throw "REFUSE: could not read free space on $Dest. Not starting a 30 GB copy blind."
    }
    $vol = [pscustomobject]@{ FreeSpace = [int64]$avail; Size = [int64]$tot; VolumeName = 'network share' }
    Write-Host ("  destination : {0}  (network, {1:N1} GB free of {2:N1} GB)" -f `
        $destDir, ($avail / 1GB), ($tot / 1GB))
} else {
    $vol = Get-CimInstance Win32_LogicalDisk | Where-Object DeviceID -ieq $Dest
    if (-not $vol) { throw "REFUSE: $Dest has no volume behind it." }
    Write-Host ("  destination : {0}  ({1}, {2:N1} GB free of {3:N1} GB)" -f `
        $destDir, $vol.VolumeName, ($vol.FreeSpace / 1GB), ($vol.Size / 1GB))
}

$total = 0
foreach ($k in $sets.Keys) {
    if (-not (Test-Path $sets[$k])) { Write-Host ("  {0,-20} MISSING {1}" -f $k, $sets[$k]) -ForegroundColor Yellow; continue }
    $s = Get-TreeSize $sets[$k] $excl[$k]
    $total += $s.Bytes
    Write-Host ("  {0,-20} {1,8:N2} GB  {2,7:N0} files   {3}" -f $k, ($s.Bytes / 1GB), $s.Count, $sets[$k])
}
Write-Host ("  {0,-20} {1,8:N2} GB" -f 'TOTAL', ($total / 1GB)) -ForegroundColor Cyan

# A copy that runs out of room halfway is worse than one that refuses.
$headroom = $vol.FreeSpace - $total
if ($headroom -lt 5GB) {
    throw ("REFUSE: {0:N1} GB free, {1:N1} GB to copy. Need at least 5 GB of headroom." -f `
        ($vol.FreeSpace / 1GB), ($total / 1GB))
}
Write-Host ("  headroom    : {0:N1} GB after the copy" -f ($headroom / 1GB))

if (-not $Go -and -not $VerifyOnly) {
    Write-Host "`nDRY RUN. Nothing copied. Re-run with -Go." -ForegroundColor Yellow
    return
}

# ---------- COPY ---------------------------------------------------------
if (-not $VerifyOnly) {
    Write-Host "`n=== COPY ===" -ForegroundColor Cyan
    $logDir = Join-Path $repo '_verify/migration_logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    Write-Host ("  logs        : {0}" -f $logDir)
    # ONLY create it if it is missing. New-Item -Force on a UNC share
    # root walks up and tries to create '\\192.168.1.10' -- the SERVER --
    # and fails with "The specified path is invalid". The share was
    # already proven to exist by the Test-Path in the preflight, so
    # there is nothing to create in the network case.
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }
    foreach ($k in $sets.Keys) {
        if (-not (Test-Path $sets[$k])) { continue }
        $to = Join-Path $destDir $k
        # $rcArgs, NOT $args. $args is a PowerShell AUTOMATIC variable
        # holding the caller's unbound arguments, so `& robocopy @args`
        # splatted the automatic one -- robocopy received nothing usable
        # and exited 16 ("serious error, copied no files"), while a
        # minimal hand-run of the same command worked fine.
        # THE LOG STAYS LOCAL. Pointing /LOG+ at the SMB destination makes
        # robocopy append a line per file ACROSS THE NETWORK -- 22,948
        # round trips for the repo alone. It hung the run outright, and
        # over a flaky link it is a way for the copy to fail on something
        # that is only bookkeeping. /V is dropped for the same reason:
        # per-file verbose output is what makes the log enormous.
        # STRING INTERPOLATION, NOT '+' INSIDE AN ARRAY LITERAL.
        # PowerShell's comma binds tighter than +, so
        #     @( 'a', '/LOG+:' + (Join-Path ...) )
        # produces TWO elements -- a bare '/LOG+:' and the path -- and
        # robocopy answers "ERROR : Invalid Parameter #7 : /LOG+:" then
        # exits 16. Three runs failed on this while the message was
        # being thrown away by the Out-Null below.
        $logFile = Join-Path $logDir "robocopy_$k.log"
        $rcArgs = @($sets[$k], $to, '/MIR', '/R:3', '/W:5', '/NP', "/LOG+:$logFile")
        foreach ($e in ($excl[$k] | Where-Object { $_ })) { $rcArgs += @('/XD', $e) }
        Write-Host ("  {0} -> {1}" -f $k, $to)
        # CAPTURED, NOT DISCARDED. `| Out-Null` hid robocopy's own error
        # text for three consecutive failures and left only an exit code
        # to guess from -- non-negotiable 14, on a run that costs
        # minutes to repeat.
        $rcOut = & robocopy @rcArgs 2>&1
        if ($LASTEXITCODE -ge 8) {
            Write-Host ($rcOut | Select-Object -Last 20 | Out-String) -ForegroundColor Red
        }
        # robocopy exit codes: <8 is success (0-7 are informational).
        if ($LASTEXITCODE -ge 8) { throw "robocopy FAILED for $k with exit $LASTEXITCODE" }
        Write-Host ("    robocopy exit {0} (below 8 = ok)" -f $LASTEXITCODE)
    }
}

# ---------- VERIFY + MANIFEST -------------------------------------------
Write-Host "`n=== VERIFY (SHA256, both trees) ===" -ForegroundColor Cyan
$manifest = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString('s') + 'Z'
    machine       = $env:COMPUTERNAME
    destination   = $destDir
    note          = 'Hashes are of the DESTINATION files, each compared to its source. A mismatch or a missing counterpart is listed under mismatches.'
    sets          = @{}
    mismatches    = @()
}
$bad = 0
foreach ($k in $sets.Keys) {
    $to = Join-Path $destDir $k
    if (-not (Test-Path $to)) { continue }
    $files = Get-ChildItem $to -Recurse -File -Force -ErrorAction SilentlyContinue
    $rows = New-Object System.Collections.ArrayList
    $i = 0
    foreach ($f in $files) {
        $i++
        if ($i % 500 -eq 0) { Write-Host ("    {0}: {1}/{2}" -f $k, $i, $files.Count) }
        $rel = $f.FullName.Substring($to.Length).TrimStart('\')
        $src = Join-Path $sets[$k] $rel
        $dh = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        $ok = $false
        if (Test-Path -LiteralPath $src) {
            $sh = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
            $ok = ($sh -eq $dh)
        }
        if (-not $ok) {
            $bad++
            $manifest.mismatches += @{ set = $k; path = $rel; reason = if (Test-Path -LiteralPath $src) { 'hash differs' } else { 'source missing' } }
        }
        [void]$rows.Add(@{ path = $rel; bytes = $f.Length; sha256 = $dh })
    }
    # THE OTHER DIRECTION: source files that never arrived.
    # Walking the destination alone answers "is what arrived intact",
    # which a copy that died halfway passes trivially -- there is simply
    # nothing at the destination to iterate over. This walks the SOURCE
    # and asserts every file has a counterpart, which is the question
    # "did it all arrive". Both are needed; neither implies the other.
    $srcFiles = Get-ChildItem $sets[$k] -Recurse -File -Force -ErrorAction SilentlyContinue
    foreach ($e in ($excl[$k] | Where-Object { $_ })) {
        $srcFiles = $srcFiles | Where-Object { $_.FullName -notlike "$e*" }
    }
    $absent = 0
    foreach ($sf in $srcFiles) {
        $rel2 = $sf.FullName.Substring($sets[$k].Length).TrimStart('\')
        if (-not (Test-Path -LiteralPath (Join-Path $to $rel2))) {
            $absent++
            $bad++
            if ($absent -le 50) {
                $manifest.mismatches += @{ set = $k; path = $rel2; reason = 'NEVER ARRIVED at destination' }
            }
        }
    }
    if ($absent -gt 50) {
        $manifest.mismatches += @{ set = $k; path = '(truncated)'; reason = "$absent files never arrived; first 50 listed" }
    }

    $manifest.sets[$k] = @{
        source        = $sets[$k]; files = $rows.Count
        source_files  = $srcFiles.Count
        never_arrived = $absent
        bytes         = ($files | Measure-Object Length -Sum).Sum
        items         = $rows
    }
    Write-Host ("  {0,-20} {1,7:N0} hashed / {2,7:N0} at source   missing {3}" -f `
        $k, $rows.Count, $srcFiles.Count, $absent)
}

$manifest.verdict = if ($bad -eq 0) { 'MATCH' } else { "MISMATCH ($bad file(s))" }
$mpath = Join-Path $destDir 'manifest.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $mpath -Encoding UTF8
Write-Host ("`nmanifest : {0}  ({1:N1} MB)" -f $mpath, ((Get-Item $mpath).Length / 1MB))
if ($bad -eq 0) {
    Write-Host "VERDICT: MATCH - every destination file hashes equal to its source." -ForegroundColor Green
} else {
    Write-Host ("VERDICT: MISMATCH on {0} file(s). See manifest.mismatches. DO NOT WIPE THE SOURCE." -f $bad) -ForegroundColor Red
    exit 5
}
