# sky.color read-back — ⛔ THE VALUE IS sRGB-ENCODED TWICE

**Audit item 4. P1-8 asked for the writer; the writer exists, and
reading its result back finds the value wrong.**

This is what standing rule 12 is for. The parameter was declared,
applied, and reasoned about in a docstring — and never read back. It has
been wrong for as long as the code has existed.

---

## The measurement

Read off the actor 2026-09-13, editor gated on project and level first.
`apply_lighting` was **not** re-run: the recipe is unchanged, so the
actor carries what the last run wrote, and re-running it would be a
lighting write this session was fenced against.

    recipe  lighting.sky.color  [0.42, 0.6, 1.0]   LINEAR
    actor   Lighting_alpine_8k_SkyLight
            light_color         (215, 231, 255)    FColor, 8-bit

## Three hypotheses, one comparison

| hypothesis | predicted bytes | match |
|---|---|---|
| H1 `encode(recipe)` — one encode, the intent | (173, 203, 255) | no |
| **H2 `encode(encode(recipe))`** | **(215, 231, 255)** | **EXACT** |
| H3 `recipe × 255` — no encode | (107, 153, 255) | no |

**Effective colour in the engine vs what the recipe asked for:**

    in force   linear (0.6795, 0.7991, 1.0000)
    intended   linear (0.4200, 0.6000, 1.0000)
    error             +0.2595  +0.1991   0.0000

The sky light is running **substantially less blue** than the recipe
specifies — R is 62 % too high, G 33 % too high, B correct (1.0 is a
fixed point of the curve, which is why the error is invisible in the
channel most likely to be eyeballed).

## Root cause, at two source lines

The host encodes:

    scripts/apply_lighting.py:155
      sky_srgb = ([_linear_to_srgb(c) for c in sky_col] if sky_col else None)
    scripts/apply_lighting.py:396
      _slc.set_light_color(_unreal.LinearColor(r, g, b, 1.0))

and the engine encodes **again**:

    LightComponent.cpp:1130-1134
      void ULightComponent::SetLightColor(FLinearColor NewLightColor, bool bSRGB)
      { const FColor NewColor(NewLightColor.ToFColor(bSRGB));
        SetLightFColor(NewColor); }

    Color.h:429     ToFColor(true) -> ToFColorSRGB()
    Color.cpp:251-267
      FColor FLinearColor::ToFColorSRGB() const
      { ... ConvertLinearToSRGBSSE2(*this) ... }   // linear -> sRGB ENCODE

## ⛔ The docstring asserts the opposite, and that is the seed

`scripts/apply_lighting.py:388-393` says:

> The C++ signature is `SetLightColor(FLinearColor, bool bSRGB = true)`
> but the Python binding exposes ONE argument, so bSRGB is always true
> and **the value is decoded as sRGB**. Recipe colours are linear (same
> as base_color), so the host sRGB-encodes them first and **the engine's
> decode lands back on the linear value the recipe asked for**.

The first half is right: the binding does expose one argument and bSRGB
is always true. **The second half inverts what bSRGB does.** `bSRGB =
true` means *produce sRGB bytes*, i.e. ENCODE. There is no decode
anywhere on this path, so the host's pre-encode is not cancelled — it is
compounded.

This is non-negotiable 9 exactly: **an unverified claim in our own
docstring, reasoned from rather than checked, and wrong.** The
containment is to fix the seed as well as the value.

## The fix — NOT APPLIED, this session is fenced against lighting changes

Pass the **raw linear** recipe value and let the engine encode once:

    _slc.set_light_color(_unreal.LinearColor(0.42, 0.6, 1.0, 1.0))
    -> stored FColor (173, 203, 255)
    -> decodes to linear (0.4200, 0.6000, 1.0000)

and delete the `_linear_to_srgb` pre-encode at :155 together with the
docstring paragraph that justified it.

⚠ **This changes the look of every frame** — the sky light gets bluer and
darker in R and G. It needs a ruling, a before/after pair, and a check
of whatever was tuned against the wrong value in the meantime. Any grade
or white-balance decision taken while the sky light was 26 points of
linear red too high was compensating for this.

## Quantisation floor, stated so the verdict is bounded

`light_color` is an 8-bit `FColor`, so the round trip has a floor of
1/255 ≈ 0.0039 in encoded space. The measured error is **66×** that floor
in R and **51×** in G. The finding is far outside quantisation and does
not depend on it.

## And the other four lights, since "the sun" had to be resolved

The level holds **four** DirectionalLights, so "the sun" is not a unique
actor and was not guessed at:

| actor | class | light_color | intensity | temperature | use_temp |
|---|---|---|---|---|---|
| `Lighting_alpine_8k_SkyLight` | SkyLight | (215, 231, 255) | 1.0 | — | — |
| `Lighting_alpine_8k_Sun` | DirectionalLight | (255, 255, 255) | 130000 | 5200 | **True** |
| `HeroStage_Key` | DirectionalLight | (244, 250, 255) | 25000 | 6500 | False |
| `HeroStage_Fill` | DirectionalLight | (255, 243, 238) | 7500 | 6500 | False |
| `HeroStage_Rim` | DirectionalLight | (255, 255, 255) | 11250 | 6500 | False |

The sun's own colour is pure white with `use_temperature` True at
5200 K, so its tint comes from the temperature, not from `light_color` —
untouched by this defect. **Only the SkyLight is affected**, because
`sky.color` is the only recipe colour on this path.

⚠ Separately: three `HeroStage_*` DirectionalLights are live in the
world level. They are the parked hero-stage rig. Whether they contribute
to bench frames is not established here, and a fourth-and-fifth light
source would matter to any lighting measurement. Flagged, not
investigated.
