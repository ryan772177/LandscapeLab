"""Stage the POLYTRICITY hair strips: import, build the card material, place 3."""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRCDIR = os.path.join(REPO, "Free", "_intake", "hair_polytricity")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Placeholder root/tip, TRACEABLE rather than tasteful: concept 02's own
# MEASURED shadow and sun colours. The operator's swatches are gated.
ROOT_RGB = [0.087, 0.101, 0.083]
TIP_RGB = [0.663, 0.597, 0.480]


def main():
    tex = {}
    tdir = os.path.join(SRCDIR, "textures")
    for f in sorted(os.listdir(tdir)):
        role = f.replace("HSD_Skecthfab_", "").rsplit(".", 1)[0]
        tex[role] = os.path.join(tdir, f).replace("\\", "/")
    fbx = os.path.join(SRCDIR, "source", "HairCards_FBX.fbx").replace("\\", "/")
    missing = [k for k in ("Mask", "RGBMask", "Depth", "AO", "Frizz",
                           "NormalMap") if k not in tex]
    if missing or not os.path.isfile(fbx):
        print("REFUSE: missing %s%s" % (missing, "" if os.path.isfile(fbx)
                                        else " and the FBX"))
        return 2
    print("  6 maps + 1 FBX resolved on disk")

    with io.open(os.path.join(REPO, "scripts", "hair_stage_payload.txt"),
                 encoding="utf-8") as fh:
        tmpl = fh.read()
    src = (tmpl.replace("SRC_JSON", repr({"textures": tex, "fbx": fbx}))
           .replace("ROOT_RGB_JSON", repr(ROOT_RGB))
           .replace("TIP_RGB_JSON", repr(TIP_RGB)))
    gen = os.path.join(REPO, "LandscapeLab", "Saved", "hair_stage_gen.txt")
    with io.open(gen, "w", encoding="utf-8") as fh:
        fh.write(src)

    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         gen, "--timeout", "25"], capture_output=True, text=True)
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if i < 0:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1500:])
        return 5
    r = json.loads(t[i:j + 1])
    if r.get("error"):
        print("FAILED: " + str(r["error"])[:600])
    print("")
    for x in r.get("textures", []):
        print("  tex  %-10s srgb %-5s %s"
              % (x.get("role"), x.get("srgb"), x.get("compression",
                                                     x.get("error"))))
    m = r.get("mesh")
    if m:
        print("  mesh %s  %s cm  tris %s  slots %s  uv ch %s"
              % (m["asset"].split("/")[-1],
                 "x".join(str(v) for v in m["size_cm"]),
                 m["tris_lod0"], m["slots"], m["uv_channels"]))
    mm = r.get("material") or {}
    if mm:
        print("  mat  %s  expressions %s  blend %s  two_sided %s"
              % (mm.get("asset", "").split("/")[-1], mm.get("expressions"),
                 mm.get("blend_mode"), mm.get("two_sided")))
        ce = mm.get("compile_errors")
        print("  compile  %s" % ("clean, 0 errors" if ce == []
                                 else "%d ERROR(S): %s" % (len(ce), ce[:2])))
    for s in r.get("staged", []):
        print("  staged  %-14s yaw %+5.0f  material %s"
              % (s["label"], s["yaw"], s["material_readback"]))
    if r.get("uv_report"):
        print("")
        print("  UV: %s" % r["uv_report"].get("note", ""))
    print("")
    print("HAIR STAGE %s" % ("OK" if r.get("ok") else "!! NOT OK"))
    return 0 if r.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
