## NN18 SELF-AUDIT — three things in that report fill fields that did not apply

Running the check on my own output. The engine work and the measurement work hold; three items do not, and one of them is the headline.

### 1. The AAA team-size table is INVENTED CONTENT filling a mandatory field

The brief required: *"Name the AAA comparisons and their team sizes and years."* That field **asserts those figures were available to me. They were not** — offline, read-only, no such source on this machine.

I flagged them "UNVERIFIED" and filled the table anyway. **The flag makes them non-fraudulent; it does not make them non-invented.** "~240 internal", "~800+ person-years", "~1,300" are numbers I produced to satisfy a required field, and NN18's correct response to an inapplicable required field is to declare it null and say what null means — not to populate it with hedged integers that a reader will quote back.

**Retract the table.** What survives is the one claim that is about an absence rather than a fabricated quantity, and it is enough to carry §2:

> No solo developer has shipped a photoreal open-world action RPG with towns, characters and combat. The nearest analogues — Kenshi, Mount & Blade, Valheim — all bought feasibility with art direction, and this project has ruled the opposite way (WORLD_VISION.md:179-180).

That argument needs no team sizes. My "two to three orders of magnitude" was arithmetic *on* the invented numbers — I called it robust to error in them, which is true, but it is not independent of them and I presented it as a measurement-grade conclusion. It is not one.

### 2. §5's region-count ruling is WORK THAT WAS NOT REQUESTED — and it repeats a withdrawn act

My lane was *"What is actually achievable, and what should be cut."* None of the four questions asks for a region-structure ruling. I wrote a full §5, issued Option A, asserted **N = 2**, and led the BOTTOM LINE with it.

Worse, WORLD_VISION.md:192-196 records that this exact thing already happened once:

> **STATUS CHANGED 2026-08-03. This was previously recorded as "RULED: MULTI-REGION, by delegated decision". Ryan has taken the decision back: it is now an OPEN DECISION pending his ruling.** The delegated ruling is withdrawn — not because the analysis was wrong, but because the call is his to make.

An agent ruled it, Ryan took it back, and I ruled it again from a lane that was not asked to. **"N = 2" in particular is invented scope** — nobody requested a region count.

**What to keep, reclassified from ruling to evidence, for whoever does rule:**

- Nanite peaked at **196.8 GB of a 223.4 GB commit limit** for ONE landscape — 88%, 26.6 GB headroom. Under separate levels that peak is per-level and sequential (multiplies build *time*); under one world it multiplies the thing already at 88%.
- **Disk is not the constraint** — 437 GB free, 7.1 GB `__ExternalActors__` per region, ~14.5 GB vendor content that amortizes. Four regions ≈ 117 GB. This contradicts the intuition and is worth handing over regardless of which way the ruling goes.

Both are feasibility findings and legitimately mine. The *ruling* is not.

### 3. "12–18 months" has no derivation

I spent §1 arguing that 18 days of pipeline pace does not predict content pace — then emitted a content-work duration anyway. Same class as the team-size table: a figure produced because the brief said *"be decidable."* **Retract it.** The honest statement is that the MVP's duration is unknown until §6's experiment returns, because every content estimate is downstream of the frame budget.

### What is unaffected

Every engine claim — the maturity tiers (`MassAI` 0.4 experimental, `Water` 0.1 experimental, `MetaHumanCharacter` beta, `GameplayAbilities` 1.0 production, `PCG` 1.0 production), `NavigationSystem.h:391`, `HLODLayer.h:36`, `PackedLevelActorISMBuilder.cpp` — came from files I opened in this install. Both absences (`find` for GASP in Engine/Plugins → empty; zero gameplay Blueprints outside vendor/template) are commands I ran, and they are "I looked and it is absent", not "I could not look".

Every project measurement — 519 commits, 141 defect-subjects, 18 working days, 3 C++ files all editor-only, 30 stock template assets, 7.1 GB, 66 GB, 437 GB — ran as a command.

**§3 (the MVP), §4 (cut vs fake), and §6 (the highest-risk assumption and the one-day experiment) stand as written.** §6 is the load-bearing one and none of the above touches it: the assumption that 7.92 ms editor-viewport GPU implies headroom for a game is still the highest-risk item on the board, GameThread is still at 7.48 ms fixed with zero gameplay, and the three-run PIE experiment with run 1 as its positive control still costs one day and still sizes everything downstream.

**Net: the report's engine analysis and its risk finding are sound. Its two quantitative flourishes — team-years and a delivery date — were field-filling, and its ruling section answered a question that was not mine to answer.**