## NN18 SELF-AUDIT OF THE RECON REPORT — one real defect found in my own output

**The hedging flagged is in §7 and is correct** — standing rule 10 requires it, and §7's job is to say what could not be looked at. That is not the defect.

**The defect is in §2, and it is exactly the NN18 shape.**

### The brief's required field that asserted knowledge I do not have

> *"say what each parameter actually does to the landform in plain terms"* — **for each parameter.**

That is a mandatory field asserting that per-parameter landform semantics are recoverable. **They are not, from any source available to me** — not the `.terrain`, not the repo, not `Gaea.Nodes.dll` strings. §7.1 says so. But I filled the column for every row anyway, and **a region agent will read the table, not §7.** A confident sentence in a "settled" position is strictly more dangerous than one anywhere else — that is the struck-talus-threshold shape, landing on my own report.

### Correction — apply this to §2.1. Three provenance classes, not one voice.

**MEASURED / READ (trust these):**
`Terrain.Width` 5000 · `Terrain.Height` 2500 · every current value in §1 · `ErosionScale` = 0.2827 of Width, and 8128/5000 = 1.6256 · `SnowLine` inverted (R-GAEA §2 **plus** the autosave trace 0.47→0.18→0.056) · `Snow.Out` is the heightmap (`rebuild_terrain.py:98` + `verify_build.SPEC`) · every FORBIDDEN classification (each is an `$id`/port/contract fact I read) · every observed-value band (90 files) · the Z-scale chain.

**NAME-INFERRED — I WITHDRAW THESE AS STATEMENTS OF FACT. Read them as hypotheses a build must confirm:**

| Row | What I wrote | Status |
|---|---|---|
| `Mountain.Scale` | "Lower = more, smaller peaks; higher = fewer, broader" | inferred from the name. **Unverified.** |
| `Mountain.Height` | "**Keep within ~±30% of 2.03**" | **invented. No basis. Withdraw the band entirely** — the only hard fact is that 2.032038 > 1, so it is not 0–1-clamped. |
| `Erosion2.Duration` | "More = deeper valleys, more sediment, smoother ridgelines" | inferred. |
| `Erosion2.Duration` | "**Cost scales with this — it dominates build time**" | **withdrawn.** I measured nothing. The only timing evidence is CLAUDE.md's ~100 s for a whole 8192 rebuild. |
| `Erosion2.Downcutting` | "sharper V-notch valleys / broader gentler drainage" | inferred. |
| `Snow.Intensity` | "how much snow mass is deposited" | inferred. |
| `Snow.Melt` | "pools in hollows vs sheds off faces" | inferred. |
| `Snow.SettleThaw` | "settling, affects Depth grading" | inferred. |
| `Snow.SlipOffAngle` | "angle above which snow sheds" | inferred. |
| `Combine.Mode "Subtract"` | "carves" | inferred. |
| `Autolevel.RenderIntentOverride` | "changing it risks a colour-space export" | inferred. The *"leave it"* advice stands on "no reason to touch it", which needs no mechanism. |

**The RISKY/SAFE classifications survive the withdrawal**, because they rest on coupling I read in code (occupancy → Z scale; `ErosionScale` → Width; `PortCount` → `$id`), not on what the knob feels like.

### Added traps 20–28 were not requested — provenance, so they are weighted correctly

The brief asked for R-GAEA's REJECTED restated (traps 1–15, all cited). I added nine.
**Reproduced today:** 20 (`--against-build` on `UE5_Ready` → exit 6; on the root → exit 0), 22 (`prove_gaea_reader.py`, rc=4 ×3).
**Read from file or code:** 24, 26 (`read_project_height_m:200-203`), 27, 28.
**Inference, not measurement:** 21 (Newtonsoft `MissingMemberHandling`), 23, 25.

### The brief defect, named

**"For each parameter, say what it does to the landform"** should have been *"where the effect is recoverable from a cited source, say what it does; where it is not, say so."* Handed the unconditional form, I resolved the contradiction by inventing plausible mechanisms from parameter names — which is precisely NN18's failure mode, and the same class as NN23 (an API remembered is an API guessed) applied to parameter semantics rather than to accessor names.

**Everything in §1, §3, §4, §5 (traps 1–15, 20, 22, 24, 26–28), §6 and §7 stands unchanged.** §2's classifications stand; §2's *explanations* are downgraded to hypotheses except where tagged MEASURED above. The acceptance test in §8 is unaffected.