"""ue_exec.py — run a Python payload FILE inside the verified editor.

WHY A FILE AND NOT INLINE SOURCE
    `MODE_EXEC_FILE` means the command IS A FILENAME. Passing source inline
    works for short payloads and SILENTLY FAILS for longer ones, surfacing as
    "Could not load Python file 'C:/.../Win64/<your entire source>'". That cost
    this project three failed placement runs and two wrong theories on
    2026-08-10, and the AlpineLab builders were rewritten to stage the payload
    under Saved/ and send the path. This tool is that pattern, once, for
    everybody.

    It also sidesteps CLAUDE.md hazard 4 -- a literal ".py" anywhere inside an
    INLINE payload makes ExecuteFile's FindFirst turn the script into a path.
    When the command genuinely is a path, that is simply correct.

RULE 7 IS NOT OPTIONAL
    The node is selected by verify_landscape._select_verified_node against
    UE_PROJECT_ROOT. The port serves whichever editor holds it; autonomy over
    this project is not authority over somebody else's.

CONTRACT
    The payload should print MARKER + one JSON object as its last act. This
    tool finds the marker, decodes the JSON and prints it. A payload that
    prints no marker is reported as "COULD NOT LOOK" and is NOT reported as
    empty -- a failed measurement never reads as a measurement (non-negotiable 6).

USAGE
    python scripts/ue_exec.py <payload-file> [--marker __LL__] [--raw]
    python scripts/ue_exec.py p.txt --set NAME=value --set OTHER=123

    --set performs literal __NAME__ -> value substitution in the payload before
    it is staged, so a payload stays a static file rather than an f-string.

Exit codes:
    0  ran, marker found, payload reported no error
    1  ran but the payload reported an error, or no marker (could not look)
    2  bad arguments / payload file missing
    3  rule 7: no verified editor node
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402
import verify_landscape  # noqa: E402

STAGE_DIR = os.path.join(bootstrap.UE_PROJECT_ROOT, "Saved", "LLPython")


def run(payload_text: str, marker: str = "__LL__", timeout: float = 30.0,
        stage_name: str = "ue_exec_payload", quiet: bool = False,
        project_root: str = None):
    """`project_root` DECLARES which editor this call expects, and the rule-7
    gate then verifies the connected node against it.

    This is not a way around rule 7 -- it is the rule applied to a project
    other than ours. The rule exists because "the port serves whichever editor
    holds it", and its remedy is to state your expectation and check it. A
    hardcoded UE_PROJECT_ROOT enforces that only while there is exactly one
    project in play; the sample-project census has several, and the danger it
    guards against (driving somebody else's editor by accident) gets LARGER,
    not smaller.

    Defaults to UE_PROJECT_ROOT, so every existing caller is unchanged.

    The payload still stages under LandscapeLab/Saved/LLPython and is executed
    by absolute path: staging into a sample project would be a write outside
    this repo, which standing rule 1 forbids and which the census does not
    need.
    Returns (exit_code, parsed_or_None, raw_text).
    """
    os.makedirs(STAGE_DIR, exist_ok=True)
    # A stable name per caller, so a failed run is inspectable afterwards
    # rather than vanishing. Two phases sharing one filename is the defect
    # save_level shipped; callers get their own name.
    path = os.path.join(STAGE_DIR, stage_name + ".py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload_text)

    # ⭐ STAGE ll_must BESIDE THE PAYLOAD, so a payload can IMPORT the
    # checked calls instead of carrying a pasted copy of them.
    #
    # Payloads run through MODE_EXEC_FILE, so `__file__` exists and
    # points here; a payload reaches the module with
    #
    #     import os, sys
    #     sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    #     import ll_must
    #
    # WHY THIS EXISTS: `_ll_wire` was a source STRING pasted into each
    # builder, which is how three builders ended up with three copies of
    # one check. Copied fresh on every run so the staged module can never
    # be older than the repo's.
    #
    # Failure here is NOT fatal to the run: a payload that does not
    # import it is unaffected, and one that does will fail loudly on its
    # own import line, which is a better place to find out than here.
    try:
        _src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ll_must.py")
        if os.path.isfile(_src):
            with open(_src, "r", encoding="utf-8") as _fh:
                _mod = _fh.read()
            with open(os.path.join(STAGE_DIR, "ll_must.py"), "w",
                      encoding="utf-8") as _fh:
                _fh.write(_mod)
    except Exception:
        pass

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote,
            bootstrap._norm(project_root or bootstrap.UE_PROJECT_ROOT),
            timeout)
        if node is None:
            print("REFUSE (rule 7):", reason)
            return 3, None, ""
        remote.open_command_connection(node["node_id"])
        r = remote.run_command(path.replace("\\", "/"), unattended=True,
                               exec_mode=remote_exec.MODE_EXEC_FILE)
        text = bootstrap._collect_output(r)
    finally:
        try:
            remote.stop()
        except Exception:
            pass

    # LAST occurrence (Pass 3 2026-09-16): the contract says the marker is
    # the payload's LAST act, but find() took the FIRST -- a payload whose
    # earlier output echoed the marker string would have its partial text
    # decoded as the verdict.
    i = text.rfind(marker)
    if i < 0:
        if not quiet:
            print("COULD NOT LOOK: payload produced no marker.")
            print("--- raw output (first 3000 chars) ---")
            print(text[:3000])
        return 1, None, text
    try:
        d, _ = json.JSONDecoder().raw_decode(text[i + len(marker):].lstrip())
    except ValueError as exc:
        if not quiet:
            print("COULD NOT LOOK: marker found but JSON did not decode:", exc)
            print(text[i:i + 2000])
        return 1, None, text
    if not isinstance(d, dict):
        # raw_decode accepts any JSON value; d.get() on a null/list/scalar
        # was an unhandled AttributeError -- a traceback where the
        # documented COULD-NOT-LOOK refusal was promised (Pass 3).
        if not quiet:
            print("COULD NOT LOOK: marker found but the JSON is not an "
                  "object (got %s) -- the contract is MARKER + one JSON "
                  "OBJECT as the payload's last act." % type(d).__name__)
            print(text[i:i + 2000])
        return 1, None, text
    return (1 if d.get("error") else 0), d, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("payload", help="local file containing the payload source")
    ap.add_argument("--marker", default="__LL__")
    ap.add_argument("--timeout", type=float, default=30.0,
                    help="node DISCOVERY WINDOW, not a deadline. The full "
                         "period is always spent waiting, even when the "
                         "node answers in 2 s. 12-25 is right; larger "
                         "values buy nothing but delay.")
    ap.add_argument("--raw", action="store_true", help="also print raw output")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="literal __NAME__ substitution in the payload")
    ap.add_argument("--stage-name", default=None)
    ap.add_argument("--project-root", default=None,
                    help="ABSOLUTE path of the project whose editor this call "
                         "expects. The rule-7 gate verifies the connected node "
                         "against it. Defaults to UE_PROJECT_ROOT. This is "
                         "rule 7 applied to another project, not a way past "
                         "it: with several projects in play the danger it "
                         "guards against gets larger, not smaller.")
    ap.add_argument("--no-syntax-check", action="store_true",
                    help="skip the local parse of the substituted payload "
                         "(only for a host/editor Python difference)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.payload):
        print("REFUSE: no such payload file:", args.payload)
        return 2

    with open(args.payload, "r", encoding="utf-8") as fh:
        text = fh.read()
    for pair in args.set:
        if "=" not in pair:
            print("REFUSE: --set needs NAME=VALUE, got:", pair)
            return 2
        k, v = pair.split("=", 1)
        # ⛔ THE GIT-BASH REWRITE GUARD. RULED 2026-08-30, and it is deliberately
        # BELT AND SUSPENDERS: forge.py already writes a "run this from
        # PowerShell" header into stage10_command.txt, but a header is ADVICE
        # and this is a CHECK. Advice is not enforcement, and the person
        # pasting the command has not read it.
        #
        # MSYS2 (Git Bash) rewrites any argument that looks like an absolute
        # POSIX path against the Git install root, so
        #   --set DEST=/Game/Scratch/ForgeWoodStack
        # arrives as
        #   DEST=C:/Program Files/Git/Game/Scratch/ForgeWoodStack
        # Measured 2026-08-30. The payload's own /Game/Scratch/ delete-guard
        # caught it that time, but only because that particular value happened
        # to feed a guarded delete -- LEVEL was mangled identically and had no
        # guard at all.
        #
        # This checks the VALUE for the rewrite signature, so it protects
        # every /Game/ and /Engine/ parameter of every payload rather than
        # the one that was thought of. (A mangled plain-filesystem POSIX
        # path has no distinguishing signature and is not detectable here.)
        # /Game/ AND /Engine/ (Pass 3 2026-09-16): the guard only knew
        # /Game/, so a mangled /Engine/BasicShapes/Cube passed silently —
        # while the comment claimed every parameter was protected. Other
        # POSIX-looking paths (plain filesystem ones) are still NOT
        # detectable this way; the comment above now says which class is.
        _mangle = re.search(r"(?i)[\\/]git([\\/](?:game|engine)[\\/])", v)
        if _mangle:
            print("REFUSE: --set %s looks like a Git-Bash-mangled content "
                  "path:" % k)
            print("    %s" % v)
            print("  MSYS2 rewrites absolute POSIX-looking arguments against")
            print("  the Git install root. The value that was MEANT is")
            # derive the hint from the MATCH, not a case-sensitive split
            # (the regex is case-insensitive; split('/Game/') printed the
            # whole mangled string back for a lowercase match)
            print("  probably: %s"
                  % v[_mangle.start(1):].replace("\\", "/"))
            print("  FIX: run this from PowerShell, or prefix the command with")
            print("       MSYS_NO_PATHCONV=1 in Git Bash.")
            return 2
        text = text.replace("__" + k + "__", v)

    # ⭐ THE STANDING RENDER PREAMBLE, SUBSTITUTED FROM ONE FILE.
    #
    # A payload that renders writes `__RENDER_PREAMBLE__` on a line of its own
    # and gets every editor-only overlay turned off plus the selection cleared.
    # Three frames were spoiled by three different overlays -- nav wireframes,
    # a light billboard, and a prose-only Volumes rule the payload never issued
    # -- each fixed in one payload at a time. This is the single declaration
    # that ends that family (non-negotiable 24).
    #
    # Indentation is PRESERVED from the marker's own line, because the marker
    # sits inside a `try:` block in every caller and a flush-left substitution
    # would split it. The 2026-08-30 IndentationError that cost a round trip
    # came from exactly this, done by hand.
    #
    # EXPANDED BEFORE THE SYNTAX CHECK (Pass 3 2026-09-16): this block
    # used to run AFTER it, so the bare marker line parsed as a valid
    # name expression and a syntax/indent fault in render_preamble.txt --
    # the exact class the check was built for -- only surfaced from the
    # editor 25 s later. The check must see what the editor receives.
    if "__RENDER_PREAMBLE__" in text:
        pre_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "render_preamble.txt")
        with open(pre_path, "r", encoding="utf-8") as fh:
            pre = fh.read()
        out_lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped == "__RENDER_PREAMBLE__":
                indent = line[:len(line) - len(line.lstrip())]
                for pl in pre.split("\n"):
                    out_lines.append((indent + pl) if pl.strip() else "")
            else:
                out_lines.append(line)
        text = "\n".join(out_lines)

    # A PAYLOAD IS A CALL SITE WITH NO COMPILER. Give it one, here, because
    # this is the single point every payload passes through -- putting the
    # check in each caller would be non-negotiable 24 again.
    #
    # Motivating case, 2026-08-30: a one-line edit to city_shot_payload landed
    # at the wrong indent level and split a `for` body. The editor answered
    # "IndentationError ... line 110" 25 seconds later, on a run that was
    # about to spend several minutes rendering. Parsing the SUBSTITUTED text
    # locally costs milliseconds and refuses before anything is sent.
    #
    # It parses the fully SUBSTITUTED AND EXPANDED source (after --set and
    # the render preamble), because only that form is what the editor
    # receives. This covers syntax and indentation ONLY: the preamble's
    # references to _u/_out are still runtime NameErrors if the host
    # payload has not defined them before the marker line. The escape
    # hatch exists because the host and the editor need not be the same
    # Python version -- but it must be asked for, so a genuine syntax
    # error cannot pass by default.
    if not args.no_syntax_check:
        try:
            ast.parse(text)
        except SyntaxError as exc:
            print("REFUSE: the payload does not parse, so the editor would "
                  "only tell you this 25 s from now.")
            print("  %s: %s" % (type(exc).__name__, exc.msg))
            print("  line %s, offset %s: %s"
                  % (exc.lineno, exc.offset, (exc.text or "").rstrip()))
            print("  (checked AFTER --set substitution and preamble "
                  "expansion, which is what the editor receives)")
            print("  --no-syntax-check overrides, for a host/editor Python "
                  "version difference.")
            return 2

    stage = args.stage_name or os.path.splitext(
        os.path.basename(args.payload))[0]
    if args.timeout > 60.0:
        # The lesson existed in LESSONS.md and did not fire: on 2026-08-16
        # it was recorded that this is a fixed discovery window, and later
        # the same day a caller passed 120-180 anyway and paid minutes per
        # call. A rule that lives only in a narrative cannot stop the hand
        # that types the flag; this prints at the point of use.
        print("NOTE: --timeout %.0f is a DISCOVERY WINDOW and will be spent "
              "in full, even though the node usually answers in seconds. "
              "12-25 is right." % args.timeout)
    t0 = time.time()
    rc, d, raw = run(text, marker=args.marker, timeout=args.timeout,
                     stage_name=stage, project_root=args.project_root)
    dt = time.time() - t0

    if args.raw:
        print("--- raw ---")
        print(raw[:8000])
        print("--- end raw ---")
    if d is not None:
        print(json.dumps(d, indent=2, default=str))
    print("(%.1f s)" % dt)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
