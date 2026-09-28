"""guard.py — the constitution's deny hooks, one dispatcher.

FIRST PRINCIPLE, ratified 2026-08-05 and the reason this file is shaped
the way it is:

    EXIT CODES OTHER THAN 0 AND 2 ARE NON-BLOCKING.
    A HOOK THAT CRASHES DOES NOT BLOCK.

The documented contract is exit 0 = proceed (optionally with JSON), exit
2 = block with stderr as the reason, **anything else = non-blocking
error, the action proceeds**. So an unhandled exception, a missing
dependency or an unparseable payload would let the very thing through
that the hook exists to stop — the enforcement layer failing open.

Therefore **every path in this file that is not an explicit ALLOW exits
2**. `main()` wraps the entire dispatch in a bare `except BaseException`
and denies. That is non-negotiable 1 — fail closed, and test that the
gate cannot be satisfied by the failure it guards against — applied to
the enforcement layer itself.

THREE-DIRECTIONS TESTING is the standard for this layer (see
`prove_hooks.py`): every rule must be proven to
  1. BLOCK the violation,
  2. PASS the legitimate case,
  3. BLOCK when the hook itself is broken — garbage input, malformed
     state, missing fields — rather than crash through.

Usage (from .claude/settings.json):
    python "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.py" <rule>
with the hook JSON on stdin.
"""

from __future__ import annotations

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
UE_PROJECT = os.path.join(REPO_ROOT, "LandscapeLab")

# Vendor trees. R-ASSET forbids authoring into a Fab folder: their
# contents are replaced wholesale on reinstall, so an edit there is lost
# work that looks like committed work.
FAB_TREES = ("Content/Fab", "Content/KiteDemo",
             "Content/MWLandscapeAutoMaterial", "Content/Pack_Bonus",
             "Content/Megascans")

ENGINE_SUFFIXES = (".uproject", ".uasset", ".umap")


def deny(reason):
    """The ONLY way to block. Exit 2, reason on stderr."""
    sys.stderr.write(reason.strip() + "\n")
    raise SystemExit(2)


def allow():
    raise SystemExit(0)


def _norm(p):
    try:
        return os.path.normcase(os.path.abspath(str(p))).replace("\\", "/")
    except Exception:
        # Unnormalisable path is not a reason to let a write through.
        deny("guard: could not normalise a path; denying rather than "
             "guessing what it referred to.")


def require_input(data, need):
    """A well-formed payload, or DENY.

    FOUND BY DIRECTION 3, and it is the whole argument for having one.
    Every rule below ALLOWS when it finds no violation — so a payload
    with no `tool_input`, a null `command`, or an integer where a path
    belongs matched nothing and sailed through with exit 0. Directions 1
    and 2 passed for all eight rules while this was true; only feeding
    the hook garbage exposed it.

    `need` is "command" or "path". Absent or wrong-typed fields are
    treated as a broken payload, not as an empty one.
    """
    ti = data.get("tool_input")
    if not isinstance(ti, dict) or not ti:
        deny("guard: hook payload has no usable `tool_input` object. "
             "Denying — a malformed payload is exactly when a guard must "
             "hold, and a rule that finds nothing to match would "
             "otherwise pass it through.")
    if need == "command":
        if not isinstance(ti.get("command"), str) or not ti["command"].strip():
            deny("guard: payload carries no string `command`. Denying "
                 "rather than evaluating a rule against a field that is "
                 "missing or the wrong type.")
    elif need == "path":
        vals = [ti.get(k) for k in ("file_path", "notebook_path", "path")]
        if not any(isinstance(v, str) and v.strip() for v in vals):
            deny("guard: payload carries no string file path. Denying "
                 "rather than evaluating a path rule against nothing.")
    elif need == "any":
        if not any(isinstance(v, str) and v.strip() for v in ti.values()):
            deny("guard: payload carries no string fields at all. "
                 "Denying rather than scanning an empty payload and "
                 "concluding it is clean.")
    return ti


