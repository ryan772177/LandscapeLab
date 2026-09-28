Audit complete. All three sources read in full: the tool, the compositor it drives, and the proven-mapping precedent; the coast recipe's actual `location_cm`/`resolution`/`scale_xy_cm` were pulled from disk rather than assumed.

**Verdict: BLOCK** (must not execute yet — neither `--selftest` nor the real run). I have no Edit/Write tools in this session, so nothing was auditor-corrected; every finding goes back to the main agent.

## findings

**B1 — BLOCK (scope/conduct, `--selftest` path).** `C:\Users\Admin\UE5LandscapePipeline\scripts\brief_loop.py:336-338` — `tempfile.TemporaryDirectory()` writes `x.png` into system `%TEMP%`, outside both declared roots, and its context-manager cleanup is `shutil.rmtree` — a recursive delete outside the roots. Under this gate's rules (scope rule 1; conduct rule on recursive deletes) both are automatic-BLOCK classes, and standing rules 1–2 say the same. Fix: write the 8-bit specimen under the repo (e.g. a `_verify/` scratch path) and remove the single file non-recursively.

**B2 — BLOCK (selftest is arithmetically wrong; it will FAIL as shipped).** `brief_loop.py:356` expects `pl["anchor_m"] == 20.0 - 50.0 + 40.0` (= 10.0). The rule at `brief_loop.py:171` computes `max(0.0, round(20.0 + 40.0 - 90.0, 1))` = **0.0**. The code matches its own docstring (lines 40–41: shift by target-mid − measured-mean), so the test expression is the defect — an arithmetic slip that double-counts. `--selftest` exits 1 today. Secondary: the `max(0.0, …)` anchor floor at :171 is undocumented in the adjustment-rules block (:36-43); a site genuinely needing a negative anchor will pin at 0.0, burn all iterations unchanged, and exit 3 — fail-closed but opaque. Document the floor and fix the expectation (0.0 for this case, or add a non-floored case, e.g. measured mean 10 → anchor 20→50).

**F3 — FIX (HIGH, latent coordinate-mapping divergence).** `brief_loop.py:138-141` hardcodes origin = −res·spacing/2; the docstring premise at :19-21 claims that is "the compositor's own mapping". It is not — `composite_stamps.py:461-462` and `:1088-1089` derive origin from `landscape.location_cm`, and the compositor's extent is `origin .. origin+(n−1)·spacing` (its own quoted print "X −2018.0..2014.0" is asymmetric, which the centred premise cannot produce). **Verified for the coast recipe the two coincide exactly**: `coast_bench.json` location_cm −201800 = −2018.0 m = −(1009·4)/2, matching `render_preview.py:17-22`'s proven `(x_cm − OX_CM)/PX_CM`. But `alpine_8k.json`'s origin (−406400 cm = −4064.0 m) is (n−1)-centred; the centred formula gives −4064.5 m — a half-cell probe offset the compositor would not share, i.e. a plausible-but-shifted measurement, this project's worst failure class. probe() must take origin from the recipe exactly as the compositor does; fix the docstring premise in the same commit.

**F4 — FIX (MEDIUM, missing scope guard on the recipe write).** `brief_loop.py:249` and `:266` write `recipe_path` (`:215`, taken verbatim from `--recipe`) with no inside-repo check. The compositor refuses out-of-repo recipes (`composite_stamps.py:1031-1033`), but brief_loop's dump at :249 runs BEFORE the compositor — an out-of-root path gets overwritten once before anything refuses. Mirror `composite_stamps.py:194-197`'s `_inside_repo` before the first dump.

**F5 — FIX (MEDIUM, crash-not-refuse paths — the tool's own direction-3 contract at :13-16).** `validate_acceptance` (:82-101) checks presence, not shape/type. Uncaught tracebacks: (a) malformed `at_m` → IndexError/TypeError at :260, outside the try that ends at :246, and the except tuple at :244 lacks TypeError/IndexError; (b) non-numeric `box_m` → TypeError in probe at :139; (c) non-list band (e.g. `"elev_m": 5`) → TypeError at :100, inside the try but TypeError is not caught; (d) `box_m` < spacing → `half = 0` at :139 → empty window → ValueError from `w.min()` at :149, outside the try. Add shape/type checks to the validator and a `half >= 1` refuse in probe.

**F6 — FIX (LOW).** `run_compositor` (:193-199) reports only stdout on failure; a compositor traceback (not a Refuse) goes to stderr and the refusal would carry no cause. Append a stderr tail.

**F7 — FIX (LOW, lint blind spot).** `lint_ordering` (:117) skips everything but `blend == "ADD"`; a MAX or MASKED placement after a flat_site's MIN carve over the probe defeats the carve identically. Also `--reorder` (:231-233) moves all MINs behind MAX/MASKED too, not just behind ADDs — logged, but worth a docstring caveat.

**F8 — LOW (robustness).** Unclosed inline file handles at :217, :218, :249, :266. The flush of :249 before the subprocess reads the file currently depends on CPython refcount closing; use `with` so the ordering is contractual.

**F9 — cosmetic.** Exit-code doc (:50) omits selftest's exit 1, and says exit 2 is "refused before any run" while :254 returns 2 mid-loop.

**Q1 — QUESTION (unanchored to brief_loop).** `C:\Users\Admin\UE5LandscapePipeline\_verify\20260831_coast_benchmark\layout_brief.json` has no `"acceptance"` key — a real run against it refuses at :86, correctly. Confirm which brief carries the acceptance list for the planned run (`_verify\20260831_brief_loop\loopdemo_brief.json`?).

## verified clean (checked, not assumed)

Row/col orientation (row=Y, col=X) matches the compositor's measured fact 2; the 10° analytic-plane selftest arithmetic is correct; the amplitude selftest case (100→30.0 at the 0.3 step floor) matches the code; both adjustment rules move in the converging direction with sane per-step clamps and absolute bounds; the whole-recipe JSON round-trip preserves all keys including `heightmap.source`, which is never adopted (and the compositor's schema makes `output == heightmap.source` unrepresentable); no deletes anywhere in the real-run path; subprocess invocation is cwd-independent with utf-8/replace decoding (the known locale-codec trap avoided); on a cap hit the on-disk recipe matches the last composited-and-measured state, which is the right invariant.

## safety answer

- `--selftest`: **not cleared** — B1's out-of-root write/rmtree, and it would exit 1 anyway on B2.
- Real run against a copy of the coast recipe: **not cleared** until B2, F3, F4 and F5 land — but note explicitly that the probe mapping is numerically exact for this specific recipe (origin coincidence verified above), so the block is guard discipline and a broken selftest, not a wrong coast number. After fixes: selftest first, then the real run is reasonable — its writes are the recipe copy plus whatever the compositor writes (`terrain/coast_bench_stamped.png` + sidecar), all inside REPO_ROOT.

LESSONS.md one-liner for the main agent to append: `2026-08-31 audit: brief_loop.py BLOCKED pre-run — selftest asserts 10.0 where its own documented rule yields 0.0 (a selftest can be the broken instrument), probe hardcoded a centred origin that only coincidentally equals the coast recipe's location_cm, and the recipe write ran before any inside-repo guard.`