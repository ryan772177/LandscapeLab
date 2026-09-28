---
name: material-builder
description: Building or editing the landscape material — the ONE DECLARATION pattern, sampler-type rules, the destructive-clear ordering trap, CPU-model invariants, and the wiring calls that fail silently. Use when touching make_landscape_material.py, the landscape material graph, or any material builder.
when_to_use: editing make_landscape_material.py; adding a texture or sampler; changing the material graph; a material compiles but renders wrong; wiring material expressions
allowed-tools: Read, Grep, Glob
---

# Material builder

Sources: `RECIPES.md` R2, `scripts/material_graph.py`,
`scripts/make_landscape_material.py`.

## THE ONE DECLARATION

The **preflight**, the **sampler type**, and the **post-build
assertion** are three PROJECTIONS of a single declaration. They are not
three lists to keep in step.

**Two lists that must agree are one list, badly stored** (NN24). The
test: *if adding a thing can be done in one place and forgotten in
another, the structure is wrong, not the author.*

*What this cost:* sub-surface textures were added to the ASSERTION and
not the PREFLIGHT. The build then died **after** the destructive
`delete_all_material_expressions`, on an asset that existed the whole
time — converting REFUSED-BEFORE-TOUCHING-ANYTHING into
CRASHED-MID-DESTRUCTIVE-REBUILD, which is strictly worse.

**So: preflight everything before the clear.** The clear is the point of
no return in memory.

## Silent failures to guard

- **`connect_material_expressions` ignores failures**
  (`MaterialEditingLibrary.cpp:928-943`). Use `_ll_wire`, which raises.
  93/30/10 unchecked calls were found across three builders.
- **`delete_all_material_expressions` does not delete all material
  expressions** — 7 wired survivors on `M_fir_bark`, which is how every
  conifer trunk rendered the twig atlas while the build reported
  success.
- **`texture_map` silently last-wins on a contested role.** A builder
  invoked without `--slot` sampled the wrong textures and never a right
  one.
- **`AutoSetSampleType` fires on texture assignment and overwrites the
  declared sampler type** (`MaterialExpressions.cpp:2625-2634`). Read
  the engine's choice BEFORE overwriting it, or the gate reads back what
  you just wrote and proves nothing.

## Sampler types

`VerifySamplerType` **errors on EVERY mismatch** and applies an EXTRA
sRGB check that fires only for Normal and Masks. It does NOT "compile
clean and silently wrong" — that claim was in two of our own docstrings,
was repeated into a REJECTED entry, and is false. **An unverified claim
in our own code contaminated the knowledge base**; fix the seed as well
as the copy.

Verify with `scripts/audit_material_samplers.py`, which reads the BUILT
graph and asks the ENGINE what each asset needs. It shares no code with
the builder's own check (NN8).

## CPU-model invariants

Every shader construct has a CPU mirror with an invariant suite, and
they run **at module import** via `_assert_cpu_model_invariants()`.

**They were dead for a while — defined, correct, and never called** —
while RECIPES claimed they were "proven before any editor contact". Two
lessons stuck:

- **Assert over the domain the VALIDATOR admits, not the value the
  recipe ships.** Sign-independence was tested only at `sharpness = 2.0`
  where `nx**s ≡ |nx|**s`, so deleting the `Abs` it guarded changed
  nothing.
- **At least one property must reference an INDEPENDENT
  implementation.** Six self-referential properties all survived a
  mis-wiring that masked the Z weight; property 7 (at m=1 the blend must
  equal canonical triplanar, from a separate reference) caught it.

Prove them: `python scripts/prove_gates.py` — mutations must be refused.

## Renders

A material that compiles is not a material that is right. Snow's and
Grass's slope masks were identically ZERO over the entire terrain,
~92% of the landscape was painted by a background constant, everything
compiled, and it took a numpy simulation of the node graph to see it.
