"""Put the hero's grooms back on, and prove they are worn rather than merely
available.

WHY THIS EXISTS
---------------
The grooms were selected once (2026-08-16) and were DROPPED by the repeated
`import_from_face_dna` calls the likeness fit makes -- the pre-fit preview
actor carried a GroomComponent and rendered visible stubble, moustache and
brows; afterwards it carried none. Ruled 2026-08-18 (fable model) as the
highest return-on-effort item remaining: hair and stubble are the largest
differing regions of the comparison frame, and hair does double duty by
covering the temples, which narrows the perceived face for free.

ADDING AN ITEM MAKES IT AVAILABLE. IT IS NOT WORN UNTIL THE INSTANCE SELECTS
IT, and conflating those is how a tool reports success over a bald hero:

    key = collection.try_add_item_from_wardrobe_item(slot_name, wardrobe_item)
    collection.default_instance.set_single_slot_selection(slot_name, key)
    subsystem.on_edit_preview_collection(character)     # NOT OPTIONAL

`on_edit_preview_collection` is required by the engine's own docstring: code
modifying the preview collection must call it to propagate the edits back to
the Character asset.

SLOT NAMES ARE READ FROM THE COLLECTION, never guessed -- `get_slot_names()`
is the contract, and a groom assigned to a slot that does not exist would be
added, selected, and invisible.

This tool leaves the Character DIRTY (preview edit) and does NOT save it -- a
downstream step persists it.

EXIT CODES
    0  grooms applied and read back as selected (in-memory instance)
    2  bad arguments
    3  no editor matched UE_PROJECT_ROOT
    5  payload error, a configured slot is not on the collection, or a
       selection did not read back
"""

from __future__ import annotations

import argparse
import json
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
GROOMS    = __GROOMS__
LIST_ONLY = __LIST_ONLY__

_out = {"ok": False, "error": None, "applied": [], "verified": {}}
try:
    _eal = _u.EditorAssetLibrary
    _sub = _u.get_editor_subsystem(_u.MetaHumanCharacterEditorSubsystem)
    _ch = _eal.load_asset(CHARACTER)
    if _ch is None:
        raise RuntimeError("could not load " + CHARACTER)
    if not _sub.is_object_added_for_editing(_ch):
        if not _sub.try_add_object_to_edit(_ch):
            raise RuntimeError("try_add_object_to_edit refused")

    _col = _sub.get_preview_collection(_ch)
    if _col is None:
        raise RuntimeError("character has no preview collection")
    _slots = [str(s) for s in _col.get_slot_names()]
    _out["slot_names"] = _slots
    if LIST_ONLY:
        _out["ok"] = True
        print("__LL__" + _json.dumps(_out, default=str))
        raise SystemExit(0)

    _inst = _col.get_editor_property("default_instance")
    if _inst is None:
        raise RuntimeError("preview collection has no default instance")

    _keys = {}
    for _slot, _wi_path in GROOMS:
        if _slot not in _slots:
            raise RuntimeError(
                "slot %r is not on this collection; it has %s"
                % (_slot, _slots))
        _wi = _eal.load_asset(_wi_path)
        if _wi is None:
            raise RuntimeError("could not load wardrobe item " + _wi_path)
        # AVAILABLE...
        _key = _col.try_add_item_from_wardrobe_item(_slot, _wi)
        if _key is None:
            raise RuntimeError(
                "try_add_item_from_wardrobe_item returned None for %s in %s"
                % (_wi_path, _slot))
        # ...then WORN.
        _inst.set_single_slot_selection(_slot, _key)
        _keys[_slot] = str(_key)
        _out["applied"].append({"slot": _slot, "item": _wi_path,
                                "key": str(_key)[:120]})

    # REQUIRED: propagate the preview-collection edits back to the Character.
    _sub.on_edit_preview_collection(_ch)
    _out["propagated"] = True

    # Read the selections back off the instance. NOTE this is the SAME in-memory
    # instance the setters just wrote (a true persisted check would reload the
    # Character), so it proves the selection took, not that it persisted. Match
    # on the selection KEY, NOT the slot name: get_slot_selection_data() dumps
    # every slot, so the slot name is in the blob whether or not the groom was
    # selected (the old `_slot in _txt` check could never fail -- a bald hero
    # read as PRESENT).
    try:
        _all = _inst.get_slot_selection_data()
        _out["selection_dump"] = str(_all)[:1200]
        _txt = str(_all)
        for _slot, _wi_path in GROOMS:
            _k = _keys.get(_slot, "")
            _out["verified"][_slot] = (
                "PRESENT" if _k and _k in _txt else "NOT FOUND")
    except Exception as _e2:
        _out["verified"]["_error"] = str(_e2)[:160]

    _sub.assemble_for_preview(_ch)
    _out["assembled"] = True
    _out["dirty"] = [str(_p.get_name()) for _p in
                     _u.EditorLoadingAndSavingUtils
                     .get_dirty_content_packages()]
    _out["ok"] = True
except SystemExit:
    raise
except Exception as _e:
    _out["error"] = str(_e) + " | " + _tb.format_exc()[:500]

