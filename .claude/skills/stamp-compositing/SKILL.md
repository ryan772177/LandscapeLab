---
name: stamp-compositing
description: Composing terrain from heightmap stamps and adopting the result — falloff and jitter, detail relief at the right wavelength, the adoption rule that forbids live pointers, and the seed discipline. Use when compositing terrain, adding stamps, adopting a heightmap, or running erosion.
when_to_use: compositing a heightmap; adding or moving a stamp; adopting a terrain; running erosion; detail relief; a terrain change that downstream instances depend on
allowed-tools: Read, Grep, Glob
---

# Stamp compositing and terrain adoption

Sources: `RECIPES.md` R-STAMP and the schema, `scripts/composite_stamps.py`,
`scripts/import_heightmap.py`.

## ADOPTION — the rule that protects everything downstream

**ADOPTED ARTEFACTS ARE COPIES AT STABLE NAMES, HASH-PROVEN AGAINST
THEIR SOURCE AT ADOPTION TIME** (NN20).

**Never point a consumer at a generator's live output.** A live pointer
makes *"what IS the terrain"* answerable only by re-running the
generator — and the generator's inputs may have moved since.

`import_heightmap` refuses `heightmap.source == stamps.output` **at the
schema level**, so adopting a composited terrain cannot be a side effect
of running the compositor. Copy to a stable name, assert its SHA-256
against the sidecar's `output_sha256`, then edit the recipe. Re-running
the compositor now rewrites its own output and **cannot touch the
terrain**.

This is the derived-records rule wearing different clothes: a live
pointer is a state claim you cannot check without recomputing it; a
hashed copy is a fact on disk.

## A terrain change re-keys everything downstream

Adopting a new surface is not a drop-in replacement:

- placed instances were computed against the OLD surface — their Z
  values are orphaned
- the weightmap must be re-baked
- the acceptance mask moves, so **counts change and that is not a
  defect**: 160,448 conifers became 157,554 for exactly this reason, and
  R5's measured result now says so explicitly

**A recipe's measured result is a property of the recipe AND THE SURFACE
IT RAN ON.** When the surface is replaced, the old figure is history,
not a target to reproduce.

Do it behind a **named restore tag** (risky-op checkpoint), and re-place
and re-verify in the same pass.

## Detail relief — wavelength is the whole thing

Detail relief adds cliff TEXTURE, and it must operate at texture scale,
not landform scale. **64 m wavelength on 4 m cells did almost nothing**
(45.2% → 42.7%); 28 m with 3 octaves moved it to 22.2%.

**And it changes what slope means.** Cell-scale slope ≥ 50° went from
6.66% to 9.15% of the map, but roughly **40% of that apparent cliff area
is texture, not landform** — ±4.7 m ridges tilt individual 4 m cells
past any threshold you name.

So anything asking *"is this a cliff"* must test **landform-scale
slope** (`landform_slope(..., smooth_m=16.0)`), or it manufactures
phantom rockfall sources across the map.

## Seeds are physics, not decoration

**A wrong seed is different physics that nothing downstream complains
about.** An erosion run with the wrong droplet seed produces a plausible
field, conserves mass, and is simply a different world. Import the
generator's `DEFAULT_SEED` rather than retyping it, and assert the other
parameters against the generator's own source.

## Measuring the result

**Measure the change on the surface that changed.** A CV metric computed
across a finished terrain measured the global detail pass, not the
placements — because the detail layer is global. To judge placements,
measure a placements-only surface.

**Look at the pixels before running a statistic** (NN10). Every metric
favoured one rock for scree; looking showed it was moss-covered bedrock.

## Caps are results

A routing loop that hits `max_steps` and dumps its remainder in place
**conserves mass by construction**, so the mass assertion cannot fail.
Hitting the cap is a **REFUSAL**, reported as loudly as an error — at
`max_steps=60` the field was 4.6× short of the 274–322 steps it actually
needs, with the error largest on the biggest fans.
