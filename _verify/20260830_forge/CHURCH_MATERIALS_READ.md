# The church's FOUR materials — built, bound, and read back

**2026-08-31.** Option A completed: four real slots, four
material instances, every binding read back off the mesh.

## WHAT IS ON IT

| slot | role | albedo | source | roughness |
|---|---|---|---|---|
| `M_Church_Stone` | `church_stone` | `rock_wall_08_diff_2k.jpg` | **Poly Haven CC0**, fetched direct | 0.88 |
| `M_Church_Plaster` | `church_plaster` | `plaster_wall_tiled.jpg` | operator-generated, `textures_v1` | 0.82 |
| `M_Church_Copper` | `church_copper` | `copper_patina_PLACEHOLDER.png` | ⛔ **PLACEHOLDER** | 0.55 |

One master (`M_Church`), three instances — not three materials. Normals and
roughness derived by `derive_material_maps.py` into `refs/derived_church/`;
all three self-checked as **DX** convention.

**Master compiles clean, 0 errors**, samplers explicit:
`BaseColor SAMPLERTYPE_COLOR`, `Normal SAMPLERTYPE_NORMAL`,
`Roughness SAMPLERTYPE_MASKS`.

**The roughness spread is the argument for option A made concrete:** 0.88
stone, 0.82 plaster, **0.55 copper**. A Z-blend across one slot could not have
given the dome a roughness distinct from the plaster under it.

## ⭐ THE FRAME CAUGHT A WRONG BAND, WHICH IS WHY THE FRAME EXISTS

The first split put the copper edge at **0.80** of height, read off `r_max`
decline about the MESH centre. It imported, bound and rendered — and
`church_textured_beside_chalet.png` showed **copper on the finial spike only,
with the onion dome still plaster.** The concept's single most specific
material call, missed, by an asset that passed every numeric check.

**Root cause: radius was measured about the wrong axis.** The tower is
off-centre from the nave by **0.2550** in mesh units, so distance-from-mesh-
centre grows with that offset and swamps the dome's own radius — the profile
came out flat and showed no bulge to find.

Measured about the **tower's own axis** (XY centroid of vertices above 0.65 of
height), the onion is unmistakable:

    0.683   r_max 0.0600   <- NECK, the dome spring line
    0.750   r_max 0.0769   <- the bulge, widest point
    0.817   r_max 0.0413   <- taper
    0.833+  collapses to the finial

Copper band corrected to **0.683 → 1.0**. Faces on that slot went
**1,098 → 4,164**, taken from plaster (40,933 → 37,867). The re-framed shot
shows copper across the dome and finial, belfry stage plaster below it.

`TEXTURING_SCOPE.md` predicted this exactly: *"the copper band's lower edge is
the one number that needs a frame to set rather than arithmetic."* It was
right, and the arithmetic I substituted for a frame was wrong by 0.117 of the
building's height.

## ⛔ WAITING ON THE OPERATOR — ONE SLOT

**`M_Church_Copper` only.** Stone and plaster are final sources; the dome
stands on a pipeline-derived placeholder whose STRUCTURE is borrowed from
`plaster_wall_tiled` and whose COLOUR is invented from the concept's words.
Provenance in `Free/_measured/copper_placeholder.json`; the role is flagged
`placeholder: true` and the assignment script prints the waiting slot on every
run. It retires by DELETION when the real tile lands — not by being kept as a
fallback.

## NOTED (the roof line below is now RESOLVED — see the fourth band)

**The nave roof was plaster** under the three ruled bands. Concept 02 calls for
a *shingled* roof, and that is what the fourth band, added below, fixes.

**The stone course has a slightly ragged top edge**, because the band cuts on
face centroids and the mesh's vertex distribution there is uneven. It reads as
weathering at this distance; it would not survive a close shot.

## A REUSED GRAPH, NOT A FORKED ONE

`c0_build_materials_payload.txt` is now parameterised (`DEST`, `MASTER_NAME`,
`TEX_PREFIX`, `MI_PREFIX`) and the church reuses it. Copying it would have
been the same mistake its own docstring argues against for seven materials —
two graphs that must agree, and the next shading-model change made twice.