def _text(data):
    """Every string in the tool input, joined. Deliberately broad."""
    ti = data.get("tool_input") or {}
    parts = []
    for v in ti.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
    return "\n".join(parts)


def _paths(data):
    ti = data.get("tool_input") or {}
    out = []
    for key in ("file_path", "notebook_path", "path"):
        v = ti.get(key)
        if isinstance(v, str) and v:
            out.append(v)
    return out


# ---------------------------------------------------------------- rules
# ONE heredoc recognizer for both heredoc-aware rules (Pass 3 2026-09-16:
# they had drifted — one tolerated trailing text after the delimiter, the
# other required an immediate newline and so FAILED OPEN on the common
# `cat <<'EOF' > out.py` shape; neither honoured <<-'s tab-indented
# terminator). Groups: (quote, tag, body).
HEREDOC_RE = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n([\s\S]*?)^\t*\2\s*$", re.M)


def rule_commit_file(data):
    """Standing rule 3: commit messages go through a FILE, always."""
    require_input(data, "command")
    cmd = (data.get("tool_input") or {}).get("command") or ""
    # Scope the -m search to EACH git-commit SEGMENT (Pass 3 2026-09-16):
    # detection was segment-scoped but the -m search ran on the WHOLE
    # command, so `python -m pytest && git commit -F msg` was a false
    # deny — manufacturing the blocked-and-rebuilt resumption hazard
    # rule_commit_claims documents. Also broadened: `-am` and attached
    # `-m"msg"` are valid git and were bypassing (^|\s)-m(\s|=).
    # \n bounds a segment too (auditor FIX-2): without it, a multi-line
    # command put a later line's -m inside the commit segment — the
    # false-deny class this fix exists to remove. (A rare backslash
    # line-continuation `git commit \⏎ -m` now passes unexamined; ruled
    # acceptable — the shell forms this session uses never split there.)
    segs = re.findall(r"\bgit\b[^|;&\n]*\bcommit\b[^|;&\n]*", cmd)
    if not segs:
        allow()
    inline = any(
        re.search(r"(^|\s)-[a-zA-Z]*m(\s|=|['\"]|$)"
                  r"|(^|\s)--message(\s|=|$)", seg)
        for seg in segs)
    if inline:
        deny(
            "STANDING RULE 3: commit messages go through a FILE, "
            "unconditionally — `git commit -F <path>`.\n"
            "This was promoted after the FOURTH message in one session was "
            "mangled by shell quoting: heredocs eaten by apostrophes, then "
            "backticks expanding as command substitution and silently "
            "deleting words from a commit that still succeeded.\n"
            "A rule that depends on remembering which characters the shell "
            "eats is the weakest kind of rule; the file path has no failure "
            "mode.")
    allow()


def rule_no_force_delete(data):
    """Standing rule 2: never recursive/forced deletes."""
    require_input(data, "command")
    cmd = (data.get("tool_input") or {}).get("command") or ""
    low = cmd.lower()
    hits = []
    if re.search(r"\brm\s+(-[a-z]*[rf][a-z]*\s+)+", low):
        hits.append("rm -r/-f")
    # Long options and synonyms (Pass 3 2026-09-16): --recursive/--force,
    # cmd's `rd /s`, and PowerShell's aliases + prefix-abbreviated
    # parameters all bypassed the literal spellings above. Alias and
    # parameter are matched in the SAME pipeline segment so `del x.txt &&
    # python foo -r` cannot cross-contaminate.
    if re.search(r"\brm\b[^|;&\n]*\s--(recursive|force)\b", low):
        hits.append("rm --recursive/--force")
    if re.search(r"\bdel\b.*\s/s\b", low) or re.search(r"\brmdir\b.*\s/s\b", low) \
            or re.search(r"\brd\b.*\s/s\b", low):
        hits.append("del/rd /s")
    for _seg in re.split(r"[|;&]", low):
        if re.search(r"\b(remove-item|ri|rd|del|erase)\b", _seg) and \
                re.search(r"\s-(r(e(c(u(r(se?)?)?)?)?)?"
                          r"|f(o(r(ce?)?)?)?)\b", _seg):
            hits.append("Remove-Item (or alias) -Recurse/-Force "
                        "(incl. abbreviated)")
            break
    if re.search(r"remove-item\b", low) and re.search(
            r"-(recurse|force)\b", low):
        hits.append("Remove-Item -Recurse/-Force")
    if hits:
        deny(
            "STANDING RULE 2: never use recursive or forced deletes "
            "({0}).\n"
            "To remove files, MOVE them to `_trash/` inside the repo. Git is "
            "the undo button; `_trash/` is the second one.\n"
            "This rule was broken once already, by `rm -f` entered as error "
            "handling.".format(", ".join(hits)))
    allow()


