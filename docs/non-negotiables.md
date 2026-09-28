> # ✅ LIVE DOCTRINE — THIS IS LAW, NOT HISTORY.
>
> Extracted verbatim from `CLAUDE.md` on 2026-08-29 by the doc-consolidation
> unit, purely so `CLAUDE.md` could fit under its size ceiling. **Nothing here
> was weakened, superseded or retired.** It is one index hop away, not
> archived — `docs/archive/` is the archive, and this file is not in it.
>
> **LOAD THIS** before writing any gate, check, tolerance, assertion or measurement — and before trusting any instrument's result. Every item cost a real defect.

---

# NON-NEGOTIABLES

Distilled from `LESSONS.md`. Each cost a real defect.

0. **AGREEMENT AMONG INSTRUMENTS THAT SHARE A SOURCE IS ONE MEASUREMENT,
   NOT MANY.**
   No claim is verified until at least one confirming instrument reads a
   **DIFFERENT REPRESENTATION** of the ground truth — heightmap vs
   collision vs render vs trace. **Every check declares its source
   artefact, and two checks with the same source cannot corroborate each
   other.**
   *Motivating case, 2026-08-06:* three independent-looking checks agreed
   the terrain was sound — `verify_grounding` (max 0.001 m over 157,554
   instances), the summit drift guard (0.04 m), and the renders. All
   three read the **heightmap**, or something derived from it. The first
   question ever put to a different representation — one line trace
   against **collision** — found the landscape RENDERS `v2` and COLLIDES
   the pre-stamp `v1`, disagreeing by **p90 30.98 m, max 217.21 m**. The
   defect had been in the level for three days, through a terrain
   adoption, a weight re-bake, a 157,554-instance re-placement and 1328
   saved packages, and every gate was green throughout.
   This outranks the rest of this list because it is how the rest of the
   list gets fooled: a gate can be correct, tested in three directions,
   and still blind — if its source is the thing that is wrong.

1. **Fail closed, and test that each gate cannot be satisfied by the
   failure it guards against.** "Unknown" is never "yes".
2. **A gate that has only seen good input has not been tested.** Prove it
   refuses.
3. **Prefer an input that cannot express the catastrophic value over a
   gate that rejects it.** A gate can be wrong; an unreachable state
   cannot.
4. **When you find a defect class, grep for it everywhere immediately.**
   NaN-passing-range-checks was fixed five times because it was fixed
   locally each time. **The sweep happens in the SAME COMMIT as the fix,
   as a mechanical step — not as an intention recorded for later.** Every
   recurrence in this project was logged conscientiously and swept never.
   4a. **AUTOMATIC ESCALATION TRIGGER: a trap class that recurs across
   TWO DIFFERENT TOOLS is promoted to shared infrastructure**, on the
   spot, without waiting for a third. One implementation, used by every
   caller, with a mandatory post-operation assertion that the result
   matches spec exactly. **Individually-patched copies of the same fix
   then become a REJECTED pattern in their own right.** Ruled 2026-08-03
   after the incomplete-clear class reached three tools; the first
   instance of this infrastructure is `scripts/material_graph.py`.
5. **A check that consumes the value it is verifying verifies nothing.**
6. **Diagnostics must distinguish "I looked and it's absent" from "I
   couldn't look".** A failed measurement reports *"I could not measure
   this"*, never the number the broken measurement produced.
7. **Verify an invariant on complete state.** A count taken while World
   Partition regions were unloaded became a gate that inverted itself.
8. **Verify with a different instrument than the one that made the
   claim.** A read-back that reads the field the setter wrote proves only
   that the value landed, not that the engine reads it.
9. **Before writing "as recorded in X", open X.**
10. **Inspect the artefact before shipping it downstream.** Look at the
    pixels before running a statistic.
11. **Sanity-check magnitudes against physical reality.**
12. **Any step a human does by hand needs a machine check after it.**
13. **When you must act on an inference, build the disproof into the same
    operation.**
14. **Never truncate the output of an operation you cannot repeat.**
15. **DERIVED RECORDS VERIFY AGAINST GROUND TRUTH.** Any claim about
    project state written into `BACKLOG.md`, `CURRENT STATE`, `ASSETS.md`
    or a report must be checked against the **artefact itself** — asset
    properties, the file on disk, or a render — **at the moment it is
    written**, or be explicitly tagged `UNVERIFIED`.
    **Narrative is not a source for state claims.** This is the recipe
    retrofit's "recover values from the project, never from memory",
    generalised to every derived record.
    *Motivating case, 2026-08-03:* a BACKLOG entry read "THE FIR WAS
    NEVER REIMPORTED AFTER THE 16-BIT FIX". It had been written from the
    `LESSONS.md` narrative without checking the engine, and it was wrong
    — both roughness maps already traced to `_8bit` sources and the twig
    alpha was RGB 8-bit, never in the trap at all. It became the opening
    premise of the next session's task. *The session caught it by
    measuring before acting, which is the behaviour this rule makes
    mandatory rather than lucky.*
