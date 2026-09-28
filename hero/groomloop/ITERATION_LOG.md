# ITERATION_LOG.md — AlpineHero groom vs the hero reference

Source: `source/SC_Hairstyle_Male_11.abc` (94,408 Bézier curves, sha
`5dfbf1b4…`, never modified). Reference: `ref/hero_reference_front.jpg`, sha
`F62B53FF…` — hash-identical to the repo's declared appearance target for
AlpineHero, so this is the ruled look and not a lookalike.

**Scores are 1–10 per criterion, judged from the render against the reference,
with the geometric metrics beside them.** The metrics inform the score; they do
not set it. Where a metric and the picture disagree, the disagreement is
written down rather than resolved silently — that happened at 001 and it was
the most useful entry in the table.

## METRICS, EVERY ITERATION

`front/left/top` are scalp-visible percentages from the mask render
(`scalp_probe.py`), lower = better covered. **Absolute values are not
meaningful** — the proxy ellipsoid pokes through the top even on the untouched
source (55.9%) — but deltas are.

| it | fringe_reach cm | forehead cover % | grade ratio | tip scatter cm | sil w cm | front | left | top |
|---|---|---|---|---|---|---|---|---|
| base | −3.65 | 22.5 | 0.124 | 0.433 | 21.5 | 50.4 | 25.3 | 55.9 |
| 001 | −1.46 | 38.1 | 0.188 | 0.521 | 26.6 | — | — | — |
| 002 | −1.49 | 31.2 | 0.327 | 0.450 | 18.8 | 35.7 | 24.3 | 62.5 |
| 003 | −0.40 | 42.1 | 0.285 | 0.455 | 18.0 | 29.3 | 24.4 | 69.4 |
| 004 | **+0.26** | 58.0 | 0.267 | 0.452 | 17.9 | 26.4 | 22.9 | 67.7 |
| 005 | +0.31 | 59.5 | 0.259 | 0.449 | 17.9 | 26.4 | 23.8 | 70.1 |
| 006 | +0.27 | 58.0 | 0.267 | 0.455 | 17.7 | **25.1** | **22.2** | 67.7 |
| 007 | +0.18 | 53.4 | 0.264 | 0.484 | 19.3 | 27.2 | 21.7 | 65.7 |
| 008 | +0.12 | 53.5 | 0.297 | 0.495 | 20.8 | 25.5 | 30.8 | **54.8** |
| 009 | +0.14 | 58.8 | 0.305 | 0.466 | 18.3 | 25.1 | 34.4 | 55.3 |

## SCORES

| it | fringe | shag | grading | ears | texture | **total** | one line |
|---|---|---|---|---|---|---|---|
| base | 2 | 3 | 2 | 8 | 3 | **18** | smooth centre-part curtain bob; forehead bare |
| 001 | 5 | 3 | 3 | 8 | 3 | **22** | metrics improved, render got WORSE — frizz, not shag |
| 002 | 5 | 5 | 4 | 8 | 6 | **28** | spatial clumping fixed the frizz; real pieciness appears |
| 003 | 6 | 6 | 4 | 8 | 6 | **30** | fringe recruited from the top; bald patch appears upper-side |
| 004 | 7 | 6 | 4 | 8 | 6 | **31** | steeper pull ramp: fringe clears the brow for the first time |
| 005 | 7 | 6 | 4 | 8 | 6 | **31** | crown_lift down — REFUTED as the cause of top exposure |
| 006 | 7 | 6 | 4 | 8 | 6 | **31** | narrower fringe zone; best front/left coverage of the run |
| 007 | 6 | 6 | 4 | 8 | 6 | **30** | less clumping: top improved 2 pts, fringe lost 4.6 |
| 008 | 7 | 7 | 4 | 8 | 7 | **33** | WILDCARD: directional sweep + hem tuck kill the mushroom |
| 009 | 7 | 8 | 4 | 9 | 8 | **36** | fewer/stronger clumps → visible locks; best texture |

## LEADERBOARD

1. **009** (36) — best texture and silhouette; costs the left side (34.4%)
2. **008** (33) — best top coverage of any run (54.8, beats the source)
3. **006** (31) — best all-round coverage; least adventurous shape