**One thing was still hardcoded three levels down**: the master's default
texture looked up the role `plaster_wall` by name, so the church build failed
with `KeyError ('plaster_wall', 'A')` *after* all 9 textures had imported. The
parameterisation looked complete because the part left behind was inside a
loop. Same class as the stage-10 `DEST`: **a name that keeps working for the
asset it was written for.** Now takes the first role in sorted order.

---

# THE FOURTH BAND — roof_tiles, 2026-08-31

## ⛔ IT COULD NOT BE A HEIGHT BAND, AND THAT IS THE WHOLE POINT

Stone, plaster and dome stack vertically, so height separates them. **The nave
roof and the tower shaft occupy the SAME heights** — any horizontal cut that
catches the roof also catches the tower, and any cut that spares the tower
spares the roof. There is no fourth height band to be had.

What distinguishes a roof is that it is **sloped**. So the fourth material is
selected by FACE NORMAL inside the existing plaster height range. The
threshold is read off the measured distribution, not chosen
(`church_normals.py`, area-weighted, inside the plaster band):

    0.00-0.05   42.91%   vertical walls, 89 deg -- the dominant mode
    0.25-0.60   <=1.01%  each: the TROUGH
    0.60-0.70   25.45%   48-51 deg -- the roof mode

**0.55 sits in the trough**, just below the roof mode.

**SIGNED, not `|n·up|`.** A deep eave's soffit faces *down* with the same
steepness as the roof above it; on an absolute test it would have come out
shingled. Only upward-facing slopes are roof.

    stone 17,969   plaster 29,124   copper 4,164   roof 8,743   = 60,000

Read back in engine: **slot_count 4, sections_lod0 4**, tris 60,000. The frame
confirms what the height band could not do: nave roof, porch roof and apse
roof all shingled, tower shaft at the same heights still plaster.

## ⭐ AND THE FRAME CAUGHT A SECOND DEFECT: TILING WAS NEVER SET

The first four-band frame showed shingles reading as **half-metre slate
slabs**. Cause: the master carries a `Tiling` scalar that **defaulted to 1.0
and that nothing had ever set**, on any role, since the C0 build. Every
material rendered at whatever density `smart_project` happened to produce.

Measured (`church_uv_density.py`): **one UV tile spans ~50 METRES of church.**

    M_Church_Stone     50.34 m/uv      M_Church_Copper   53.31 m/uv
    M_Church_Plaster   50.54 m/uv      M_Church_Roof     54.28 m/uv

The unwrap itself is sound — density is near-uniform across all four slots.
Only the multiplier was missing. A parameter that exists, compiles, and is
never written is indistinguishable from one that was never added.

**Tiling is now DERIVED, never typed:** `tiling = metres_per_uv / tile_m`.

| role | m/uv (measured) | tile_m | tiling | tile_m basis |
|---|---|---|---|---|
| `church_stone` | 50.34 | 1.80 | **27.96** | **MEASURED** — Poly Haven publishes rock_wall_08 as 1800×1800 mm |
| `church_plaster` | 50.54 | 2.00 | **25.27** | declared intent |
| `church_copper` | 53.31 | 2.00 | **26.65** | declared intent, doubly provisional |
| `church_roof` | 54.28 | 1.50 | **36.19** | declared intent — 1.5 m across a 1024 tile puts a shingle course near 0.3 m |

Only the stone's is a measurement; the other three are declared intents and
the recipe says so per role. The builder **refuses the half-configured case**:
declaring `tile_m` without passing `--uv-density` is an error, because an
intent that is silently ignored is worse than no intent.

The scalar is read back like every other write.

## NOTED, NOT FIXED

**The roof shows visible tile repetition.** 36× tiling across a 1024 tile
repeats often enough to read as a pattern at this distance. That is the
trade-off high tiling buys: correct feature scale, visible repeat. The fixes
are a larger source tile or detail-blending in the graph, and neither is in
scope tonight.

**The copper's patina now reads subtler**, because at 26.65× the ramp's
structure is small. It looks more like smooth bronze than mottled verdigris.
The real tile will settle it.