16. **When a fix "lands" but the artefact disagrees with expectation,
    MEASURE THE ARTEFACT before re-diagnosing.** Do not rebuild, do not
    form a second theory, do not look harder. Take the pixel statistic,
    the texture mean, the patch average.
    *Motivating case, 2026-08-03:* conifer trunks were called "pale
    cream" twice, from a frame whose measured value was a tan-brown
    (`109/90/62`) under direct sun. A patch mean settled in one command
    what two rounds of looking did not, and a frame-to-frame diff proved
    the fix had landed (44–48% of pixels changed) when the eye said
    nothing had happened. **The eye is a poor photometer against a dark
    background.**

---
26. **BAKED FOR SELECTION, LIVE FOR SHADING.**
    A live per-pixel read (the vertex normal, a screen-space derivative)
    is **permitted when its degradation mode is benign at the range where
    the degradation occurs**, and **rejected when degradation defeats the
    feature's purpose**.
    - **SELECTION** — *which surface is here* — must be BAKED. The vertex
      normal is the DECIMATED mesh's normal and flattens with distance,
      so a slope-selected layer dissolves exactly where it was needed.
      R2 rejects this twice.
    - **SHADING** — *how to project the surface already selected* — may
      read live. Triplanar's slope blend is the worked example: as the
      normal flattens with distance the projection weighting softens,
      and it softens precisely where UV stretching is already sub-pixel.
      **The degradation lands where it does not matter.**
    The test is not "is this the vertex normal" but "what does this look
    like when it degrades, and does that happen where it counts".

27. **A DESIGN THAT CANNOT CITE ITSELF IS NOT READY TO BUILD, AND THE BAR
    SCALES WITH BLAST RADIUS.**
    Every engine API name in a design carries a source citation, and the
    reviewer OPENS the citation — a reference that does not contain the
    claimed name is worse than none.
    *Worked example, 2026-08-03:* four designs came back from review;
    macro variation carried **13** uncited names and RVT **20**. RVT
    spawns actors and allocates GPU memory on a machine that has already
    lost its GPU to a driver timeout once. **Both were HELD.** A design
    for a pure-arithmetic node graph and a design that allocates video
    memory do not get the same benefit of the doubt.

24. **TWO LISTS THAT MUST AGREE ARE ONE LIST, BADLY STORED.** When a
    requirement is checked in more than one place — a preflight and an
    assertion, a producer and a consumer, a spec and its test — those
    places must **DERIVE FROM A SINGLE DECLARATION**. One source of
    truth, N projections of it. "Update both carefully" is not a fix; it
    is non-negotiable 19 at a smaller scale, and it fails the same way.
    **The test:** if adding a thing can be done in one place and forgotten
    in another, the structure is wrong, not the author.
    *Motivating case, 2026-08-03:* sub-surface textures were added to the
    material builder's ASSERTION and not its PREFLIGHT. The build then
    died **after** the destructive graph clear, on an asset that existed
    the whole time — converting REFUSED-BEFORE-TOUCHING-ANYTHING into
    CRASHED-MID-DESTRUCTIVE-REBUILD, which is strictly worse.

25. **PROSE CLAIMS INSIDE CODE ROT LIKE CONFIG COMMENTS. A CLAIM WORTH
    MAKING IN A WARNING STRING IS A CLAIM WORTH ASSERTING.**
    A message that says "X cannot happen" is a belief compiled into
    text, and nothing re-checks it when the code changes underneath.
    *Motivating case, 2026-08-03:* the material builder's failure banner
    read *"Missing texture assets are pre-flighted before the clear and
    cannot cause this."* True when written; false the moment sub-surfaces
    were added — and it printed, unchanged, on the exact failure it
    denied. Either assert the claim or delete it; do not print it.

23. **AN API REMEMBERED IS AN API GUESSED.** Engine interface names —
    accessors, properties, pin names, enum members — verify against the
    LIVE EDITOR or engine source **before a call is written**, not after
    it fails. A plausible accessor that does not exist is the same class
    as a config file read as state (17): a confident answer from a source
    that was never authoritative.
    *Motivating case, 2026-08-03:* probing for the pins of
    `/Engine/.../HeightLerp`, I called
    `MaterialEditingLibrary.get_inputs_for_material_function`. It does
    not exist in 5.8. The function I wanted was real and on disk; the
    accessor for it was invented by me, and it read as knowledge.
    **Corollary, and it is an engineering preference not just a
    protocol:** prefer VERIFIABLE PRIMITIVES over UNVERIFIABLE
    CONVENIENCE. Six arithmetic nodes with a CPU reference beat one
    opaque function call *even when the call works*, because the
    reference makes the graph provable and the call makes it trusted.

