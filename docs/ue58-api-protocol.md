> # ✅ LIVE DOCTRINE — THIS IS LAW, NOT HISTORY.
>
> Extracted verbatim from `CLAUDE.md` on 2026-08-29 by the doc-consolidation
> unit, purely so `CLAUDE.md` could fit under its size ceiling. **Nothing here
> was weakened, superseded or retired.** It is one index hop away, not
> archived — `docs/archive/` is the archive, and this file is not in it.
>
> **LOAD THIS** before writing or calling ANY Unreal API, property, enum or MCP tool. Training data predates 5.8; this is the resolution order and the reference doctrine.

---

# UE 5.8 RESOLUTION PROTOCOL (HARD)

Training data predates 5.8. Before writing or calling **any** Unreal API,
property, or MCP tool:

1. **unreal-mcp `SemanticSearchToolset`** — query the RUNNING editor.
   This is the engine we actually have. Outranks all documentation.
2. **`describe_toolset`** before `call_tool`. Never guess arguments.
   Re-read each session; Unreal MCP is Experimental in 5.8 and drifts.
3. **context7**, scoped to the subsystem.
4. The 5.8 documentation.

Then, in order of authority:

- **The reflected Python surface is the contract, not the C++ header.**
  C++ declares `SetLightColor(FLinearColor, bool bSRGB)`; Python exposes
  one argument.
- **Prove the call reaches the code, not just that the code exists.**
- **A value can arrive and still mean something else.** Ask not only "did
  it arrive" but "in what units, in what space, against what datum".
- **If a lookup contradicts an assumption, the lookup wins — say so.**
- State the maturity tier of any 5.8 feature you recommend.

## REFERENCE DOCTRINE — see `REFERENCES.md`

**Docs describe INTENT; source is GROUND TRUTH; `RECIPES.md` outranks
both once proven.**

- **Tier 1, local ground truth** — engine source at the 5.8 install path,
  and the generated Python stub
  (`LandscapeLab\Intermediate\PythonStub\unreal.py`) for exact signatures.
  **Grep these BEFORE any API call not already proven in `RECIPES.md`.**
  API-remembered-is-API-guessed extends to DOCS: an API read in
  documentation and never checked against this install is the same
  unverified-derivation class.
- **Tier 2, Epic versioned docs (5.8)** — intent and concepts only, never
  signatures. Foliage Mode; PCG overview; PCG development guides; and
  **PCG Biome Core** as the study target, being the closest shipped analog
  to this project's biome-general schema.
- **Tier 3, everything else** — cite or it didn't happen
  (design-reviewer standard: the reviewer OPENS the citation).

## The one rule that would have prevented most defects

**Read the engine source before trusting a name.** Every value handed to
an API needs its *meaning* confirmed at a source line, not just its
magnitude derived correctly. Getting the number right from a wrong
premise produces confident, wrong output.

Casualties: `ReductionSettings[0]` IS LOD 0, so the obvious LOD chain
would have decimated the source mesh; `delete_all_material_expressions`
does not delete all material expressions; `CullDistance` 0 means
"disabled", not "unlimited", and cost a GPU hang; `FGrassVariety` has two
density fields and the engine reads whichever a runtime switch selects;
`sections_per_component` allows only {1,2} where the docs said 1-or-4;
`MATUSAGE_Landscape` was removed in 5.8; `hit_actor` is a Blueprint
break-node PIN name, NOT a property — `FHitResult` carries
`HitObjectHandle`/`Component`, so a Python read of `hit_actor` finds
nothing (`Engine/HitResult.h:126-131`; cite LESSONS.md:1754);
`ReadRenderTargetRawPixelArea`'s `min_x`/`min_y`/`max_x`/`max_y` are NOT a
bounding box — they forward positionally into `X, Y, WIDTH, HEIGHT`, so
`max_*` are sizes not corners (`KismetRenderingLibrary.cpp:454, :326`; cite
LESSONS.md:1898).

---



---

## THE CAMERA MIRROR TRAP — SCREEN ORDER IS NOT WORLD ORDER (2026-08-30)

**`unreal.Rotator` is (ROLL, PITCH, YAW) — roll first.** That one has cost this
project three cameras set to a -25 degree ROLL while the author believed they
had set pitch, and each frame still looked plausible enough to ship.

**And a second, subtler one.** UE's right-vector for yaw *y* is
`(-sin y, cos y, 0)`: at yaw 0 the camera's right is **+Y**, and at **yaw 90 the
camera's right is -X**. So a row of actors laid out along ascending X appears
**RIGHT-TO-LEFT** in a frame shot at yaw 90.

    2026-08-30, Hair_Stage. Three variants at x -80.6 / 0.0 / +80.6, shot at
    yaw 90. Read left-to-right off the image, the labels came out REVERSED --
    which would have reported two instances of the SAME material as differing
    more than a different material did. The exact opposite of the truth.

**NEVER INFER ACTOR IDENTITY FROM SCREEN POSITION.** The level knows: ask it
for `get_actor_location()` and the material, and label the measurement from
that. A camera convention is not a thing to derive from a picture — the picture
is the thing you are trying to explain.
