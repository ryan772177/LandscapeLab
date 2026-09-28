"""compare_to_reference.py — a character's grooming beside its ruled look.

CHARACTER-AGNOSTIC BY CONSTRUCTION
----------------------------------
The reference is a PARAMETER resolved through `characters/registry.json`, not
a path compiled into this file. LandscapeLab is heading toward party
development, and a comparison tool with the hero's face baked in is wrong the
moment there is a second character — wrong SILENTLY, because it would judge
party member two against the hero's reference and still print a number.
`--character` selects; the hero is invocation #1, not the design.

WHICH REFERENCE, AND WHY IT IS NOT A CHOICE
-------------------------------------------
Every character declares TWO targets and they are not interchangeable: an
APPEARANCE target (grooming, colour, wardrobe) and a SHAPE target (geometry,
the fit). Confusing them cost this project 1.29 cm of jaw width — the fit
widened the mandible to match a beard. This tool hash-checks the reference it
was given against that character's declaration and REFUSES the shape target
outright.

Each character's appearance target and its sha256 are declared ONLY in
`characters/registry.json`; this tool reads them from there and hash-checks the
reference against them. No path or hash is baked into this file, so nothing
here can rot when the registry is re-pointed.

WHAT IT IS FOR, AND WHAT IT CANNOT SETTLE
-----------------------------------------
Grooming is an ART judgement and this tool does not make it. It puts the two
images side by side at a matched face size so a human can. The crops are
constants in this file rather than eyeballed per run, so two comparisons taken
weeks apart are actually comparable -- the same reason the capture stage is
framed once and then locked. NOTE: only the render's pixel SIZE (2048 square)
is verified here; the capture FRAMING (dist/fov/cam-up) is assumed, not read
back, so a 2048-square frame shot at a different framing would be cropped
wrongly. A non-2048 render is REFUSED rather than cropped.

It does NOT compare colour numerically. The reference is flat studio light and
our renders are a low warm alpine sun with half the face in shadow; an
absolute RGB difference between those two is a statement about the lamps.
`groom_presence.py` measures what is PRESENT; the eye judges whether it is
RIGHT; and any tone claim needs both subjects under the same rig.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

REGISTRY = os.path.join(REPO_ROOT, "characters", "registry.json")


def _resolve(character: str):
    """Appearance and shape targets for a character, from the registry.

    The reference is a PARAMETER, not a constant. A comparison tool with one
    character's face compiled into it is wrong the moment there is a second
    character, and wrong silently -- it would judge party member two against
    the hero's reference and report a number.
    """
    with open(REGISTRY, "r", encoding="utf-8") as fh:
        reg = json.load(fh)
    chars = reg.get("characters", {})
    if character not in chars:
        raise KeyError("no character %r in the registry; it has %s"
                       % (character, ", ".join(sorted(chars))))
    ref = chars[character]["reference"]
    return (os.path.join(REPO_ROOT, ref["appearance"]["path"]),
            ref["appearance"]["sha256"], ref["shape"]["sha256"])

# Fixed crops, so successive comparisons are comparable. The render box is
# quoted for a 2048 square shot at --dist 110 --fov 26 --cam-up 152
# --look-up 158, which is the framing the first comparison used.
REF_BOX = (330, 0, 1010, 768)
REN_BOX = (330, 60, 1720, 1620)
HEIGHT = 880


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render", required=True,
                    help="a 2048 square frame at the documented framing")
    ap.add_argument("--out", required=True)
    ap.add_argument("--character", default="AlpineHero",
                    help="resolved through characters/registry.json, which is "
                         "the single declaration of which image each "
                         "character's look answers to")
    ap.add_argument("--reference", default=None,
                    help="override the registry's appearance target. Still "
                         "hash-checked against that character's declaration, "
                         "so this cannot quietly become a different image.")
    ap.add_argument("--previous", default=None,
                    help="the LAST ACCEPTED state, rendered at the same "
                         "framing. Given, the sheet is three panels: "
                         "reference | previous | current -- which is the only "
                         "arrangement that shows whether a change moved "
                         "TOWARDS the target or merely moved.")
    ap.add_argument("--label", default=None,
                    help="what changed this cycle, e.g. "
                         "'hair_tip_scale 0.85 -> 0.60'. Drawn on the sheet, "
                         "because a comparison whose caption lives in a chat "
                         "message stops being evidence the moment it scrolls.")
    args = ap.parse_args(argv)

    try:
        default_ref, ref_sha, shape_sha = _resolve(args.character)
    except (OSError, ValueError, KeyError) as exc:
        # ValueError covers a corrupt registry.json (JSONDecodeError); KeyError
        # a registry missing reference/appearance/shape sub-keys -- both must be
        # a clean REFUSE (exit 2), not an uncaught traceback.
        print("REFUSE:", exc)
        return 2
    reference = args.reference or default_ref

    if not os.path.isfile(reference):
        print("REFUSE: no reference at", reference)
        return 2
    if not os.path.isfile(args.render):
        print("REFUSE: no render at", args.render)
        return 2

    got = sha256(reference)
    if got == shape_sha:
        print("REFUSE: that is %s's SHAPE target. Grooming answers to the "
              "APPEARANCE target. Confusing the two cost 1.29 cm of jaw "
              "once already." % args.character)
        return 2
    if got != ref_sha:
        print("REFUSE: the reference does not hash to %s's declared "
              "appearance target.\n  expected %s\n  got      %s\n"
              "A comparison against an unrecorded image is not evidence about "
              "the ruled look." % (args.character, ref_sha, got))
        return 2

    ref = Image.open(reference).convert("RGB")
    ren = Image.open(args.render).convert("RGB")
    print("character : %s" % args.character)
    print("reference : %s  %s" % (os.path.basename(reference), ref.size))
    print("render    : %s  %s" % (os.path.basename(args.render), ren.size))
    if ren.size != (2048, 2048):
        # The fixed REN_BOX assumes a 2048-square source; cropping anything else
        # produces a mis-framed sheet that LOOKS like a valid one. Refuse rather
        # than emit a non-comparable artefact with exit 0.
        print("REFUSE: the render is %s, not 2048 square; the fixed crop would "
              "mis-frame it and the sheet would not be comparable." % (ren.size,))
        return 2

    panels = [(ref.crop(REF_BOX), "REFERENCE")]
    if args.previous:
        if not os.path.isfile(args.previous):
            print("REFUSE: no previous frame at", args.previous)
            return 2
        prev = Image.open(args.previous).convert("RGB")
        if prev.size != (2048, 2048):
            print("REFUSE: the previous frame is %s, not 2048 square; it would "
                  "be cropped with the same box and mis-framed." % (prev.size,))
            return 2
        panels.append((prev.crop(REN_BOX), "PREVIOUS (last accepted)"))
    panels.append((ren.crop(REN_BOX), "CURRENT"))

    scaled = []
    for im, cap in panels:
        s = im.resize((int(im.width * HEIGHT / im.height), HEIGHT),
                      Image.LANCZOS)
        scaled.append((s, cap))

    bar = 34
    gap = 10
    width = sum(s.width for s, _ in scaled) + gap * (len(scaled) - 1)
    sheet = Image.new("RGB", (width, HEIGHT + bar), (22, 22, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    x = 0
    for s, cap in scaled:
        sheet.paste(s, (x, bar))
        draw.text((x + 8, 9), cap, fill=(235, 235, 235), font=font)
        x += s.width + gap
    if args.label:
        w = draw.textlength(args.label, font=font) if hasattr(
            draw, "textlength") else 8 * len(args.label)
        draw.text((max(width - w - 10, 0), 9), args.label,
                  fill=(255, 210, 120), font=font)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sheet.save(args.out)
    if not (os.path.isfile(args.out) and os.path.getsize(args.out) > 0):
        print("REFUSE: sheet %s did not write to disk." % args.out)
        return 2
    print("wrote %s %s (%d bytes)   | %s"
          % (args.out, sheet.size, os.path.getsize(args.out),
             "  |  ".join(c for _, c in scaled)))
    if args.label:
        print("label: %s" % args.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