def rule_engine_files(data):
    """Standing rule 4: never modify .uproject/.uasset/.umap on disk."""
    require_input(data, "path")
    for p in _paths(data):
        if p.lower().endswith(ENGINE_SUFFIXES):
            deny(
                "STANDING RULE 4: never modify `.uproject`, `.uasset` or "
                "`.umap` directly on disk — {0}\n"
                "Editor-side changes go through the UE Python API. (`.ini` "
                "files are normal project config and ARE edited directly.)"
                .format(p))
    allow()


def rule_outside_repo(data):
    """Standing rule 1: never write outside the repo or UE project.

    SANCTIONED EXCEPTION — the session scratchpad. Found in production
    on 2026-08-05 when this rule blocked a commit-message file being
    staged in the harness's own temp directory.

    Standing rule 1 targets OTHER PROJECTS AND SYSTEM CONFIG — "autonomy
    over this project is not authority over somebody else's". The
    per-session scratchpad under the system temp directory is neither:
    it is the environment's designated location for exactly this, it is
    disposable, and refusing it pushes temporary files INTO the repo,
    which is worse. A guard that blocks sanctioned work gets disabled,
    and a disabled guard protects nothing.
    """
    require_input(data, "path")
    roots = (_norm(REPO_ROOT), _norm(UE_PROJECT))
    # ANCHORED to the real temp root (Pass 3 2026-09-16): the old
    # substring test ("/temp/claude/" anywhere) sanctioned e.g.
    # C:/OtherProject/temp/claude/x — a carve-out wider than the stated
    # sanction. Now only the system temp's claude dir (or POSIX
    # /tmp/claude/) qualifies.
    # NEVER _norm("") — abspath("") is the process CWD, so an "empty"
    # fallback would silently anchor the sanction to the hook's cwd
    # (auditor FIX-1). Unset TEMP/TMP leaves only /tmp/claude/ sanctioned.
    _tmp_env = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    _tmp = _norm(_tmp_env) if _tmp_env else ""
    for p in _paths(data):
        n = _norm(p)
        scratch = ((_tmp and (n == _tmp + "/claude"
                              or n.startswith(_tmp + "/claude/")))
                   or n.startswith("/tmp/claude/"))
        if scratch:
            continue          # session scratchpad, sanctioned above
        if not any(n == r or n.startswith(r + "/") for r in roots):
            deny(
                "STANDING RULE 1: never write outside this repo or the UE "
                "project directory — {0}\n"
                "Reading elsewhere is fine and expected, engine source "
                "especially. Writing is not.".format(p))
    allow()


