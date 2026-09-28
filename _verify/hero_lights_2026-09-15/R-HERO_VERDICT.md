# R-HERO (closure A-3) — the HeroStage lights do not reach the bench, by two instruments

2026-09-15. Editor verified against UE_PROJECT_ROOT (bootstrap), level
verified `/Game/Alpine8K` (audit_level_gate: 4,339 actors, Landscape 1,
LandscapeStreamingProxy 256). Payload: `scripts/payloads/hero_lights_readback.py`
(audited PASS). Raw output: `_verify/hero_lights_readback_2026-09-15.txt`.

## The table — every DirectionalLight in the level (n = 4; rule 13)

| light | intensity (lux) | affects_world | visible | atmosphere_sun_light | atmo index | cast_shadows | lighting_channels |
|---|---|---|---|---|---|---|---|
| HeroStage_Key | 25,000 | **False** | True | False | 0 | True | ch0 only |
| HeroStage_Fill | 7,500 | **False** | True | False | 0 | True | ch0 only |
| HeroStage_Rim | 11,250 | **False** | True | False | 0 | True | ch0 only |
| Lighting_alpine_8k_Sun | 130,000 | True | True | **True** | 0 | True | ch0 only |

Reading, against R-HERO's doc basis: `affects_world` is
LightComponentBase's master disable — a disabled light contributes to the
scene in no way; `visible` True is irrelevant when it is False. None of
the three requests an atmosphere-light slot (`atmosphere_sun_light`
False), so the sun holds the only occupied slot of the two supported.

## Why the prescribed capture pair was NOT run

A-3 prescribes one PPI0 capture "with all three disabled (affects_world
False) vs the standing baseline" — **and affects_world False IS the
standing baseline.** Both arms of the pair would be the identical world
state; the delta would measure capture noise and attribute it to the
lights. The pair is degenerate, so it was not captured.

## The second instrument (replacing the degenerate capture): the disk

The three light actors' OFPA packages, located by content search and
confirmed by UAID + label inside the bytes:

    HeroStage_Key    ...\5\6K\FXY62MVLLU3CKBQY0PC4CS.uasset  2026-08-27 18:28
    HeroStage_Fill   ...\6\UW\6ZB3AZ0LGOE3EA6Q76BE4F.uasset  2026-08-27 18:28
    HeroStage_Rim    ...\9\DS\22V78TEOPWST2M6KD3R7HC.uasset  2026-08-27 18:28

**None has been written since 2026-08-27** — seventeen days before the
first grade number in question. Every capture since 09-13 ran in an
editor loaded from this disk state, and the live read-back above is that
same disk state loaded today. Two representations — the live reflected
property and the persisted package dates — agree.

## Verdict

- **The ruling does NOT trigger.** Contribution to bench frames is zero
  by the master-disable property, held on disk through the entire
  window. **No grade number since 09-13 needs re-reading.**
- **Nothing was mutated, so nothing needed restoring** — the
  hero_lights_set payload (built and audited for the trigger path) was
  never run.
- STATE's ⚠ "three HeroStage_* DirectionalLights are live in the world
  level … contribution not established" is CLOSED: they are present but
  disabled. Presence is not contribution — the 09-14 probe docstring
  said exactly this, and the read-back now proves the safe branch.
- Deletion/relocation of the HeroStage rig stays with the hero-parked
  scope (R-O1 archive session), not this closure.

## Instrument notes

- `scripts/hero_delta.py` (per-depth-bin luma delta, selftest 7/7 PASS)
  was built for the trigger path and stands ready; it was not exercised
  on real frames this session because the pair was degenerate. Its known
  limit, recorded per the audit round-trip: it stamps
  `instrument: finalimage_linear` from its caller's construction and
  does not itself verify the EXR's provenance — pair it only with
  same-session --linear captures.
- The readback payload filters on exact type `DirectionalLight`; a
  Blueprint-subclassed light would be missed. Backstop: the zero-count
  refusal (rule 13) plus the level census (4 directional lights found,
  matching the 09-14 probe's count).
