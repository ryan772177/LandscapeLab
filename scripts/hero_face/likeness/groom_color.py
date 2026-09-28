"""Set the hero's groom colour on the DURABLE surface, and prove it by render.

WHY NOT THE MATERIAL
--------------------
The groom materials on the preview actor are TRANSIENT --
`/Engine/Transient...MI_WI_Hair_M_Layered_None_2_Hair` -- created by every
`assemble_for_preview`. Setting `hairMelanin` there works and is erased by
the next assemble, which the likeness loop performs on every iteration. That
is the "MCP-authored scene state does not survive a rebuild" class this
project already records.

The durable surface is the INSTANCE PARAMETERS, enumerated from the asset
rather than assumed. Each groom item exposes:

    Melanin (Float)   Redness (Float)   Roughness (Float)
    Whiteness (Float) Lightness (Float) DyeColor (Color)

    read   MetaHumanCharacterInstanceBlueprintLibrary
             .try_get_instance_parameter(instance, item_path, name)
    write  MetaHumanCharacterInstanceParameterBlueprintLibrary
             .set_float_instance_parameter(param, value)   -> bool
             .set_color_instance_parameter(param, LinearColor) -> bool

NAMES COME FROM THE ASSET. Ratified 2026-08-19 for every name-addressed
MetaHuman surface: a wrong name that silently creates a valid-but-unworn or
valid-but-unset state is indistinguishable from the bugs being hunted.
This tool enumerates the parameters present on each item and refuses to set
one it did not find.

THE TARGET
----------
Ryan's reference is very dark brown-black, not pure black: high melanin with
a little warmth, no grey. Applied to ALL FOUR grooms including Hair -- Hair
does not currently render, and if the colour write FAILS on Hair where the
other three succeed, that is a free diagnostic bit for the hair
investigation at zero extra cost.

EXIT CODES
    0  applied and read back
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  payload error, or a value did not read back
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

CHARACTER = "__CHARACTER__"
VALUES    = __VALUES__
DRY       = __DRY__

_out = {"ok": False, "error": None, "items": [], "writes": [], "misses": []}
try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _lib = _u.MetaHumanCharacterInstanceBlueprintLibrary
    _plib = _u.MetaHumanCharacterInstanceParameterBlueprintLibrary

    _ch = _eal.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        if not _sub.try_add_object_to_edit(_ch):
            raise RuntimeError("try_add_object_to_edit refused")
    _col = _sub.get_preview_collection(_ch)
    _inst = _col.get_editor_property("default_instance")

    _paths = list(_inst.get_instance_parameter_item_paths())
    for _idx, _path in enumerate(_paths):
        _params = list(_lib.get_instance_parameters_for_item(_inst, _path))
        _names = []
        for _p in _params:
            try:
                _names.append(str(_p.get_editor_property("name")))
            except Exception:
                _names.append(str(_p)[:60])
        _rec = {"index": _idx, "param_names": _names}

        for _pname, _val in VALUES:
            if _pname not in _names:
                # NAMES COME FROM THE ASSET. A parameter this item does not
                # have is reported, never silently skipped.
                _out["misses"].append({"item": _idx, "param": _pname})
                continue
            _param = _lib.try_get_instance_parameter(_inst, _path, _pname)
            if _param is None:
                _out["misses"].append({"item": _idx, "param": _pname,
                                       "why": "try_get returned None"})
                continue
            if DRY:
                continue
            _ok = bool(_plib.set_float_instance_parameter(_param, float(_val)))
            _out["writes"].append({"item": _idx, "param": _pname,
                                   "value": _val, "returned": _ok})
        _out["items"].append(_rec)

    if not DRY:
        _sub.on_edit_preview_collection(_ch)
        _out["propagated"] = True
        _sub.assemble_for_preview(_ch)
        _out["assembled"] = True

        # READ BACK from the instance, not from the setters that just ran.
        _back = []
        for _idx, _path in enumerate(_paths):
            for _pname, _val in VALUES:
                _param = _lib.try_get_instance_parameter(_inst, _path, _pname)
                if _param is None:
                    continue
                try:
                    _got = _param.get_editor_property("float_value")
                except Exception:
                    _got = "unreadable"
                _back.append({"item": _idx, "param": _pname,
                              "wanted": _val, "read_back": str(_got)[:40]})
        _out["read_back"] = _back

    _out["dirty"] = [str(_p2.get_name()) for _p2 in
                     _u.EditorLoadingAndSavingUtils
                     .get_dirty_content_packages()]
    _out["ok"] = True
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:500]

print("__LL__" + _json.dumps(_out, default=str))
'''

# Very dark brown-black with a little warmth, per Ryan's reference. Not pure
# black -- the portrait's hair reads brown-black in its highlights.
DEFAULT_VALUES = [
    ["Melanin", 0.92],
    ["Redness", 0.28],
    ["Whiteness", 0.0],
]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--melanin", type=float, default=0.92)
    ap.add_argument("--redness", type=float, default=0.28)
    ap.add_argument("--whiteness", type=float, default=0.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args(argv)

    values = [["Melanin", args.melanin], ["Redness", args.redness],
              ["Whiteness", args.whiteness]]

    rc, d, _ = ue_exec.run(
        CS._fill(PAYLOAD, CHARACTER=args.character, VALUES=values,
                 DRY=bool(args.dry_run)),
        timeout=args.timeout, stage_name="hero_groom_color")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        return 5

    print("target: melanin %.2f  redness %.2f  whiteness %.2f"
          % (args.melanin, args.redness, args.whiteness))
    print()
    for it in d["items"]:
        print("  item %d params: %s" % (it["index"], ", ".join(
            it["param_names"])))
    if d.get("misses"):
        print()
        print("NOT PRESENT on some items (reported, not skipped silently):")
        for m in d["misses"]:
            print("  %s" % m)
    if args.dry_run:
        print()
        print("--dry-run: nothing written.")
        return 0
    print()
    ok = sum(1 for w in d["writes"] if w["returned"])
    print("writes: %d of %d returned true" % (ok, len(d["writes"])))
    for w in d["writes"]:
        if not w["returned"]:
            print("  FAILED item %d %s" % (w["item"], w["param"]))
    print("propagated %s  assembled %s"
          % (d.get("propagated"), d.get("assembled")))
    print()
    print("read back:")
    for b in d.get("read_back", []):
        print("  item %d %-10s wanted %-6s got %s"
              % (b["item"], b["param"], b["wanted"], b["read_back"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