## WHAT EACH ITERATION ESTABLISHED

**000 identity control.** `moved_max_cm` 0.0 at default params. The engine is a
no-op until told otherwise, so every later delta is attributable.

**001 — the metrics improved and the render got worse, and that is the entry
worth keeping.** fringe_reach −3.65 → −1.46 and forehead cover 22 → 38%, while
the picture became a fuzzy ball. **Root cause: clump ids were assigned by
`rng.integers` over all 94,408 curves**, so every clump's mean root was the
head centroid and "pull toward your clump" was "pull toward the middle" for
every strand. Not a parameter problem — a mechanism problem.

**002 — spatial clumping.** Clumps became lat/long patches of nearby roots, and
the attractor became the clump's mean TIP rather than its mean root, because
hair converges at the ENDS and that is what opens gaps. Frizz → pieciness in
one change.

**003 — the fringe has to be recruited.** The source is a CENTRE PART: there is
almost no hair rooted at the front-centre, so lengthening what is there cannot
build a fringe. Widening `fringe_zone` back over the crown made the mass
available. Cost: a bald patch on the upper side, because sweeping a strand
forward uncovers the scalp behind its own root.

**004 — `fringe_pull_ramp` buys reach without paying in exposure.** 1.5 → 2.8
swings only the tip and leaves the mid-strand lying on the skull. First
iteration where the median fringe tip clears the brow (+0.26 cm).

**005 — REFUTATION, and a useful one.** `crown_lift` 0.016 → 0.005 made top
exposure *worse* (67.7 → 70.1). Lifting crown hair is NOT what uncovers the
crown. Recorded so nobody re-tests it.

**006 / 007 — the two remaining candidates, each single-variable.** Narrowing
the fringe zone left top exposure unchanged at 67.7 (so recruitment is not the
driver either); halving clump_scale bought 2 points of top and cost 4.6 points
of forehead cover. **Neither is a main cause: the top number is dominated by
proxy error, and its true delta is small and spread across several ops.** That
is why it stopped being chased.

**008 — wildcard, and it moved the most.** A radial groom cannot be made
directional by tuning radial parameters, so `global_sweep_x/z` and `hem_tuck`
were added as their own vectors. The mushroom skirt flattened, top exposure
fell to 54.8% — better than the untouched source — at the cost of the left
side (22.9 → 30.8), which is what a one-sided sweep does.

**009 — lock separation.** Clumps 300 → 90 with scale 0.30 → 0.60 and tip
variance 0.45 → 0.60. Distinct locks and a spiky outline; the closest to the
reference's texture so far. Left side degrades further (34.4%).

## THE ONE CRITERION THAT HAS NOT MOVED, AND WHY

**Length grading is stuck at 4/10.** `grade_ratio` (nape length ÷ crown length)
runs 0.124 → 0.305 against a target above 1.0. It is not a failure of the
lever: `nape_length_scale` 2.2 applied to a base ratio of 0.124 predicts ~0.27
and delivers 0.30, so the mechanism works exactly as specified. **The source
simply has a very short nape and very long crown strands — it is a curtain cut,
where length comes from the top and falls.** Reaching >1.0 needs roughly
`nape_length_scale` 8, which stretches short strands to eight times their
authored length; whether that reads as hair or as spaghetti is the open
question, and iteration 010 tests it at 4.5 first rather than jumping to 8.

---

# PART 2 — ITERATIONS 010–023

