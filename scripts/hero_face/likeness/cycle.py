"""cycle.py -- one groom refinement cycle, blend to judgment frames.

    python cycle.py --blend <in.blend> --name L1 --out-dir <ABS>

    export (fixed exporter + sidecar; refused unless ok) -> import (curve
    count re-checked) -> bind (up to 3 attempts) with respawn -> colour +
    binding re-assert (refused unless the payload reports ok) -> presence gate
    (refuses on a non-zero exit) -> alpine frames -> neutral-lit frames ->
    STOP.

ONE KNOB PER CYCLE is the operator's rule and this script does not enforce it --
it cannot see what changed in the blend. What it enforces is that every cycle is
measured the SAME way, so two frames differ because the groom differs and not
because the rig moved. Every camera pose, crop and light is fixed here.

THE NEUTRAL FRAME IS NOT DECORATION. Alpine's 12-degree sun rakes across the
groom and flattens it, so a lifted cut and a slicked one photograph alike. The
alpine frame is the shipping condition; the neutral frame is the one that can be
read for volume.
"""

import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LIK = os.path.join(REPO, "scripts", "hero_face", "likeness")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
GROOMS = "/Game/Characters/AlpineHero/Grooms"
HEAD = [354600.0, -321400.0, 31019.47 + 168.0]

# The ruled hair colour, RECIPES.md R-HAIRCOLOUR, as one declaration.
RULED_COLOUR_FILE = os.path.join(
    REPO, "_verify", "20260823_colour2", "params_SHIPPED.json")
RULED_COLOUR_FALLBACK = {"hairMelanin": 1.0, "hairRedness": 0.0}


def RULED_COLOUR():
    """The ruled base-layer colour, read from the file the recipe names.

    Falls back to the RULED numbers, never to this tool's old literals, and
    prints when it falls back -- a silent fallback to a stale default is how the
    ruled colour got overwritten seven times in one day.
    """
    try:
        with open(RULED_COLOUR_FILE, encoding="utf-8") as fh:
            sc = json.load(fh)["scalars"]
        return {"hairMelanin": float(sc["hairMelanin"]),
                "hairRedness": float(sc["hairRedness"])}
    except Exception as e:
        sys.stderr.write(
            "  WARNING: could not read the ruled colour from %s (%s); using the "
            "ruled fallback %s\n" % (RULED_COLOUR_FILE, e, RULED_COLOUR_FALLBACK))
        return dict(RULED_COLOUR_FALLBACK)


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO, **kw)


def marker(txt, tag):
    i = txt.find(tag)
    if i < 0:
        return None
    return json.loads(txt[i + len(tag):].splitlines()[0])


def ue(payload, sets, want):
    a = [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         os.path.join(LIK, payload), "--timeout", "25"]
    for k, v in sets:
        a += ["--set", "%s=%s" % (k, v)]
    txt = "".join(x for x in run(a).__dict__.values() if isinstance(x, str))
    dec = json.JSONDecoder()
    for i, ch in enumerate(txt):
        if ch != "{":
            continue
        try:
            o, _ = dec.raw_decode(txt[i:])
        except ValueError:
            continue
        if isinstance(o, dict) and want in o:
            return o
    raise SystemExit("REFUSE: no JSON with %r from %s\n%s"
                     % (want, payload, txt[-1200:]))


def shot(out_dir, name, loc, rot, settle=6.0):
    pre = ue("console_and_camera.txt",
             [("CAM_LOC", json.dumps(loc)), ("CAM_ROT", json.dumps(rot)),
              ("CMDS", "[]"), ("SHOT", "0"), ("SETTLE", "0")], "shot_dir")
    sd, before = pre["shot_dir"], pre.get("before_files", [])
    ue("console_and_camera.txt",
       [("CAM_LOC", "None"), ("CAM_ROT", "None"), ("CMDS", "[]"),
        ("SHOT", "1"), ("SETTLE", "%g" % settle)], "shot_dir")
    t0 = time.time()
    while time.time() - t0 < 90:
        new = sorted(set(os.listdir(sd)) - set(before))
        if new:
            f = os.path.join(sd, new[-1])
            s = os.path.getsize(f)
            time.sleep(0.6)
            if os.path.getsize(f) == s and s > 0:
                dst = os.path.join(out_dir, name + ".png")
                os.replace(f, dst)
                return dst
        time.sleep(0.4)
    return None


