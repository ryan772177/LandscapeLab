"""start_mcp_server.py — start the UE 5.8 MCP server and PROVE it is listening.

Render/runtime state only: issues one console command in the live editor.
Touches no asset, no actor, no config file, and saves nothing.

WHY THIS EXISTS — THE PLUGIN REPORTS SUCCESS ON A FAILED BIND
-------------------------------------------------------------
`ModelContextProtocol.StartServer` logs

    LogModelContextProtocol: Starting MCP server on port 8000 ...

*before* the HTTP listener has bound, and `FHttpServerModule::GetHttpRouter`
is called with `bFailOnBindFailure = false`
(ModelContextProtocolServer.cpp:432). When the port is already held by
another process the engine logs

    LogHttpListener: Error: HttpListener unable to bind to 127.0.0.1:8000
    LogHttpServerModule: All listeners started

and the MCP plugin says nothing further. Measured 2026-08-14: IncrediBuild's
Manager.exe held [::]:8000, three StartServer attempts all "succeeded", and
nothing served /mcp. The editor's own log is therefore NOT an instrument for
"is the server up".

So the read-back here is a REAL MCP `initialize` request sent from OUTSIDE
the editor over a TCP socket — a different representation from the log line
that made the claim (non-negotiable 0, 8).

AND THE READ-BACK DISCRIMINATES. A responder on the port is not evidence the
EDITOR is the responder: probing 8000 during the incident above got a TCP
connection from IncrediBuild, not a refusal. Two separate checks therefore
run, and they read different things:

  * the MCP `initialize` response must carry a JSON-RPC `result` with a
    `protocolVersion`. `serverInfo` is NOT usable for identity — UE 5.8
    returns it with name, title and version all empty strings (measured
    2026-08-14), so a tool that keyed on the name would read a live server
    as anonymous and could not tell it from anyone else's;
  * an occupied port's OWNING PROCESS is compared against the PID the
    verified editor reports for itself. Only the editor's own port may be
    rebound; any other owner is refused by name before the editor is
    touched.

The owner check is also what makes a re-bind safe. `StartServer` MOVES the
server: after starting on another port the old one stays BOUND by the
editor's HTTP module and answers 404 on /mcp. That is our own stale
listener, not a foreign squatter, and only the PID tells them apart.

Exit codes:
  0  the server answered `initialize` on the requested port
  2  editor gate refused (conduct rule 7), or bad arguments
  4  the port is held by a FOREIGN process — refused before touching the
     editor, because starting into an occupied port is the silent failure
  5  the command was sent and nothing MCP-shaped answered the port
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_MCPSTART__"

# The console command and its port argument are verified against engine
# source on THIS install rather than remembered (non-negotiable 23):
#   ModelContextProtocolModule.cpp:32-52  registration, optional <port>,
#                                         range 1..65535
#   ModelContextProtocolSettings.h:38     ServerPortNumber default 8000
#   ModelContextProtocol.h:45             DefaultServerPort = 8000
PAYLOAD = '''
import json as _json
import os as _os
import unreal as _unreal

_out = {{"ok": False, "pid": _os.getpid(), "started": False, "error": None}}
try:
    if {do_start}:
        _sl = _unreal.SystemLibrary
        _ues = _unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem)
        _w = _ues.get_editor_world()
        _sl.execute_console_command(
            _w, "ModelContextProtocol.StartServer {port}")
        _out["started"] = True
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "{{0}}: {{1}}".format(type(_e).__name__, _e)
print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def port_owner(port):
    """(pid, name) of the process listening on 127.0.0.1:port, or (None, why).

    Windows exposes no stdlib route to the TCP table, so this shells out to
    PowerShell. A failure here reports as "could not read" and is never
    rendered as "nobody owns it" (non-negotiable 6).
    """
    ps = (
        "$c = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue"
        " | Where-Object {{ $_.LocalPort -eq {0} }} | Select-Object -First 1;"
        " if ($c) {{ $p = Get-Process -Id $c.OwningProcess"
        " -ErrorAction SilentlyContinue;"
        " '{{0}}|{{1}}' -f $c.OwningProcess, $p.ProcessName }}"
    ).format(port)
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=25).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return None, "could not read the TCP table: {0}".format(e)
    if "|" not in out:
        return None, "no listener found for port {0}".format(port)
    pid, _, name = out.partition("|")
    try:
        return int(pid), (name.strip() or "?")
    except ValueError:
        return None, "unparseable owner row {0!r}".format(out)


def probe(port, url_path, timeout=8.0):
    """Send a real MCP `initialize`. Returns (ok, detail).

    ok is True only when the responder returns a JSON-RPC `result` carrying
    a `protocolVersion`. A bare TCP connection is NOT success, and neither
    is `serverInfo` — UE 5.8 leaves its name/title/version empty, so it
    identifies nothing. See the module docstring.
    """
    url = "http://127.0.0.1:{0}{1}".format(port, url_path)
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "start_mcp_server.py", "version": "1"},
        },
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, "HTTP {0} from {1}".format(e.code, url)
    except (urllib.error.URLError, socket.timeout, ConnectionError,
            OSError) as e:
        return False, "{0}: {1}".format(type(e).__name__, e)

    # The transport may answer as SSE (`data: {...}` lines) or as a whole
    # JSON body. The engine PRETTY-PRINTS its JSON across many lines, so a
    # line-at-a-time parser sees no complete object and reports a live
    # server as dead — measured 2026-08-14, and it is the same
    # "I could not look" read as "it is absent" that non-negotiable 6
    # forbids. Try the whole body FIRST, then the SSE framing.
    candidates = [raw]
    candidates += [ln[5:].strip() for ln in raw.splitlines()
                   if ln.startswith("data:")]
    for chunk in candidates:
        chunk = chunk.strip()
        if not chunk.startswith("{"):
            continue
        try:
            msg = json.loads(chunk)
        except ValueError:
            continue
        result = msg.get("result")
        if isinstance(result, dict) and result.get("protocolVersion"):
            caps = sorted((result.get("capabilities") or {}).keys())
            return True, "MCP protocol {0}, capabilities: {1}".format(
                result["protocolVersion"], ", ".join(caps) or "none")
    return False, "responded, but no MCP initialize result: {0!r}".format(
        raw[:200])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8001,
                    help="port to serve /mcp on (default 8001; the engine "
                         "default 8000 collides with IncrediBuild here)")
    ap.add_argument("--url-path", default="/mcp")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    if not (1 <= args.port <= 65535):
        print("REFUSE: --port must be 1..65535 (engine range, "
              "ModelContextProtocolModule.cpp:41).")
        return 2

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("RUNTIME STATE ONLY: one console command, no asset, no config, "
          "no save.")
    print("target    : http://127.0.0.1:{0}{1}".format(args.port,
                                                       args.url_path))

    # PRE-FLIGHT. Starting into a port held by someone else is exactly the
    # silent failure this tool exists for, so it is decided BEFORE the
    # console command is sent rather than diagnosed afterwards.
    ok, detail = probe(args.port, args.url_path, timeout=4.0)
    if ok:
        print("already serving: {0}".format(detail))
        return 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        occupied = s.connect_ex(("127.0.0.1", args.port)) == 0

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()

    def _run(do_start):
        r = remote.run_command(
            PAYLOAD.format(port=args.port, do_start=bool(do_start),
                           marker=MARKER),
            unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
        return _parse(bootstrap._collect_output(r) if r else "")

    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        remote.open_command_connection(node["node_id"])

        got = _run(do_start=False)          # read-only: who are you?
        if got is None or got.get("error"):
            print("REFUSE: could not read the editor's PID ({0}). This is "
                  "'I could not look', not 'the port is free'."
                  .format((got or {}).get("error", "no parseable result")))
            return 5
        editor_pid = got.get("pid")
        print("editor pid: {0}".format(editor_pid))

        if occupied:
            owner_pid, owner_name = port_owner(args.port)
            if owner_pid is None:
                print("REFUSE: port {0} is occupied and its owner could not "
                      "be read ({1}). Refusing rather than binding blind."
                      .format(args.port, owner_name))
                return 4
            if owner_pid != editor_pid:
                print("REFUSE: port {0} is held by PID {1} ({2}), not this "
                      "editor (PID {3}). The engine binds with "
                      "bFailOnBindFailure false, so starting here would log "
                      "success and serve nothing. Pick a free port."
                      .format(args.port, owner_pid, owner_name, editor_pid))
                return 4
            print("port {0} is held by THIS editor's own HTTP module "
                  "({1}) — rebinding its /mcp route."
                  .format(args.port, owner_name))

        got = _run(do_start=True)
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass
        remote.stop()

    if got is None:
        print("REFUSE: no parseable result from the editor. This is 'I could "
              "not look', not 'the server is down'.")
        return 5
    if got.get("error"):
        print("REFUSE: payload error: {0}".format(got["error"]))
        return 5

    ok, detail = probe(args.port, args.url_path)
    if not ok:
        print("REFUSE: the command was sent and nothing MCP-shaped answered "
              "{0} ({1}). Check the editor log for 'HttpListener unable to "
              "bind'.".format(args.port, detail))
        return 5

    print("SERVING   : {0}".format(detail))
    print("VERDICT   : the MCP server answered initialize on port {0}. This "
          "is a socket read from outside the editor, not the editor's own "
          "log line.".format(args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
