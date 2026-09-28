---
name: verification-practice
description: How this project builds gates, checks and measurements — three-directions testing, fail-direction-follows-failure-mode, instrument premises, and the traps that produced each rule. Use when writing any gate, assertion, tolerance, hook or measurement, or when a check refuses something you believe is correct.
when_to_use: writing a gate or assertion; choosing a tolerance; a check refuses input you believe correct; adding a hook; designing a test; measuring anything whose result will be recorded
allowed-tools: Read, Grep, Glob
---

# Verification practice

Every rule here was written after a real defect. The sources are
`RECIPES.md` verification guidance (a)–(j) and the non-negotiables.

## Before you write the check

**State the instrument's PREMISE, and check it transfers.** An
instrument is calibrated against a specimen, and its validity does not
travel to a different one.

- The ORM channel test assumes **geometry-driven albedo** — cavities
  darken in colour and occlusion together. True of photoscanned rock,
  false of pigment-driven grass. It FAILED a correct mapping.
- The LOD cost model was solved for **generated** chains and applied to
  **vendor** chains: wrong by 20.3× understated to 0.4× overstated.

**A refusal on an answer you have independent reason to believe correct
means the INSTRUMENT left its class.** The response is a
class-appropriate instrument, never a widened tolerance.

## Choosing a tolerance

**Derive it or measure it on a known-good specimen. Never widen until
the run goes green.** When a gate refuses input you believe is correct,
the two legitimate moves are: derive the bound properly, or discover the
input was not correct after all.

**A verdict needs its threshold derived just as much as a gate does.**
`score > 12` in a throwaway analysis script declared a whole approach
impossible; the real question was a projection test, and clear subjects
were found immediately.

## Testing the check

**THREE DIRECTIONS for anything in the enforcement layer:**

1. **BLOCK the violation**
2. **PASS the legitimate case**
3. **BLOCK WHEN BROKEN** — garbage input, malformed state, missing
   fields must refuse, not crash through

Direction 3 found 32 of 109 malformed payloads sailing through hooks
that were perfect on well-formed input. **A rule that allows-by-default
when it matches nothing fails open on every input it never imagined.**
Fix pattern: **validate the payload's SHAPE before interrogating its
CONTENT.**

**A test confounded by live state asserts an OUTCOME, not a CONTRACT.**
The suite must pass identically whatever the repo looks like when it
runs.

**An invariant the failure mode preserves is not a check.** Ask what the
failure would look like, then confirm the assertion can see it. A
`max_steps` loop that dumps its remainder in place conserves mass *by
construction* — the assertion passes with full marks in exactly the case
it was written to catch.

## Fail direction

**Fail-closed is not the principle. MAKE THE FAILURE LAND WHERE IT COSTS
LEAST is.**

- failure ⇒ **unguarded action** → fail CLOSED
- failure ⇒ **trapped operator** → fail OPEN, and say why
- failure ⇒ **missing information** → DEGRADE, naming the gap (NN6)

## Reporting the result

- **Verify with a DIFFERENT instrument** than the one that made the
  claim. A read-back that reads the field the setter wrote proves only
  that the value landed.
- **A failed measurement reports that it failed**, never the number the
  broken measurement produced.
- **State the denominator.** A statistic about a modulator is only
  meaningful conditioned on where it modulates — 72% of the map versus
  99% of the layer it actually modulates.
- **Never truncate the output of an operation you cannot cheaply
  repeat.**

## Two traps that look like success

**Ratification is not verification.** An operator sign-off PROPAGATES a
rule; it does not test it.

**A lesson written from a crash is only as good as the search that
preceded it.** Root cause, engine citation, two altitudes and sign-off
are not enough if the investigation started at the crash instead of at
the repo.
