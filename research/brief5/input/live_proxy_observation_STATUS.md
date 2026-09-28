# Item 8 — live -game proxy observation: status (2026-09-20)

**The live -game proxy-fraction STILL is NOT captured this session, and NOT
faked.** The derivation stands as the instrument of record; today's HLOD-share
pass independently corroborates its qualitative core.

## Why the live still is still blocked

Three tools of record agree the runtime HLOD proxy band renders **only in an
actual `-game` process**, not in the editor or in-editor MRQ:
- `bench_capture.py` help (line ~881): `player_streaming` "must run in a `-game`
  process to show the proxy band — in the editor it still renders real cells."
- D-1 item 1 / D-2 item 1a: in-editor MRQ renders the **editor world** (resident
  real cells), never the proxy band.
- The `-game` **HighResShot** fallback is **empirically settled non-viable**
  (commit ee4e173c): `-ExecCmds` fires before streaming and `-game` has no
  channel for a delayed shot. Re-confirmed this session: `wp.Runtime.HLOD 0`
  passed via startup `-ExecCmds` logged `LogEngine: Warning` (deferred/
  unprocessed) and never applied.

The one clean settled path is **MRQ-in-game** (a saved LevelSequence at the
vista camera + a MoviePipeline config + the `-game` command-line MRQ contract,
`MovieRenderPipelineCommandLine.cpp:202-213`). The desk (R1/R2) scoped it as
**hours of LevelSequence authoring against a cold DDC and an untested `-game`
MRQ path**, on a machine with a DEVICE_HUNG history — a risk not taken on an
already-long session (context-exhaustion discipline). No runnable scaffold was
ever committed; the R1 "commit the A scaffolding" produced only the editor
reference + analyzer, not a `-game` driver.

## Instrument of record (derivation)

`_verify/bench/2026-09-15/dev_d2_1b_depth/proxy_fraction_vista_derived.json`:
**proxy_fraction 0.05727** of visible ground at vista — 88,065 proxy pixels of
**1,537,813** non-sky ground pixels (2,148,587 sky excluded at the 10485.76 m
finite ceiling; 0.02389 of the whole frame). Depth pass at editor_player,
force-loaded, dev 2560×1440; the beyond-512 m (R-RANGE) band is the runtime HLOD
proxy band. Sample count reported (rule 13). Locked in RECIPES R-PROXYFRACTION.

## New corroboration this session (HLOD-share pass)

The live still was meant to confirm one thing: **does the landscape/forest HLOD
proxy actually render in the real runtime band?** Today's HLOD-share pass answers
YES independently of a -game capture:
- **1042 WorldPartitionHLOD actors are resident and all visible**
  (`hlod_share_enumerate.json`), nearest 2.2–3.5 km from the stations — the
  runtime proxy band is real and populated, not empty.
- Hiding all 1042 (verified 1042/1042) changed vista GPUTime p90 by 0.015 ms
  (`hlod_share.json`) — the band renders, cheaply.

So the qualitative claim behind 1b is confirmed; what remains unmeasured is only
the **exact live pixel fraction** in a true `-game` frame (vs the 0.05727 derived
in a force-loaded editor frame). Whether the live fraction differs from 0.05727
is the open quantitative question, and it needs the `-game` MRQ build.

## Recommendation

Run the `-game` MRQ build as its own focused session (author the vista
LevelSequence + MoviePipeline config, commit them as the durable scaffold, then
one time-boxed `-game` render → `proxy_fraction.py --mode depth`). Not started
here to avoid a large untested authored artefact on a long session. The
derivation 0.05727 + the HLOD-share corroboration are sufficient for the desk to
proceed in the meantime.
