# Audit package — 2026-09-14

**Read-only.** Nothing in this folder changed the pipeline. It is
evidence for the desk to rule on; removals and applications happen in
later sessions.

## What is here

| file | what |
|---|---|
| `pipeline_full_2026-09-14_part{1..4}.zip` | the corpus: every recipe, script, doc, register, brief, plan, skill, commit message and sidecar, plus the git history as text |
| `corpus_stats.json`, `corpus_tree.txt` | what went in, what was dropped and why |
| `lever_inventory.json` | every engine lever any script writes or reads |
| `api_inventory.json` | every `unreal.*` symbol touched, plus calls that fail by returning a value |
| `claims_ledger.json` | every factual claim in the record, with contradictions |
| `findings_ledger.json` | every finding, and whether anything implements it |
| `script_claims.json` | per script: purpose, marked rules, thresholds, tests, callers |
| `tools_of_record.json` | tools named as of-record vs scripts that exist and are called |
| `report_groups.json` | the report's groups, extracted |
| `CONTRADICTIONS_AND_DEAD_WEIGHT.md` | **start here** — the prose report |
| `tools/` | the four generators, so every number can be re-derived |

## Read the precision statement first

`CONTRADICTIONS_AND_DEAD_WEIGHT.md` §0 measures the contradiction
finder against five contradictions the project already knows about. **It
rediscovers two of the five.** Everything downstream is a floor, not a
census.

## The git history lives in the zips

`_history/` (864 files: CLAUDE.md × 249 versions, LESSONS.md × 332,
RECIPES.md × 253, STATE.md × 7, registers × 20, plus
`git_log_stat.txt`) is **inside the zips**. The loose copy was 574 MB of
exact duplication and was moved to `_trash/`; `tools/build_corpus.py`
regenerates it.

## Re-deriving anything

    python research/audit/tools/build_corpus.py        # zips + history
    python research/audit/tools/scan_levers_and_api.py # levers, API
    python research/audit/tools/build_ledgers.py       # claims, findings,
                                                      # scripts, tools
    python research/audit/tools/summarise.py           # report groups

All four are read-only against the repo and write only here.

## Known limits, so they are not discovered as surprises

* **No engine was launched.** Every "DOES NOT EXIST in 5.8" is quoted
  from an earlier live enumeration, not re-run.
* **`applied_where` is a text search.** A finding implemented under a
  different name reads as UNAPPLIED. The 405 rows are an index to
  review, not a work list to execute.
* **The claim scan is line-based**, so a finding wrapping two lines
  yields a half-sentence.
* **`has_read_back` means a read EXISTS**, not that it reads the object
  that honours the value — the distinction that `grass_varieties`
  (copies) and the HLOD builder settings (nested structs) both turn on.
* Excluded from the claims ledger, each for a reason: `_verify/`
  (evidence, not claims), `dist/` (a packaged copy of the forge, which
  manufactures duplicates), `hero/` (parked separate product),
  `docs/archive/` (superseded by construction). All are in the zips.
