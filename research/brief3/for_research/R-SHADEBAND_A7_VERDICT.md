# A-7 (R-SHADEBAND) — shade pair on the 09-13 instrument, verdict with its white point

2026-09-15. Editor verified `/Game/Alpine8K`, capture certified
(residency PASS). Measured by `scripts/shade_card_pair.py --measure-ppi0`
on the multilayer EXR's `FinalImagePPI0` channel — the 09-13 instrument:
PPI0 (scene-linear, pre-tonemap), each channel divided by the lit card's
own channel (von Kries with the 18% neutral that is physically in frame),
metric `(B/luma shade)/(B/luma lit)`, Rec.709 luma.

## Verdict

    measured shade/lit B/luma   2.1896
    band                        2.229 - 2.998
    white point                 3438.6 K   (the IN-FORCE grade white point)
    verdict                     FAIL -- 0.039 (1.7%) below the floor

    lit card linear RGB    [0.1838, 0.1015, 0.0466]
    shade card linear RGB  [0.0103, 0.0085, 0.0087]
    shade normalised       [0.0561, 0.0836, 0.1865]
    shade crop std luma    0.00022  (uniformly shadowed)

## The band tracks the white point (R-SHADEBAND), and A-6 moved it

The desk's ruling gave the band as 2.254-3.029 @ 3415.7 K — but that
assumed 3415.7 stayed the white point. **A-6's joint WB solve adopted
3438.6 K this session**, so by the ruling's own construction ("the band
belongs to the CURRENT white point; whenever white_temp_k moves this
command runs first") the band re-derives at 3438.6:
`shade_reference.py --white 3438.6` → **2.229-2.998**. The
shade_card_pair selftest now RE-DERIVES the band from shade_reference at
BAND_WHITE_K, so the constant can never silently drift from the white
point again.

## Reading the FAIL (not tuned — scope fence)

The shade fill is marginally WARM of the daylight-shade model's floor:
2.1896 vs a 2.229 floor. This is a measurement with a verdict, not a
target — no lighting or grade value was moved to chase it (the scope
fence permits only A-3's ruling and A-6/A-7's solve). For reference, the
09-13 measurement read 2.2598 against the then-band 2.184-2.940 (PASS,
white point 3481.9) — but the scene, sky (R-SKYCOLOR), grade and HLOD all
moved between then and now, so the two are not a clean before/after.

The gap is small (1.7%) and the desk owns whether to close it (more sky
fill, per the historical slope note) or to accept the shade as-measured
and record the band edge. Recorded for the desk; nothing changed.

## Provenance

Placed: `scripts/shade_card_pair.py --place --station near_ground`
(blocker cube 40 cm at 90 cm along the card-to-sun ray, sun-to-camera
32.55 deg — clears the card). Captured: `bench_capture --profile target
--stations near_ground --linear --pp-pass PPI0 --exr-multilayer --tag
a7_shade_ml` (multilayer so the PPI0 pass is the FinalImagePPI0 channel,
reproducing the 09-13 construction). Cards REMOVED and level saved after
measurement (`shade_pair_remove.py`) so they cannot contaminate later
near_ground captures (R-SHADE).

---

## AMENDMENT 2026-09-15 — the floor is D6000 for a low sun, and the verdict FLIPS to PASS

R-SHADEBAND amendment (desk): the shade illuminant floor is **D6000, not
D6500**, whenever the sun is below ~30 deg elevation. The shade card sees
hemispherical skylight only, and low-sun skylight is warmer (less blue)
than the D6500 overhead-daylight default — Hernandez-Andres et al.,
"Color and spectral analysis of daylight in southern Europe", JOSA A 18
(2001). This recipe's sun is at 12 deg, so the floor moves to D6000.

    band re-derived   shade_reference.py --white 3438.6 --shade 6000 10000
                      -> 2.065 - 2.998   (was 2.229 - 2.998 at the D6500 floor)
    measured (A-7)    2.1896   -- UNCHANGED, no new capture
    verdict           PASS     2.065 <= 2.1896 <= 2.998  (sits at ~D6380)

The FAIL reported above was against the D6500 floor. Nothing in the scene
moved; the acceptance band's shade-illuminant range was corrected for sun
elevation. shade_card_pair.py now carries BAND_FLOOR_K = 6000 and its
selftest re-derives the band at that floor, so a future white-point OR
floor change cannot silently drift the constant.
