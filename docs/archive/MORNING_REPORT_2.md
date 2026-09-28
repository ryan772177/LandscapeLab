# ⛔ SUPERSEDED — session report, superseded by STATE.md. History only, never a source.

# MORNING REPORT 2 — overnight run #2, groom infrastructure + hero hair

**Read the contact sheet first, then the one ruling at the bottom. Everything
between is why.**

---

## 1. THE CONTACT SHEET — your coffee deliverable

`_verify/20260820_hair_shortlist/CONTACT_SHEET.png`

Six stock hairs on the hero at one locked framing, the ruled reference in the
first cell, every tile captioned with its gate verdict and **crown fraction**.

    L_MessyClumps      PRESENT  crown 57%  114k px
    M_BobBangs         PRESENT  crown 69%  124k px
    M_BobMessy         PRESENT  crown 65%  117k px
    M_Layered          PRESENT  crown 46%   93k px
    M_SideSweptFringe  PRESENT  crown 70%  105k px
    S_Messy            PRESENT  crown 97%   67k px

**My read, and it is yours to overrule: `M_SideSweptFringe` remains the best
stock match.** The reference is a shaggy medium — volume on top, a fringe
across the brow with the brows still visible, ears covered, jaw length.
`M_BobBangs` has a fringe but a blunt, low one. `L_MessyClumps` has the
texture but parts in the middle. `M_BobMessy` curtains the eyes and fails the
brow gate. `M_Layered` and `S_Messy` are the two length extremes.

**The character is set to `M_SideSweptFringe` and re-assembled**, so the hero
you open in the morning is wearing the recommendation, not the last
experiment.

---

## 2. THE HEADLINE FINDING — the design fork is answered, NEGATIVELY, and it is one call

**A custom groom cannot currently reach any character in this project.** Not
the hero, not a party member. Both routes were built and both failed at the
same place.

    direct: duplicate groom -> build binding -> assign to component
            -> BALD CROWN with a clump of strands hanging at the jaw
    wardrobe: build archetype binding -> mint wardrobe item -> select
            -> assemble -> NO HAIR AT ALL, empty Hair component

The cause, from the engine's own log, on **all eight** bindings built tonight:

    LogHairStrands: Display: Waiting for groom bindings to be ready 0/1 (BND_...)

`GroomLibrary.create_new_groom_binding_asset_with_path` creates the asset —
it exists, it saves, every property reads back correctly, the parameters are
IDENTICAL to a working assemble-built binding — and **its build never
completes**. Held four minutes and re-rendered: identical pixels. The strands
that do draw are the free-hanging ends, which need no root attachment.

**Vendor wardrobe items work for exactly one reason: their bindings ship
already built.**

### THIS IS THE PARTY-CHARACTER ARCHITECTURE FLAG

Every character you add is limited to the 38 stock hairs until this one
question is answered. The Blender→Alembic pipeline you promoted to strategic
infrastructure is complete on the authoring side and blocked on the UE side by
a single engine call. **Not blocked by design, licensing or scope — by one
async build that does not finish.**

### THREE ROOT CAUSES IN ONE NIGHT, AND I COMMITTED TWO WRONG ONES

Worth your attention because the pattern is mine, not the engine's:

1. *"Vendor content cannot bind"* — tidy, committed to LESSONS **and**
   RECIPES as R-GROOMBIND **PROVEN**.
2. *"The assemble conditions the groom, re-projecting roots"* — an
   interesting architectural discovery, written into the correction.
3. *"The build never finished and I did not read the log"* — boring, and true.

They rank in order of how flattering they were to the investigator. I locked
(1) on gate numbers that were every one of them true — `Hair PRESENT,
155,153 px, 87.2x floor, drift 0.0%` — over a picture nobody had opened. It
was a hanging clump. **R-GROOMBIND is struck in place with the symptom in its
REJECTED section; the retraction is louder than the original.**

And I *did* read a log for (2) — the stale one. `LandscapeLab.log` goes cold
at every editor restart while the live session writes `LandscapeLab_2.log`.

---

## 3. `ingest_groom.py` — built, character-agnostic, and waiting on that call

Exists, runs end to end, and its binding step is refuted. What works and is
reusable the moment the blocker lifts:

