# THE FACE-COMPARISON CAMERA — framing search and noise floor

2026-08-17. Recipe **R-HEROCAP**; narrative in LESSONS 2026-08-17.
Instruments `scripts/hero_face/likeness/build_capture_stage.py` and
`capture_shot.py`. Stage built in the OPEN level `/Game/Alpine8K`; nothing
was saved.

## THE FRAMING SEARCH — the facing is a property of the asset, so it is
## SEARCHED and confirmed by the landmark gate, not recalled

`--azimuths "90,75,105,60,120,45,135"`. `yaw_frac` is where the nose tip
sits between the two irises; 0.500 is frontal.

    azimuth   verdict      yaw_frac   note
    ----------------------------------------------------------------
      90.0    GATE PASS     0.489     CHOSEN, 0.011 off frontal
      75.0    reject        0.349
     105.0    reject        0.680
      60.0    reject        0.144
     120.0    reject        0.871
      45.0    reject          --      nose outside the iris span (-0.539)
     135.0    reject          --      nose outside the iris span ( 0.682)

**The gate discriminates rather than agreeing with a hope:** yaw_frac moves
monotonically with azimuth across the whole sweep, and only one azimuth is
accepted. Frames kept: `frame_az090.png` (chosen) and `frame_az270.png` (the
back of the head — the framing the search had previously locked while every
candidate was white). The five rejected mid-azimuth frames are in
`_trash/hero_capture_superseded_20260817/` and the search reproduces in one
command.

## THE LOCKED TRANSFORM

    camera loc   [0.0, 86.784, 250167.345]
    camera rot   [pitch 0.0, yaw -90.0, roll 0.0]
    fov          24.0 deg horizontal   (~85 mm on a 36 mm sensor)
    resolution   2048 x 2048
    exposure     AEM_MANUAL, bias 0.0, min == max brightness
    warm-up      30 triggered captures, then the shot
    persist      always_persist_rendering_state TRUE
    lights       Key 90,000 / Fill 30,000 / Rim 45,000 lux, aimed relative
                 to the locked azimuth

Every one of these is READ BACK on every shot and a disagreement refuses
with exit 5.

## THE NOISE FLOOR — n=4, ALL SIX PAIRS, NOTHING CHANGED BETWEEN THEM

    shot       ipd_px     roll_deg   yaw_frac
    noise_a    429.749     +0.212      0.4994
    noise_b    429.625     +0.127      0.4978
    noise_c    429.167     +0.095      0.5002
    noise_d    429.833     +0.183      0.4986

    pair     p50        p90        max        (interpupillary units)
    a-b    0.00206    0.00758    0.01140     <- WORST, adopted
    a-c    0.00194    0.00559    0.01000
    a-d    0.00139    0.00301    0.00640
    b-c    0.00189    0.00305    0.00604
    b-d    0.00144    0.00514    0.00997
    c-d    0.00211    0.00450    0.00897

    ADOPTED BAR    p90 0.00758 IPD = 0.057 cm
                   max 0.01140 IPD = 0.086 cm
    scale          0.01745 cm/px, IPD 429.79 px = 7.502 cm
                   pinhole off the locked camera, APPROXIMATE

**The worst pair is 3.2x the best, and an earlier n=2 run of this same test
answered 0.00240** — near the bottom of that spread. The bar is the worst
pair, not the mean: a floor that averages away its own bad case is a floor a
real delta can hide under.

**CALIBRATION CLASS.** This bar belongs to this stage, this level, this
editor session and this GPU. Re-measure before quoting a delta across an
editor restart.

## WHAT THIS BUYS THE AXIS TEST

A 2.0 cm neutral-joint translation should read about 0.27 IPD, roughly
**35x the adopted p90**. If the first DNA write reads anywhere near the
floor, the write did not reach the mesh — which is the question the axis
test exists to answer, not a threshold to be relaxed.

## STATED PLAINLY

- The stage lives only in the open editor's transient level. Nothing is
  saved, so a restart costs a rebuild and a re-measured floor.
- The pinhole scale is derived from the manifest's own orbit distance, not
  measured on the head; the irises sit nearer than the orbit centre, so the
  cm figures are good to a few percent.
- `vt_persist.png` is kept because it is the evidence for the white-render
  root cause: a frame with mean 161.7, std 92.8 and full 0-255 range that
  MediaPipe still refuses, because it is the back of a head.