def rule_lessons_append_only(data):
    """LESSONS.md is append-only. DUMB HOOK, LOUD EXCEPTION.

    RULED 2026-08-05: deny ALL non-appends rather than try to permit the
    documented supersession pattern.

    A hook that tried to allow "legitimate corrections" would have to
    distinguish a supersession-with-marker from a quiet deletion, which
    is semantic judgement it cannot do reliably — and getting it wrong
    silently destroys the append-only guarantee. So the hook stays dumb.

    A genuine correction (loop (d) supersession) goes through a
    DELIBERATE hook-disable plus a checkpoint, which keeps the exception
    LOUD and auditable instead of routine. NN3: prefer an input that
    cannot express the catastrophic value over a gate that must judge it.
    """
    require_input(data, "path")
    for p in _paths(data):
        if os.path.basename(p).lower() == "lessons.md":
            deny(
                "LESSONS.md IS APPEND-ONLY. The constitution forbids "
                "deleting from it, and this hook does not attempt to tell a "
                "legitimate supersession from a quiet deletion.\n"
                "APPEND instead:  python -c \"...\"  or  >> LESSONS.md\n"
                "A real correction (loop (d) supersession: original "
                "preserved, superseded marker, correction appended) is a "
                "DELIBERATE hook-disable plus a checkpoint — loud and "
                "auditable, not routine.")
    allow()


def rule_fab_protection(data):
    """R-ASSET: no authoring into a vendor/Fab folder."""
    require_input(data, "path")
    for p in _paths(data):
        n = _norm(p)
        for tree in FAB_TREES:
            if ("/" + tree.lower().replace("\\", "/")) in n:
                deny(
                    "R-ASSET: never author into a vendor folder — {0}\n"
                    "`{1}` is vendor-delivered content. It is replaced "
                    "wholesale on reinstall, so an edit there is lost work "
                    "that looks like committed work.\n"
                    "Copy what you need to a project-owned path and edit "
                    "the copy (non-negotiable 20: adopted artefacts are "
                    "copies at stable names, hash-proven at adoption)."
                    .format(p, tree))
    allow()


def rule_load_level(data):
    """R14: level switching goes through scripts/open_level.py.

    ORIGIN STORY — this hook exists because of a real editor kill on
    2026-08-05. A hand-rolled payload called
    `LevelEditorSubsystem.load_level()` after reading the world with
    `get_editor_world()`. The engine fatals:

        EditorServer.cpp:1951 — World Memory Leaks: 1 leaks objects
        and packages

    `load_level` tears down the outgoing world and asserts nothing
    references it, and THE EXECUTING PYTHON FRAME IS A REFERENCE.
    `scripts/open_level.py` already existed, had root-caused that exact
    crash TWICE, and carries the fix (`gc.collect()` immediately before
    the call). The cost was not the crash — it was writing a wrong rule
    from it and getting it ratified, because the investigation started
    at the crash instead of at the repo.
    """
    require_input(data, "any")
    text = _text(data)
    if "load_level" not in text:
        allow()
    # INVOKED, not merely MENTIONED (Pass 3 2026-09-16): a substring
    # allow let any payload that named open_level.py in a comment or
    # echo re-run the hand-rolled load. For shell tools the sanctioned
    # tool must be the EXECUTED script; file tools (authoring payloads
    # that reference it) keep the mention allow — invocation is not a
    # meaningful test for content being written.
    _cmdf = (data.get("tool_input") or {}).get("command")
    if isinstance(_cmdf, str) and _cmdf.strip():
        if re.search(r"(?i)\b(python[\w.]*|py)(\.exe)?\b[^|;&\n]*"
                     r"open_level\.py\b", _cmdf):
            allow()      # the sanctioned tool, actually invoked
    elif "open_level.py" in text:
        allow()          # file tool referencing the sanctioned tool
    deny(
        "R14: `load_level` must go through `scripts/open_level.py`.\n"
        "A hand-rolled load payload FATALS THE EDITOR: "
        "EditorServer.cpp:1951 'World Memory Leaks' — the teardown "
        "asserts nothing references the outgoing world, and the executing "
        "Python frame IS a reference. Merely having read the level in the "
        "payload is enough to die.\n"
        "`open_level.py` releases those references (gc.collect) "
        "immediately before the call, atomically with its guard. It had "
        "already root-caused this crash TWICE before it was reinvented.")


