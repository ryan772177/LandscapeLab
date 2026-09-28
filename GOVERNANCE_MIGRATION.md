# GOVERNANCE MIGRATION TABLE — for ratification

**Status: RATIFIED 2026-08-05. Hooks BUILT and proven 113/113.**

## THE STANDARD FOR THIS DOCUMENT

**EVERY RULE THAT IS *NOT* MIGRATED STATES WHY, OR IT READS AS A GAP.**
A missing row is indistinguishable from an oversight; a row saying "not
migrated, because X already enforces it" is a decision a reviewer can
disagree with. Ratified off the standing-rules-7-and-8 omission, which
was correct precisely because it was written down.

Every surface below was verified against the live docs on 2026-08-05
before classification — `code.claude.com/docs/en/{hooks,skills,
plugins-reference}` — because *an API remembered is an API guessed*
applies to Claude Code's own surfaces too. Field names, event names and
the blocking contract quoted here are from those pages, not recalled.

---

## TWO FINDINGS THAT CHANGE THE CAMPAIGN AS WRITTEN

**1. Custom commands have been MERGED INTO SKILLS.** The docs state
`.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both
create `/deploy` and work the same way, and skills are recommended for
new work. So campaign item 5 (COMMANDS) does **not** need a separate
surface: each ritual becomes a **skill with
`disable-model-invocation: true`**, which is exactly the documented
mechanism for "only the user triggers this" — `/commit`, `/deploy` are
the docs' own examples. This is strictly better than `commands/`: skills
get a directory for helper scripts, which several of our rituals need.

**2. Plugin-shipped agents CANNOT carry hooks.** Verbatim: *"For
security reasons, `hooks`, `mcpServers`, and `permissionMode` are not
supported for plugin-shipped agents."* So the **SubagentStop gate in
campaign item 4 cannot live in the agent definition.** It goes in
`hooks/hooks.json` (plugin) or `.claude/settings.json` (repo), matched
by agent type — `SubagentStop` matches against agent type per the
matcher table.

A third, smaller one: `.claude/settings.local.json` is **gitignored**.
Anything that must ship with the repo goes in `.claude/settings.json`
or the plugin. Our only existing settings file is the local one.

---

## THE BLOCKING CONTRACT (verified, for every hook below)

```json
{ "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "..." } }
```
on **exit 0**; or **exit 2** with the reason on stderr. Exit codes other
than 0 and 2 are *non-blocking* — the action proceeds. **That matters:
a hook that crashes does not block.** Every hook below must therefore
fail closed by construction, which is non-negotiable 1 applied to the
enforcement layer itself.

---

## A. MUST-ENFORCE → HOOKS

| # | Rule | Event / matcher | How it blocks | Confidence |
|---|---|---|---|---|
| H1 | **Standing 3** — commit messages go through a FILE, `git commit -F` unconditionally | `PreToolUse`, matcher `Bash\|PowerShell`, `if: Bash(git commit *)` | deny when the command contains `-m`/`--message` | **High** — pure string test |
| H2 | **Standing 2** — no recursive/forced deletes | `PreToolUse`, `Bash\|PowerShell` | deny `rm -rf`, `rm -f`, `del /s`, `Remove-Item -Recurse`/`-Force` | **High** |
| H3 | **Standing 4** — never modify `.uproject`/`.uasset`/`.umap` on disk | `PreToolUse`, `Write\|Edit\|NotebookEdit` | deny by `file_path` suffix | **High** |
| H4 | **Standing 1** — never write outside repo or UE project | `PreToolUse`, `Write\|Edit` | deny when `file_path` resolves outside both roots | **High** |
| H5 | **LESSONS append-only** | `PreToolUse`, `Edit\|Write` on `LESSONS.md` | deny `Edit` outright; deny `Write` (append via `>>` only) | **High** |
| H6 | **Fab-source write protection** (R-ASSET: no authoring into a Fab folder) | `PreToolUse`, `Write\|Edit` | deny under `Content/{Fab,KiteDemo,MWLandscapeAutoMaterial,Pack_Bonus}` | **High** |
| H7 | **`load_level` must go through `open_level.py`** (R14) | `PreToolUse`, `Bash\|PowerShell\|Write` | deny a payload containing `load_level(` unless the command *is* `open_level.py` | **High** — caught tonight's editor kill |
| H8 | **MSYS path mangling** — `/Game/...` args are rewritten by Git Bash | `PreToolUse`, matcher `Bash` | deny when the command contains a `/Game/` argument; tell it to use PowerShell | **High** — cost a real misdiagnosis tonight |
| H9 | **SessionStart context** — inject `CURRENT STATE` + open defects | `SessionStart`, matcher `startup\|resume\|clear` | additionalContext (non-blocking) | **High** |
| H10 | **Stop on dirty tree** — no session ends with uncommitted work | `Stop` | exit 2 with `git status --short` when dirty | **Medium** — must not trap a user who intends to stop; needs an escape |
| H11 | **Standing 6** — two consecutive script failures ⇒ stop | `PostToolUseFailure`, `Bash` | stateful counter in session dir; block the third | **Medium** — stateful, needs care |
| H12 | **Standing 5** — record dependencies | `PostToolUse`, `if: Bash(pip install *)` | non-blocking reminder to update the record | **Low** — advisory only, cannot verify the record was written |

**Not migrated, deliberately:** Standing 7 (editor identity) and
Standing 8 (dry-run destructive) are **already enforced in code** —
`verify_landscape._select_verified_node` and each script's own dry-run.
Re-implementing them as hooks would create the two-lists-that-must-agree
defect (NN24). Recorded here so the omission is visible, not accidental.

## B. KNOWLEDGE → SKILLS (`.claude/skills/<name>/SKILL.md`)

Body sourced from RECIPES; helper scripts co-located. `description`
written for trigger accuracy — the docs cap `description` +
`when_to_use` at 1,536 chars in the listing.

| Skill | Sources | Triggers on |
|---|---|---|
| `asset-intake` | R-ASSET, R3, the ORM branch, `unpack_orm.py`, `surface_coherence.py` | importing/cataloguing any new asset or surface |
| `material-builder` | R2, the ONE DECLARATION, `material_graph.py`, sampler rules | editing `make_landscape_material.py` or the landscape material |
| `texture-conversion` | `texture_16bit.py`, 16-bit trap, ORM unpack, bit-depth verification | converting/importing textures |
| `stamp-compositing` | R-STAMP, `composite_stamps.py`, adoption via NN20 | terrain stamping or heightmap adoption |
| `scatter-placement` | R12, R4/R5, orphan-sweep warning, `verify_grounding.py` | placing foliage, rocks, clutter |
| `ue-api-resolution` | UE 5.8 RESOLUTION PROTOCOL, NN23, the casualty list | before calling any unfamiliar Unreal API |
| `verification-practice` | RECIPES verification (a)–(i), NN2/6/8/22 | writing any gate, check or measurement |

## C. DELEGATION → SUBAGENTS (`.claude/agents/`)

| Agent | Change | Tools |
|---|---|---|
| `auditor` | **exists**; currently has `Edit, Write` — the campaign says read-only, so those come off | `Read, Grep, Glob` |
| `design-reviewer` | new; NN27 cite-every-API-name mandate in its prompt, and it must OPEN each citation | `Read, Grep, Glob, WebFetch` |
| `registry-analyst` | new; Fab registry reads without loading assets (the tag-is-stale finding) | `Read, Grep, Glob, Bash` |

Plus **`SubagentStop` hook** enforcing NN18 (a required output field is
an instruction; nullable fields must say what null means) across fleet
output. Lives in `hooks/hooks.json`, **not** in the agent frontmatter —
see finding 2.

## D. RITUAL → SKILLS with `disable-model-invocation: true`

| Ritual | Does |
|---|---|
| `/handoff` | writes the CONTEXT-EXHAUSTION handoff: committed / proven / decided-but-unbuilt / named open items |
| `/ruling` | records an operator ruling at both altitudes with today's LOCAL date |
| `/checkpoint` | risky-op checkpoint: tag named for the operation, then commit |
| `/sweep` | NN4 defect-class sweep across `scripts/`, in the same commit as the fix |
| `/liveness` | context-exhaustion self-check against the liveness condition |

## E. ALWAYS-ON → stays in CLAUDE.md

The operating loop (a)–(f), the two escalations, standing rules 9 and
10, and the non-negotiables that are **judgement, not mechanism**: 5, 7,
9, 10, 11, 12, 13, 15, 16, 17, 19, 20, 21, 22, 24, 25, 26, 27. These
cannot be hooked without a model in the loop, and CLAUDE.md stays short
by holding only them plus pointers to the skills.

---

## PROPOSED BUILD ORDER

1. **H1, H2, H3, H5, H6, H7, H8** — the high-confidence deny hooks,
   each with a both-directions test proving it blocks the violation
   **and** passes the legitimate case, before it is trusted.
2. **H9** SessionStart, **H10** Stop.
3. Skills B, agents C, rituals D.
4. Plugin bundle `landscapelab-governance v1` at
   `.claude-plugin/plugin.json` (only `name` is required), components at
   `skills/`, `agents/`, `hooks/hooks.json`.
5. H11, H12 last — the stateful and advisory ones, lowest confidence.

**Hooks are code**, so each gets a REJECTED entry when it misfires and a
recipe when it is proven, exactly like every other tool here.

## Known gap (Pass 3 reading, 2026-09-16): path rules bind to file tools only

The four path rules (engine files, outside-repo, LESSONS append-only,
vendor folders) bind to the Write|Edit|NotebookEdit matcher. A Bash or
PowerShell command writing the same targets (sed -i on a .uasset, a
redirect onto LESSONS.md, Set-Content outside the roots) passes through
the Bash-matcher hooks, none of which examine write targets. The rules
are therefore enforced for the file tools and ADVISORY for the shell.
A shell-side write-target scanner is a design item (BACKLOG 2026-09-16);
until it lands, sessions must not read the hooks as full mechanical
enforcement of standing rules 1/4 or LESSONS append-only.
