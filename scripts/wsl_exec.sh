#!/usr/bin/env bash
# Run a local shell script inside WSL, with NOTHING for a shell to eat.
#
# WHY THIS EXISTS. Passing a payload inline to wsl.exe fails in at least three
# distinct ways, all measured on 2026-08-16:
#   1. PowerShell 5.1 splits a single-quoted argument at the first space, so
#      bash receives a fragment and dies on an unterminated `if`.
#   2. Git Bash rewrites absolute paths -- /usr/lib/wsl/lib/nvidia-smi arrived
#      as C:/Program Files/Git/usr/lib/... (the msys path-conversion hazard).
#   3. wsl.exe RE-PARSES the command line, so a heredoc's quoted delimiter
#      <<"EOF" arrives as <<EOF and the body expands after all. That one wrote
#      an expanded Windows PATH snapshot into /etc/profile.d/cuda.sh and the
#      file then looked correct while doing the wrong thing.
#   And `$(...)` inside a payload returns empty unpredictably -- which produced
#   "command -v nvcc" empty in the same shell where "type -a nvcc" resolved it.
#
# THE FIX: base64. The alphabet is [A-Za-z0-9+/=] -- no spaces, no quotes, no
# dollars, no slashes that look like paths to msys. Nothing in any layer has
# anything to mangle.
#
# USAGE
#   scripts/wsl_exec.sh <local-script.sh> [remote-name]
#
# TO RUN SOMETHING LONG, background the CALLER (the Bash tool's
# run_in_background), NOT the remote process.
#
# WSL_BG=1 exists and is a TRAP, kept only because the trap is worth naming:
# WSL tears down the whole session process tree when the initiating wsl.exe
# exits, and setsid+nohup does NOT survive that without systemd. Measured
# 2026-08-16 -- the launcher printed "STARTED ... log ..." and exited 0, and
# then there was no log, no /opt/trellis and no process. A detach that reports
# success and leaves nothing behind is worse than one that fails loudly.
# Keeping wsl.exe alive on the Windows side is what actually holds the session
# open, which is why the CUDA and PyTorch installs completed and this did not.
#
# The remote copy lands at /root/_exec/<name> so a failing run is inspectable
# afterwards rather than vanishing with the pipe.
set -euo pipefail

DISTRO="${WSL_DISTRO:-Ubuntu-24.04}"
SRC="${1:?usage: wsl_exec.sh <local-script.sh> [remote-name]}"
NAME="${2:-$(basename "$SRC")}"

[ -f "$SRC" ] || { echo "REFUSE: no such script: $SRC" >&2; exit 2; }

export WSL_UTF8=1 MSYS2_ARG_CONV_EXCL='*'

# Strip CR: a script written on Windows carries CRLF and bash fails on the \r
# with errors that name the wrong thing entirely.
B64="$(tr -d '\r' < "$SRC" | base64 -w0)"

REMOTE="/root/_exec/$NAME"
LOG="/root/_exec/$NAME.log"

if [ "${WSL_BG:-0}" = "1" ]; then
  wsl.exe -d "$DISTRO" --user root -- bash -c \
    "mkdir -p /root/_exec; echo $B64 | base64 -d > $REMOTE; chmod +x $REMOTE; setsid nohup bash $REMOTE > $LOG 2>&1 < /dev/null & echo STARTED $REMOTE log $LOG"
else
  wsl.exe -d "$DISTRO" --user root -- bash -c \
    "mkdir -p /root/_exec; echo $B64 | base64 -d > $REMOTE; chmod +x $REMOTE; bash $REMOTE"
fi
