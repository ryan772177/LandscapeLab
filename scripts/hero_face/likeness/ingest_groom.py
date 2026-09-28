"""ingest_groom.py — put a groom on a character, for ANY character.

THIS IS PARTY-CHARACTER INFRASTRUCTURE, not a hero tool. The hero is
invocation #1. Every path is resolved from `characters/registry.json`, so a
second character costs a registry entry rather than a fork of this file.

    python ingest_groom.py --character AlpineHero --slot Hair \
        --style Shag --version 1 --from-asset <vendor groom path>
    python ingest_groom.py --character AlpineHero --slot Hair \
        --style Shag --version 2 --abc  C:/authoring/shag_v2.abc

THE TWO INVARIANTS, both measured rather than assumed (RECIPES R-GROOMBIND)
------------------------------------------------------------------------
1. THE GROOM MUST LIVE IN PROJECT CONTENT. A groom in a vendor plugin's
   content binds cleanly, reports every property correctly, and DRAWS
   NOTHING -- bald at 60 s and at 90 s. The same asset duplicated into
   project content renders at 87x the repeat floor. So the duplicate is a
   precondition, not housekeeping.
2. EVERY GROOM GETS A BINDING BUILT AGAINST THE TARGET CHARACTER'S OWN FACE
   MESH, read off the placed actor rather than named by convention. Vendor
   bindings target `SKM_Groom_Head_Legacy01` and render EXPLODED on our
   heads -- a loud failure, unlike the silent bald one, and the only reason
   it was ever noticed.

COLOUR GOES ON A MATERIAL WE OWN. A directly-assigned groom renders with the
vendor material, so the character-instance colour surface the wardrobe path
uses never reaches it. This writes a project-content material instance and
sets it on the component, walking up the parent chain first so a re-run
cannot make an instance its own parent -- a trap this project paid for once
already in the face-texture bake.

THE ALEMBIC ROUTE IS IMPLEMENTED AND UNEXERCISED. No .abc has been authored
for this project yet. It is written so the Blender round trip has somewhere
to land, and both the tool and its output say UNEXERCISED so nobody mistakes
it for a proven path. `--from-asset` is the proven one.

Exit codes:
    0  ingested, assigned, read back
    2  bad arguments / unknown character / missing source, OR a draw-gate
       refusal (missing/mismatched sidecar, or zero/unreadable widths)
    3  no editor matched UE_PROJECT_ROOT (standing rule 7)
    5  payload error, a non-zero payload exit, the payload produced no marker,
       or a read-back disagreed (groom name, vendor-legacy bind target, or
       colour not written)
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts import ue_exec                      # noqa: E402

REGISTRY = os.path.join(REPO_ROOT, "characters", "registry.json")
PAYLOAD = os.path.join(_HERE, "ingest_groom_payload.txt")

# Matches the assembled bindings, which is where the number came from rather
# than from a default anyone liked the look of.
INTERP_POINTS = 100

# The material every ingested groom is coloured through. DECLARED rather than
# discovered from component state -- see the payload for why both discovery
# routes are wrong -- and shared across hairs so a catalogue is comparable.
GROOM_MATERIAL_MASTER = "/MetaHumanCharacter/Materials/MI_Hair"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="AlpineHero")
    ap.add_argument("--slot", default="Hair",
                    choices=("Hair", "Beard", "Mustache", "Eyebrows"))
    ap.add_argument("--style", required=True,
                    help="the style name, e.g. Shag. Becomes <Char>_<Style>_vN")
    ap.add_argument("--version", type=int, default=1)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-asset", help="an existing GroomAsset to duplicate")
    src.add_argument("--abc", help="an Alembic file to import (UNEXERCISED)")
    ap.add_argument("--melanin", type=float, default=0.92)
    ap.add_argument("--redness", type=float, default=0.28)
    ap.add_argument("--whiteness", type=float, default=0.0)
    ap.add_argument("--subject", default="HeroInWorld",
                    help="the placed actor whose face mesh is the bind target")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--no-draw-gate", action="store_true",
                    help="skip the zero-width sidecar gate. The escape exists "
                         "because an .abc can legitimately predate the gate; "
                         "using it is a claim you own.")
    args = ap.parse_args(argv)

    if not os.path.isfile(REGISTRY):
        print("REFUSE: no registry at", REGISTRY)
        return 2
    with open(REGISTRY, "r", encoding="utf-8") as fh:
        reg = json.load(fh)
    chars = reg.get("characters", {})
    if args.character not in chars:
        # Build the message from the GUARDED value: reg["characters"] would
        # KeyError on a registry with no characters key -- the very case the
        # .get above was written to tolerate.
        print("REFUSE: no character %r in the registry; it has %s"
              % (args.character, ", ".join(sorted(chars))))
        return 2
    ch = chars[args.character]
    groom_root = ch.get("ue_groom_content",
                        "/Game/Characters/%s/Grooms/" % args.character).rstrip("/")

    asset_name = "%s_%s_v%d" % (args.character, args.style, args.version)
    dst_groom = "%s/%s" % (groom_root, asset_name)
    bind_path = "%s/Bindings/BND_%s" % (groom_root, asset_name)
    mi_dir = "%s/Materials" % groom_root

    # ---- THE DRAW GATE. Fails closed on the defect that cost nine days.
    #
    # 2026-08-22: an exporter silently skipped `groom_width`; the .abc shipped a
    # PRESENT, correct-length, correctly-typed widths array of ZEROS; the groom
    # bound, reported the right curve count and correct bounds, read back
    # correctly on every property, and drew nothing.
    #
    # It cannot be caught HERE by inspection. `max_import_width` is not a
    # reflected property on GroomAsset in 5.8 (measured -- it raises), so the
    # widths are invisible from UE; and PyAlembic ships inside the Blender
    # add-on and will not load in system Python (ImportError: DLL load failed),
    # so this process cannot open the file either.
    #
    # The only process that can see them is the exporter. It now writes
    # `<abc>.groomstats.json` recording the widths and root UVs it verified by
    # REOPENING the file it wrote, plus the sha256 of that file. This refuses
    # anything without a matching sidecar -- which is every .abc produced before
    # the fix, by an unpatched process, or by another tool.
    if args.abc and os.path.isfile(args.abc) and not args.no_draw_gate:
        side_p = args.abc + ".groomstats.json"
        if not os.path.isfile(side_p):
            print("REFUSE: no draw-gate sidecar beside", args.abc)
            print("  expected:", side_p)
            print("  An .abc with no sidecar was not produced by the fixed")
            print("  export path and may carry zero widths, which binds")
            print("  cleanly and draws nothing. Re-export through")
            print("  hero/groomloop/scripts/export_hero_groom.py, or pass")
            print("  --no-draw-gate and say in the commit why.")
            return 2
        with open(side_p, "r", encoding="utf-8") as fh:
            side = json.load(fh)
        actual = _sha256(args.abc)
        if side.get("abc_sha256") != actual:
            print("REFUSE: sidecar hash does not match the .abc.")
            print("  sidecar:", side.get("abc_sha256"))
            print("  actual :", actual)
            print("  The file changed after it was gated; the sidecar")
            print("  describes a different artefact.")
            return 2
        w = side.get("widths")
        # w.get("max") can be null (present-but-None), which float() would crash
        # on -- the exact malformed-sidecar case the gate exists to reject.
        _mx = w.get("max") if isinstance(w, dict) else None
        if not isinstance(w, dict) or w.get("all_zero") \
                or not isinstance(_mx, (int, float)) or float(_mx) <= 0.0:
            print("REFUSE: sidecar reports widths", w)
            print("  A groom with zero/unreadable width draws zero pixels.")
            return 2
        print("draw gate     : PASS  widths max %g, root UVs %s distinct, "
              "exporter %s" % (w.get("max"),
                               (side.get("root_uv") or {}).get("unique"),
                               side.get("exporter_sha256_16")))

    if args.abc and not os.path.isfile(args.abc):
        print("REFUSE: no alembic at", args.abc)
        return 2

    with open(PAYLOAD, "r", encoding="utf-8") as fh:
        text = fh.read()
    for k, v in (("CHARACTER", args.character), ("SUBJECT", args.subject),
                 ("SLOT", args.slot),
                 ("SRC_GROOM", args.from_asset or ""),
                 ("DST_GROOM", dst_groom),
                 ("ABC_PATH", (args.abc or "").replace("\\", "/")),
                 ("BIND_PATH", bind_path),
                 ("INTERP_PT", str(INTERP_POINTS)),
                 ("MELANIN", repr(args.melanin)),
                 ("REDNESS", repr(args.redness)),
                 ("WHITENESS", repr(args.whiteness)),
                 ("MI_DIR", mi_dir),
                 ("HAIR_MASTER", GROOM_MATERIAL_MASTER)):
        text = text.replace("__" + k + "__", v)

    if args.abc:
        print("NOTE: the ALEMBIC route is UNEXERCISED -- no .abc has been "
              "authored for this project yet. Treat the result as a first "
              "run, not as a proven path.")

    rc, d, _raw = ue_exec.run(text, timeout=args.timeout,
                              stage_name="ingest_groom")
    if rc == 3:
        return 3
    if d is None:
        print("COULD NOT LOOK: the payload produced no marker.")
        return 5
    if d.get("error"):
        print("PAYLOAD ERROR:", d["error"])
        return 5
    if rc not in (0,):
        # Trust the process status too, not only the dict: a non-zero exit with
        # a marker but no "error" key would otherwise flow through to success.
        print("PAYLOAD exited %d without an error marker -- refusing." % rc)
        return 5

    print("character      :", args.character)
    print("slot           :", args.slot)
    print("groom          :", dst_groom)
    print("binding        :", bind_path)
    print("target mesh    :", d.get("target_mesh"))
    print("curves/guides  : %s / %s" % (d.get("num_curves"), d.get("num_guides")))
    print("steps          :", "; ".join(d.get("steps", [])))
    print("colour written :", d.get("colour_params_written"))
    print("material       : %s  (parent %s)"
          % (d.get("material_instance"), d.get("material_parent")))
    print("timings        :", json.dumps(d.get("t")))
    print("read back      :", json.dumps(d.get("readback")))

    rb = d.get("readback") or {}
    if rb.get("groom") != asset_name:
        print("REFUSE: the component read back groom %r, wanted %r"
              % (rb.get("groom"), asset_name))
        return 5

    # Invariant 2 (docstring): the bind target must be the character's OWN face
    # mesh. The vendor legacy head renders EXPLODED; refuse it rather than only
    # print target_mesh and exit 0.
    tm = d.get("target_mesh") or ""
    if "SKM_Groom_Head_Legacy01" in tm:
        print("REFUSE: bound against the vendor legacy head %r, which renders "
              "EXPLODED. Rebind against the subject's own face mesh." % tm)
        return 5

    # The docstring makes colour a core function and exit 0 claims "read back";
    # honour the payload's own colour_params_written verdict rather than only
    # the groom name. (Guarded so an older payload that omits the key is not
    # false-refused; an explicit False refuses.)
    if d.get("colour_params_written") is False:
        print("REFUSE: the payload reported colour params were NOT written to "
              "the owned material instance.")
        return 5

    # PROVENANCE. Every derived asset in this project is either committed or
    # re-derivable from a recorded producer, and a 74 MB groom is firmly the
    # second. This sidecar IS the producer record.
    side_dir = os.path.join(REPO_ROOT, "characters", args.character, "grooms")
    os.makedirs(side_dir, exist_ok=True)
    side = {
        "asset": dst_groom,
        "character": args.character,
        "slot": args.slot,
        "style": args.style,
        "version": args.version,
        "ingested_utc": datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "source": {
            "kind": "alembic" if args.abc else "duplicated_asset",
            "path": args.abc or args.from_asset,
            "sha256": _sha256(args.abc) if args.abc else None,
            "_note": ("Alembic route is UNEXERCISED as of this write."
                      if args.abc else
                      "Vendor asset duplicated; vendor original untouched."),
        },
        "binding": {
            "path": bind_path,
            "target_mesh": d.get("target_mesh"),
            "num_interpolation_points": INTERP_POINTS,
            "source_skeletal_mesh_for_transfer": None,
            "_why_null": ("The WORKING assembled binding has this null; "
                          "passing the authoring head was tried and changed "
                          "nothing. See RECIPES R-GROOMBIND REJECTED."),
        },
        "colour": {"melanin": args.melanin, "redness": args.redness,
                   "whiteness": args.whiteness,
                   "material_instance": d.get("material_instance"),
                   "written": d.get("colour_params_written")},
        "measured": {"num_curves": d.get("num_curves"),
                     "num_guides": d.get("num_guides"),
                     "timings_s": d.get("t")},
        "_verified_by": ("Assignment read-back only. PIXELS are verified "
                         "separately by groom_presence.py at the framing the "
                         "result will be judged at -- a binding that assigns "
                         "and does not draw reports perfectly here."),
    }
    sp = os.path.join(side_dir, asset_name + ".json")
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(side, fh, indent=2)
    print("provenance     :", sp)
    print()
    print("INGESTED. This proves the asset, the binding and the assignment "
          "exist. It says NOTHING about what will render -- run "
          "groom_presence.py at the judging framing before calling it good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
