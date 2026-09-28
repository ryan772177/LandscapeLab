# Five discriminating cvars, read from the LIVE editor — Alpine8K

Measured 2026-08-15 via `EditorAppToolset.SearchCVars` on the running editor
(PID 23888). These five were chosen because every cvar this project PINS
outranks scalability and therefore cannot discriminate; these are unpinned,
so their value says whether the scalability GROUPS actually expanded.

The question they settle: `[SystemSettings]` can set an `sg.*` VALUE without
RUNNING the group, a mechanism this project has measured before. Whether the
groups ran was recorded as unverifiable without a live read.

    cvar                                 if groups     if groups    MEASURED
                                          did NOT ran     DID run
    r.Streaming.MipBias                        0            1          0
    r.VolumetricFog                            1            0          1
    r.Shadow.Virtual.MaxPhysicalPages       2048          512       2048
    r.TSR.History.ScreenPercentage           200          100        100
    r.Nanite.Foliage                           -            -          1

## VERDICT: the scalability groups did NOT degrade this editor

Three of the four discriminators agree, and each is good news:

- **`r.Streaming.MipBias = 0`** — textures run at FULL resolution. The
  concern that the 4096² surface set (Rock051, Rock026, Snow006, Ground037,
  WildGrass) was running one mip down is REFUTED.
- **`r.VolumetricFog = 1`** — volumetric fog is enabled, matching what
  `recipes/alpine_8k.json` declares (`fog.volumetric = true`). The renderer
  feature and the recipe agree.
- **`r.Shadow.Virtual.MaxPhysicalPages = 2048`** — the VSM page pool is at
  engine default, NOT quartered to 512, under a 66M-vertex Nanite landscape.

## THE FOURTH DOES NOT DISCRIMINATE, and saying so is the point

`r.TSR.History.ScreenPercentage` reads **100**, which the plan predicted
would mean the groups DID run. But the cvar's own help text says it is "set
to 200 on Epic and Cinematic, 100 otherwise" — so 100 is ALSO what a cvar
sitting at its C++ default looks like when no group ran at all. **The two
hypotheses predict the same observation, so this reading is evidence for
neither.** It is reported because a discriminator that turns out not to
discriminate is a fact about the instrument, and quietly dropping it would
leave a 3-of-4 result looking like 4-of-4.

Whether TSR history is genuinely at half resolution under a
153,796-instance needle forest — that mechanism's worst case — needs the
AntiAliasingQuality group's actual level, which this read does not give.

## ALSO CLOSED

`r.Nanite.Foliage = 1` **verified on the running process**, not inferred
from `DefaultEngine.ini:36`. Its three consumers cache it as
`static const bool` on first call, so an editor launched before that line
landed would not have it — which is exactly why the ini was not sufficient
evidence. It is now confirmed by a different instrument than the file that
set it.
