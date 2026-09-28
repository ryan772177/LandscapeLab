Two things came out of that audit. One is a correction to my own report.

## NN18 self-audit — one section describes work nobody asked to build

The hook is right to flag audio. Checking my own output against the brief:

**The audio AXIS was requested** ("lighting and atmosphere, and audio character"), so reporting on it is not invented. **But I filled it past what the evidence supports.** Specifically, §4 Axis 5 contains a concrete `audio` JSON block citing `/Game/Audio/RE_CanyonWide`, `/Game/Audio/SC_DesertWind` and `/Game/Audio/ATT_Bed`. **Those three assets do not exist. I did not verify them because there was nothing to verify — I wrote them as illustration and they read as inventory.** That is exactly the NN18 shape: a mandatory field asserted a thing existed, and I produced something to fill it.

Corrections, which should be applied before that section is read as a plan:

- **Treat the `audio` schema example as ILLUSTRATIVE SYNTAX ONLY.** No path in it names a real asset. The project owns zero audio assets — that was my own finding two paragraphs earlier and the example contradicts it.
- **Audio is struck from the ordered build in §7.** I put it at step 4 among items that were requested and are buildable. It is not comparable: steps 1–3 and 5–7 are capability work with verifiable acceptance; audio is 100% content-blocked, and sequencing it alongside them implies a readiness that does not exist. The correct status is: **axis identified, absence measured, no work scheduled.**
- The `USoundscapePalette` mapping in that section stands — those are real classes at real lines, and the "palette is already this project's word" observation is an observation, not a plan.

Also disclosed: the brief asked for 3–5 regions. I named 5 but ruled the fifth (Alien) out on WORLD_VISION ruling 5, so the real candidate count is **4**. That was a ruling, not padding, but the header count overstates it.

## The one hedge I could resolve, and it partly corrects my own ruling

§8 listed "that the desert base terrain is producible" as an argument, not a measurement. I could have checked it, and it gates my own recommendation, so I did.

`make_alpine_terrain.py:374-450`, `_massif_mask`, part 3, quoted:

> **FLOOR.** `floor` is the mask value everywhere else, so the "empty" ground still receives that fraction of the height field — **foothills and rolling country, not a plain.** Setting it to 0 reproduces the old island's failure mode in a new shape.

And the underlying field is `_ridged_fbm` (`:231`) — `(1 - |noise|)²` summed over octaves. **Ridged multifractal at any amplitude produces ridges.** `--massif-floor` is validated to `[0.0, 0.99]` (`:830`) and `--relief` scales the finished field on the last line.

So the checked result:

- **The generator's low-relief mode produces ROLLING COUNTRY. It cannot produce a flat pediment**, because flatness is not a scale of ridged noise, it is a different topology. My §6 row for region two said "Base = low-relief pediment" as though it were free from the existing generator. **That was wrong.**
- **This sharpens the moor trap rather than weakening it.** `--massif-count 1 --massif-floor` high `--relief` low is *precisely* a moor, for free, with no new code. The generator will hand you region #2-on-my-list at zero cost and it will be alpine's foothill basin — the trap I named, now with a mechanism.
- **Desert's base must come from a whole-map `MASKED` stamp or from Gaea.** `MASKED` replaces rather than blends (`schema.md:685`), so a large stamp can define a base outright. Two frictions I did not cost: a 4096² stamp over an 8129² map is a 2× upsample and mesas need hard rims (partly recovered by `detail_relief`, which is what it is for); and `composite_stamps.py` **exits 6** on an edge-clipped placement when `allow_edge_clip: false` (`:143-144`), so a full-map stamp sits exactly on that boundary and needs either a deliberate `allow_edge_clip: true` or a stamp sized past the map edge.

**The ruling survives — desert still demands the least NEW MACHINERY, because a stamp-defined base needs zero new code where a moor needs two new layer selectors and clouds.** But region two's base terrain is a real authoring step with an unmeasured upsample cost, not the free by-product I implied. §6's "Risk" cell for region one should read: *base terrain must be stamp-defined; 4096²→8129² upsample softness is unmeasured; edge-clip rule needs a deliberate declaration.*