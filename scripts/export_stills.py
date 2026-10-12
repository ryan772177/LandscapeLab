"""export_stills.py -- package every landscape/world capture into one zip for picking.

    python scripts/export_stills.py [--out _exports/alpine_stills.zip] [--max-px 1280]

Each image becomes NNNN.jpg (downscaled, JPEG) inside the zip, plus:
  index.csv     id, source path, folder, file date, size, sidecar files beside it,
                and the git commit that first recorded the folder (hash, date, subject)
  contact.html  every image as a numbered thumbnail, grouped by folder, newest first

Pick by number; the index leads back to the source frame and from there to the
recipe and commit that made it. READ-ONLY on the repo except the output zip.

EXCLUDED, by folder or name: character/hero/hair/groom work, concept-art refs,
texture and terrain source maps, vendor packs, the engine project, _trash, and
render-buffer diagnostics (SceneDepth, _diff, bc_ base-colour tiles, masks,
REJECTED frames). The exclusion list is printed with its counts.
"""
import argparse
import csv
import datetime
import io
import os
import re
import subprocess
import sys
import zipfile

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Image.MAX_IMAGE_PIXELS = None

SKIP_TOP = {"LandscapeLab", "Free", "_trash", ".git", "textures", "terrain",
            "hero", "refs", "characters", "_exports", "forge_runs", "Saved",
            "node_modules"}
SKIP_FOLDER = re.compile(r"(hair|groom|hero|catalogue|blender|agents|difflocks|bindfix|"
                         r"eyeball|rootuv|threepanel|viewmode|colour2|haircolor|flip|"
                         r"hug|k28|rot90|shorter|studio|three_orient|vendor|youredit|"
                         r"face|artspec|fall|FINAL|_v2|_P1|_L1|gaterehab|macro|"
                         r"final|ingest|rear|artdirect|_ue$|likeness)", re.I)
SKIP_NAME = re.compile(r"(scenedepth|_diff|^bc_|mask|depth|rejected|\.prev|normal|"
                       r"_weights|hillshade|thumb|_tile|buffer)", re.I)
EXT = (".png", ".jpg", ".jpeg")


def first_commit(folder):
    try:
        out = subprocess.run(["git", "log", "--reverse", "--format=%h|%ad|%s",
                              "--date=short", "--", folder], cwd=REPO,
                             capture_output=True, text=True, timeout=60).stdout
        line = out.splitlines()[0] if out.strip() else ""
        return line.split("|", 2) if line else ["", "", ""]
    except Exception:
        return ["", "", ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("_exports", "alpine_stills.zip"))
    ap.add_argument("--max-px", type=int, default=1280)
    a = ap.parse_args()
    out = os.path.abspath(os.path.join(REPO, a.out))
    if os.path.commonpath([out, REPO]) != REPO:
        print("REFUSE: output outside the repo (standing rule 1)")
        return 2

    rows, skipped = [], {"top": 0, "folder": 0, "name": 0, "unreadable": 0}
    for d, subs, files in os.walk(REPO):
        rel = os.path.relpath(d, REPO)
        parts = [] if rel == "." else rel.split(os.sep)
        if parts and parts[0] in SKIP_TOP:
            subs[:] = []
            skipped["top"] += sum(f.lower().endswith(EXT) for f in files)
            continue
        if any(SKIP_FOLDER.search(p) for p in parts):
            skipped["folder"] += sum(f.lower().endswith(EXT) for f in files)
            continue
        side = sorted(f for f in files if f.lower().endswith((".json", ".txt", ".md"))
                      and not f.startswith("_"))
        for f in files:
            if not f.lower().endswith(EXT):
                continue
            if SKIP_NAME.search(f):
                skipped["name"] += 1
                continue
            p = os.path.join(d, f)
            st = os.stat(p)
            rows.append({"path": os.path.relpath(p, REPO).replace(os.sep, "/"),
                         "folder": rel.replace(os.sep, "/"),
                         "mtime": st.st_mtime, "bytes": st.st_size,
                         "sidecars": ";".join(side[:6])})

    rows.sort(key=lambda r: r["mtime"], reverse=True)
    commits = {}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    groups = {}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        n = 0
        for r in rows:
            try:
                im = Image.open(os.path.join(REPO, r["path"])).convert("RGB")
            except Exception:
                skipped["unreadable"] += 1
                continue
            w, h = im.size
            im.thumbnail((a.max_px, a.max_px), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            n += 1
            r["id"] = "%04d" % n
            r["orig_px"] = "%dx%d" % (w, h)
            z.writestr("images/%s.jpg" % r["id"], buf.getvalue())
            th = im.copy()
            th.thumbnail((320, 320))
            tb = io.BytesIO()
            th.save(tb, "JPEG", quality=70)
            z.writestr("thumbs/%s.jpg" % r["id"], tb.getvalue())
            if r["folder"] not in commits:
                commits[r["folder"]] = first_commit(r["folder"])
            r["commit"], r["commit_date"], r["commit_subject"] = commits[r["folder"]]
            r["date"] = datetime.datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M")
            groups.setdefault(r["folder"], []).append(r)
        rows = [r for r in rows if "id" in r]

        s = io.StringIO()
        wr = csv.writer(s)
        cols = ["id", "date", "path", "folder", "orig_px", "sidecars",
                "commit", "commit_date", "commit_subject"]
        wr.writerow(cols)
        for r in rows:
            wr.writerow([r.get(c, "") for c in cols])
        z.writestr("index.csv", s.getvalue())

        esc = lambda t: (t or "").replace("&", "&amp;").replace("<", "&lt;")
        html = ["<!doctype html><meta charset=utf-8><title>Alpine stills</title>",
                "<style>body{font:13px system-ui;background:#16191a;color:#ddd;margin:16px}"
                "h2{font-size:14px;margin:28px 0 6px;color:#9fd}"
                ".g{display:flex;flex-wrap:wrap;gap:8px}figure{margin:0;width:220px}"
                "img{width:220px;display:block;border-radius:3px}figcaption{font:12px ui-monospace,monospace;color:#aaa}"
                "a{color:inherit}</style>",
                "<p>%d images. Open images/NNNN.jpg for full size; index.csv has the source of each.</p>" % len(rows)]
        for folder in sorted(groups, key=lambda f: -max(x["mtime"] for x in groups[f])):
            g = [x for x in groups[folder] if "id" in x]
            c = commits.get(folder, ["", "", ""])
            html.append("<h2>%s <span style='color:#888'>(%d) &middot; %s %s</span></h2><div class=g>"
                        % (esc(folder), len(g), esc(c[1]), esc(c[2])[:90]))
            for x in g:
                html.append("<figure><a href='images/%s.jpg'><img src='thumbs/%s.jpg' loading=lazy></a>"
                            "<figcaption>%s &middot; %s<br>%s</figcaption></figure>"
                            % (x["id"], x["id"], x["id"], x["date"][:10], esc(os.path.basename(x["path"]))[:34]))
            html.append("</div>")
        z.writestr("contact.html", "\n".join(html))

    print("images packed:", len(rows), " folders:", len(groups))
    print("skipped:", skipped)
    print("zip:", os.path.relpath(out, REPO), "%.0f MB" % (os.path.getsize(out) / 2**20))
    return 0


if __name__ == "__main__":
    sys.exit(main())
