<#
lookdev_shot.ps1 -- one look-dev frame: foreground the editor, place the camera
on TRACED ground + eye height, settle, shoot. The inner loop of the fast look
iteration (Ryan, 2026-09-30: change, compare, repeat).

    powershell -File scripts/lookdev_shot.ps1 -Iter iter00 -Name mtn_a -X 0 -Y 60000 -Pitch 3 -Yaw 270 -Eye 3000

Frames land in _verify/lookdev/<Iter>/<Name>.png (absolute path passed on).

WHY THE FOREGROUND STEP: an editor that is not the foreground window does not
write the HighResShot (LESSONS 2026-09-30b). The foreground PID is READ BACK
and the script refuses if it is not the editor.
#>
param(
    [Parameter(Mandatory=$true)][string]$Iter,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][double]$X,
    [Parameter(Mandatory=$true)][double]$Y,
    [double]$Pitch = 0.0,
    [double]$Yaw = 0.0,
    [double]$Eye = 175.0,
    [int]$Settle = 12
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$out = Join-Path $repo ("_verify\lookdev\" + $Iter)
New-Item -ItemType Directory -Force -Path $out | Out-Null

Add-Type @"
using System; using System.Runtime.InteropServices;
public class LookdevWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  // The editor FRAME, by title. With -log the process's MainWindowHandle is the
  // log console (title = the exe path): foregrounding THAT passes a PID check
  // and leaves the viewport unfocused (2026-09-30, NO FRAME on LookDevMtn).
  public static IntPtr EditorFrame(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) {
        var sb = new System.Text.StringBuilder(512); GetWindowText(h, sb, 512);
        if (sb.ToString().Contains("Unreal Editor")) { found = h; return false; }
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static string Title(IntPtr h) { var sb = new System.Text.StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
}
"@
$ed = @(Get-Process UnrealEditor -ErrorAction SilentlyContinue)
if ($ed.Count -ne 1) { throw "expected exactly one editor, found $($ed.Count) (rule 11)" }
$frame = [LookdevWin]::EditorFrame([uint32]$ed[0].Id)
if ($frame -eq [IntPtr]::Zero) { throw "no visible window titled '... Unreal Editor' for PID $($ed[0].Id) (offscreen editor?)" }
[LookdevWin]::keybd_event(0x12,0,0,[UIntPtr]::Zero); [LookdevWin]::keybd_event(0x12,0,2,[UIntPtr]::Zero)
# A MINIMISED frame is "visible" to EnumWindows and can even take the foreground,
# and its viewport never draws (frame counter frozen, 2026-09-30). Restore first.
if ([LookdevWin]::IsIconic($frame)) { [void][LookdevWin]::ShowWindow($frame, 9) }
[void][LookdevWin]::ShowWindow($frame, 3)
[void][LookdevWin]::SetForegroundWindow($frame)
Start-Sleep -Milliseconds 1500
if ([LookdevWin]::IsIconic($frame)) { throw "editor frame is still minimised after SW_RESTORE" }
$fg = [LookdevWin]::GetForegroundWindow()
# The editor's own popups (Message Log) may hold the foreground: accept any window
# of the editor PROCESS, given the frame itself is restored (checked above).
$fpid = 0; [void][LookdevWin]::GetWindowThreadProcessId($fg, [ref]$fpid)
if ($fpid -ne $ed[0].Id) { throw "editor is not the foreground app (foreground title '$([LookdevWin]::Title($fg))')" }

$o = python (Join-Path $repo "scripts\ue_exec.py") (Join-Path $repo "scripts\brief7_place_cam_payload.txt") --timeout 25 `
    --set "X=$X" --set "Y=$Y" --set "PITCH=$Pitch" --set "YAW=$Yaw" --set "EYE=$Eye" 2>&1 | Out-String
if ($o -notmatch '"shoot_loc":\s*"([^"]+)"') { throw "place_cam failed: $o" }
$loc = $Matches[1]
Start-Sleep -Seconds $Settle
$s = python (Join-Path $repo "scripts\shoot.py") --name $Name "--loc=$loc" "--rot=0,$Pitch,$Yaw" --outdir $out --deadline 120 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "shoot failed: $s" }
Write-Output ("{0}  loc {1}  -> {2}" -f $Name, $loc, (Join-Path $out ($Name + ".png")))
