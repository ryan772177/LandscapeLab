# Blender_Test — what can actually round-trip, and how

## The short answer to "can I open a .uasset in Blender?"

**No.** `.uasset` is Unreal's own package format. Nothing outside the editor
reads it, and there is no converter.

**And for hair it is worse than that: a groom cannot leave Unreal at all.**
The 5.8 Python surface reflects 26 `Exporter` subclasses — T3D, OBJ, FBX, STL,
glTF, textures, sound — and **not one of them handles grooms or Alembic**.
`GroomFactory`, `GroomBindingFactory` and `HairStrandsFactory` are IMPORT-only.
No source `.abc` ships with the MetaHuman groom content anywhere on this
machine either.

That is *"I looked and it is absent"*, not *"I did not look"* — the enumeration
is in commit `1089b87a`. So **the vendor `Hair_M_SideSweptFringe` cannot be
brought into Blender.** The only unexplored route is a `UFUNCTION` in
`LandscapeLabEditor` reading the strands bulk data directly, which is how
R-CREATE and R-GROOMBIND3 were unblocked. That is a plugin change plus an
~18 s rebuild, not a file operation.

**A skeletal mesh will not come out through `ExporterFBX` either** — tried on
`SKM_MHC_AlpineHero_FaceMesh`, the exporter reported False and wrote nothing.
It did not need to: see below.

## What you CAN do, and it is the interesting half

**Our own groom is already a Blender file.** The DiffLocks hair lives natively
in `.blend`, so there is nothing to convert — open it and groom.

| file | what it is |
|---|---|
| `EDIT_ME_hair.blend` | the current best custom cut (`hi_HUG3`), 52,839 curves |
| `SOURCE_untouched.blend` | the raw reconstruction before any restyling, 100,943 curves at 28 points |

**The hero's head is already inside both files** — `SKM_MHC_AlpineHero_FaceMesh.001`,
19,284 verts, his actual face mesh, with the armature. So you are grooming
against the real skull, not a stand-in. That is also *why* it is there: every
root was snapped onto that surface, and the root UVs were read from it.

## If the viewport looks EMPTY when you open it

It was, and it is fixed in the files as shipped — but here is what was
happening, because it reads exactly like a corrupt file and it is not.

Nothing is hidden and no collection is excluded. **The scene is in the DNA's own
space: centimetres, with the head at Z 140.9 to 180.4.** Blender opens framed on
a two-unit cube at the origin, so his head sits about a hundred and seventy
units overhead, outside both the view and the default far-clip. You get an empty
viewport with a complete character just off-screen.

Both blends now SAVE their view framed on the head (location Z ~164, distance
~75, far-clip 10,000) and carry a `HeadCam`. If a view ever gets lost:

  - **Home** — View > Frame All
  - **Numpad 0** — look through `HeadCam`
  - **Numpad .** — frame the selected object

**The geometry is deliberately NOT moved to the origin.** Every root sits where
it was snapped onto the hero's face mesh, and its root UV was read from that
surface; sliding the objects somewhere convenient would move the groom in UE and
void the seating. `scripts/frame_blend_view.py` moves the VIEW instead, and can
be re-run on any groom blend.

## Getting an edit back onto the hero

One command, about three minutes, and it does the whole chain — export to
Alembic, import, build a fresh binding against his face, apply the colour,
render alpine + neutral, and gate the result in pixels:

    python scripts/hero_face/likeness/cycle.py \
        --blend hero/groomloop/Blender_Test/EDIT_ME_hair.blend \
        --name MyEdit \
        --out-dir C:/Users/Admin/UE5LandscapePipeline/_verify/20260823_myedit

It needs a running editor on `/Game/Alpine8K`. It refuses rather than guesses:
the export is checked for non-zero strand widths and resolved root UVs before
anything is imported, because a groom exported without those imports cleanly,
binds cleanly, reports every property correctly and **renders bald** — that
defect cost nine days.

To see how an edit scores before paying for a UE trip (about 40 s):

    blender --background <your.blend> --python hero/groomloop/scripts/benchmarks.py
    blender --background <your.blend> --python hero/groomloop/scripts/skull_standoff.py

## Two things worth knowing before you start

**Keep the points per curve.** The strands are 28 points each. An earlier
version was resampled to 12 for a diagnostic and never put back, which gave
8 mm straight segments with a 14° corner at each joint — it read as barbed
wire rather than hair. Measured: kink p50 **14.18°** at k12 against **5.59°**
at k28, for a length cost of 0.5%.

**Volume is the open problem, not detail.** The raw reconstruction hugs the
skull (mean standoff 1.011 cm, half-width 11.61); every restyling pass so far
inflated it, up to 2.44 cm and 20.70. The vendor hair — the look being matched
— lies flat and falls past the ears. `skull_standoff.py` measures this; the
seven benchmarks do not, which is how a groom scored 6/7 while standing off the
head like a pompadour.

## Why this folder is here and not on the Desktop

`CLAUDE.md` standing rule 1: no writes outside this repo or the UE project
directory. It is a rule about where *I* am allowed to write, not a limit on
you — move or symlink this folder wherever you like, and the `cycle.py`
invocation above takes any absolute path.
