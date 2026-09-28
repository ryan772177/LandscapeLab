"""forge serve — the whole forge as one local web page.

Serves the Layout Author on 127.0.0.1 with a "Forge this world" bridge
injected IN MEMORY (the file on disk is never modified): author the
layout in the browser, click Forge, watch the build log stream, and
when it finishes get the render plus a downloadable zip of the UE
project. The browser is the steering wheel; the engine still runs
locally — this changes the experience, not the requirements.

Every build goes through the exact CLI (`python -m forge_tool.cli
build ... --layout ...`) as a subprocess, so every gate, refusal and
provenance rule holds unchanged. One build at a time (heavy ops are
serialized, R10); a second Forge click while one runs is refused.

Endpoints (localhost only — the server binds 127.0.0.1 and nothing
else; there is no auth because there is no remote access):
    GET  /               the author page + injected bridge
    POST /api/forge      {name, layout, image} -> starts a build
    POST /api/polish     {name}                -> starts forge polish
    GET  /api/status     {state, name, kind, exit, log}
    GET  /api/render?name=X    the run's render PNG
    GET  /api/download?name=X  zip of LandscapeLab/ (minus
                               Intermediate/Saved/DerivedDataCache);
                               &list=1 returns the manifest as JSON
                               instead of building the zip

On the packaged dist the project zip is exactly the skeleton plus the
worlds forged there. On the DEV repo it includes the whole dev project
— use &list=1 there.

Usage: python -m forge_tool.cli serve [--port 8765] [--no-browser]
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAX_BODY = 30 * 1024 * 1024  # concept images are MBs; 30 MB is generous
ZIP_SKIP_DIRS = {"Intermediate", "Saved", "DerivedDataCache",
                 "__pycache__"}

# one build/polish at a time — module state under a lock
_lock = threading.Lock()
_zip_lock = threading.Lock()  # two idle-time zips share a .part (F7)
_job = {"state": "idle", "name": None, "kind": None, "proc": None,
        "log": None, "exit": None}


def _busy_check():
    """Refuse while a job runs. Callers that WRITE anything a running
    build reads must call this BEFORE the write, not rely on _spawn's
    own check after it (audit F4: staging files first overwrote a
    running build's inputs)."""
    with _lock:
        if _job["state"] == "running" and _job["proc"].poll() is None:
            raise Refuse("a %s of %r is still running — one heavy "
                         "operation at a time"
                         % (_job["kind"], _job["name"]))


class Refuse(Exception):
    pass


def _safe_name(name):
    """Run names the server will touch: lowercase, no leading
    underscore (``_uploads`` is the server's own staging dir), and
    already in the CLI's biome alphabet so the subprocess cannot
    disagree about identity."""
    if not isinstance(name, str) \
            or not re.fullmatch(r"[a-z0-9][a-z0-9_]{0,40}", name):
        raise Refuse("world name must be 1-41 chars of [a-z0-9_], "
                     "starting with a letter or digit (got %r)" % (name,))
    return name


def _run_dir(name):
    p = os.path.realpath(os.path.join(REPO, "forge_runs", _safe_name(name)))
    root = os.path.realpath(os.path.join(REPO, "forge_runs"))
    if not p.startswith(root + os.sep):
        raise Refuse("run path escapes forge_runs")
    return p


def _decode_image(data_url):
    m = re.match(r"data:image/(jpeg|png);base64,(.+)$", data_url or "",
                 re.DOTALL)
    if not m:
        raise Refuse("image must be a JPEG or PNG data URL (drop the "
                     "concept image on the page first)")
    ext = "jpg" if m.group(1) == "jpeg" else "png"
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception:
        raise Refuse("image data URL is not valid base64")
    if not raw:
        raise Refuse("image decoded to zero bytes")
    return ext, raw


def _spawn(name, kind, argv):
    """Start the CLI subprocess for a build/polish; refuse if busy."""
    with _lock:
        if _job["state"] == "running":
            if _job["proc"].poll() is None:
                raise Refuse("a %s of %r is still running — one heavy "
                             "operation at a time"
                             % (_job["kind"], _job["name"]))
            _finish_locked()
        # logs live in the STAGING dir, never the run dir: creating
        # forge_runs/<name>/ here made the CLI's own never-overwrite
        # gate refuse the very build being started (measured on the
        # first serve build, 2026-09-04)
        log_dir = os.path.join(REPO, "forge_runs", "_uploads")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "%s_%s.log" % (name, kind))
        # the child duplicates the handle; close the parent's
        # deterministically (audit F8)
        log_f = open(log_path, "w", encoding="utf-8")
        try:
            # -u: unbuffered child, or the page's live log lags a full
            # block behind the build (measured: empty tail 100 s in)
            proc = subprocess.Popen(
                [sys.executable, "-u", "-m", "forge_tool.cli"] + argv,
                cwd=REPO, stdout=log_f, stderr=subprocess.STDOUT)
        finally:
            log_f.close()
        _job.update(state="running", name=name, kind=kind, proc=proc,
                    log=log_path, exit=None)