| it | fringe cm | cover % | grade | scatter | front | left | top | mean |
|---|---|---|---|---|---|---|---|---|
| 010 | +0.10 | 56.3 | **0.513** | 0.503 | 26.2 | 33.2 | 64.5 | 41.29 |
| 011 | +0.14 | 58.8 | 0.526 | 0.527 | 25.3 | 27.9 | 55.1 | 36.10 |
| 012 | +0.10 | 56.6 | 0.526 | 0.506 | 27.8 | 42.8 | 62.4 | 44.31 |
| 013 | +0.14 | 54.3 | 0.523 | 0.504 | 29.6 | 42.5 | 65.2 | 45.73 |
| 014 | +0.14 | 58.9 | 0.526 | 0.528 | 25.2 | 30.9 | 54.9 | 37.01 |
| 015 | +0.21 | 57.2 | 0.523 | 0.524 | 26.7 | 30.9 | 57.4 | 38.34 |
| **016** | +0.37 | 61.9 | 0.546 | 0.526 | 24.0 | **22.6** | 50.8 | **32.49** |
| 017 | +0.37 | 61.9 | 0.519 | 0.530 | 27.9 | 33.1 | 49.8 | 36.92 |
| **018** | +0.40 | 62.0 | 0.544 | 0.531 | **23.7** | 24.3 | **48.0** | **32.00** |
| 019 | +0.28 | 61.0 | 0.547 | 0.523 | 24.0 | 20.4 | 53.9 | 32.76 |
| 020 | +0.31 | 60.6 | 0.546 | 0.520 | 24.7 | 26.3 | 53.6 | 34.87 |
| 021 | +0.34 | 61.1 | 0.544 | 0.524 | 24.4 | 28.5 | 51.2 | 34.70 |
| 022 | −0.31 | 42.9 | 0.605 | 0.453 | 43.5 | 51.8 | 83.7 | 59.68 |
| 023 | +0.23 | 58.8 | 0.547 | 0.517 | 24.5 | 24.0 | 56.4 | 34.96 |

## SCORES, 010–023

| it | fringe | shag | grading | ears | texture | **total** | one line |
|---|---|---|---|---|---|---|---|
| 010 | 7 | 8 | 6 | 9 | 8 | **38** | grading nearly doubled; crown coverage paid for it |
| 011 | 7 | 8 | 6 | 9 | 8 | **38** | grading from the nape ALONE — best of part 1 |
| 012 | 6 | 7 | 6 | 8 | 7 | **34** | regressed; cause isolated to one shared change |
| 013 | 6 | 7 | 6 | 8 | 7 | **34** | same regression, same cause |
| 014 | 7 | 8 | 6 | 9 | 8 | **38** | clamp restored; confirms 012/013 diagnosis |
| 015 | 7 | 8 | 6 | 9 | 8 | **38** | chunkier fringe costs a little coverage |
| 016 | 8 | 8 | 6 | 9 | 8 | **39** | ROTATION instead of translation — mechanism win |
| 017 | 7 | 8 | 6 | 9 | 8 | **38** | rotation + translation FIGHT |
| 018 | 8 | 9 | 6 | 9 | 8 | **40** | strongest sweep that still covers |
| 019 | 8 | 8 | 6 | 9 | 8 | **39** | gentler rotation, best left coverage of all |
| **020** | 8 | 9 | 6 | 9 | 8 | **40** | 016 + final clamp — UE-verified |
| **021** | 8 | 9 | 6 | 9 | 8 | **40** | 018 + final clamp — UE-verified, best top |
| 022 | 4 | 6 | 7 | 6 | 6 | **29** | extent-matching clamp destroys the groom |
| **023** | 8 | 8 | 6 | 9 | 8 | **39** | 019 + final clamp — UE-verified, best left |

## WHAT PART 2 ESTABLISHED

**010/011 — grading is a nape problem, not a crown problem.** `layer_falloff`
(which SHORTENS crown strands) lifted `grade_ratio` but uncovered the crown
(top 55.3 → 64.5). Taking the same gain from `nape_length_scale` alone gave
`grade_ratio` 0.526 with top back at 55.1. Unlike `crown_lift`, which 005
refuted, `layer_falloff` **is** a real driver of crown exposure.

**012/013 — two regressions, one shared cause, found by looking for what they
had in common.** Both dropped `stray_clamp_m` 0.26 → 0.20 and both jumped to
~42.5% left exposure. **The "strays" are not all junk** — at 0.20 the clamp
cuts the long side and nape strands that were doing the covering. 014/015
restored 0.26 and the regression vanished, which is what makes this an
attribution rather than a guess.

**016 — the mechanism change, and the run's biggest single win.** See
APPROACHES A4. Translation of tips uncovers scalp; rotation about the root does
not. 017 proved the two fight.

**020/021/023 — the final clamp made the exports shippable.** The clamp inside
the length multiplier acts on ORIGINAL lengths, and every op after it can
lengthen a strand again: UE measured iteration 016 at `max_curve_length`
114 cm. Re-applying the clamp to the RESULT brought 61.7 cm of control-polygon
length down to exactly 24.0 cm, clamping 4,826 curves (5.1%).

