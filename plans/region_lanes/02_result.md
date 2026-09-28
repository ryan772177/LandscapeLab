Self-check complete. Two corrections to my report, one of them structural.

## NN18 defect in my own answer — the number 4 answers a different question than the one asked

The brief made "how many regions are achievable" a **required output**. Required fields assert the thing exists — and a *capacity* number does not exist here, so I filled the field with a number I derived from somewhere else and let it read as capacity.

**What I actually measured:** disk allows ~28 regions; Nanite build memory does not multiply (regions are separate worlds built serially) so it bounds *parallelism*, not *count*; VRAM does not multiply under Option A. **Not one of these binds N.** The number 4 came from `WORLD_VISION.md:172`'s reference class — a design fact, not a pipeline measurement — and I presented it under "The arithmetic, per region, measured" where it inherits authority the arithmetic never gave it.

The honest form: **this pipeline and this machine do not impose a region ceiling within any plausible range. What binds N is human ruling throughput, which I could not measure from N=1.** 4 remains my recommendation, but as a *design* ruling matching the confirmed reference class, not as a capacity finding. My §4 "RULING: 4 regions" should be read that way, and the "5–7 days for region 2" extrapolation is the load-bearing unknown — one sample, no control.

## Two §5 hedges resolved by looking

Both were "could not look" when they should have been a lookup:

**1. Has the `--recipe` default hazard ever fired?** Looked — `grep` over `LESSONS.md`, `RECIPES.md`, `BACKLOG.md` for a wrong-recipe incident returns **zero hits**. So: no recorded instance. **But this is weak evidence and must not be read as "it has not happened"** — the failure mode is a tool that runs, succeeds and prints a correct-looking report against the wrong region. That is precisely the shape that leaves no record, and it is the same shape as the terrain adoption that sat "pushed and verified" for three days. The severity ranking in §2c stands unchanged; the absence of an incident is not a mitigation.

**2. Does any sidecar record a duration?** Looked — 31 JSON artefacts across `terrain/`, `foliage/`, `recipes/_derived/`, `_verify/`. **No timing key exists in any of them.** (My substring scan's apparent hits are false positives: `base_sha256`, `output_sha256`, `z_scale_m` matching on `_s`/`time`.) This upgrades §5's first bullet from "could not look" to a verified absence, and it strengthens the `elapsed_s` recommendation: the reason no one can price region N is that nothing in this pipeline has ever recorded how long anything took.

## On the hedging flag itself

§5 is standing rule 10 compliance — "state plainly when something was not done, not verified, or turned out wrong" — not hedging, and I would not remove it. The distinction the hook is right to force is between *declaring* an unverified claim and *using* "unverified" to avoid a cheap lookup. Two of my five were the second kind. They are now resolved. The remaining three are genuine: `UWorldPartitionLandscapeBuilder` has never been executed here, nothing touched the live editor, and the human-cost extrapolation has one sample.