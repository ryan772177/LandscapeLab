# REFERENCES.md — what may be cited, and in what order

Ratified 2026-08-06. **Docs describe INTENT; source is GROUND TRUTH;
`RECIPES.md` outranks both once proven.**

This exists because "API remembered is API guessed" (non-negotiable 23)
kept costing real defects, and because the same failure wears a second
costume: an API read in DOCUMENTATION and never checked against the
install. Both are confident answers from a source that was never
authoritative for THIS engine.

---

## Tier 1 — LOCAL GROUND TRUTH. Grep before any API call not already proven in RECIPES.md.

| What | Where |
|---|---|
| Engine source | `C:\Program Files\Epic Games\UE_5.8\Engine\Source\` |
| **Generated Python stub — exact signatures** | `LandscapeLab\Intermediate\PythonStub\unreal.py` |

**The stub is the reflected surface, which is the contract.** C++ declares
what the engine has; the stub declares what Python can call, and they
differ — `SetLightColor(FLinearColor, bool bSRGB)` in C++ is one argument
in Python.

Worked examples from the session that ratified this file:

    LandscapeComponent.h:643   int32 ForcedLOD    UPROPERTY(EditAnywhere,
                                                  BlueprintReadOnly)
    LandscapeComponent.h:1300  SetForcedLOD(int32) UFUNCTION(BlueprintCallable)
    LandscapeProxy.h:491       bool bEnableNanite  -> enable_nanite
    PythonStub unreal:242932   Actor.set_is_temporarily_hidden_in_editor(bool)
    PythonStub unreal:381178   set_hidden_in_game(bool, propagate) -- the GAME
                               path, WRONG instrument for an editor capture
    PythonStub unreal:365930   line_trace_single(world_context_object, start,
                               end, trace_channel, trace_complex,
                               actors_to_ignore, draw_debug_type, ...)

That `set_visibility` / `set_hidden_in_game` /
`set_is_temporarily_hidden_in_editor` distinction is the point of Tier 1:
all three are real, all three are plausible, and two of them would have
mutated something the editor screenshot does not photograph — a dead
control that looks like a dead engine.

## Tier 2 — EPIC VERSIONED DOCS (5.8). Intent and concepts, not signatures.

- https://dev.epicgames.com/documentation/en-us/unreal-engine/foliage-mode-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview
- https://dev.epicgames.com/documentation/en-us/unreal-engine/pcg-development-guides
- **PCG Biome Core** — study target: the closest shipped analog to this
  project's biome-general schema. Attribute tables, priority-based spawn,
  and the local/global graph split are the three things to read it for.

Consult for WHY and WHAT FOR. Never take a signature from here without
confirming it in Tier 1 — the docs are versioned but not generated from
this install.

## Tier 3 — everything else: CITE OR IT DIDN'T HAPPEN.

The design-reviewer standard: every engine API name carries a citation,
and **the reviewer OPENS the citation**. A reference that does not contain
the claimed name is worse than none.

---

## Precedence

    RECIPES.md (proven)  >  Tier 1 source/stub  >  Tier 2 docs  >  Tier 3

`RECIPES.md` outranks source ONLY where a recipe is PROVEN — a locked
value that has been executed and verified beats a reading of the source,
because the recipe encodes what this engine on this machine actually did.
An UNPROVEN recipe outranks nothing.

**And this file is itself a derived record** (non-negotiable 15): the line
numbers above were read at ratification and will drift with engine
updates. Re-grep; do not trust them because they are written down here.