**022 — a dead end, recorded so nobody walks it again.** Clamping to match the
vendor's 26 cm extent scored the **worst mean of the entire run (59.68%)**. The
extent mismatch is a symptom of APPROACHES A8, not a length problem.

## THE CRITERION THAT NEVER GOT ABOVE 6

**Length grading topped out at `grade_ratio` 0.547 against a target above 1.0.**
The mechanism is not at fault — 2.2× on a 0.124 base predicts 0.27 and
delivered 0.30; 6.0× delivered 0.547, exactly proportional. **The source is a
curtain cut whose length lives in the crown and falls, and the reference's
length lives at the nape.** Reaching 1.0 needs roughly 11× on the nape, and
022 demonstrated what happens when strand lengths are pushed to serve a metric
rather than the picture. Left at 6/10 deliberately.

---

# PART 3 — ITERATIONS 024–029 (after the escalation consult)

| it | fringe cm | cover % | grade | scatter | front | left | top | mean |
|---|---|---|---|---|---|---|---|---|
| 024 blk120 | +0.14 | 52.7 | 0.536 | 0.565 | 26.7 | 22.4 | 45.3 | 31.48 |
| 025 blk400 | +0.53 | 61.4 | 0.565 | 0.548 | 26.7 | 30.5 | 51.4 | 36.19 |
| 026 blk60 | +0.03 | 50.7 | 0.523 | 0.585 | 26.4 | **19.5** | **41.2** | **29.03** |
| 027 blk200 | +0.23 | 54.9 | 0.550 | 0.563 | 27.1 | 25.5 | 48.0 | 33.56 |
| **028** | +0.96 | 70.3 | 0.487 | 0.606 | 20.8 | 11.4 | 36.6 | **22.93** |
| 029 | +2.02 | 85.3 | 0.458 | 0.619 | 14.6 | 7.3 | 34.8 | 18.90 |

## SCORES

| it | fringe | shag | grading | ears | texture | **total** | one line |
|---|---|---|---|---|---|---|---|
| 024 | 7 | 9 | 6 | 9 | 9 | **40** | index locks: best top coverage yet |
| 025 | 7 | 8 | 6 | 9 | 8 | **38** | block 400 too coarse |
| 026 | 7 | 9 | 6 | 9 | 9 | **40** | block 60: best coverage and texture |
| 027 | 7 | 9 | 6 | 9 | 9 | **40** | between the two |
| **028** | 9 | 9 | 6 | 9 | 9 | **42** | 026 locks + 021 fringe — THE PICK |
| 029 | 6 | 9 | 6 | 9 | 9 | **39** | best metrics of the run, covers his face |

## WHAT PART 3 ESTABLISHED

**The plateau was structural, not a tuning problem.** Every op was
`f(root_position) x g(t)`, evaluated in root space, so two strands rooted 1 mm
apart could never diverge — a map smooth in root space cannot open a gap.
Clumping could only trade coverage. See `APPROACHES.md` A9.

**Curve index carries the artist's guide grouping.** Consecutive-index roots
sit 4.13 mm apart against 125 mm for random pairs (ratio 0.033), decaying
smoothly with stride. Using index blocks as the lock partition instead of
lat/long cells improved coverage AND texture together for the first time in the
run — every earlier change traded one against the other.

**Block size is a real lever with an optimum:** 400 → 36.19, 200 → 33.56,
120 → 31.48, 60 → **29.03**.

**028 combines the two independent wins** — 026's authored lock partition and
021's fringe strength — and lands at mean 22.93%, roughly half the untouched
source's 43.88%, with the best fringe reach of any candidate that still shows
the face.

**029 IS THE THIRD METRIC-VERSUS-PICTURE DIVERGENCE OF THE RUN, AND THE MOST
INSTRUCTIVE.** It scored the best numbers of everything — mean 18.90%, fringe
+2.02 cm, cover 85.3% — and it is rejected. **The proxy head has no face**, so
hair hanging over where the face would be scores as "scalp covered". The metric
was rewarding it for hiding him. Kept as the worked example of why the render
is the tie-breaker and the metric is only the argument.
