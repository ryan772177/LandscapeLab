"""cap_street_textures.py -- cap MaxTextureSize on the street-overlay cobble textures (2026-10-10).

    python scripts/cap_street_textures.py            # read-only: report size/srgb/compression/max_texture_size
    python scripts/cap_street_textures.py --apply    # set max_texture_size = recipe max_texture_px, save, READ BACK

Design review change 4ii (research/town_kit/STREETS_DESIGN.md): T_Cobblestone_A / _N are 8192^2 sources, and
max_texture_size 0 (the default) means "the maximum for the format" (PythonStub :415247), i.e. a full 8K encode on
the first material compile on a cold DDC -- the GroundRevealRock hang class. A 2 m tile at 2048^2 is ~1 mm/texel.
Values from recipes/alpine_8k.json material.street_overlay (albedo, normal, max_texture_px). Idempotent. The
setting lives on the VENDOR asset (Megascans pack, untracked): a re-intake loses it -- recorded in ASSETS.md.
The read-back is a PROPERTY RE-READ from the engine object after the save (rule 12's "property re-read"). It is
NOT a fresh load from disk -- load_asset returns the resident object -- so "persisted" is proven later, by the
material build's preflight in a fresh editor session, not here.
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

REPO = bootstrap.REPO_ROOT
PAYLOAD = r'''
import json as _json, traceback as _tb, unreal as _u
CFG = _json.loads(r"""__CFG__""")
_out = {"ok": False, "rows": []}
try:
    _eal = _u.EditorAssetLibrary
    for _p in CFG["textures"]:
        _t = _eal.load_asset(_p)
        if _t is None:
            raise RuntimeError("texture not found: " + _p)
        _row = {"path": _p, "before": int(_t.get_editor_property("max_texture_size"))}
        if CFG["apply"] and _row["before"] != CFG["max_px"]:
            _t.set_editor_property("max_texture_size", int(CFG["max_px"]))
            if not _eal.save_asset(_p, only_if_is_dirty=False):
                raise RuntimeError("save_asset returned False for " + _p)
        _t2 = _eal.load_asset(_p)
        _row.update({"after": int(_t2.get_editor_property("max_texture_size")),
                     "srgb": bool(_t2.get_editor_property("srgb")),
                     "compression": str(_t2.get_editor_property("compression_settings")),
                     "lod_group": str(_t2.get_editor_property("lod_group")),
                     "source_size": [int(_t2.blueprint_get_size_x()), int(_t2.blueprint_get_size_y())]})
        _out["rows"].append(_row)
    _out["ok"] = True
except Exception as _e:
    _out["error"] = "%s: %s" % (type(_e).__name__, _e)
    _out["traceback"] = _tb.format_exc()
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    rec = json.load(io.open(os.path.join(REPO, "recipes", "alpine_8k.json"), encoding="utf-8"))
    so = (rec.get("material") or {}).get("street_overlay")
    if not so:
        print("REFUSE: no material.street_overlay in recipes/alpine_8k.json")
        return 2
    cfg = {"textures": [so["albedo"], so["normal"]], "max_px": int(so["max_texture_px"]), "apply": a.apply}
    import ue_exec
    code, out, raw = ue_exec.run(PAYLOAD.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=20,
                                 stage_name="cap_street_textures")
    if not isinstance(out, dict) or not out.get("ok"):
        print("FAILED (code %s): %s" % (code, out if isinstance(out, dict) else (raw or "")[-1500:]))
        return 4
    bad = []
    data_group = []
    for r in out["rows"]:
        print("  %-55s max_texture_size %s -> %s  srgb %s  %s  %s  resident %s"
              % (r["path"], r["before"], r["after"], r["srgb"], r["compression"], r["lod_group"],
                 r["source_size"]))
        if a.apply and r["after"] != cfg["max_px"]:
            bad.append(r["path"])
        # audit F4: GetSamplerTypeForTexture branches on LODGroup BEFORE compression
        # (MaterialExpressionUtils.cpp:25-28): an 8Bit/16BitData group derives SAMPLERTYPE_Data, which the
        # material preflight (compression/srgb only) would not catch -- it would die after the graph clear.
        if "8BITDATA" in r["lod_group"].upper().replace("_", "") or "16BITDATA" in r["lod_group"].upper().replace("_", ""):
            data_group.append(r["path"] + " " + r["lod_group"])
    if data_group:
        print("REFUSE: Data LOD group would derive SAMPLERTYPE_Data: %s" % data_group)
        return 6
    if len(out["rows"]) != 2:
        print("REFUSE: read back %d rows, want 2 (rule 13)" % len(out["rows"]))
        return 4
    if bad:
        print("READ-BACK MISMATCH: %s" % bad)
        return 5
    print("applied; property re-read after save (persistence is proven in a fresh session)" if a.apply
          else "read-only (pass --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
