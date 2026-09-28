"""prove_hooks.py — THREE-DIRECTIONS proof for every deny hook.

The standard for this layer, ratified 2026-08-05. A hook is not trusted
until it is proven to:

  1. BLOCK the violation        — it does the job
  2. PASS the legitimate case   — it does not block real work
  3. BLOCK WHEN BROKEN          — garbage input, malformed state and
                                  missing fields DENY rather than
                                  crash through

Direction 3 is the one this layer adds, and it exists because of the
contract: **exit codes other than 0 and 2 are NON-BLOCKING**. A hook
that throws on a malformed payload would let the guarded action proceed
— the enforcement layer failing open, silently, exactly when something
unusual is happening. Directions 1 and 2 cannot see that; only feeding
the hook garbage can.

Run:  python .claude/hooks/prove_hooks.py
Exit: 0 all proven, 4 any direction failed.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard.py")
REPO = os.path.dirname(os.path.dirname(HERE))

BLOCK, PASS = "BLOCK", "PASS"


def run(rule, payload, raw=None):
    """(exit_code, stderr). `raw` sends a literal string instead of JSON."""
    data = raw if raw is not None else json.dumps(payload)
    p = subprocess.run([sys.executable, GUARD, rule],
                       input=data, capture_output=True, text=True)
    return p.returncode, (p.stderr or "").strip()


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def powershell(cmd):
    return {"tool_name": "PowerShell", "tool_input": {"command": cmd}}


def write(path, content="x"):
    return {"tool_name": "Write",
            "tool_input": {"file_path": path, "content": content}}


def edit(path):
    return {"tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": "a",
                           "new_string": "b"}}


P = os.path.join(REPO, "scripts", "ok.py")
NL = chr(10)
BS = chr(92)          # a literal backslash, built rather than typed

# H14 fixtures. R999 cannot exist; R15 does.
_FIX = os.path.join(HERE, "_fixtures")
os.makedirs(_FIX, exist_ok=True)


def _fixture(name, text):
    fp = os.path.join(_FIX, name)
    with io.open(fp, "w", encoding="utf-8") as fh:
        fh.write(text)
    return fp


BAD_MSG = _fixture("bad.txt", "R999 records the new thing" + NL)
GOOD_MSG = _fixture("good.txt", "R15 records the enforcement layer" + NL)
PLAIN_MSG = _fixture("plain.txt", "no recipe reference here" + NL)

# (rule, direction, label, payload-or-raw)
CASES = [
    # ---- H1 commit -F ------------------------------------------------
    ("commit-file", BLOCK, "git commit -m",
     bash('git commit -m "msg"')),
    ("commit-file", BLOCK, "git commit --message=",
     bash('git commit --message="msg"')),
    ("commit-file", PASS, "git commit -F (the required form)",
     bash('git commit -F /tmp/msg.txt')),
    ("commit-file", PASS, "unrelated git command",
     bash('git status --short')),
    ("commit-file", PASS, "the word commit in prose, not a git commit",
     bash('echo "commit -m is banned"')),

    # ---- H14 commit message claims -----------------------------------
    # Fixtures written beside the suite so the cases are reproducible.
    ("commit-claims", BLOCK, "message names a recipe that does not exist",
     bash('git commit -F ' + BAD_MSG)),
    ("commit-claims", PASS, "message names an EXISTING recipe",
     bash('git commit -F ' + GOOD_MSG)),
    ("commit-claims", PASS, "message with no recipe reference",
     bash('git commit -F ' + PLAIN_MSG)),
    ("commit-claims", PASS, "message on stdin (nothing to read)",
     bash('git commit -F -')),

    # ---- H13 heredoc escape mangling ---------------------------------
    # Built with explicit joins rather than literal heredocs, because
    # writing this very test through a heredoc mangled it -- the FOURTH
    # instance of the trap, and the one that finally promoted it.
    ("heredoc-escapes", BLOCK, "heredoc body containing backslash escapes",
     bash(NL.join(["python - <<'EOF'", "s = " + BS + "n", "EOF"]))),
    ("heredoc-escapes", PASS, "heredoc with NO backslashes",
     bash(NL.join(["cat <<'EOF'", "plain text, no escapes", "EOF"]))),
    ("heredoc-escapes", PASS, "no heredoc at all",
     bash("python scripts/capture.py")),

    # ---- H2 forced deletes -------------------------------------------
    ("no-force-delete", BLOCK, "rm -rf", bash("rm -rf build/")),
    ("no-force-delete", BLOCK, "rm -f", bash("rm -f a.txt")),
    ("no-force-delete", BLOCK, "del /s", bash("del /s C:\\tmp")),
    ("no-force-delete", BLOCK, "Remove-Item -Recurse",
     bash("Remove-Item -Recurse -Force .\\x")),
    ("no-force-delete", PASS, "plain rm of one file", bash("rm a.txt")),
    ("no-force-delete", PASS, "move to _trash (the sanctioned form)",
     bash("mv a.txt _trash/")),

    # ---- H3 engine files ---------------------------------------------
    ("engine-files", BLOCK, "write .uasset",
     write(os.path.join(REPO, "LandscapeLab", "Content", "X.uasset"))),
    ("engine-files", BLOCK, "edit .umap",
     edit(os.path.join(REPO, "LandscapeLab", "Content", "Alpine.umap"))),
    ("engine-files", BLOCK, "write .uproject",
     write(os.path.join(REPO, "LandscapeLab", "LandscapeLab.uproject"))),
    ("engine-files", PASS, "write .ini (explicitly allowed)",
     write(os.path.join(REPO, "LandscapeLab", "Config", "DefaultEngine.ini"))),
    ("engine-files", PASS, "write a python script", write(P)),

    # ---- H4 outside repo ---------------------------------------------
    ("outside-repo", BLOCK, "write to C:/Windows",
     write("C:/Windows/System32/x.txt")),
    ("outside-repo", BLOCK, "write to a sibling project",
     write("C:/Users/ryanb/OtherProject/x.txt")),
    ("outside-repo", PASS, "write inside the repo", write(P)),
    ("outside-repo", PASS, "write inside the UE project",
     write(os.path.join(REPO, "LandscapeLab", "Config", "a.ini"))),
    # DIRECTION 2, added after this rule blocked a commit-message file
    # in the harness's own scratchpad. Sanctioned; see the rule.
    # TEMP-derived (Pass 3 2026-09-16): the sanction is now ANCHORED to
    # the system temp root, so a hardcoded other-user path (the old
    # fixture) is correctly no longer sanctioned.
    ("outside-repo", PASS, "session scratchpad (sanctioned temp)",
     write(os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp"),
                        "claude", "sess", "scratchpad", "m.txt"))),
    ("outside-repo", BLOCK, "another Temp dir that is NOT the scratchpad",
     write("C:/Users/ryanb/AppData/Local/Temp/other/x.txt")),

    # ---- H5 LESSONS append-only --------------------------------------
    ("lessons-append-only", BLOCK, "Edit LESSONS.md",
     edit(os.path.join(REPO, "LESSONS.md"))),
    ("lessons-append-only", BLOCK, "Write LESSONS.md",
     write(os.path.join(REPO, "LESSONS.md"))),
    ("lessons-append-only", PASS, "Edit RECIPES.md (not append-only)",
     edit(os.path.join(REPO, "RECIPES.md"))),
    ("lessons-append-only", PASS, "Edit BACKLOG.md",
     edit(os.path.join(REPO, "BACKLOG.md"))),

    # ---- H6 Fab protection -------------------------------------------
    ("fab-protection", BLOCK, "write into Content/Fab",
     write(os.path.join(REPO, "LandscapeLab", "Content", "Fab", "x.uasset"))),
    ("fab-protection", BLOCK, "write into Content/KiteDemo",
     write(os.path.join(REPO, "LandscapeLab", "Content", "KiteDemo", "a.txt"))),
    ("fab-protection", BLOCK, "write into Content/Pack_Bonus",
     write(os.path.join(REPO, "LandscapeLab", "Content", "Pack_Bonus", "a.txt"))),
    ("fab-protection", PASS, "write into our own Content/Surfaces",
     write(os.path.join(REPO, "LandscapeLab", "Content", "Surfaces", "a.txt"))),
    ("fab-protection", PASS, "write into Free/_intake (our staging)",
     write(os.path.join(REPO, "Free", "_intake", "a.png"))),

    # ---- H7 load_level -----------------------------------------------
    ("load-level", BLOCK, "hand-rolled load_level payload",
     bash('python -c "import unreal; unreal.LevelEditorSubsystem.load_level(x)"')),
    ("load-level", BLOCK, "load_level inside a written file",
     write(P, "_les.load_level('/Game/Alpine')")),
    ("load-level", PASS, "the sanctioned tool",
     bash("python scripts/open_level.py")),
    ("load-level", PASS, "unrelated command", bash("python scripts/capture.py")),

    # ---- H8 MSYS /Game/ mangling -------------------------------------
    ("msys-game-path", BLOCK, "bare /Game/ argument",
     bash("python scripts/audit_material_samplers.py --material /Game/Materials/M")),
    ("msys-game-path", BLOCK, "quoted /Game/ argument",
     bash('python x.py --p "/Game/Alpine"')),
    ("msys-game-path", PASS, "no /Game/ path", bash("python scripts/capture.py")),
    ("msys-game-path", PASS, "Game without leading slash",
     bash("python x.py --p Game/Alpine")),
    # DIRECTION 2, added after the hook blocked its own author's commit:
    # a content path as PROSE inside a heredoc is not an argument and
    # MSYS does not rewrite it.
    ("msys-game-path", PASS, "content path as prose inside a heredoc",
     bash("git commit -F - <<'EOF'\nfixed the " + "/Game" + "/Materials path\nEOF")),
    ("msys-game-path", PASS, "content path inside a quoted string",
     bash('echo "the path ' + "/Game" + '/Alpine was mangled"')),
    # REGRESSION FIXTURES, captured 2026-08-06 BEFORE the narrowing, per
    # the ruling's condition (a). The hook fired on BOTH of its own
    # suggested remedies — "use the PowerShell tool" and "set
    # MSYS_NO_PATHCONV=1" — because it matched the /Game/ string
    # regardless of tool_name and had no carve-out for the env var.
    # LESSONS.md 2026-08-06: A HOOK THAT BLOCKS ITS OWN REMEDY.
    ("msys-game-path", PASS, "REMEDY 1: PowerShell tool (no MSYS layer)",
     powershell("python scripts/audit_material_samplers.py "
                "--material /Game/Meshes/Materials/M_fir_bark")),
    ("msys-game-path", PASS, "REMEDY 2: MSYS_NO_PATHCONV=1 prefix",
     bash("MSYS_NO_PATHCONV=1 python scripts/audit_material_samplers.py "
          "--material /Game/Meshes/Materials/M_fir_bark")),
    ("msys-game-path", PASS, "REMEDY 2 with a QUOTED /Game/ argument "
     "(conversion is disarmed for those too)",
     bash('MSYS_NO_PATHCONV=1 python x.py --material '
          '"/Game/Meshes/Materials/M_fir_bark"')),
    # BOUNDING CASES for the two exceptions (R15 s8: an exception
    # without a test proving its edge is not bounded, it is a hole).
    ("msys-game-path", BLOCK, "no tool_name at all -> treated as Bash",
     {"tool_input": {"command":
      "python scripts/audit_material_samplers.py --material /Game/M"}}),
    ("msys-game-path", BLOCK, "MSYS_NO_PATHCONV=0 does NOT disarm",
     bash("MSYS_NO_PATHCONV=0 python x.py --material /Game/M")),
    ("msys-game-path", BLOCK, "MSYS_NO_PATHCONV=1 as QUOTED PROSE does "
     "not disarm a bare /Game/ argument",
     bash('echo "later set MSYS_NO_PATHCONV=1" && python x.py '
          '--material /Game/M')),

    # ---- Pass 3 (2026-09-16) regression fixtures ----------------------
    # Each captures a bypass or false-deny the reading found CONFIRMED.
    # heredoc: redirect after the delimiter is the common file-writing
    # form and was invisible (the body regex required an immediate \n).
    ("heredoc-escapes", BLOCK, "redirect after delimiter, backslash body",
     bash(NL.join(["cat <<'EOF' > out.py", "s = " + BS + "n", "EOF"]))),
    ("heredoc-escapes", PASS, "redirect after delimiter, clean body",
     bash(NL.join(["cat <<'EOF' > out.txt", "plain text", "EOF"]))),
    ("heredoc-escapes", BLOCK, "<<- with TAB-indented terminator, "
     "backslash body",
     bash(NL.join(["cat <<-EOF", "s = " + BS + "n", "\tEOF"]))),
    # commit-file: compound with -m in ANOTHER segment must PASS; the
    # -am and attached -m"msg" shorthands must BLOCK; --amend must PASS.
    ("commit-file", PASS, "compound: python -m elsewhere, commit uses -F",
     bash("python -m pytest && git commit -F msg.txt")),
    ("commit-file", BLOCK, "git commit -am shorthand",
     bash('git commit -am "quick fix"')),
    ("commit-file", BLOCK, "git commit -m with attached message",
     bash('git commit -m"quick fix"')),
    ("commit-file", PASS, "git commit --amend -F",
     bash("git commit --amend -F msg.txt")),
    ("commit-file", PASS, "MULTI-LINE: commit -F, then python -m on the "
     "next line (auditor FIX-2: \\n bounds a segment)",
     bash("git commit -F msg.txt" + NL + "python -m pytest")),
    # commit-claims: --file= form must be checked, not skipped.
    ("commit-claims", BLOCK, "--file= form naming a nonexistent recipe",
     bash("git commit --file=" + BAD_MSG)),
    # force-delete: long options, rd /s, PowerShell alias + abbreviation;
    # and alias/param in DIFFERENT segments must not cross-contaminate.
    ("no-force-delete", BLOCK, "rm --recursive long option",
     bash("rm --recursive build/")),
    ("no-force-delete", BLOCK, "rd /s (cmd alias)",
     bash("rd /s /q C:\\tmp\\x")),
    ("no-force-delete", BLOCK, "Remove-Item abbreviated -rec",
     powershell("Remove-Item -rec .\\x")),
    ("no-force-delete", BLOCK, "ri alias with -Force",
     powershell("ri .\\x -Force")),
    ("no-force-delete", PASS, "del in one segment, -r flag in another",
     bash("del x.txt && python foo.py -r")),
    # load-level: MENTIONING the sanctioned tool in a shell command is
    # not INVOKING it.
    ("load-level", BLOCK, "shell command that only mentions open_level.py",
     bash('echo "see open_level.py" && python -c '
          '"unreal.LevelEditorSubsystem.load_level(x)"')),
    ("load-level", PASS, "actual open_level.py invocation (mentions "
     "load_level in a comment)",
     bash("python scripts/open_level.py --recipe recipes/alpine_8k.json "
          "# wraps load_level safely")),
    # outside-repo: the scratchpad sanction is anchored to the system
    # temp root, not any path containing /temp/claude/.
    ("outside-repo", BLOCK, "temp/claude under some OTHER project",
     write("C:\\OtherProject\\temp\\claude\\x.txt")),
]

# Direction 3: the hook itself is broken/fed garbage. EVERY rule must
# deny on EVERY one of these, never crash through.
BROKEN = [
    ("empty stdin", ""),
    ("not JSON at all", "this is not json"),
    ("JSON but not an object", "[1,2,3]"),
    ("JSON null", "null"),
    ("object with no tool_input", '{"tool_name":"Bash"}'),
    ("tool_input is a string", '{"tool_input":"oops"}'),
    ("tool_input has nulls", '{"tool_input":{"command":null,"file_path":null}}'),
    ("deeply wrong types", '{"tool_input":{"file_path":12345}}'),
    ("truncated JSON", '{"tool_input":{"command":'),
]


def prove_event_hooks():
    """H9 SessionStart and H10 Stop — different contracts, same bar.

    Neither is a deny hook, so direction 3 asks a different question of
    each. SessionStart CANNOT block, so its failure mode is missing
    context: it must still emit VALID JSON naming the gap. Stop CAN
    block, so its failure mode is TRAPPING the operator: it must ALLOW
    anything it cannot establish.
    """
    ok = bad = 0
    sc = os.path.join(HERE, "session_context.py")
    st = os.path.join(HERE, "stop_dirty_tree.py")

    def run_hook(script, payload):
        p = subprocess.run([sys.executable, script], input=payload,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout or "").strip()

    print("--- H9 SessionStart (cannot block; must always emit JSON) ---")
    for label, payload in [
            ("normal startup", json.dumps({"hook_event_name": "SessionStart",
                                           "matcher": "startup"})),
            ("[3] empty stdin", ""),
            ("[3] garbage stdin", "not json at all"),
            ("[3] JSON array", "[1,2,3]")]:
        code, out = run_hook(sc, payload)
        good = code == 0
        try:
            j = json.loads(out)
            good = good and (j.get("hookSpecificOutput", {})
                             .get("additionalContext"))
        except Exception:
            good = False
        ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
        print("  {0:<28} {1}".format(
            label, "ok" if good else "*** no valid context JSON ***"))

    print("--- H10 Stop (must never trap; allows what it cannot verify) ---")
    # THE ASSERTION HERE TESTS THE CONTRACT, NOT A FIXED OUTCOME.
    #
    # The first version asserted "malformed input => allow" and failed on
    # empty stdin and a JSON array. The HOOK was right and the TEST was
    # wrong: those inputs fall through to the real check, and the working
    # tree genuinely was dirty, so blocking was the correct answer. The
    # test could not tell "blocked by malformed input" from "blocked
    # because the tree really is dirty" — it was confounded by live
    # state, which is exactly the flaw non-negotiable 22 names.
    #
    # What direction 3 actually requires of a Stop hook: it must never
    # crash, never exit non-zero, and never block for a reason unrelated
    # to the tree. So: exit 0, parseable output, and any block must carry
    # the dirty-tree reason.
    for label, payload in [
            ("loop guard: stop_hook_active",
             json.dumps({"stop_hook_active": True})),
            ("[3] empty stdin", ""),
            ("[3] garbage stdin", "not json"),
            ("[3] JSON array", "[1,2,3]"),
            ("[3] nested nonsense", json.dumps({"stop_hook_active": {"x": 1}}))]:
        code, out = run_hook(st, payload)
        good = (code == 0)
        reason = ""
        try:
            j = json.loads(out) if out else {}
            if j.get("decision") == "block":
                reason = j.get("reason", "")
                good = good and ("uncommitted work" in reason)
        except Exception:
            good = False
        ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
        print("  {0:<28} {1}".format(
            label, "ok" if good else
            "*** exit {0}, unparseable or off-contract block ***".format(code)))
    print("--- H11/H12 advisories (never block; exit 1 = one-line hint) ---")
    adv = os.path.join(HERE, "advisory.py")
    _sess = json.dumps({"session_id": "prove", "tool_input":
                        {"command": "python scripts/x.py"}})

    def _adv(which, payload):
        q = subprocess.run([sys.executable, adv, which], input=payload,
                           capture_output=True, text=True)
        return q.returncode, (q.stderr or "").strip()

    # streak: first failure silent, second advises, success clears
    _adv("clear-streak", _sess)
    c1, _ = _adv("consecutive-failures", _sess)
    c2, e2 = _adv("consecutive-failures", _sess)
    _adv("clear-streak", _sess)
    c3, _ = _adv("consecutive-failures", _sess)
    for label, cond in [
            ("[2] first failure stays silent", c1 == 0),
            ("[1] second failure advises", c2 == 1 and "RULE 6" in e2),
            ("[1] advice names the LESSONS search", "LESSONS.md" in e2),
            ("[2] advice is ONE line", len(e2.splitlines()) == 1),
            ("[2] success clears the streak", c3 == 0)]:
        ok, bad = (ok + 1, bad) if cond else (ok, bad + 1)
        print("  {0:<44} {1}".format(label, "ok" if cond else "*** WRONG ***"))

    dep = json.dumps({"tool_input": {"command": "pip install numpy"}})
    d1, de = _adv("dependency-record", dep)
    d2, _ = _adv("dependency-record",
                 json.dumps({"tool_input": {"command": "python x.py"}}))
    for label, cond in [
            ("[1] pip install advises", d1 == 1 and "RULE 5" in de),
            ("[2] unrelated command silent", d2 == 0),
            ("[3] garbage stdin never obstructs",
             _adv("consecutive-failures", "not json")[0] in (0, 1)),
            ("[3] unknown handler never obstructs",
             _adv("nosuchrule", _sess)[0] == 0)]:
        ok, bad = (ok + 1, bad) if cond else (ok, bad + 1)
        print("  {0:<44} {1}".format(label, "ok" if cond else "*** WRONG ***"))

    print("--- SubagentStop NN18 (degrades; never blocks) ---")
    sub = os.path.join(HERE, "subagent_output.py")
    for label, payload, want_note in [
            ("hedging language present",
             json.dumps({"last_assistant_message": "import_plan: not "
                         "applicable, assumed defaults",
                         "agent_type": "auditor"}), True),
            ("clean report, no hedging",
             json.dumps({"last_assistant_message": "3 findings, each with "
                         "a file and line.", "agent_type": "auditor"}),
             False),
            ("[3] empty stdin", "", False),
            ("[3] garbage stdin", "not json", False),
            ("[3] message is not a string",
             json.dumps({"last_assistant_message": 12345}), False)]:
        p2 = subprocess.run([sys.executable, sub], input=payload,
                            capture_output=True, text=True)
        good = (p2.returncode == 0)
        out = (p2.stdout or "").strip()
        got_note = False
        if out:
            try:
                got_note = bool(json.loads(out).get("hookSpecificOutput", {})
                                .get("additionalContext"))
            except Exception:
                good = False
        good = good and (got_note == want_note)
        ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
        print("  {0:<28} {1}".format(
            label, "ok" if good else
            "*** exit {0}, note={1} wanted {2} ***".format(
                p2.returncode, got_note, want_note)))

    print("  note: a dirty-tree BLOCK is proven live every time this "
          "session tries to stop with uncommitted work.")
    return ok, bad


def main():
    rules = sorted({c[0] for c in CASES})
    ok = bad = 0
    print("THREE-DIRECTIONS PROOF")
    print("  1 block the violation   2 pass legitimate   3 block when broken")
    print("")
    for rule in rules:
        print("--- {0} ---".format(rule))
        for r, direction, label, payload in CASES:
            if r != rule:
                continue
            code, err = run(r, payload)
            blocked = (code == 2)
            want = (direction == BLOCK)
            good = (blocked == want)
            ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
            print("  {0:<5} {1:<52} {2}".format(
                "[1]" if want else "[2]", label[:52],
                "ok" if good else
                "*** WRONG: exit {0}, wanted {1} ***".format(
                    code, "2 (block)" if want else "0 (pass)")))
            if not good and err:
                print("        stderr: {0}".format(err.splitlines()[0][:90]))
        # direction 3
        for label, raw in BROKEN:
            code, err = run(rule, None, raw=raw)
            good = (code == 2)
            ok, bad = (ok + 1, bad) if good else (ok, bad + 1)
            if not good:
                print("  [3]   {0:<52} *** CRASHED THROUGH: exit {1} ***"
                      .format(label[:52], code))
        print("  [3]   {0} broken-input cases -> all deny"
              .format(len(BROKEN)))
    print("")
    eok, ebad = prove_event_hooks()
    ok, bad = ok + eok, bad + ebad
    print("")
    # NN13 applied to this suite itself: a proof that ran ZERO checks (empty
    # CASES/BROKEN, or the event hooks all skipped) is not "all proven" -- it is
    # silence wearing a pass's clothes. Refuse rather than print 0/0 correct.
    if ok + bad == 0:
        print("REFUSE: the proof ran ZERO checks -- nothing was proven. A suite "
              "that proves nothing is not a pass (non-negotiable 13).")
        return 4
    print("{0}/{1} checks correct.".format(ok, ok + bad))
    if bad:
        print("A hook is not trusted until all three directions hold. "
              "Direction 3 is the one the contract forces: exit codes "
              "other than 0 and 2 are NON-BLOCKING, so a hook that "
              "crashes lets the guarded action through.")
        return 4
    print("All hooks block the violation, pass legitimate work, and DENY "
          "when fed garbage rather than crashing through.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
