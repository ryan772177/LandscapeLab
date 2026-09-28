# The town at oblique and at eye level, under ONE sun — 2026-08-27

Two frames. Both are the first of their kind since the three `HeroStage_*`
directional lights were disabled, so both have a defined sun for the first time
since 2026-08-24.

    CITY_oblique_seated.png   1242 x 1322   luma mean 0.4864  std 0.2294
    PLAZA_eyelevel.png        1242 x 1322   luma mean 0.2660  std 0.2037
    both: 0.000% blown, <0.02% black

---

## The oblique: the town reads as a town

Gabled roofs at varied angles, a spire standing clear of the rooflines,
buildings clustered in a clearing at the foot of a mountain with forest closing
around them. At range the massing works — it is legible as an alpine village
and not as a pile of boxes.

**⚠ The orange wireframes across its sky are the 72 `NavMeshBoundsVolume`
actors drawing in the editor viewport.** An EDITOR artefact, not something in
the world. `ShowFlag.Volumes 0` clears it, was applied afterwards, and the
eye-level frame below is clean. **Every future editor-viewport render of this
world needs that flag off.**

---

## The eye level: the proof that was owed, and two defects it makes plain

### ⭐ THE SEATED SLABS ARE CONFIRMED BY PICTURE

`PLAZA_slab_edge_crop.png` is the midground band at 2x. The street slabs lie
flat ON the grass and TILT WITH THE GROUND — the receding segment down the
centre visibly follows the terrain rather than cutting through it. **There is no
daylight under the edges**, and grass overlaps the slab margins in places, which
means the slab is at or fractionally below the grass line.

That closes the proof owed from 2026-08-27b, where the seating fix was
established by measurement (corner gap p50 67.9 → 10.9 cm) and had never been
seen.

### ⛔ AND THE 932 OVERLAPPING PAIRS ARE VISIBLE IN THE SAME CROP

Consecutive slabs meet at a LIP. Where two segments join, one sits proud of the
other by a visible step, because each is tilted to its own local ground plane
and adjacent planes differ. This is the 932 overlapping street pairs measured
offline and deferred — now confirmed as something a player would see and trip
over, not merely a number.

**Seating each slab correctly is exactly what makes the joins wrong.** A slab
that follows its own ground is right in isolation and discontinuous with its
neighbour. Fixing it means the network is emitted as a continuous surface —
shared edge heights between adjacent segments — which belongs with the
kit-driven re-plan.

### ⛔ THE BUILDINGS ARE STILL NEAR-BLACK. THEY ARE NOT MATERIALED.

Asked directly by the brief: **no.** They carry the engine `Cube`'s default
material and read as dark masses at eye level exactly as they did at range. The
kit answers this; nothing about the sun fix or the seating fix touches it. At
1.75 m this is the most conspicuous thing in the frame after the trees.

### ⛔ A CONIFER STANDS DIRECTLY IN FRONT OF THE PLAYER START

The trunk is dead centre of frame, roughly 3–4 m from the spawn, and several
more stand within the plaza. **Press Play and the first thing the player sees is
a tree trunk**, with the landmark behind it.

This is worse than the oblique's "trees among the houses". The 2026-08-26 clear
removed 2,541 instances at a 3 m / 2 m margin around STRUCTURES, and the plaza
is defined as ground with no structures on it — so nothing there was ever a
candidate for removal. It is not a bug in the clear; it is a gap in what the
clear was asked to do. **The plaza needs its own clear radius**, and re-running
against kit footprints will not fix it because the plaza has no footprints.

---

## How the frames were obtained, and a reproducible editor fault

**BOTH frames landed after their payload had given up and reported failure**,
each at the same 841 s deadline including its 240 s grace. Corrected: an earlier
version of this file said the eye-level shot landed inside its window. It did
not — its payload exited 1 with `"ok": false` and the frame was on disk anyway.
I only saw it because I was polling the filesystem rather than reading the
reply, which is the rule R-CITYSHOT now carries.

That makes it **3 of 3 across two sessions**: the watcher's deadline has never
once been the truth about whether a frame exists.

The camera itself is not in doubt — the payload's own read-back reports
`max_loc_err_cm 0.0` and `max_rot_err_deg 0.0`, so the framing is exactly what
was requested.

**⛔ BOTH TIMES, THE EDITOR WEDGED IMMEDIATELY AFTER THE CAPTURE COMPLETED.**
0.01 and 0.02 CPU-seconds per wall-second, `Responding=False`, and NO modal —
every visible window enumerated both times, finding only `UnrealWindow` and the
console. Remote execution stops answering. Last session it recovered on its own
some hours later; the same process (PID 26492) was healthy at 3.76 CPU-s per
wall-second at the start of this one.

So: **a completed `HighResShot` leaves this editor unable to serve remote
execution, reproducibly.** That is a capture-path fault, not a stall in the
render, and it is why the post-render checks in this session had to be deferred.

**CPU per wall-second is the discriminator, not responsiveness.** The same
`Responding=False` reading has meant 6.04 (working, delivered late), 1.02 (busy,
answered next try) and 0.01–0.02 (wedged) on this machine today.