22. **A STATISTIC ABOUT A MODULATOR IS ONLY MEANINGFUL CONDITIONED ON
    WHERE IT MODULATES.** Reporting a layer-scoped field against the
    whole map is the MISLEADING-DENOMINATOR class: the number is
    arithmetically true and answers a question nobody asked.
    *Motivating case, 2026-08-03:* the forest-floor selector reported
    ">0.5 on 72.07% of map", which reads as "72% of the world is forest
    floor". Conditioned on the Grass layer it actually modulates, the
    figure is **99.03%** — the sub-surface would replace the primary
    almost everywhere. Same array, two numbers, and only the conditioned
    one is about the decision being made.
    Always state the denominator. Where a modulator can saturate its own
    scope, warn on it — the selector bake now trips a warning above 90%.
    **And read a saturated modulator as EVIDENCE, not only as a defect:**
    99% coverage may be the field telling you the "sub"-surface is
    really the primary and the exception lies elsewhere.

21. **EVERY CHANNEL IN A MULTI-CHANNEL ARTEFACT IS EITHER COMPUTED OR
    EXPLICITLY DECLARED INERT. A SILENT CHANNEL IS AN INERT FIELD.**
    Packed formats — selector maps, weightmaps, ORM textures, any future
    RGBA payload — invite a channel that nobody assigned and nobody
    zeroed. It then carries whatever the allocator or the previous bake
    left there, reads like data, and is sampled by something eventually.
    Write it as zero **and say so in the output**, or compute it. Never
    leave it unstated.
    This is the inert-field class the recipe schema already forbids for
    KEYS (`anchor_m` on an `ADD` placement is refused because an inert
    field reads like a setting). Channels are the same defect in a
    different container.
    *Current instances:* the selector map's R channel — no Snow
    sub-surface is declared, so it is written zero and the bake prints
    that it did; and the ORM convention's B channel, already flagged as
    undiscriminated rather than silently trusted.

20. **ADOPTED ARTEFACTS ARE COPIES AT STABLE NAMES, HASH-PROVEN AGAINST
    THEIR SOURCE AT ADOPTION TIME.**
    Never point a consumer at a generator's live output. A live pointer
    makes "what IS the terrain / the weightmap / the plan" answerable
    only by re-running the generator — and the generator's inputs may
    have moved since. Copy the output to a stable name, assert its
    SHA-256 against the producer's recorded hash **at the moment of
    adoption**, and point the consumer at the copy.
    This is the derived-records rule (15) wearing different clothes: a
    live pointer is a state claim you cannot check without recomputing
    it; a hashed copy is a fact on disk.
    *Motivating case, 2026-08-03:* `import_heightmap` refuses
    `heightmap.source == stamps.output` at the SCHEMA level, so adopting
    a composited terrain cannot be a side effect of running the
    compositor. Adoption copied `alpine_stamped.png` to
    `alpine_heightmap_v2.png` and asserted its hash equalled the
    sidecar's `output_sha256` before the recipe was edited. Re-running
    the compositor now rewrites its own output and cannot touch the
    terrain.

19. **WHEN TWO PASSES RENDER THE SAME PHYSICAL FACT, THE FACT IS
    DEFINED ONCE AND BOTH READ IT. Pass boundaries organise WORK; they
    do not partition TRUTH.**
    A parameter that describes the world — an angle of repose, a cliff
    source angle, a runout length — is pass-independent *because it is
    physical*. Duplicating it so each pass "owns" its copy guarantees
    the two copies drift, and the drift is invisible: both passes
    succeed, both verify, and the artefacts silently disagree.
    **Being physical is the test.** A stylistic knob (a tint, a density
    someone tuned by eye) may legitimately differ per consumer. A
    measured property of rock may not.
    *Motivating case, 2026-08-03:* Pass 2's scree TEXTURE mask and Pass
    3's scree MESH scatter both need the talus deposition field. Had
    each pass defined its own, the scree texture and the scree rocks
    would have landed in **different places** — a defect no single
    pass's verification could detect, because each would be internally
    consistent. `foliage.rock_scatter` is now the single source and
    `rock_scatter.talus_deposit()` the single implementation.
    *What surfaced it:* `rock_scatter.py` **refused with exit 2** —
    "recipe declares no `foliage.rock_scatter` block" — rather than
    defaulting. **That clean refusal is the behaviour being praised
    here.** A guess at those parameters would have run, produced a
    plausible field, and baked the divergence in silently. A tool that
    fails closed on missing shared truth is how the shared truth gets
    noticed at all.