print("__LL__" + _json.dumps(_out, default=str))
'''

# RYAN'S RULED GROOM SET, 2026-08-19 (night). Supersedes the 2026-08-16 set.
#
# WHY IT CHANGED, and it was a measurement not a preference. The old set was
# chosen by reading the portrait by eye and was never compared against it
# afterwards. Put side by side (`_verify/20260819_hero_grooms/
# reference_vs_render.png`) three of the four were wrong in KIND:
#
#     was                     reference shows              now
#     Hair_M_Layered          short, spiky, swept fringe,  Hair_M_SideSweptFringe
#       long, straight,         above the shoulder
#       sleek past the jaw
#     Beard_M_Stubble         a full SHORT beard, dense    Beard_S_Full
#       sparse stubble,         on jaw/chin/cheeks
#       0.8% of the face
#     Mustache_M_Stubble      a full moustache joined      Mustache_S_Full
#       faintest groom on       to the beard
#       him, only reads at
#       0.9 m
#     Eyebrows_M_Dense        thick, dark, strong          UNCHANGED -- the
#                                                          one that was right
#
# Hair COLOUR was measured close already (43/35/36 against the reference's
# 34/30/28); it was the STYLE that missed. See LESSONS 2026-08-19 (night).
DEFAULT_GROOMS = [
    # HAIR TRIALS 2026-08-19 (night), all rendered and kept side by side in
    # _verify/20260819_hero_grooms/hair_options_three_way.png so the choice is
    # made on pixels rather than on names:
    #
    #   M_Layered           long, straight, sleek to the chest        too long
    #   M_SideSweptFringe   fringe, ears covered, jaw length, FLAT    closest
    #   S_Messy             short crop, ears bare, no fringe          too short
    #   M_BobMessy          medium AND messy -- the only candidate    <- now
    #                       carrying both properties the others split
    #
    # The reference is a SHAGGY MEDIUM: volume on top, fringe across the brow,
    # ears covered, length to the jaw. Length and texture were the two axes and
    # each earlier trial got one of them.
    ["Hair", "/MetaHumanCharacter/Optional/Grooms/Bindings/Hair/"
             "WI_Hair_M_BobMessy.WI_Hair_M_BobMessy"],
    ["Beard", "/MetaHumanCharacter/Optional/Grooms/Bindings/Beards/"
              "WI_Beard_S_Full.WI_Beard_S_Full"],
    ["Mustache", "/MetaHumanCharacter/Optional/Grooms/Bindings/Mustaches/"
                 "WI_Mustache_S_Full.WI_Mustache_S_Full"],
    ["Eyebrows", "/MetaHumanCharacter/Optional/Grooms/Bindings/Eyebrows/"
                 "WI_Eyebrows_M_Dense.WI_Eyebrows_M_Dense"],
]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", default="/Game/Hero/MHC_AlpineHero")
    ap.add_argument("--list-slots", action="store_true",
                    help="print the collection's slot names and stop")
    ap.add_argument("--hair", default=None,
                    help="override the Hair selection with a wardrobe item "
                         "name, e.g. WI_Hair_L_MessyClumps. For catalogue "
                         "runs, which need one hair per assemble and should "
                         "not be editing a committed declaration to get it.")
    ap.add_argument("--hair-path", default=None,
                    help="full object path to a wardrobe item, for MINTED "
                         "items in project content that have no vendor path")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args(argv)

    grooms = [list(g) for g in DEFAULT_GROOMS]
    if args.hair_path:
        # A MINTED wardrobe item -- one we duplicated and repointed at a custom
        # groom -- lives in project content and has no vendor path to derive.
        if "/" not in args.hair_path:
            print("REFUSE: --hair-path must be an object path containing '/'.")
            return 2
        for g in grooms:
            if g[0] == "Hair":
                g[1] = "%s.%s" % (args.hair_path,
                                  args.hair_path.rsplit("/", 1)[1])
        print("hair overridden (full path) ->", args.hair_path)
    elif args.hair:
        name = args.hair if args.hair.startswith("WI_") else "WI_" + args.hair
        path = ("/MetaHumanCharacter/Optional/Grooms/Bindings/Hair/"
                "%s.%s" % (name, name))
        for g in grooms:
            if g[0] == "Hair":
                g[1] = path
        print("hair overridden ->", name)

    rc, d, _ = ue_exec.run(
        CS._fill(PAYLOAD, CHARACTER=args.character,
                 GROOMS=([] if args.list_slots else grooms),
                 LIST_ONLY=bool(args.list_slots)),
        timeout=args.timeout, stage_name="hero_grooms")
    if rc == 3:
        return 3
    if d is None or d.get("error"):
        print("PAYLOAD ERROR:\n%s" % ((d or {}).get("error") or "no result"))
        return 5

    print("slots on the collection: %s" % ", ".join(d.get("slot_names", [])))
    if args.list_slots:
        return 0
    print()
    for a in d["applied"]:
        print("  %-10s <- %s" % (a["slot"], a["item"].split("/")[-1]))
    print("propagated: %s   assembled: %s"
          % (d.get("propagated"), d.get("assembled")))
    print()
    print("read back from the instance:")
    verified = d.get("verified", {})
    for k, v in verified.items():
        print("  %-10s %s" % (k, v))
    if d.get("dirty"):
        print()
        print("dirty: %s (left dirty for a downstream save; this tool does not "
              "save the Character)" % d["dirty"])
    # GATE THE EXIT on the read-back (docstring: exit 0 = "read back as
    # selected", exit 5 = "a selection did not read back"). Previously the
    # verdict was only printed and exit 0 was unconditional.
    if "_error" in verified:
        print("REFUSE: the read-back accessor failed: %s" % verified["_error"])
        return 5
    not_worn = [g[0] for g in grooms if verified.get(g[0]) != "PRESENT"]
    if not_worn or len(d.get("applied", [])) != len(grooms):
        print("REFUSE: %d groom(s) did not read back as selected: %s"
              % (len(not_worn) or (len(grooms) - len(d.get("applied", []))),
                 not_worn or "applied-count mismatch"))
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
