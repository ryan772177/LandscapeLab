# Re-baseline at a declared FOV 90 — GPU improved, GameThread rose on every zone

**2026-09-05.** Ruled: declare FOV 90 and resolution in the spline, then
re-baseline.

## WHAT IS NOW DECLARED, AND WHAT DELIBERATELY IS NOT

    fov_horizontal_deg    90.0            SET on the viewport, READ BACK,
                                          and GATED per station
    frame_resolution      [2560, 1440]    STATION RENDERS only (shoot.py /
                                          HighResShot, which can be told)
    viewport_size_policy  RECORDED, NOT SET

**The perf numbers' resolution cannot be declared, only observed.** The
measurement class is the editor viewport, and the viewport is the window —
`measure_frame_cost`'s own calibration block has always said "whatever the
viewport resolution is". Declaring a resolution this toolchain cannot impose
would be a parameter that exists and is never written: exactly the defect the
material `Tiling` scalar had, sitting at its default for every asset while
looking configured.

**The FOV gate is proven in both directions.** With the key removed,
`perf_flythrough` exits 5 before touching the editor:

    REFUSING: recipes/perf_budgets.json spline declares no fov_horizontal_deg.

With it present, every station read back **90.0** and the run proceeded. A
station whose read-back disagreed by >0.05° gets NO VERDICT rather than a
number of unknown class.

## THE RESULT — check_perf says RED

    zone         GPU p90  old -> new         Game p90 old -> new        budget
    plaza          8.84 ->  7.84  (-11.3%)   9.67 -> 14.00 (+44.8%)   12.0/12.0
    main_street    5.73 ->  5.56  ( -3.0%)  10.26 -> 13.90 (+35.5%)    8.0/13.0
    treeline       7.44 ->  7.05  ( -5.2%)  10.80 -> 13.98 (+29.4%)   10.0/13.5
    vista          9.24 ->  8.33  ( -9.8%)  10.20 -> 14.15 (+38.7%)   12.5/13.0

    plaza  Game 14.00 vs 12.00  ** OVER by 2.00 (17%) **   -> RED
    the other three pass inside the 10% tolerance; all four GPU pass

**Budgets NOT tuned.** They are ratified law and a red budget is reported, not
adjusted.

## READING IT HONESTLY

**GPUTime fell 3–11% on every zone.** Consistent with the old baseline having
been captured at a FOV wider than 90 — but that is an inference and cannot be
confirmed, because the old baseline records no FOV at all. It is equally
consistent with run-to-run variance and with world changes since 08-29.

**GameThreadTime rose 29–45% on every zone, and all four now sit within
0.25 ms of each other (13.90–14.15).** That uniformity is the important part.
A per-zone regression would move zones differently — the plaza has the densest
actor concentration in the world and the vista is 1.2 km out, and they now
cost the same on the game thread to within 2%.

**That pattern says the game thread is no longer scene-driven at these
stations.** It looks pinned near ~14 ms by something constant, with the
editor's own frame clamp at 16.67 ms not far above. So I would not read
"plaza breached its GameThread budget" as "the plaza got more expensive" —
the more likely reading is that a systemic cost moved on all four, and the
plaza is simply the zone whose budget sat lowest (12.0, the tightest of the
four).

**What that means for the gate:** the RED is real and correctly raised, and
its cause is probably not in the plaza. Chasing plaza content would be
chasing the wrong thing.

## ⛔ ONE THING I ADDED THAT DOES NOT WORK

`viewport_size` came back **None on all four stations**. I wired
`SystemLibrary.get_viewport_size`, which is a GAME-viewport API and does not
answer for an editor level viewport. So **the viewport resolution is still
unrecorded** — the field exists and is empty, which is worse than absent if a
reader takes `None` for a measurement.

Stated plainly rather than left to be discovered: the resolution half of the
original problem is **not fixed**. The FOV half is.

## WHAT WOULD CLOSE THE REST

1. **Record the viewport size properly** — it needs the editor viewport
   client's size, not the game viewport's. Until then, comparability across
   runs rests on the machine's window being the same size, which nothing
   checks.
2. **Find the systemic GameThread shift** before touching any zone's content.
   The 29–45% uniform rise is one cause, not four.
3. The pre-2026-09-05 baseline stays of **unknown FOV** and should not be
   compared against future runs as though it were a like-for-like control.
