# HAIR CATALOGUE — 2026-08-20

Sheet: `hair_catalogue.png` (1680 x 4540, 36 hair tiles + the reference).
Index: `index.json`. Every row bound through R-GROOMBIND3 and gated.

## WHAT RAN

    styles in the vendor pack        38
    bound, rendered, gated           36   all PRESENT, all reproduced
    NOT REACHABLE                     2   Hair_M_TwistedBraids, Hair_S_BrushCut

The two unreachable styles ship a groom asset and **no `<name>_Binding`
sibling** — the pack has 38 grooms and 36 bindings, counted by directory
listing. R-GROOMBIND3 duplicates an already-built binding, so those two have
no input to duplicate. That is an absence of input, not a failed bind, and
the index records it as `NO VENDOR BINDING` rather than as a defect.

## THE SHEET IS FIT FOR 16 STYLES AND NOT FOR THE OTHER 20

**Read this before using the catalogue to pick a hair.** All 36 rows passed
the gate. Twenty of them are nonetheless not visually distinguishable from a
balding head in these renders, and the gate could not have told you that.

The discriminating measurement is the gate's own hair-hidden control frame:
crown-band mean luminance with the groom shown, against the same frame with
only the groom hidden.

    style                 with hair   hidden    delta
    Hair_M_BobCurly            7.2      58.2   -51.0     reads as hair
    Hair_S_Pixie              18.6      58.2   -39.6     reads as hair
    Hair_S_Casual             56.2      58.2    -2.0     does not read
    Hair_S_Cornrows           57.1      58.2    -1.0     does not read
    Hair_S_SlickBack          57.7      58.2    -0.4     does not read
    Hair_S_BuzzCut            58.0      58.2    -0.2     does not read
    Hair_M_Mohawk             57.9      58.2    -0.2     does not read
    Hair_S_BaldingStubble     58.2      58.2     0.0     the control

`Hair_S_BaldingStubble` is the natural control — a balding style contributes
almost nothing at the crown by construction, and it measures exactly zero.
Twenty styles sit within four luminance units of it (crown luma 54.4 to
58.3), against a 39 to 51 unit swing for any style that genuinely reads.

**The gate was not wrong.** `Hair_S_BuzzCut` really did change 27,994 pixels,
reproducibly, above floor. A sub-luma-unit change spread over a large area
produces many changed pixels while being invisible. PRESENT means *pixels
changed where hair should be*, and that is all it has ever meant.

## THE CROWN METRIC RUNS BACKWARDS HERE

`crown_frac` was built to catch one failure — hair clumped at the jaw with a
bald crown, which is what a wrong bind produced. It is not a quality signal
and in this catalogue it inverts:

    Spearman(crown_frac, changed_px)   -0.314
    crown >= 0.90    20 styles   median  57,590 px
    crown <  0.90    16 styles   median 108,181 px

A style with plenty of visible hair covers the whole silhouette including the
sides, so its crown FRACTION falls (BobCurly 0.57, StraightBangs 0.25). A
style whose only contribution is a faint wash over the lit scalp scores
0.93 to 0.97. **The highest crown scores in this table belong to the styles
you cannot see.** Do not rank by it.

## ~~NOT ESTABLISHED~~ — ANSWERED THE SAME DAY. THEY RENDER.

This section read *"whether the twenty short styles are rendering
correctly-but-subtly or failing to render is NOT settled by this run."*
**It is settled now: they render, and the fault was entirely my framing.**

Proven by macro render at `--dist 45 --fov 14` on the crown:

    Hair_S_BuzzCut    27,994 px @ dist 110  ->  231,763 px @ dist 45  (272x floor)
                      crown luma delta -0.2 -> -13.0

`_verify/20260820_macro/` holds the frames. `Hair_S_BuzzCut` resolves into
individual dark strands with a correct hairline and scalp visible between
them. `Hair_S_Cornrows` resolves into distinct braided rows with partings —
**visibly different from BuzzCut**, which is the stronger claim: not merely
"hair renders" but "these styles render as themselves".

Re-run at `--dist 60 --fov 18` in `_verify/20260820_catalogue_close/`, every
short style gains 5-8x its pixel count:

    BuzzCut   27,994 -> 149,890      Casual   51,120 -> 407,919
    Cornrows  28,361 -> 242,651      Coil     74,792 -> 423,560
    Mohawk    57,697 -> 385,001      CurlyFade 41,008 -> 324,346

**And `crown_frac` reverses**, 0.93-0.97 falling to 0.61-0.88 — exactly what
the inversion analysis above predicts once the hair actually resolves and
covers the sides. The metric was reporting the shape of the noise.

**THE REAL DEFECT WAS ONE HARDCODED FRAMING.** `catalogue_run.py` pinned
`--dist 110 --fov 26`, which long hair needs in order to fit in frame and at
which a 5 mm strand is sub-pixel against a dark forest. One framing cannot
serve styles whose scale differs by an order of magnitude. It is now a
parameter and is recorded in every row. The tool's own docstring already said
*"a groom's verdict belongs to its framing"* — that applies to the catalogue
as documentation, not only to gate verdicts.

**Use the close sheet for short styles and the wide sheet for long ones.**
Still true and unchanged: the catalogue clears `override_materials`, so every
render here is at vendor default colour, not the hero's 0.92 / 0.28 / 0.00.

## USABLE OUTPUT

The 16 medium and long styles are legible and comparable on the sheet, which
is enough to choose among them. In crown-luma order, darkest crown first —
i.e. most hair visible first: BobCurly, Updo, Pixie, StraightBangs, BobMessy,
BobStraight, UpdoBraids, BobBangs, Straight, LowPonytail, SideSweptFringe(M),
Layered, SideSweptFringe(S), BobLayered, BobSlick, MessyClumps.
