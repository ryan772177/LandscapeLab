"""Move a REGION of a DNA's head geometry, in the DNA's own coordinate space.

WHY GEOMETRY AND NOT JOINTS
---------------------------
Ruled 2026-08-17 after measurement: a neutral-joint-translation edit is
invisible through `import_from_face_dna`, because `FitToFaceDna` fits the
parametric face state to the DNA's GEOMETRY and never reads the neutral
joints. The identity arm and the joints-only arm came back at 1.13x and
1.26x the noise floor -- indistinguishable. Writing joints is dead weight
and a false audit trail, so this replaces it.

What the fit path buys, and it is the reason a raw vertex edit is safe here
at all: `FitToFaceDna` REGENERATES the model state from geometry, so rig
self-consistency -- teeth following, pivots staying honest -- is enforced by
the engine rather than by our edit discipline.

THE SPACE IS THE DNA'S, NOT UE'S
--------------------------------
This file declares `axes X=Left Y=Up Z=Front`, centimetres
(`IDNAReader::GetCoordinateSystem`, `DNACommon.h:47,268`). Measured on
`MHC_AlpineHero_Head.dna`, `head_lod0_mesh` (index 0, 24,049 vertices):

    X (Left)   -19.034 .. 19.034
    Y (Up)     140.878 .. 178.439
    Z (Front)  -11.616 .. 14.988
    teeth_lod0_mesh  Y 156.5 .. 162.1
    eyes             Y 165.6 .. 168.5

So the jaw is LOW Y and FRONT-facing Z, and "down" is -Y. Nothing here
converts to UE space; the caller works in the space the file declares, and
the tool prints that declaration on every run.

ONLY LOD0 IS EDITED by default. The DNA carries 8 LODs of the head; the fit
reads LOD0. The other LODs are deliberately left alone and this is stated
rather than silently assumed.

EXIT CODES
    0  wrote the DNA, self-verified
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  payload error, or the plugin REFUSED (the reason is printed)
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (REPO_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import ue_exec                       # noqa: E402
import capture_shot as CS                         # noqa: E402


PAYLOAD = r'''
import json as _json
import traceback as _tb
import unreal as _u

IN_DNA  = r"__IN_DNA__"
OUT_DNA = r"__OUT_DNA__"
MESH    = __MESH__
BMIN    = __BMIN__
BMAX    = __BMAX__
DELTA   = __DELTA__
FEATHER = __FEATHER__

_out = {"ok": False, "error": None}
try:
    _n, _c, _bmin, _bmax, _mc, _info, _rok, _rerr = \
        _u.LandscapeLabTools.read_dna_meshes(IN_DNA)
    if not _rok:
        raise RuntimeError(_rerr)
    _out["reader_info"] = str(_info)
    _out["mesh_count"] = int(_mc)
    if MESH < int(_mc):
        _out["mesh_name"] = str(_n[MESH])
        _out["mesh_vertices"] = int(_c[MESH])
        _out["mesh_bounds"] = {
            "min": [round(_bmin[MESH].x, 3), round(_bmin[MESH].y, 3),
                    round(_bmin[MESH].z, 3)],
            "max": [round(_bmax[MESH].x, 3), round(_bmax[MESH].y, 3),
                    round(_bmax[MESH].z, 3)]}

    _core, _sel, _cnt, _note, _ok, _err = \
        _u.LandscapeLabTools.write_dna_vertex_delta_in_box(
            IN_DNA, OUT_DNA, MESH,
            _u.Vector(BMIN[0], BMIN[1], BMIN[2]),
            _u.Vector(BMAX[0], BMAX[1], BMAX[2]),
            _u.Vector(DELTA[0], DELTA[1], DELTA[2]),
            FEATHER)
    _out["core"] = int(_core)
    _out["selected"] = int(_sel)
    _out["vertices"] = int(_cnt)
    _out["layer_note"] = str(_note)
    if not _ok:
        raise RuntimeError(_err)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:400]

print("__LL__" + _json.dumps(_out, default=str))
'''


def _triple(text, name):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise SystemExit("%s needs three comma-separated numbers, got %r"
                         % (name, text))
    return [float(p) for p in parts]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=CS.DEFAULT_MANIFEST)
    ap.add_argument("--in-dna", default=None,
                    help="defaults to the manifest's canonical DNA")
    ap.add_argument("--out-dna", required=True)
    ap.add_argument("--mesh", type=int, default=0,
                    help="0 is head_lod0_mesh; confirmed by name on every run")
    ap.add_argument("--region", default=None,
                    help="named region from the manifest's geometry_regions; "
                         "supplies mesh, box and feather band")
    ap.add_argument("--box-min", default=None,
                    help="x,y,z in the DNA's OWN space (X=Left Y=Up Z=Front)")
    ap.add_argument("--box-max", default=None)
    ap.add_argument("--feather", type=float, default=None,
                    help="feather band in cm. The box is the CORE and weight "
                         "falls smoothstep to 0 at box+band. 0 is a HARD box, "
                         "which CHANGES THE ATTENUATION IT MEASURES because "
                         "seam vertices drag their unmoved neighbours through "
                         "skinning and the fit")
    ap.add_argument("--delta", required=True,
                    help="x,y,z centimetres in the DNA's OWN space")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    man = CS.load_manifest(args.manifest)
    in_dna = args.in_dna or CS.resolve(man, "dna_canonical")
    out_dna = args.out_dna
    if not os.path.isabs(out_dna):
        out_dna = os.path.join(REPO_ROOT, out_dna)
    os.makedirs(os.path.dirname(out_dna), exist_ok=True)

    mesh = args.mesh
    feather = args.feather
    if args.region:
        regions = man.get("geometry_regions") or {}
        if args.region not in regions:
            raise SystemExit(
                "manifest has no geometry_regions[%r]; it has %s"
                % (args.region, sorted(k for k in regions if k[0] != "_")))
        reg = regions[args.region]
        bmin = [float(v) for v in reg["box_min"]]
        bmax = [float(v) for v in reg["box_max"]]
        mesh = int(reg["mesh"])
        if feather is None:
            feather = float(reg["feather_band_cm"])
        print("region     %s (from the manifest)" % args.region)
    else:
        if not args.box_min or not args.box_max:
            raise SystemExit("give --region, or both --box-min and --box-max")
        bmin = _triple(args.box_min, "--box-min")
        bmax = _triple(args.box_max, "--box-max")
    if feather is None:
        # No default. A hard box is a measurement decision, not a fallback.
        raise SystemExit(
            "--feather is required without --region. 0 is a HARD box and "
            "changes the attenuation it is used to measure; state it.")
    delta = _triple(args.delta, "--delta")

    rc, d, _ = ue_exec.run(
        CS._fill(PAYLOAD, IN_DNA=in_dna, OUT_DNA=out_dna, MESH=mesh,
                 BMIN=bmin, BMAX=bmax, DELTA=delta,
                 FEATHER=float(feather)),
        timeout=args.timeout, stage_name="hero_dna_geometry")
    if rc == 3:
        return 3
    if d is None:
        print("no result from the payload")
        return 5

    print("reader     %s" % d.get("reader_info"))
    print("mesh       %d %s  (%s vertices)"
          % (mesh, d.get("mesh_name"), d.get("mesh_vertices")))
    print("bounds     %s" % d.get("mesh_bounds"))
    print("box        %s .. %s" % (bmin, bmax))
    print("delta      %s cm" % delta)
    print("feather    %.3f cm smoothstep  (0 would be a HARD box)"
          % float(feather))
    if d.get("error"):
        print()
        print("REFUSED / FAILED:")
        print("  %s" % d["error"].split(" | ")[0])
        return 5
    print("weighted   %d of %d vertices, %d at full weight"
          % (d["selected"], d["vertices"], d.get("core", -1)))
    print("layer      %s" % d["layer_note"])
    print()
    print("wrote %s" % os.path.relpath(out_dna, REPO_ROOT))
    print("ONLY THIS MESH WAS EDITED. The DNA carries 8 head LODs; the fit")
    print("reads LOD0 and the others are deliberately untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
