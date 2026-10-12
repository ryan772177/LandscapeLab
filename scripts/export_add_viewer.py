"""Add viewer.html (scroll-through viewer with picks) to an export_stills zip.

    python scripts/export_add_viewer.py [--zip _exports/alpine_stills.zip]
"""
import argparse, csv, io, json, os, sys, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=os.path.join("_exports", "alpine_stills.zip"))
    a = ap.parse_args()
    zp = os.path.join(REPO, a.zip)
    with zipfile.ZipFile(zp) as z:
        if "viewer.html" in z.namelist():
            print("viewer.html already present"); return 0
        rows = list(csv.DictReader(io.StringIO(z.read("index.csv").decode("utf-8"))))
    data = [{"id": r["id"], "date": r["date"][:10], "f": r["folder"],
             "n": os.path.basename(r["path"])} for r in rows]
    tpl = open(os.path.join(REPO, "scripts", "export_viewer.html"), encoding="utf-8").read()
    html = tpl.replace("__DATA__", json.dumps(data))
    with zipfile.ZipFile(zp, "a") as z:
        z.writestr("viewer.html", html)
    print("viewer.html added:", len(data), "images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
