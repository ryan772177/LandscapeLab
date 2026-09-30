# Brief 7 P4, 2026-09-28: wait for the batch-0 runner (--only 0 --no-force) to
# finish, then run the remaining 23 batches unattended and resumable.
# batches.json carries progress; a second crash of one batch stops the run.
$repo = "C:\Users\Admin\UE5LandscapePipeline"
$rd = "$repo\_verify\hlod\p4b_20260928"
Set-Location $repo
"chain start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append "$rd\chain_rest.log"
while ((Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*hlod_build_batched.py run --only 0*' }) -or (Get-Process UnrealEditor-Cmd -ErrorAction SilentlyContinue)) {
    Start-Sleep 30
}
"batch 0 runner gone $(Get-Date -Format 'HH:mm:ss'); launching --start 1" | Out-File -Append "$rd\chain_rest.log"
Start-Sleep 20
python -u scripts/hlod_build_batched.py run --no-force --start 1 --run-dir $rd 2>&1 | Out-File "$rd\run_rest_noforce.log"
"run --start 1 exited $(Get-Date -Format 'HH:mm:ss') rc=$LASTEXITCODE" | Out-File -Append "$rd\chain_rest.log"
