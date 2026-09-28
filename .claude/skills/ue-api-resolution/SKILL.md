---
name: ue-api-resolution
description: How to establish an Unreal Engine 5.8 API before calling it — the resolution order, the reflected-surface rule, and the casualty list of names that meant something other than they read. Use before writing or calling any Unreal API, property, enum or MCP tool, especially an unfamiliar one.
when_to_use: writing a UE Python payload; calling an unfamiliar unreal API; a property read returns nothing; an accessor raises; choosing between a C++ signature and the Python one
allowed-tools: Read, Grep, Glob
---

# UE 5.8 API resolution

Training data predates 5.8. **An API remembered is an API guessed.**

## Resolution order

1. **unreal-mcp `SemanticSearchToolset`** — query the RUNNING editor.
   This is the engine we actually have; it outranks all documentation.
2. **`describe_toolset` before `call_tool`.** Never guess arguments.
   Re-read each session — Unreal MCP is Experimental in 5.8 and drifts.
3. **context7**, scoped to the subsystem.
4. The 5.8 documentation.

Cheapest reliable move for a Python payload: **enumerate the reflected
surface in one pass** rather than burning the two-failure budget one
guess at a time.

    sorted(n for n in dir(unreal.Texture2D) if "source" in n.lower())

That is how `get_num_triangles`, `get_lod_screen_sizes` and
`compute_texture_source_channel_min_max` were established. It is also how
`get_inputs_for_material_function` was found NOT to exist after being
confidently written.

## Then, in order of authority

- **The reflected Python surface is the contract, not the C++ header.**
  C++ declares `SetLightColor(FLinearColor, bool bSRGB)`; Python exposes
  one argument.
- **Prove the call reaches the code, not just that the code exists.**
- **A value can arrive and still mean something else.** Ask not only
  "did it arrive" but **"in what units, in what space, against what
  datum".**
- **If a lookup contradicts an assumption, the lookup wins — say so.**

## The datum trap, twice in one session

- `written_utc` is UTC. Read as a local date, it dated seven records a
  day ahead.
- `intensity_lux` is honestly named — the number really is in lux — and
  it is **top-of-atmosphere** illuminance, because
  `atmosphere_sun_light` is unconditionally true. A ground-level value
  there is attenuated twice, and the scene was 5× underlit.
- `azimuth_deg` is the light actor's **yaw**, the direction light
  TRAVELS. Read as the sun's bearing it puts a camera on the shadowed
  side. The sun is at `azimuth − 180`.

**A unit is not a datum.** A correctly-named field can still be measured
somewhere else.

## The casualty list — names that meant something else

- `ReductionSettings[0]` **IS** LOD 0 — the obvious LOD chain would have
  decimated the source mesh.
- `delete_all_material_expressions` does not delete all material
  expressions — 7 wired survivors.
- `CullDistance` 0 means **disabled**, not unlimited — cost a GPU hang.
- `FGrassVariety` has two density fields; the engine reads whichever a
  runtime switch selects.
- `sections_per_component` allows only {1,2} where the docs said 1-or-4.
- `MATUSAGE_Landscape` was removed in 5.8.
- `get_bounds()` returns a **BoxSphereBounds object**, not a tuple.
- `export_assets` takes **path strings**, not loaded objects.
- `get_lod_material_slot` **returns −1** for an out-of-range section
  rather than raising — a walk that stops on an exception runs to 64.

## Operations that destroy their own caller

`load_level` tears down the outgoing world and asserts nothing
references it — and **the executing Python frame IS a reference**.
Merely having read the level in the payload is enough to fatal the
editor at `EditorServer.cpp:1951`.

**Use `scripts/open_level.py`.** It releases those references
(`gc.collect()`) immediately before the call, atomically with its guard.
It had already root-caused that crash twice before it was reinvented.

The general form: **an operation that destroys the context its caller
runs inside must explicitly release the caller's references first** —
and the tool that does so probably already exists, so **look before you
build**.