def _finish_locked():
    _job.update(state="idle", exit=_job["proc"].returncode
                if _job["proc"] else None)


def _status():
    with _lock:
        if _job["state"] == "running" and _job["proc"].poll() is not None:
            _job["state"] = "done"
            _job["exit"] = _job["proc"].returncode
        tail = ""
        if _job["log"] and os.path.isfile(_job["log"]):
            with open(_job["log"], "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 4000))
                tail = f.read().decode("utf-8", errors="replace")
        return {"state": _job["state"], "name": _job["name"],
                "kind": _job["kind"], "exit": _job["exit"], "log": tail}


def _zip_manifest():
    """(relpath, abspath) for every project file the zip carries."""
    proj = os.path.join(REPO, "LandscapeLab")
    if not os.path.isdir(proj):
        raise Refuse("no LandscapeLab/ project here — run "
                     "forge init --dest . --compile first")
    out = []
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in ZIP_SKIP_DIRS]
        for fn in files:
            full = os.path.join(root, fn)
            out.append((os.path.relpath(full, os.path.dirname(proj)),
                        full))
    return out


def _build_zip(name):
    """Zip the project into the run dir. The zip is of the WHOLE
    project, so its cache invalidates against the newest PROJECT file
    (audit F6 — keying on this run's render silently shipped a zip
    missing worlds forged after it). Refuses mid-build: zipping a
    project the editor is mutating captures half-written assets."""
    _busy_check()
    rd = _run_dir(name)
    if not os.path.isdir(rd):
        raise Refuse("no run named %r" % name)
    zip_path = os.path.join(rd, "project_%s.zip" % name)
    with _zip_lock:
        manifest = _zip_manifest()
        newest = max(os.path.getmtime(f) for _r, f in manifest)
        if os.path.isfile(zip_path) \
                and os.path.getmtime(zip_path) >= newest:
            return zip_path
        tmp = zip_path + ".part"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, full in manifest:
                z.write(full, rel)
        try:
            os.replace(tmp, zip_path)
        except PermissionError:
            # Windows: a previous download still streams the old zip
            # (no FILE_SHARE_DELETE). Serve the existing complete zip;
            # the fresh one rebuilds on the next request (audit F5).
            try:
                os.remove(tmp)
            except OSError:
                pass
    return zip_path


# ------------------------------------------------------------- the bridge

