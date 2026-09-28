---
name: texture-conversion
description: Converting and importing textures — the 16-bit single-channel trap, the shared conversion module and why a local re-implementation is a rejected pattern, bit-depth verification before conversion, and the per-role import settings. Use when converting, staging or importing any texture.
when_to_use: converting a texture; importing a surface map; a 16-bit source; checking bit depth; choosing compression or sRGB settings for a role
allowed-tools: Read, Grep, Glob
---

# Texture conversion

Sources: `scripts/texture_16bit.py`, `scripts/import_surface_set.py`,
`RECIPES.md` R3.

## ONE SHARED MODULE — a local copy is a REJECTED pattern

`texture_16bit.py` is the single 16-bit conversion, used by every
importer. It was promoted under NN4a because the fix lived in
`import_static_mesh.py` while `import_surface_set.py` **had none at
all** — the trap class had reached two tools, which is the automatic
escalation trigger.

**A local re-implementation of it is itself a REJECTED pattern.** One
implementation, used by every caller, with a mandatory post-operation
assertion that the result matches spec exactly.

## The trap it exists for

A **16-bit single-channel** PNG goes through a bad import path. Paid for
three times: the grass opacity mask (weightmap clipped to zero, grass
never rendered), and Pass 2's displacement maps which had no conversion
at all.

**RGB 16-bit is NOT in the defect class** — only single-channel.

## The bound is DERIVED, not chosen

`65535 = 257 × 255` exactly, so a full-range 16-bit value maps to a
full-range 8-bit value with **no datum shift**, and `+128` rounds.

    MAX_REQUANT_RESIDUAL = 128        # exact integer bound

`1/512` ("half an 8-bit step") was written first and **refused a correct
conversion by 3e-8**. The derived constant then still refused by one
ULP, because the observed error *equals* the bound and the two sides
reach the same real number by different operation orders — so the
assertion moved into **INTEGER space**, where `|v − 257q| ≤ 128` is
exact.

**Twice the tempting fix was a slightly larger number. The second would
have admitted conversions off by a whole step.**

Mask-coverage tripwire is **33025** (`= 129×257 − 128`), **not**
`128×257 = 32896`. They are not the same threshold and the difference
refused real data.

## Verify the SOURCE depth before converting

An 8-bit export of a 16-bit source is silent precision loss wearing a
familiar file extension.

    blueprint_get_texture_source_disk_and_memory_size() / (w*h)
      4 bytes/px -> BGRA8 (8-bit)
      8 bytes/px -> 16-bit RGBA
      2 bytes/px -> 16-bit grayscale

Let the shared module return the verdict — it reports *"not the 16-bit
single-channel defect class"* rather than fabricating precision, and
that verdict belongs in the provenance record.

## Per-role import settings (read back and asserted)

| role | suffix | sRGB | compression |
|---|---|---|---|
| color | `C` | **True** | `TC_Default` |
| normal | `N` | False | `TC_Normalmap` |
| roughness | `R` | False | `TC_Masks` |
| ambient-occlusion | `AO` | False | `TC_Masks` |
| displacement | `D` | False | `TC_Grayscale` |

Normals are **vectors, not colour** — sRGB on a normal map is a silent
gamma error, and `TC_Normalmap` also selects BC5.

**Normal convention is DX** (ruling 1). An asset shipping only `*_nor_gl`
is GL and its green channel must be inverted; there is no flip for DX
sets. If the pack ships a height map, **measure** the convention rather
than trusting the filename.

## Register the source

Every imported texture traces to a file in `Free/` through
`manifest.json`, with role, bytes and format. A texture with no manifest
row is a texture nobody can re-derive.
