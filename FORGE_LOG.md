# FORGE_LOG.md — every generation run, with what it cost

Appended by `scripts/forge.py`. One line per run. A forge whose
runs are not costed becomes a way to spend a GPU without anyone
noticing, and a generated asset with no logged provenance is the
one thing R-AIGATE cannot check after the fact.

| asset | class | inputs | generate | retopo | genus | UVs | wall |
|---|---|---|---|---|---|---|---|
| SM_Church_Forge | hero_prop | 4 views | gen 5.5s / VRAM 10082 MiB | 381364 -> 60000 tris | genus 61 -> 61 | UVs True | 44.0 s total |
| SM_Church_Forge | hero_prop | 4 views | gen 5.5s / VRAM 10082 MiB (REUSED) | 381364 -> 60000 tris | genus 61 -> 61 | UVs True | 7.1 s total |
| SM_Church_Forge | hero_prop | 4 views | gen 5.5s / VRAM 10082 MiB (REUSED) | 381364 -> 60000 tris | genus 61 -> 61 | UVs True | 7.1 s total |
| SM_Church_Forge | hero_prop | 4 views | gen 5.5s / VRAM 10082 MiB (REUSED) | 381364 -> 60000 tris | genus 61 -> 61 | UVs True | 7.4 s total |
| SM_Church_Forge | hero_prop | 4 views | gen 5.5s / VRAM 10082 MiB (REUSED) | 381364 -> 60000 tris | genus 61 -> 61 | UVs True | 8.2 s total |
| SM_WoodStack_Forge | prop_small | 4 views | gen 55.7s / VRAM 14870 MiB | 2801712 -> 15000 tris | genus 392 -> 392 | UVs True | 133.3 s total |

## THE REPEATABILITY COMPARISON — church vs wood stack, 2026-08-30

**Two assets is the smallest number from which anything can be said about
repeatability, and the honest summary is that the WRAPPER repeated and the
COST did not.**

| | church | wood stack | ratio |
|---|---|---|---|
| class | hero_prop | prop_small | — |
| views | 4 | 4 | 1x |
| generate | 5.5 s | 55.7 s | **10.1x** |
| VRAM peak | 10,082 MiB | 14,870 MiB | 1.47x |
| VRAM headroom | ~5,000 MiB | **175 MiB** | — |
| raw mesh | 190,562 v / 381,364 f | 1,400,074 v / 2,801,712 f | **7.3x v** |
| tri ceiling | 60,000 | 15,000 | 0.25x |
| decimation | 6.4 : 1 | **186.8 : 1** | 29x |
| genus | 61 | 392 | 6.4x |
| thin/long | 0.4317 | 0.617 | — |
| wall clock | 44.0 s | 133.3 s | 3.0x |
| stage 10 | 1845.0 cm, err 0.00 | 120.0 cm, err 0.00 | — |

### WHAT REPEATED

Every stage, in order, with no intervention: 1–9 headless, 10 in a verified
editor. **Both hit their declared height to 0.00 cm** and both passed the
orientation gate with expected and measured shape ratios identical to 4 dp.
The forge is not asset-specific.

### WHAT DID NOT REPEAT, AND THE ONE THAT MATTERS

**Inference time went 10.1x on the same view count and the same sampler
settings.** Four views, 12 steps, identical cfg — and 5.5 s became 55.7 s.
Whatever drives cost, it is NOT the input count, which is the only thing the
recipe lets you set. It tracks the OUTPUT: 7.3x the vertices.

That has a consequence for planning: **a forge run's cost cannot be estimated
from its inputs.** Two assets, identical on every knob the recipe exposes,
differ by an order of magnitude. The second one also came within **175 MiB —
1.2%** of the VRAM floor. There is no basis yet for predicting which side of
that line a third asset lands on, and the honest position is that the next one
should be assumed not to fit until measured.

**Decimation ratio is the number to watch**: 6.4:1 against 186.8:1. Throwing
away 99.5% of the generated triangles is not obviously the same operation as
throwing away 84%, and `tri_within_budget` reports success identically for
both. Genus 392 survived it, as designed and as disclosed.

| SM_CrystalSpire_Forge | hero_prop | 3 views | gen 6.3s / VRAM 10362 MiB | 375448 -> 60000 tris | genus 11 -> 11 | UVs True | 46.6 s total |