_MSYS_REASON = (
    "MSYS PATH MANGLING: Git Bash rewrites a bare content-root argument "
    "into a filesystem path.\n"
    "Measured 2026-08-05: an audit tool was passed a material path and it "
    "arrived prefixed with the Git install directory, so the tool reported "
    "'material not found' — which reads as the asset being missing "
    "rather than the argument being rewritten. That is a misdiagnosis "
    "wearing a plausible error message.\n"
    "Use the PowerShell tool for UE content paths, or set "
    "MSYS_NO_PATHCONV=1 for this command.")


def rule_msys_game_path(data):
    """Git Bash rewrites /Game/... arguments into filesystem paths.

    ORIGIN STORY — 2026-08-05. `audit_material_samplers.py --material
    /Game/Materials/M_fir_bark` came back "material not found", and the
    argument had been silently rewritten to
    `C:/Program Files/Git/Game/Materials/M_fir_bark`. The tool then
    reported absence, which reads as *the material is missing* rather
    than *your argument was rewritten* — a misdiagnosis wearing a
    plausible error message.

    NARROWED 2026-08-06, ruling with three conditions (fixtures first,
    threat case still fires, LESSONS logged). The hook fired on BOTH of
    its own suggested remedies: it matched the /Game/ string regardless
    of `tool_name`, so the PowerShell tool tripped it, and it had no
    carve-out for MSYS_NO_PATHCONV=1. A guard whose remedy is also
    refused gets circumvented, and a circumvented guard protects
    nothing. The exceptions are bounded, fail-closed:
      - tool_name must EXPLICITLY equal "PowerShell" — absent or
        anything else is treated as Bash (MSYS mangling is a Git Bash
        phenomenon; PowerShell has no MSYS layer to rewrite argv).
      - MSYS_NO_PATHCONV=1 disarms only as UNQUOTED text with =1
        exactly, checked AFTER heredoc/quote stripping so prose about
        the variable does not disarm the rule. (An env prefix disarms
        the whole compound command — accepted looseness: this guard
        exists to catch accidents, and the operator who types the
        prefix has named the hazard.)
    Both remedies and all three exception edges are fixtures in
    prove_hooks.py. The two remedy fixtures were captured BEFORE the
    narrowing and reproduced the false positives (164/166, exactly the
    two remedies failing); post-narrow, with a third remedy fixture for
    the quoted-argument form, the suite is 167/167 and the original
    threat case still fires.
    """
    require_input(data, "command")
    if data.get("tool_name") == "PowerShell":
        allow()          # remedy 1: no MSYS layer, nothing rewrites argv
    cmd = (data.get("tool_input") or {}).get("command") or ""
    # STRIP HEREDOC BODIES AND QUOTED STRINGS BEFORE MATCHING.
    #
    # FALSE POSITIVE, caught 2026-08-05 by this hook blocking its own
    # author's commit. The commit message DESCRIBED the defect this rule
    # guards, so the content path appeared as prose inside a heredoc and
    # was matched as though it were an argument. MSYS rewrites
    # ARGUMENTS; it does not rewrite prose inside a quoted document.
    #
    # A guard that fires on commentary about itself is the kind of false
    # positive that gets guards disabled, which is worse than the defect
    # it prevents.
    # Heredoc bodies are documents, never argv. Strip them outright.
    scrubbed = HEREDOC_RE.sub(" ", cmd)
    # A QUOTED STRING IS AN ARGUMENT IF IT *IS* A PATH, AND PROSE IF IT
    # MERELY CONTAINS ONE. Stripping every quoted string was too blunt
    # and let a genuine `--material "/Game/..."` through; keeping them
    # all re-introduced the false positive. The discriminator is whether
    # the quoted content STARTS with the content root.
    bare = re.sub(r"'[^']*'", " ", scrubbed)
    bare = re.sub(r'"[^"]*"', " ", bare)
    # Remedy 2: an UNQUOTED MSYS_NO_PATHCONV=1 disarms MSYS conversion
    # (for quoted and bare arguments alike), so it disarms this rule
    # entirely. Checked on `bare` (heredoc- and quote-stripped) so
    # quoted prose about the variable does not disarm it, and =1
    # exactly so =0 does not.
    if re.search(r"(^|\s)MSYS_NO_PATHCONV=1(\s|;|$)", bare):
        allow()
    quoted = re.findall(r"'([^']*)'|\"([^\"]*)\"", scrubbed)
    for a, b in quoted:
        if (a or b).strip().startswith("/Game/"):
            deny(_MSYS_REASON)
    if re.search(r"(^|\s)/Game/", bare):
        deny(_MSYS_REASON)
    allow()


