"""lookdev_tex_encoding.py -- read (default) or set IN MEMORY the source-encoding
override of colour textures, through lookdev_tex_encoding_payload.txt.

    python scripts/lookdev_tex_encoding.py T_gray_rocks_C T_forest_floor_C
    python scripts/lookdev_tex_encoding.py --apply TSE_SRGB T_gray_rocks_C

Nothing is saved by this tool. Exit 0 when the payload reported ok.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--apply", default=None, help="enum member, e.g. TSE_SRGB")
    a = ap.parse_args()
    cmd = [sys.executable, os.path.join(HERE, "ue_exec.py"),
           os.path.join(HERE, "lookdev_tex_encoding_payload.txt"), "--timeout", "25",
           "--set", "APPLY=%s" % bool(a.apply),
           "--set", "NAMES=%s" % json.dumps(a.names),
           "--set", "ENC=%s" % (a.apply or "TSE_SRGB")]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    i, j = out.find("{"), out.rfind("}")
    if i < 0 or j <= i:
        print("COULD NOT LOOK: no JSON from the payload\n" + out[-1500:])
        return 1
    rep = json.loads(out[i:j + 1])
    print("ok %s  error %s" % (rep.get("ok"), rep.get("error")))
    print("enum members %s" % rep.get("enum_members"))
    for n, row in (rep.get("textures") or {}).items():
        print("  %-22s %s" % (n, row))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