- **character-agnostic by construction** — `(character, slot, style, version)`
  resolved through `characters/registry.json`; the hero is invocation #1
- duplicate-into-project-content, colour on a material we own, provenance
  sidecar per groom (`.abc` sha256, import settings, binding target, colour)
- **wardrobe minting works**: a `MetaHumanWardrobeItem` holds a **binding**,
  not a groom, in an `EditorOnlyAssetReference` struct whose `asset` field is
  read-write. Repoint verified across a save and reload.

Integration-test frame: `_verify/20260819_hair_catalogue/
ingest_integration_frame.png` — and it is an HONEST FAILURE, showing the bald
crown, not a success.

---

## 4. THE INSTRUMENT GOT BETTER, TWICE

**`groom_presence.py` now has a crown check.** A presence gate certifies
presence and nothing adjacent; a hair whose binding never built reads
"PRESENT" with a big number while the scalp is bare. Proven both directions on
one character, one framing, one variable:

    our binding      145,194 px  83x floor  crown  1%   SCALP-BALD
    assemble binding 117,304 px  71x floor  crown 66%   PRESENT

**Sixty-six-fold separation on the discriminating statistic, while the
headline pixel count FAVOURS the broken render.**

**`catalogue_run.py` is resumable by construction** — each hair writes its row
as it completes, indexed hairs are skipped, and morning can interrupt it
without loss.

---

## 5. THE COST MODEL, MEASURED

    a hair that has NEVER been on this character   ~12 min (wardrobe+assemble)
    a hair that HAS been, ever                     seconds

Because a groom can be swapped straight onto the component **as long as the
binding it is handed was built by an assemble**. That is what let six hairs be
catalogued in well under the estimate.

**The full 38-hair catalogue was NOT run.** At ~12 min per never-assembled
hair it is ~6 hours, which is over your bar and was correctly parked. The
machinery is built and resumable whenever you want it.

---

## 6. ADVISOR — one consult, and it changed the outcome

`ADVISOR_LOG.md` 2026-08-19 (overnight #2), consult 1. Ruled: stop hunting the
mechanism, accept wardrobe+assemble, mint a wardrobe item for ingest, and
**fix the wrong R-GROOMBIND seed first**.

**Its correction 3b was worth the entire consult:** *"You have not established
that your binding ever BUILT."* That question forced the log check that
replaced root cause (2) with root cause (3). Two wrong root causes were
already in the record; the advisor's question is what stopped a third.

It also predicted the shape of my error — reaching for the interesting
architectural explanation over the boring procedural one.

---

## 7. COMMITS

    e2e5ddc6  PROBE VERDICT: project content (LATER RETRACTED)
    9c151189  RETRACTION: R-GROOMBIND is wrong; I gated and never looked
    87d25f8e  Crown-coverage check: the gate can see WRONGNESS
    3518727d  Shortlist machinery + Blender handoff + cost model
    99fa95e0  The pre-assemble restart is mandatory (I proved it by dropping it)
    e362930c  SHORTLIST CONTACT SHEET
    513b5805  Ingest fork answered NEGATIVELY

Also: `BLENDER_HANDOFF.md` (leads with the honest UE-side state; Skin Cache
**verified** `r.SkinCache.CompileShaders=True` at `DefaultEngine.ini:48`),
`characters/registry.json` (per-character appearance/shape targets, hash-
refused), and one self-inflicted editor hang recorded in full — I dropped the
pre-assemble restart to save four minutes per hair and hit the 20.4 GB spin on
the second hair.

---

## 8. THE ONE RULING I NEED

**Do I spend the next session on "can a groom binding build be forced to
complete from Python?"**

It is one question with four untried candidates: a rebuild/build entry point
on the asset, a save-and-reload cycle, an editor-side Rebuild Bindings action,
or building through the MetaHuman subsystem rather than `GroomLibrary`.

**Yes** unlocks custom hair for every character you will ever add, and turns
`ingest_groom.py` from a stub into the party pipeline. **No** means the stock
38 are the permanent hair palette, the Blender work should not start, and I
should finish the catalogue instead so at least the palette is documented.

I recommend **yes**, time-boxed to two hours, because everything else in the
groom pipeline is already built and waiting behind it — and because the answer
is equally valuable if it is no.