def rule_heredoc_escapes(data):
    """Multi-line content goes through the FILE TOOLS, not heredocs.

    PROMOTED 2026-08-05 after the THIRD cost in one session. The Bash
    tool mangles backslash escapes inside heredoc bodies, and every
    instance looked different:

      1. `\\n` in a Python string became a real newline, producing an
         unterminated string literal.
      2. A `\\\\` in a regex collapsed to one backslash and changed what
         the pattern matched.
      3. The same `\\n` mangling broke this very hook's reason string
         while it was being repaired.

    Three costs in one session is past the same-mistake threshold, and
    the fix is structural rather than vigilance: **any multi-line
    content destined for a file goes through Write/Edit.**

    THE DISCRIMINATOR IS BACKSLASHES IN A HEREDOC BODY. A heredoc with
    no escapes survives the shell intact and is left alone, so ordinary
    `cat <<EOF` usage is untouched. It is exactly the escape-bearing
    bodies — the ones that silently change meaning — that are refused.
    """
    require_input(data, "command")
    cmd = data["tool_input"]["command"]
    # HEREDOC_RE (shared): the old regex here required a newline right
    # after the delimiter, so `cat <<'EOF' > out.py` — the most common
    # file-writing form, the exact class this rule exists for — was
    # never matched and its backslashes passed (Pass 3 2026-09-16).
    bodies = HEREDOC_RE.findall(cmd)
    for _q, _tag, body in bodies:
        if "\\" in body:
            deny(
                "HEREDOC ESCAPE MANGLING: this heredoc body contains "
                "backslash escapes, and the shell layer rewrites them.\n"
                "Measured THREE times on 2026-08-05: `\\n` became a real "
                "newline and broke a Python string literal; a doubled "
                "backslash collapsed and changed a regex; the same fault "
                "then broke a hook's own message while it was being "
                "repaired.\n"
                "Write the content with the Write or Edit tool instead. A "
                "rule that depends on remembering which characters the "
                "shell eats is the weakest kind of rule — the file tools "
                "have no such failure mode.\n"
                "(A heredoc with NO backslashes is fine and is not "
                "blocked.)")
    allow()