POSES = [
    ("front", [HEAD[0] - 75.0, HEAD[1], HEAD[2] + 4.0], [0.0, -2.0, 0.0]),
    ("threequarter", [HEAD[0] - 62.0, HEAD[1] - 45.0, HEAD[2] + 8.0],
     [0.0, -5.0, 36.0]),
    ("rear", [HEAD[0] + 78.0, HEAD[1], HEAD[2] + 6.0], [0.0, -4.0, 180.0]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out-dir", required=True)
    # THE COLOUR DEFAULTS COME FROM THE RULED RECIPE, NOT FROM THIS FILE.
    #
    # These were literals 0.92 / 0.28 and they silently overwrote the operator's
    # ruled colour on EVERY run -- six times on 2026-08-23 before it was
    # noticed, and once more immediately after the recipe was locked, because a
    # locked recipe does not stop a tool that carries its own copy of the value.
    # `MI_AlpineHero_CustomHair` is ONE material instance shared by whatever
    # groom is mounted, so this tool is the most frequent writer of a value it
    # does not own.
    #
    # Two lists that must agree are one list badly stored (non-negotiable 24).
    # The single declaration is the shipped params file that R-HAIRCOLOUR names;
    # this reads it, and falls back to the ruled numbers rather than to the old
    # literals if it cannot be read -- and says so.
    _ruled = RULED_COLOUR()
    ap.add_argument("--melanin", type=float, default=_ruled["hairMelanin"])
    ap.add_argument("--redness", type=float, default=_ruled["hairRedness"])
    a = ap.parse_args()
    if not os.path.isabs(a.out_dir):
        raise SystemExit("REFUSE: --out-dir must be ABSOLUTE.")
    os.makedirs(a.out_dir, exist_ok=True)
    rep = {"cycle": a.name, "blend": a.blend}

    abc = os.path.join(REPO, "hero", "groomloop", "exports",
                       "difflocks_%s_ue.abc" % a.name)
    p = run([BLENDER, "--background", a.blend, "--python",
             os.path.join(REPO, "hero", "groomloop", "scripts",
                          "export_hero_groom.py"), "--", abc])
    ex = marker(p.stdout + p.stderr, "__EXPORT__")
    if not ex or not ex.get("ok"):
        raise SystemExit("EXPORT REFUSED: %s" % (ex or p.stderr[-800:]))
    rep["export"] = {"widths": ex["abc_widths"], "root_uv": ex["abc_root_uv"],
                     "sidecar": ex.get("sidecar")}
    print("  export      : widths max %g, root UVs %d distinct"
          % (ex["abc_widths"]["max"], ex["abc_root_uv"]["unique"]))

    groom = "%s/AlpineHero_%s" % (GROOMS, a.name)
    bind = "%s/BND_%s" % (GROOMS, a.name)
    bound = "%s/AlpineHero_%s_bound" % (GROOMS, a.name)

    im = ue("import_groom_abc_payload.txt",
            [("ABC_PATH", abc.replace("\\", "/")), ("DST_GROOM", groom),
             ("EXPECT_CURVES", str(ex["curves"]))], "total_curves")
    if not im.get("curve_count_matches"):
        raise SystemExit("IMPORT count mismatch: %s" % im)
    print("  import      : %d curves" % im["total_curves"])

    run([sys.executable, os.path.join(LIK, "place_hero_in_world.py"),
         "--dist", "170", "--respawn", "yes"])
    ok = False
    for _ in range(3):
        b = ue("fresh_bind_payload.txt",
               [("GROOM", groom), ("SOURCE_MESH", ""), ("BIND_PATH", bind),
                ("DEST_GROOM", bound), ("SUBJECT", "HeroInWorld")], "ok")
        if b.get("ok") and (b.get("readback") or {}).get("binding"):
            ok = True
            break
    if not ok:
        raise SystemExit("BIND never took after 3 attempts")
    print("  bind        : %s" % b["readback"]["binding"])

    c = ue("custom_hair_color_payload.txt",
           [("MI_PATH", "%s/MI_AlpineHero_CustomHair" % GROOMS),
            ("PARENT", "/MetaHumanCharacter/Materials/MI_Hair"),
            ("MELANIN", "%g" % a.melanin), ("REDNESS", "%g" % a.redness),
            ("SUBJECT", "HeroInWorld"), ("SLOT", "Hair"),
            ("BINDING", bind)], "ok")
    # The payload reads melanin/redness back and raises (ok stays False) if
    # either did not apply -- honour that verdict, not just the binding side
    # effect. Checking only binding_after let a failed colour readback surface
    # as a misleading "colour nulled the binding".
    if not c.get("ok"):
        raise SystemExit("COLOUR/BINDING REFUSED: %s" % c.get("error"))
    if c.get("binding_after") != os.path.basename(bind):
        raise SystemExit("colour nulled the binding: %s" % c.get("binding_after"))
    print("  colour      : %s, binding held" % c["readback"])

    g = run([sys.executable, os.path.join(LIK, "groom_presence.py"),
             "--out-dir", a.out_dir, "--stamp", a.name])
    echoed = 0
    for line in (g.stdout + g.stderr).splitlines():
        if "Hair " in line:
            print("  gate        :" + line.split("Hair")[1][:78])
            echoed += 1
    # This IS the presence gate (the docstring says so): its verdict lives in
    # the child's EXIT CODE, not in the "Hair " echo. Ignoring the code let a
    # failed presence check fall straight through to the frame captures, and a
    # zero-echo run (label change / crash) read as a silent pass (NN13).
    if g.returncode != 0:
        raise SystemExit(
            "PRESENCE GATE REFUSED (rc=%d):\n%s"
            % (g.returncode, (g.stdout + g.stderr)[-1200:]))
    if echoed == 0:
        print("  gate        : (passed rc=0; no 'Hair ' line to echo)")

    # shot() returns None on a 90 s timeout; a discarded None let the cycle
    # report success over frames that never rendered. Refuse on any miss and
    # record the frames actually produced.
    frames = []
    for tag, loc, rot in POSES:
        dst = shot(a.out_dir, "%s_alpine_%s" % (a.name, tag), loc, rot)
        if dst is None:
            raise SystemExit("SHOT FAILED (timeout): %s_alpine_%s"
                             % (a.name, tag))
        frames.append(dst)
    ue("neutral_light.txt", [("ACTION", "spawn"), ("HEAD", json.dumps(HEAD)),
                             ("INTENS", "180000")], "ok")
    for tag, loc, rot in POSES[:2]:
        dst = shot(a.out_dir, "%s_neutral_%s" % (a.name, tag), loc, rot,
                   settle=8.0)
        if dst is None:
            raise SystemExit("SHOT FAILED (timeout): %s_neutral_%s"
                             % (a.name, tag))
        frames.append(dst)
    ue("neutral_light.txt", [("ACTION", "remove"), ("HEAD", json.dumps(HEAD)),
                             ("INTENS", "0")], "ok")
    rep["frames"] = frames

    with open(os.path.join(a.out_dir, "%s_cycle.json" % a.name), "w",
              encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print("  frames      : %d written to %s" % (len(frames), a.out_dir))


if __name__ == "__main__":
    main()
