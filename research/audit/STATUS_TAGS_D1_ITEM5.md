# D-1 item 5 — STATUS tags on the 81 PASS4 §4 seed entries

Each seed entry was READ (not tagged from the seed) and judged by the rule:
HISTORY (the entry records its own correction / is honest narrative) /
SUPERSEDED-BY <ruling> (states an old value as current) / WRONG (states
something later shown false) / CURRENT (still in force). The full
entry-by-entry judgement is in `status_tags_2026-09-15.tsv` (applied rows)
and reproduced in the desk's read-back.

## Tag counts (all 81 judged)

    HISTORY         59
    SUPERSEDED-BY   17
    WRONG            2   (seq 41 "composition is not a product" inverted 09-13c;
                         seq 61 recommends an HLOD layer the same doc shows inert)
    CURRENT          3   (seq 68/69/70 -- the 512 m R-RANGE streaming lock)

**62 of 81 deviate from the seed's SUPERSEDED-BY default.** The dominant
reason: LESSONS.md is append-only NARRATIVE (CLAUDE.md), so a dated block
records the correction -- honest HISTORY, not a stale value a reader acts
on. All of seq 1-51 are LESSONS entries, all HISTORY except seq 41.
RECIPES `REJECTED` blocks are anti-spec HISTORY, not superseded values.

## Applied: 65 of 81

`scripts/apply_status_tags.py --apply` inserted `> STATUS:` under 65
entries whose headings grep UNIQUELY (fail-closed: it refuses a grep that
matches 0 or >1 lines, and excludes the generated TOC/CURRENT_VALUES
blocks so a heading is matched in the BODY only). `gen_doc_tocs.py` gained
a **status** column; the TOC shows the tag for the ~17 top-level entries
that are TOC entries, and the ~48 sub-heading tags live in the body where
they apply. `status_for` reads only the STATUS line DIRECTLY under a
heading, so a tagged `### REJECTED` sub-part does not make its parent
recipe read as superseded.

## Deferred: 16 (generic headings; decisions recorded, not applied)

These have headings too generic to anchor a grep safely on this long
session; their tags are DECIDED and a fresh session can apply them with a
body-phrase disambiguator. All HISTORY except the two noted:

    seq 7,8,9,10  HISTORY  "What was attempted/happened", "The rule",
                           "What this invalidates" (under THE EXPERIMENT DID NOT RUN)
    seq 13        HISTORY  "### TIER 2"
    seq 16,17     HISTORY  "The assignment", "What survives..." (B3.21 HLOD block)
    seq 20        HISTORY  "WHAT HAPPENED" (Brief 2 block)
    seq 25        HISTORY  "### OPEN" (2026-09-11m, Q12 open, later closed)
    seq 31        HISTORY  "### The measurement" (2026-09-12h, WB 3481.9)
    seq 33        HISTORY  "### What follows" (2026-09-12h)
    seq 38        HISTORY  "### What it is not"
    seq 53        SUPERSEDED-BY Task 3 09-13  "## EXACT VALUES" (pre-8K material)
    seq 57        HISTORY  "## REJECTED" (Nanite displacement 4.0 anti-spec)
    seq 58        HISTORY  "THE FLUSH DOES NOT WORK" (collision investigation)
    seq 60        SUPERSEDED-BY B3.21  "### The procedure" (HLOD landscape-layer example)

Nothing is lost: every one of the 81 has a decided tag here; the 16 await
a safe anchor, not a decision.

## 1d resolution (2026-09-16) — 14 of the 16 applied; 2 subsumed at entry level

Applied via 10 new TSV rows (`applied 10 | skipped 65 | REFUSED 0`,
idempotent on re-run → 75 skipped). Two sub-headings were COLLAPSED to one
dated-entry anchor each because they share an entry and a tag: seq 7-10 →
the "AND IT HANDED ME THE CONTROL I HAD SKIPPED" entry; seq 31,33 → the
2026-09-12h "ACCEPTANCE AND THE GRADE ARE IN CONFLICT" entry. Where a full
sub-heading was unique (13,16,17,38,60) it was anchored directly; where not
(20,25,31/33 and 7-10) the tag was anchored on the containing unique dated
entry — the "at dated-entry level" instruction.

**Two left unanchored ON PURPOSE, not forced (their decided tag is already
honoured at the enclosing level):**

- **seq 53** `## EXACT VALUES` (pre-8K R2 material): the bare heading is
  non-unique (18+ in RECIPES) with no distinctive substring. Its recipe
  `# R2 — Landscape material (LOCKED, UNPROVEN)` is ALREADY tagged with the
  identical `SUPERSEDED-BY Task 3 09-13` by the applied seq 52, which governs
  the whole block. Adding seq 53 is both unanchorable and redundant.
- **seq 57** `## REJECTED` (Nanite displacement 4.0 anti-spec): bare heading
  non-unique (20+); the only unique heading-level anchor is the containing
  `## NANITE DISPLACEMENT … LOCKED 2026-08-11, UNPROVEN` recipe, which is
  LIVE — tagging it HISTORY would mislabel a live recipe. No safe anchor;
  forcing it would be the KB defect the fail-closed tool exists to prevent.

So 79 of 81 now carry an applied STATUS line or are governed by an
entry-level tag; the 2 above are decided-and-subsumed, not open.