BRIDGE = """
<style>
#forgeBridge{position:fixed;right:14px;bottom:14px;z-index:99999;
 width:340px;background:#141a22;color:#dce6f2;border:1px solid #2e3a48;
 border-radius:10px;font:13px/1.45 system-ui,sans-serif;
 box-shadow:0 6px 24px rgba(0,0,0,.5)}
#forgeBridge .hd{padding:10px 12px;font-weight:600;border-bottom:1px
 solid #2e3a48}
#forgeBridge .bd{padding:10px 12px}
#forgeBridge button{background:#2f6fed;color:#fff;border:0;
 border-radius:6px;padding:8px 12px;cursor:pointer;font-weight:600}
#forgeBridge button:disabled{opacity:.5;cursor:default}
#forgeBridge pre{max-height:180px;overflow:auto;background:#0b0f14;
 padding:8px;border-radius:6px;white-space:pre-wrap;font-size:11px}
#forgeBridge img{max-width:100%;border-radius:6px;margin-top:6px}
#forgeBridge a{color:#7fb3ff}
</style>
<div id="forgeBridge"><div class="hd">&#9874; The Forge</div>
<div class="bd" id="fbBody">
 <p style="margin:0 0 8px">Author above, then forge it — the build runs
 on this machine (~25 min) and ends with the render and a UE-project
 download.</p>
 <button id="fbGo">Forge this world</button>
 <span id="fbMsg"></span>
</div></div>
<script>
(function(){
const body=document.getElementById('fbBody');
function h(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function poll(){fetch('/api/status').then(r=>r.json()).then(st=>{
  if(st.state==='running'){
    body.innerHTML='<p style="margin:0 0 6px">'+h(st.kind)+' of <b>'+h(st.name||'')+
      '</b> running&hellip;</p><pre>'+h(st.log||'')+'</pre>';
    setTimeout(poll,3000);
  }else if(st.state==='done'&&st.exit===0){
    body.innerHTML='<p style="margin:0 0 6px"><b>'+h(st.name)+'</b> is forged.</p>'+
      '<img src="/api/render?name='+encodeURIComponent(st.name)+'&t='+Date.now()+'">'+
      '<p><button id="fbZip">Download UE project (.zip)</button></p>'+
      '<button id="fbPolish">Polish exposure</button> '+
      '<button id="fbAgain">Forge another</button>';
    document.getElementById('fbZip').onclick=function(){
      this.disabled=true;this.textContent='zipping…';
      fetch('/api/zip',{method:'POST',headers:{'Content-Type':'application/json','X-Forge':'1'},
        body:JSON.stringify({name:st.name})}).then(r=>r.json()).then(j=>{
          if(j.error){alert(j.error);this.disabled=false;this.textContent='Download UE project (.zip)';}
          else{location.href='/api/download?name='+encodeURIComponent(st.name);
               this.disabled=false;this.textContent='Download UE project (.zip)';}
        });};
    document.getElementById('fbPolish').onclick=()=>{post('/api/polish',{name:st.name})};
    document.getElementById('fbAgain').onclick=()=>location.reload();
  }else if(st.state==='done'){
    body.innerHTML='<p style="margin:0 0 6px">The forge said no (exit '+st.exit+
      ') — the log ends with why, and what to change:</p><pre>'+h(st.log||'')+
      '</pre><button id="fbAgain">Back</button>';
    document.getElementById('fbAgain').onclick=()=>location.reload();
  }else{setTimeout(poll,3000);}
}).catch(()=>setTimeout(poll,5000));}
function post(url,payload){
  body.innerHTML='<p style="margin:0">starting&hellip;</p>';
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Forge':'1'},
    body:JSON.stringify(payload)}).then(r=>r.json()).then(j=>{
      if(j.error){body.innerHTML='<p style="margin:0;color:#ff9a9a">'+h(j.error)+
        '</p><button onclick="location.reload()">Back</button>';}
      else poll();
    });}
document.getElementById('fbGo').onclick=function(){
  var name=prompt('World name (letters, digits, _):',
                  (typeof S!=='undefined'&&S.world)?S.world:'');
  if(!name)return;
  if(typeof S==='undefined'||!S.imageData){
    alert('Drop the concept image on the page first — its lighting is '+
          'measured from the file.');return;}
  post('/api/forge',{name:name.toLowerCase(),layout:brief(),image:S.imageData});
};
fetch('/api/status').then(r=>r.json()).then(st=>{if(st.state==='running')poll()});
})();
</script>
"""


# ------------------------------------------------------------- the server

