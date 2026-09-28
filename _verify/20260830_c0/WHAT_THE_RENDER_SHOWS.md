# C0 side-by-side — what the frame actually shows

`C0_side_by_side.png`, 2032x1273, luma mean 0.3842 std 0.2537, blown 0.000%,
black 0.113%. Tonally non-trivial, so it is safe to read.

Camera `(-215300, 278800, 19595)` rot `(0, -2.75, 0)`, 899.8 cm above its own
traced ground, location and rotation both read back at **0.0 error**. Yaw 0
looks down +X, so **+Y is screen right**: the left house is `ORIGINAL`
(y 277500), the right is `SWAPPED` (y 280100).

## ⭐ WHAT IS PROVEN

**Both houses are materialed and neither is a checkerboard.** The left house
shows a grey shingle roof, cream plaster panels, brown timber framing with
clear X-braces, a plank band under the eaves and a stone-course skirt. The
right house shows the same architecture with a warm tan plank band and pale
panels between dark braces. **The swap reached the pixels.**

That is the question C0 exists to answer, and the answer is yes. Ten slots,
seven materials, one master, and the house reads as a timber-framed medieval
building at 45 m.

Both are also **visibly seated** — grass meets the stone skirt on all sides of
the left house, no daylight under it, which corroborates the measured
`base_above_ground_cm 0.0` from a different representation.

## ⛔ WHAT IS **NOT** PROVEN, AND THE NUMBERS MUST NOT BE QUOTED

    ORIGINAL_left    mean RGB 125.1/113.2/98.1   luma 0.450   sat 0.295
    SWAPPED_right    mean RGB  73.0/ 66.7/58.9   luma 0.265   sat 0.353

**This is not a material comparison and reporting it as one would be
non-negotiable 22.** Three things differ between the two crops besides the
textures:

1. **The right house is behind a conifer.** A large tree occupies roughly the
   right third of its crop. Much of what is being averaged is foliage.
2. **The right house is in shadow.** It sits **2.03 m lower** on real terrain
   and takes tree shade; the left house is in direct sun.
3. Consequently the luma gap of 0.185 is **lighting and occlusion**, and the
   material contribution is not separable from it.

The pair was placed for a single-variable comparison and the SITE defeated it.
The materials are the only variable in the *scene graph*; they are not the only
variable in the *photograph*.

## THE FIX FOR THE RENDER BATCH

Re-site the pair on clear, evenly-lit ground of **equal height**, with no
foliage in either sight line — the plaza's cleared disc has room, and the tree
clear already ran there. Same camera treatment, then the crops are comparable
and a real read is possible.

**Until then: C0's mechanism is verified and C0's LOOK is unjudged.** No
opinion about which texture set is better is available from this frame, and
none is offered.

## ALSO VISIBLE, INCIDENTALLY

The greybox town behind — near-black gabled cubes and the landmark spire — and
the street slabs as flat grey quads on the grass. Both are the known state of
`/Game/Alpine8K` and neither was touched. **No orange nav wireframes**, which
is the `ShowFlag.Volumes 0` fix working on its first outing.