def rule_commit_claims(data):
    """A commit message that names a recipe must not invent it.

    A BLOCKED-AND-REBUILT OPERATION IS A RESUMPTION HAZARD. When a guard
    blocks a compound action, the rebuild must re-verify that EVERY part
    of the original intent landed — not just the part that tripped the
    guard. Twice on 2026-08-05 a commit message described work that was
    not in the tree, and the second time the mechanism was exactly this:
    the msys hook blocked the commit, the commit was rebuilt, and the
    R15 insertion that had been bundled into the same command was never
    re-run. The message shipped describing a recipe that did not exist.

    DISCRIMINATOR, deliberately narrow: only `R<number>` recipe
    references are checked, against `# R<number>` headings in
    RECIPES.md. Recipe IDs are unambiguous, cheap to verify, and were
    the thing wrong both times. File paths are NOT checked — a commit
    legitimately names files it deletes, renames, or describes in prose,
    and a guard that fired on those would be the
    commentary-about-itself false positive again.
    """
    require_input(data, "command")
    cmd = data["tool_input"]["command"]
    # --file= and attached -Fpath are valid git forms too (Pass 3
    # 2026-09-16: requiring whitespace after -F skipped the whole check
    # for them — the invented-R15 class shipping unchecked).
    m = re.search(r"\bgit\b[^|;&\n]*\bcommit\b[^|;&\n]*?(?:--file[=\s]+|-F\s*)"
                  r"(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    if not m:
        allow()
    path = m.group(1).strip("\"'")
    if path == "-":
        allow()          # message on stdin; nothing to read here
    # A relative path resolves against the SESSION's cwd when the hook
    # payload carries one; the hook process's own cwd may differ (Pass 3
    # 2026-09-16 — the old comment claimed "the commit itself will fail",
    # which is only true when git ALSO cannot resolve it).
    if not os.path.isabs(path):
        _cwd = data.get("cwd")
        if isinstance(_cwd, str) and _cwd:
            path = os.path.join(_cwd, path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            msg = fh.read()
    except OSError:
        # Unopenable from the hook's vantage. The commit MAY still
        # succeed (a cwd this process cannot see); the claims check
        # self-disables here — a documented limitation, not a guarantee.
        allow()
    claimed = set(re.findall(r"\bR(\d{1,3})\b", msg))
    if not claimed:
        allow()
    try:
        with open(os.path.join(REPO_ROOT, "RECIPES.md"), "r",
                  encoding="utf-8", errors="replace") as fh:
            recipes = fh.read()
    except OSError:
        allow()
    have = set(re.findall(r"^#\s*R(\d{1,3})\b", recipes, flags=re.M))
    missing = sorted(claimed - have, key=int)
    if missing:
        deny(
            "COMMIT MESSAGE NAMES A RECIPE THAT DOES NOT EXIST: {0}\n"
            "RECIPES.md has no `# R{1}` heading.\n"
            "This has happened TWICE, and both times the mechanism was a "
            "BLOCKED-AND-REBUILT COMMIT: a guard stopped a compound "
            "command, the commit was rebuilt, and a sibling edit bundled "
            "into the same command was never re-run — so the message "
            "described work that is not in the tree.\n"
            "Re-verify that EVERY part of the original intent landed, not "
            "just the part that tripped the guard. Verified by grep, not "
            "asserted.".format(", ".join("R" + n for n in missing),
                               missing[0]))
    allow()


RULES = {
    "commit-claims": rule_commit_claims,
    "heredoc-escapes": rule_heredoc_escapes,
    "commit-file": rule_commit_file,
    "no-force-delete": rule_no_force_delete,
    "engine-files": rule_engine_files,
    "outside-repo": rule_outside_repo,
    "lessons-append-only": rule_lessons_append_only,
    "fab-protection": rule_fab_protection,
    "load-level": rule_load_level,
    "msys-game-path": rule_msys_game_path,
}


def main():
    # EVERYTHING is inside the guard. Any failure denies.
    try:
        if len(sys.argv) < 2:
            deny("guard: no rule named. Refusing rather than passing an "
                 "unguarded tool call through.")
        name = sys.argv[1]
        fn = RULES.get(name)
        if fn is None:
            deny("guard: unknown rule {0!r}. A misconfigured hook must "
                 "block, not wave the call through.".format(name))
        raw = sys.stdin.read()
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            deny("guard: hook input was not valid JSON. Denying — an "
                 "unreadable payload is exactly when a guard must hold.")
        if not isinstance(data, dict):
            deny("guard: hook input was not a JSON object.")
        fn(data)
        allow()
    except SystemExit:
        raise
    except BaseException as exc:          # noqa: BLE001 — deliberate
        # THE WHOLE POINT. Any unhandled failure exits 2, because exit
        # codes other than 0 and 2 are NON-BLOCKING and would let the
        # guarded action proceed.
        sys.stderr.write(
            "guard: INTERNAL FAILURE ({0}: {1}). Denying.\n"
            "Exit codes other than 0 and 2 are non-blocking, so a hook that "
            "crashed would let this call through. It fails closed instead.\n"
            .format(type(exc).__name__, str(exc)[:200]))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