18. **A REQUIRED OUTPUT FIELD IS AN INSTRUCTION.** A mandatory field in a
    subagent's output schema *asserts that the thing exists*. If it may
    not apply to every input, make it optional or explicitly nullable,
    and say what null means — e.g.
    `"import_plan": null — pipeline input, no engine import`.
    **Never hand one schema to jobs of different KINDS.**
    *Motivating case, 2026-08-03:* I required an `import_plan` for a pack
    I had myself labelled "a PIPELINE INPUT, not an engine import". The
    agent resolved the contradiction by inventing something to import — a
    terrain replacement nobody wanted — and a diligent reviewer then
    spent a third of an expensive audit finding real defects in the
    fiction I had commissioned. **When a reviewer's findings concern work
    you did not request, that is a brief defect, not a reviewer defect.**
17. **A CONFIG FILE RECORDS DIFFERENCES FROM A DEFAULT. Reading one
    tells you what was OVERRIDDEN, never what is IN EFFECT.**
    **Plugin and feature state verifies against the LIVE EDITOR** —
    query the running instance, or the plugin's delivered content on
    disk, or the `.uplugin`'s `EnabledByDefault` flag. Never
    `.uproject` alone.
    *Motivating case, 2026-08-03:* I read `LandscapeLab.uproject`, found
    no `Fab` entry, and reported the Fab plugin as DISABLED — escalating
    a "gating click" that blocked all Fab content. `Fab.uplugin`
    declares `"EnabledByDefault": true`; the `.uproject` array is
    per-project OVERRIDES only, and the plugin had been working the
    whole time. **I read an absence as a negative when it carried no
    information about the state at all.**
    Three instances of this mechanism now, in three different files:
    `sg.*` in `[SystemSettings]` setting a value without applying the
    group; `t.MaxFPS=45` present in the ini and `0.0` in the editor;
    and this. **The file is not the state.**

---

> **MOVED HERE FROM `CLAUDE.md`, 2026-08-29, VERBATIM.** It is verification
> doctrine and belongs beside the non-negotiables; the index routes all
> gate and measurement work to this file. Not weakened, not retired.

# THE AUDIT

**Not a gate. Still the highest-value habit.** No verdict blocks
execution; nothing waits on it.

`LESSONS.md` Division 3 is a table of defects an independent review caught
*before first execution* — an enum removed in 5.8 that would have crashed
every run; a residency gate that would have passed **exactly when loading
failed**; a "refusal" that mutated and saved before printing REFUSE; two
findings that meant a script could not run at all. Not one was found by
the author.

- **Reach for review when the cost of being wrong is not recoverable by
  git** — anything that deletes, saves, or mutates editor state a reload
  will not restore.
- **Skip it freely** for generators, analysis, materials, docs, and
  anything whose failure mode is a bad number in a printout.
- Every review that runs is logged to `LESSONS.md` Division 3 with its
  verdict and findings; every edit it makes appears in its findings list.
- Every audit prompt states `REPO_ROOT` and `UE_PROJECT_ROOT` as absolute
  paths, verbatim, at the top.

---


## 29. A GUARD ASSERTS ON THE VALUE AT THE POINT OF USE, NEVER ON THE CORRECTNESS OF THE STEP THAT PRODUCED IT

**Ruled 2026-08-30, after two guards in one session caught hazards neither was
designed for.**

    written against  a TYPO in a destination path
    caught           MSYS2 rewriting /Game/Scratch/X into
                     C:/Program Files/Git/Game/Scratch/X

    written against  more than one CURRENT STATE block existing
    caught           a swap script about to truncate CLAUDE.md to 424 bytes,
                     because it had matched the file's prose mention of the
                     heading instead of the heading

Neither author imagined the mechanism that eventually fired. Both guards
worked anyway, and they worked for the same structural reason: **they checked
the VALUE that was about to be used, immediately before using it.** A check
positioned there does not need to anticipate how a bad value arrives — shell
rewriting, a bad regex, a typo, a refactor, a wrong argument order all
converge on the same observable.

**The contrast is what makes this a rule.** A guard written as *"refuse if
DEST is empty"* — an equally reasonable-sounding defence of the same delete —
would have passed `C:/Program Files/Git/Game/Scratch/ForgeChurch` and
attempted the deletion there. It guards the STEP (did we forget to set it?)
rather than the VALUE (is what I am about to delete inside /Game/Scratch/?).

**In practice:**

* Assert the property the operation actually requires, at the line that
  performs it — not that the preceding step ran, returned, or looked right.
* Prefer a positive shape (`must start with /Game/Scratch/`) over an absence
  (`must not be empty`). Absences are satisfied by any nonsense.
* Advice is not enforcement. A "run this from PowerShell" header on a
  generated command is useful and is not a check; the check belongs where the
  value is consumed. Both were kept — belt and suspenders, ruled 2026-08-30.
* A guard that can only go green by matching a message is asserting on prose.
  Verify it can FAIL.
