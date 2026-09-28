"""ASSETS.md and recipes/ai_restrictions.json must agree. One declaration.

The register is the SOURCE -- the guard reads it, and the guard is what
actually stops a run. ASSETS.md is the human-readable row. Two places that must
agree with no checker between them is non-negotiable 24, and this project has
already been bitten by it twice this week: R-CITYSHOT specified
`ShowFlag.Volumes 0` in prose that the payload never issued, and the kit closure
walker and its verifier disagreed about what counted as a dangling reference.

So this asserts, for every restriction carrying `no_ai_input`:

  * ASSETS.md mentions the asset at all;
  * ASSETS.md carries the literal token `no_ai_input: true` near it, so a
    reader of the document cannot miss what the tooling enforces;
  * the guard's self-test still passes, because a register that no longer
    matches its own guard is worse than no register.

Exit 0 agree, 4 disagree, 5 could not look.
"""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(REPO, "recipes", "ai_restrictions.json")
DOC = os.path.join(REPO, "ASSETS.md")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if not os.path.isfile(REG) or not os.path.isfile(DOC):
        print("REFUSE: register or ASSETS.md missing -- could not look.")
        return 5
    with io.open(REG, encoding="utf-8") as fh:
        reg = json.load(fh)
    doc = io.open(DOC, encoding="utf-8").read()

    restricted = [r for r in reg["restrictions"] if r.get("no_ai_input")]
    print("AI-RESTRICTION CROSS-CHECK")
    print("  register: %d restriction(s), %d with no_ai_input"
          % (len(reg["restrictions"]), len(restricted)))
    print("")
    bad = []
    for r in restricted:
        title = r["title"]
        named = title in doc
        flagged = "no_ai_input: true" in doc
        print("  %-28s in ASSETS.md: %-5s   no_ai_input token: %s"
              % (title[:28], "yes" if named else "NO",
                 "yes" if flagged else "NO"))
        if not named:
            bad.append("%s is restricted but ASSETS.md never names it" % title)
    if "no_ai_input: true" not in doc and restricted:
        bad.append("ASSETS.md carries no `no_ai_input: true` token at all, so "
                   "a reader cannot see what the tooling enforces")

    print("")
    p = subprocess.run([sys.executable,
                        os.path.join(REPO, "scripts", "ai_input_guard.py"),
                        "--self-test"], capture_output=True, text=True)
    guard_ok = p.returncode == 0
    print("  guard self-test: %s" % ("passes" if guard_ok else "FAILS"))
    if not guard_ok:
        bad.append("the guard's own self-test fails")
        print((p.stdout or "")[-500:])

    print("")
    if bad:
        for b in bad:
            print("  !! %s" % b)
        print("")
        print("REFUSE: the register and the document disagree.")
        return 4
    print("ok  register, document and guard agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