class Handler(BaseHTTPRequestHandler):
    server_version = "forge-serve"

    def log_message(self, fmt, *args):  # quiet: one line, no per-poll spam
        # base class also routes log_error("code %d, ...", int, ...)
        # through here — format first or an int crashes the 'in' test
        # (audit F9)
        msg = (fmt % args) if args else fmt
        if "/api/status" not in msg:
            sys.stderr.write("serve: %s\n" % msg)

    def _host_ok(self):
        """DNS rebinding turns an attacker page same-origin with a
        localhost server (audit F2): allow only the two names that are
        really us."""
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").strip().lower()
        if host in ("127.0.0.1:%d" % port, "localhost:%d" % port):
            return True
        self._send(403, {"error": "bad Host"})
        return False

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else \
            json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _q(self, key):
        from urllib.parse import urlparse, parse_qs
        v = parse_qs(urlparse(self.path).query).get(key, [None])[0]
        return v

    def do_GET(self):
        if not self._host_ok():
            return
        try:
            path = self.path.split("?")[0]
            if path == "/":
                page = open(os.path.join(REPO, "examples",
                                         "forge_layout_author.html"),
                            encoding="utf-8").read()
                page = page.replace("</body>", BRIDGE + "</body>")
                self._send(200, page.encode("utf-8"),
                           "text/html; charset=utf-8")
            elif path == "/api/status":
                self._send(200, _status())
            elif path == "/api/render":
                rd = _run_dir(self._q("name") or "")
                png = os.path.join(rd, "renders",
                                   os.path.basename(rd) + ".png")
                if not os.path.isfile(png):
                    raise Refuse("no render for that run yet")
                self._send(200, open(png, "rb").read(), "image/png")
            elif path == "/api/download":
                # GET is SERVE-ONLY: building the zip is a state change
                # and lives behind POST /api/zip (audit F3 — a bare GET
                # that writes is CSRF surface whatever the verb's name)
                name = _safe_name(self._q("name") or "")
                if self._q("list"):
                    man = _zip_manifest()
                    total = sum(os.path.getsize(f) for _r, f in man)
                    self._send(200, {"files": len(man),
                                     "total_bytes": total})
                    return
                zp = os.path.join(_run_dir(name),
                                  "project_%s.zip" % name)
                if not os.path.isfile(zp):
                    raise Refuse("zip not built yet — the page builds "
                                 "it first (POST /api/zip)")
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition",
                                 'attachment; filename="forge_%s.zip"'
                                 % name)
                self.send_header("Content-Length",
                                 str(os.path.getsize(zp)))
                self.end_headers()
                with open(zp, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        self.wfile.write(chunk)
            else:
                self._send(404, {"error": "unknown path"})
        except Refuse as e:
            self._send(400, {"error": str(e)})
        except (OSError, ConnectionError):
            pass  # client went away mid-stream; nothing to salvage

    def do_POST(self):
        if not self._host_ok():
            return
        try:
            # a cross-origin no-cors POST cannot carry a custom header;
            # requiring one kills the CSRF class (audit F1)
            if self.headers.get("X-Forge") != "1":
                raise Refuse("missing X-Forge header (cross-site POST "
                             "refused)")
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > MAX_BODY:
                raise Refuse("body must be 1 byte .. 30 MB")
            try:
                payload = json.loads(self.rfile.read(n).decode("utf-8"))
            except Exception:
                raise Refuse("body is not JSON")
            if not isinstance(payload, dict):
                raise Refuse("body must be a JSON object")

            if self.path == "/api/forge":
                name = _safe_name(payload.get("name"))
                layout = payload.get("layout")
                if not isinstance(layout, dict) or \
                        layout.get("schema") != "forge-layout/1":
                    raise Refuse("layout missing or not a Layout Author "
                                 "export (schema forge-layout/1)")
                # BEFORE staging: a same-name POST must not overwrite
                # the inputs a running build still reads (audit F4)
                _busy_check()
                ext, raw = _decode_image(payload.get("image"))
                up = os.path.join(REPO, "forge_runs", "_uploads")
                os.makedirs(up, exist_ok=True)
                img_path = os.path.join(up, "%s.%s" % (name, ext))
                with open(img_path, "wb") as f:
                    f.write(raw)
                lay_path = os.path.join(up, "%s.layout.json" % name)
                with open(lay_path, "w", encoding="utf-8") as f:
                    json.dump(layout, f, indent=1)
                _spawn(name, "build",
                       ["build", img_path, "--layout", lay_path,
                        "--name", name, "--max-brief-iters", "14"])
                self._send(200, {"ok": True, "name": name})
            elif self.path == "/api/polish":
                name = _safe_name(payload.get("name"))
                _spawn(name, "polish", ["polish", "--name", name])
                self._send(200, {"ok": True, "name": name})
            elif self.path == "/api/zip":
                name = _safe_name(payload.get("name"))
                zp = _build_zip(name)
                self._send(200, {"ok": True,
                                 "bytes": os.path.getsize(zp)})
            else:
                self._send(404, {"error": "unknown path"})
        except Refuse as e:
            self._send(400, {"error": str(e)})
        except (OSError, ConnectionError):
            pass


def main(argv=None):
    import argparse
    import webbrowser
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/" % a.port
    print("The Forge is serving at %s  (Ctrl+C stops it; a build in "
          "flight keeps running)" % url)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nserve stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
