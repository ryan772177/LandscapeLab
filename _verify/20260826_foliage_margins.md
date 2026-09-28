# Foliage clearing margins, measured — REPORT ONLY

**2026-08-26. Nothing was removed.** Dry runs of
`scripts/city_clear_foliage_payload.txt` with `COMMIT=False`; no instance
removed, no foliage package touched, tree clean throughout.

## The counts are ADDITIONAL, not totals

2,541 trees were already cleared at the shipped **3 m building / 2 m street**
margins. Those are gone, so a wider margin only ever finds NEW ones.

| margin | additional | cumulative | remaining of the original 6,244 |
|---|---|---|---|
| 5.0 m | 960 | 3,501 | ~2,743 |
| 10.0 m | 2,259 | 4,800 | ~1,444 |
| 15.0 m | 2,873 | 5,414 | ~830 |

Margin applied equally to building footprints and street edges.

### By species, at 15 m

    SM_PVE_Norway_Spruce_01_A   912
    spruce_half_01              764
    ScotsPineTall_01            642
    spruce_small_05             555

## Two notes on the measurement

**The scan widened at 15 m** — 7,280 instances examined against 6,369 at the
narrower margins — because more foliage actors overlap the expanded shapes. The
bounds filter still limits the work to a handful of the 1,093 foliage actors.

**Idempotence holds:** the 6,369 baseline is 8,910 minus the 2,541 already
removed, so the dry run is measuring the world as it stands rather than
re-counting cleared trees.

## No ruling taken

The shipped margin stays 3 m / 2 m. At 15 m roughly **830 of the original 6,244**
trees would remain inside the town extent — that is a different settlement, open
ground with a few specimen trees rather than houses in a wood. An art call, not
a measurement.
