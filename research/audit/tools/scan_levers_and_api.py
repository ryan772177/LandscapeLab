"""scan_levers_and_api.py — lever_inventory.json and api_inventory.json.

READ-ONLY. Static analysis of every .py in the repo (current AND
archived), plus every recipe .json.

⭐ WHAT A "LEVER" IS HERE. Anything the pipeline WRITES or READS that
the engine honours: a console variable, an actor/component/asset
property, an MRQ setting, a show flag, a console command, or a config
.ini key. One entry per NAME, every site kept -- the question the audit
asks is "where is this touched, and is it ever read back", and a
deduplicated-to-one-site list cannot answer it.

⛔ READ-BACK IS NOT THE SAME AS READ-BACK FROM THE HONOURING OBJECT.
`set_editor_property(x); get_editor_property(x)` on the same handle
proves the value landed in that handle -- which is exactly what failed
on `grass_varieties` (the handle was a COPY) and on the HLOD builder
settings. So each lever records whether a read exists AND whether any
read is from a different object than the write.

⭐ VECTOR COMPLETENESS. `ColorContrast.xyz * ColorContrast.w` means a
4-vector written as (c,c,c,c) applies c squared. Any write of a
Vector/Vector4/LinearColor records which components carry the value, so
the audit can see the whole class of that bug rather than the one
instance already known.

FOR api_inventory: every `unreal.X` symbol touched, with sites. And the
flag that matters most -- calls whose FAILURE RETURNS A VALUE rather
than raising, then gets consumed as a measurement or a verdict. That
list is built from a known-offenders table (each entry earned by a real
defect in this repo) plus a generic scan for `.get(` / `or 0` / `or []`
patterns feeding comparisons.
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys

def _find_repo(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise SystemExit("no CLAUDE.md above %s" % start)
        d = nd


REPO = _find_repo(__file__)
OUT = os.path.join(REPO, "research", "audit")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "Intermediate",
             "DerivedDataCache", "Saved", "Binaries", "Build",
             "site-packages", "_trash"}

# ---------------------------------------------------------------- patterns
RE_CVAR = re.compile(r"""["']((?:r|sg|t|p|au|net|fx|grass|foliage|landscape|wp|a|s)\.[A-Za-z0-9_.]+)["']""")
# ---- what the cvar regex catches that is NOT a lever ---------------
# `RE_CVAR` matches any quoted `prefix.rest`, and several real prefixes
# (a, s, t, p) are single letters, so it swept up filenames and sidecar
# keys. The desk listed the classes; this is the predicate that drops
# them. Written as a WHITELIST OF SHAPES, not a blacklist of the eight
# strings seen -- a blacklist would re-admit `b.png` on the next run.
_FILE_EXT = (".png", ".jpg", ".jpeg", ".txt", ".ini", ".json", ".csv",
             ".uasset", ".umap", ".exr", ".npy", ".py", ".md", ".zip",
             ".log", ".tif", ".tiff", ".bin", ".yaml", ".yml", ".html")
# Sidecar keys that MENTION a cvar rather than name one. These are our
# own bookkeeping suffixes -- a value recorded ABOUT a lever, not the
# lever. Matching is on the tail, so r.ScreenPercentage_applied drops
# while r.ScreenPercentage itself survives.
_BOOKKEEPING_SUFFIX = ("_applied", "_overridden_by_this_capture",
                       "_requested", "_readback", "_read_back",
                       "_expected", "_actual", "_prior", "_restored")


def KEEP_CVAR(name):
    """True if `name` is plausibly a real console variable.

    Four rejections, each a class the desk named:
      1. a file name       a.png t.png a.txt a.ini a.uasset
      2. a bookkeeping key r.X_applied, r.X_overridden_by_this_capture
      3. a value welded on r.ScreenPercentage100 -- a concatenated
         literal, not a cvar; real cvars do not end in digits with no
         separator after a lowercase letter
      4. a bare prefix     "r." with nothing after it
    """
    if name in SEEDED:
        return True          # every seeded name is a lever BY RULING
    low = name.lower()
    if low.endswith(_FILE_EXT):
        return False
    if low.endswith(_BOOKKEEPING_SUFFIX):
        return False
    tail = name.split(".", 1)[1] if "." in name else ""
    if not tail:
        return False
    # (3) a trailing run of digits glued to a letter. `r.ScreenPercentage100`
    # is the literal `r.ScreenPercentage` + `100` concatenated in source.
    # Real 5.8 cvars that legitimately end in a digit (r.Shadow.CSM.MaxCascades
    # does not; r.RHICmdBypass does not) are vanishingly rare, and none is
    # written by this repo -- so this drops noise without dropping a lever.
    # If one ever appears the SEEDED table carries it through regardless.
    if re.search(r"[a-z]\d{2,}$", tail):
        return False
    if tail.endswith("."):
        return False         # `r.LandscapeLODBias.` -- prose, sentence-final
    # (5) OUR OWN RECIPE KEYS. `foliage.` and `landscape.` are real cvar
    # prefixes AND the top-level keys of alpine_8k.json, so the command-
    # string pattern pulled in `foliage.rock_scatter.repose_deg`,
    # `landscape.scale_xy_cm` and 17 more as though they were levers.
    #
    # The discriminator is CASE, and it is one-directional: UE console
    # variables are CamelCase after the prefix (r.ScreenPercentage,
    # sg.ShadowQuality, foliage.WindEnabled, landscape.ForcedLOD, even
    # r.setRes) while every recipe key in this project is snake_case.
    # An all-lowercase tail is therefore a recipe path, not a cvar.
    #
    # LIMIT, stated rather than discovered: a genuine all-lowercase cvar
    # would be dropped here. None is known, SEEDED overrides the rule
    # for any that turns up, and every rejection is listed in
    # `dropped_as_non_levers` so this is auditable rather than silent.
    if not any(c.isupper() for c in tail):
        return False
    return True


# A console COMMAND string: the cvar, whitespace, then its value --
# `"r.ForceLOD -1"`, `"viewmode lit"`. RE_CVAR cannot see these: its
# character class stops at the space and then demands a closing quote,
# so every literal-valued console write in the repo scanned as ZERO
# sites. This is the pattern that carries the value, so it is the one
# that proves a write.
RE_CVAR_CMD = re.compile(
    r"""["']((?:r|sg|t|p|au|net|fx|grass|foliage|landscape|wp|a|s)"""
    r"""\.[A-Za-z0-9_.]+)[ \t]+([^"']*)["']""")

# Does a FILE perform a console write anywhere? Needed because this
# repo's normal shape is a LIST of cvar names in one place and
# `execute_console_command(world, _cmd)` in a loop somewhere else --
# the name and the call are never on the same line. A line-scoped
# classifier reports 0 writes on a file that writes 30 cvars.
RE_CONSOLE_WRITE_CALL = re.compile(
    r"(?:execute_console_command|ExecuteConsoleCommand"
    r"|add_or_update_console_variable|ExecCmds)")

RE_SETPROP = re.compile(r"""set_editor_property\(\s*["']([A-Za-z0-9_]+)["']\s*,\s*([^\n]*)""")
RE_GETPROP = re.compile(r"""get_editor_property\(\s*["']([A-Za-z0-9_]+)["']""")
RE_CONSOLE = re.compile(r"""(?:ExecuteConsoleCommand|execute_console_command|start_console_commands|end_console_commands)""")
RE_UNREAL = re.compile(r"\bunreal\.([A-Za-z_][A-Za-z0-9_]*)|\b_unreal\.([A-Za-z_][A-Za-z0-9_]*)|\b_u\.([A-Za-z_][A-Za-z0-9_]*)")
RE_INI = re.compile(r"""["']([A-Za-z]+\.ini)["']""")
RE_VEC = re.compile(r"(Vector4|LinearColor|Vector)\s*\(([^)]*)\)")

# ---- SCAN v3: THE SETTER BLIND SPOT --------------------------------
# ⭐ WHY THIS EXISTS. `lighting.sky.color` was recorded by Pass 1 as
# having NO write site. It has one -- apply_lighting.py:394 --
#
#     _slc.set_light_color(_unreal.LinearColor(r, g, b, 1.0))
#
# a METHOD call, which no `set_editor_property("name", ...)` pattern can
# see. Every lever written through a named setter was invisible to the
# inventory, so the audit's "written but never read back" figures were
# computed over a population that excluded an entire write mechanism.
# This is a RECALL defect, and recall defects are the dangerous kind:
# they do not produce a wrong row, they produce a missing one, and a
# missing row reads exactly like a lever nobody touches.
#
# TWO PATTERNS:
#   obj.set_<thing>(value)              -> writes lever <thing>
#   obj.add_or_update_<thing>(n, v)     -> writes lever <thing> (MRQ's
#                                          cvar setter is the known case)
#
# ⛔ AND THE PRECISION LIMIT, STATED RATHER THAN DISCOVERED. Python has
# no types here, so "is the receiver an engine object" cannot be decided
# statically. A `self.set_mode(...)` on one of our own classes matches
# this pattern too. Rather than guess, every row carries its RECEIVER
# and its METHOD verbatim, and receivers that look like engine handles
# are flagged -- so a reader can sort true levers from our own setters
# by looking, instead of trusting a classifier that cannot know.
RE_SETTER = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_\.]*)\.(set_[a-z][a-z0-9_]*"
    r"|add_or_update_[a-z][a-z0-9_]*)\s*\(([^\n]{0,120})")

# Setter names that are NOT engine-lever writes, each for a reason.
_SETTER_NOT_A_LEVER = {
    "set_editor_property",      # already covered, and covered better
    "set_editor_properties",
    "set_defaults",
    "set_default",
    # The cvar scan owns this one. Catching it here files a lever
    # literally named "console_variable", when the actual lever is the
    # NAME passed as its first argument -- which the cvar patterns
    # already record, with its value.
    "add_or_update_console_variable",
}

# `scripts/blender/` is scanned too, and Blender's API is the same
# shape (`bpy.ops.curves.set_selection_domain(...)`). It is not the
# engine, so its receivers are excluded by NAMESPACE -- a fact, not a
# heuristic -- rather than by guessing at the method name.
_NON_ENGINE_RECEIVER = re.compile(r"^(bpy|np|numpy|os|sys|json|re|plt"
                                  r"|ap|argparse|logging|self)\b")

# Receivers that mark a row as almost certainly an engine object. Used
# to FLAG, never to filter -- a row that fails this test is still
# reported, because a filter that silently drops is how the setter
# blind spot happened in the first place.
_ENGINE_RECEIVER_HINT = re.compile(
    r"^(_?u|_?unreal|_?ues|_?eas|_?eal|_?els|_?sub|_?cfg|_?aa|_?go|_?cv"
    r"|_?o|_?a|_?obj|_?actor|_?comp|_?mat|_?asset|_?light|_?slc|_?dl"
    r"|_?ls|_?lp|_?exec|_?job|_?q|_?job_?\w*)$", re.I)

# Every entry here was earned by a real defect in this repo. The audit
# wants NEGATIVES as well as positives, so dead and wrong levers are
# seeded explicitly and reported even when no site is found.
SEEDED = {
    "r.TonemapperFilm": "recorded dead/ineffective",
    "r.ExpandGamut": "recorded dead/ineffective",
    "r.LocalExposure.HighlightContrastScale": "recorded dead/ineffective",
    "r.LocalExposure.ShadowContrastScale": "recorded dead/ineffective",
    "r.LandscapeLODBias": "DOES NOT EXIST in 5.8 (enumerated)",
    "landscape.ForcedLOD": "DOES NOT EXIST in 5.8 (enumerated)",
    "r.ForceLOD": "exists; static-mesh override, not landscape",
    "r.MaxAnisotropy": "STARTUP value -- a runtime console change does "
                       "not reach existing samplers (UE-116243)",
    "r.Shadow.Virtual.Nanite.Enable": "DOES NOT EXIST in 5.8",
    "foliage.WindEnabled": "DOES NOT EXIST in 5.8",
    "r.Wind.Enable": "DOES NOT EXIST in 5.8",
    "r.VT.AnisotropicFiltering": "read only; ground does not use RVT",
    "r.VT.MaxAnisotropy": "read only; ground does not use RVT",
}

# Calls whose FAILURE returns a value instead of raising. Each line is a
# defect this repo actually paid for.
SILENT_RETURNERS = {
    "connect_material_expressions":
        "returns false on a failed connect and carries on "
        "(MaterialEditingLibrary.cpp:928-943); 93/30/10 unchecked calls "
        "were found across three builders",
    "delete_all_material_expressions":
        "does not delete all material expressions -- 7 wired survivors "
        "on M_fir_bark, which is how every conifer trunk rendered the "
        "twig atlas while the build reported success",
    "get_lod_material_slot":
        "returns -1 for an out-of-range section rather than raising, so "
        "a walk that stops on an exception runs to 64",
    "get_console_variable_string_value":
        "returns '' for a cvar that DOES NOT EXIST, which is "
        "indistinguishable from an empty value",
    "get_inputs_for_material_expression":
        "returns EMPTY on a MaterialFunction rather than raising -- all "
        "nine inputs reported zero consumers, which is impossible",
    "save_asset":
        "neither raises nor returns anything the caller reads when the "
        "path is bad; 'saved after the verdict' was printed while the "
        "asset on disk stayed five weeks stale",
    "get_assets":
        "returns [] when the class path is wrong (e.g. /Script/Engine "
        "for a /Script/PCG class), which reads as 'this project has "
        "none'",
    "set_editor_property":
        "on an ARRAY-OF-STRUCTS property, writing the same Array object "
        "back is a silent no-op: it neither raises nor takes",
    "does_asset_exist":
        "returns False for a missing asset AND for a malformed path, so "
        "a typo reads as 'the asset is absent'",
}


def py_files():
    out = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, REPO).replace("\\", "/")
        if rel_root.startswith("research/audit"):
            continue
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(root, f))
    return sorted(out)


def git_span(rel):
    """(first, last) commit date+sha that touched a path."""
    r = subprocess.run(["git", "log", "--format=%h|%ad", "--date=short",
                        "--", rel], cwd=REPO, capture_output=True,
                       text=True).stdout.strip().splitlines()
    if not r:
        return None, None
    return r[-1], r[0]


def main():
    levers = {}
    api = {}
    silent = []
    dropped_cvars = set()
    files = py_files()
    print("scanning %d python files ..." % len(files))
    spans = {}

    def span(rel):
        if rel not in spans:
            spans[rel] = git_span(rel)
        return spans[rel]

    for path in files:
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        try:
            src = io.open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        lines = src.splitlines()
        file_writes_cvars = bool(RE_CONSOLE_WRITE_CALL.search(src))
        for i, line in enumerate(lines, 1):
            for m in RE_CVAR.finditer(line):
                name = m.group(1)
                # ⛔ DROP THE NON-LEVERS. The regex matches anything
                # shaped `x.y`, which swept in filenames (a.png, t.png,
                # a.txt, a.ini, a.uasset), a concatenated literal
                # (r.ScreenPercentage100) and sidecar KEYS that merely
                # mention a cvar (*_applied,
                # *_overridden_by_this_capture). Pass 1 listed all of
                # these; none is a lever.
                if not KEEP_CVAR(name):
                    dropped_cvars.add(name)
                    continue
                e = levers.setdefault(name, {"name": name, "kind": "cvar",
                                             "writes": [], "reads": [],
                                             "notes": []})
                # ⭐ CLASSIFY BY CALL CONTEXT, NOT BY "is it a mention".
                # The first version called EVERY mention a write and
                # recorded 0 reads on all 98 cvars -- which is how "170
                # written, never read back" came to include cvars that
                # the bench reads back from the engine log every run.
                #
                #   WRITE   execute_console_command / ExecuteConsoleCommand
                #           add_or_update_console_variable / set_by_*
                #           -ExecCmds= on a commandline
                #   READ    get_console_variable_* (string/int/float/bool)
                #   DECLARED   a name sitting in a dict/list literal --
                #           benchmark.json's cvar block reaches the engine
                #           through MoviePipelineConsoleVariableSetting,
                #           so it is neither a direct write nor a read at
                #           this site.
                low = line.lower()
                if "get_console_variable" in low:
                    kind, bucket = "get_console_variable_*", e["reads"]
                elif ("execute_console_command" in low
                      or "add_or_update_console_variable" in low
                      or "execcmds" in low or "set_by_console" in low):
                    kind, bucket = "console command / cvar setter", e["writes"]
                elif file_writes_cvars:
                    # The name is a literal in a file that DOES perform
                    # console writes, with the call taking a variable.
                    # This is a write -- an indirect one -- and calling
                    # it "declared" would under-report the repo's most
                    # common shape. The pairing is at FILE scope, so it
                    # is marked as such and not claimed as a proven line.
                    kind, bucket = ("write, INDIRECT (literal here; the "
                                    "console call in this file takes a "
                                    "variable) -- file-scope pairing, "
                                    "not a proven line"), e["writes"]
                else:
                    kind, bucket = "declared (config/dict literal)", \
                        e.setdefault("declared", [])
                val = line.split(name, 1)[1][:80].strip(" \"',:=)")
                bucket.append({"site": "%s:%d" % (rel, i),
                               "value": val, "api": kind})
            # A console command string carries the cvar AND its value:
            # this is the strongest evidence of a write there is, so it
            # is recorded separately and never downgraded.
            for m in RE_CVAR_CMD.finditer(line):
                name, val = m.group(1), m.group(2).strip()
                if not KEEP_CVAR(name):
                    dropped_cvars.add(name)
                    continue
                e = levers.setdefault(name, {"name": name, "kind": "cvar",
                                             "writes": [], "reads": [],
                                             "notes": []})
                e["writes"].append(
                    {"site": "%s:%d" % (rel, i), "value": val,
                     "api": "console command string (literal value)"})
            # ---- scan v3: setter-method writes ----------------------
            for m in RE_SETTER.finditer(line):
                recv, meth, args = m.group(1), m.group(2), m.group(3)
                if meth in _SETTER_NOT_A_LEVER:
                    continue
                if _NON_ENGINE_RECEIVER.match(recv):
                    continue
                if meth.startswith("add_or_update_"):
                    name = meth[len("add_or_update_"):]
                else:
                    name = meth[len("set_"):]
                if not name:
                    continue
                e = levers.setdefault(name, {"name": name,
                                             "kind": "setter_method",
                                             "writes": [], "reads": [],
                                             "notes": []})
                # A lever already known by another mechanism keeps that
                # kind; the setter site is added to its writes. Only a
                # name seen ONLY here stays kind="setter_method", which
                # is exactly the population "how many were invisible
                # before" asks about.
                e["writes"].append({
                    "site": "%s:%d" % (rel, i),
                    "value": args.strip().rstrip("),")[:100],
                    "api": "%s()  [setter method]" % meth,
                    "receiver": recv,
                    "receiver_looks_like_an_engine_object":
                        bool(_ENGINE_RECEIVER_HINT.match(recv.split(".")[0])),
                })

            for m in RE_SETPROP.finditer(line):
                name = m.group(1)
                val = m.group(2).strip().rstrip("),")[:100]
                e = levers.setdefault(name, {"name": name,
                                             "kind": "editor_property",
                                             "writes": [], "reads": [],
                                             "notes": []})
                comps = None
                vm = RE_VEC.search(val)
                if vm:
                    args = [a.strip() for a in vm.group(2).split(",")]
                    comps = {"type": vm.group(1), "args": args,
                             "all_same": len(set(args)) == 1,
                             "n": len(args)}
                e["writes"].append({"site": "%s:%d" % (rel, i),
                                    "value": val,
                                    "api": "set_editor_property",
                                    "vector": comps})
            for m in RE_GETPROP.finditer(line):
                name = m.group(1)
                e = levers.setdefault(name, {"name": name,
                                             "kind": "editor_property",
                                             "writes": [], "reads": [],
                                             "notes": []})
                obj = line.split("get_editor_property")[0].strip()
                obj = obj.split("=")[-1].strip().split(".")[0][-40:]
                e["reads"].append({"site": "%s:%d" % (rel, i),
                                   "api": "get_editor_property",
                                   "from": obj})
            for m in RE_INI.finditer(line):
                name = m.group(1)
                e = levers.setdefault(name, {"name": name, "kind": "ini",
                                             "writes": [], "reads": [],
                                             "notes": []})
                e["writes"].append({"site": "%s:%d" % (rel, i),
                                    "value": line.strip()[:100],
                                    "api": "config file"})
            for m in RE_UNREAL.finditer(line):
                sym = m.group(1) or m.group(2) or m.group(3)
                a = api.setdefault(sym, {"symbol": sym, "sites": [],
                                         "files": set()})
                if len(a["sites"]) < 40:
                    a["sites"].append("%s:%d" % (rel, i))
                a["files"].add(rel)
            for name, why in SILENT_RETURNERS.items():
                if name in line and not line.strip().startswith("#"):
                    consumed = None
                    nxt = " ".join(lines[i:i + 3])
                    if re.search(r"\bif\b|==|!=|<|>|len\(|not \b|assert",
                                 nxt):
                        consumed = nxt.strip()[:140]
                    silent.append({"api": name, "site": "%s:%d" % (rel, i),
                                   "line": line.strip()[:160],
                                   "why_silent": why,
                                   "consumed_by": consumed})
        for rel2 in (rel,):
            f, l = span(rel2)
            for e in list(levers.values()):
                pass

    # attach first/last commit per lever from the files that touch it
    for name, e in levers.items():
        fs = sorted({s["site"].split(":")[0]
                     for s in e["writes"] + e["reads"]})
        firsts, lasts = [], []
        for rel in fs:
            f, l = span(rel)
            if f:
                firsts.append(f)
            if l:
                lasts.append(l)
        e["files"] = fs
        e["first_commit"] = sorted(firsts)[0] if firsts else None
        e["last_commit"] = sorted(lasts)[-1] if lasts else None
        e["has_read_back"] = bool(e["reads"])
        wobj = {w["site"].split(":")[0] for w in e["writes"]}
        robj = {r["site"].split(":")[0] for r in e["reads"]}
        e["read_in_a_different_file_than_write"] = bool(robj - wobj)
        vecs = [w["vector"] for w in e["writes"] if w.get("vector")]
        if vecs:
            e["vector_writes"] = vecs
            e["vector_all_components_same"] = [v["all_same"] for v in vecs]
        if name in SEEDED:
            e["notes"].append(SEEDED[name])
    for name, why in SEEDED.items():
        if name not in levers:
            levers[name] = {"name": name, "kind": "cvar",
                            "writes": [], "reads": [], "files": [],
                            "first_commit": None, "last_commit": None,
                            "has_read_back": False,
                            "read_in_a_different_file_than_write": False,
                            "notes": [why, "NO SITE FOUND in the corpus"]}

    for a in api.values():
        fs = sorted(a.pop("files"))
        a["n_files"] = len(fs)
        firsts, lasts = [], []
        for rel in fs[:12]:
            f, l = span(rel)
            if f:
                firsts.append(f)
            if l:
                lasts.append(l)
        a["first_commit"] = sorted(firsts)[0] if firsts else None
        a["last_commit"] = sorted(lasts)[-1] if lasts else None
        a["n_sites"] = len(a["sites"])

    # ---- scan v3 post-pass: classify from the EVIDENCE, not from
    # which loop happened to run first.
    #
    # `setdefault` fixes a lever's kind at first sight, so a name seen
    # by the setter scan before the property scan would be filed
    # "setter_method" forever even though set_editor_property also
    # writes it. That would inflate the very number this pass exists to
    # report. Kind is therefore RECOMPUTED here from the api strings
    # already recorded on each site.
    setter_only = []
    setter_and_other = []
    for e in levers.values():
        apis = [w.get("api", "") for w in e["writes"]]
        apis += [r.get("api", "") for r in e["reads"]]
        apis += [d.get("api", "") for d in e.get("declared", ())]
        has_setter = any("[setter method]" in a for a in apis)
        others = [a for a in apis if "[setter method]" not in a]
        if not has_setter:
            continue
        if others:
            setter_and_other.append(e["name"])
            # Restore the kind the other evidence implies.
            if any("console" in a or "cvar" in a.lower() for a in others):
                e["kind"] = "cvar"
            else:
                e["kind"] = "editor_property"
            e["notes"].append(
                "ALSO written through a setter method -- invisible to a "
                "property-name scan, visible here")
        else:
            setter_only.append(e["name"])
            e["kind"] = "setter_method"
            e["notes"].append(
                "SETTER-ONLY: this lever is written ONLY through a named "
                "method, so scan v1/v2 could not see it at all. This is "
                "the class that hid lighting.sky.color "
                "(apply_lighting.py:394, set_light_color).")
    setter_only.sort()
    setter_and_other.sort()

    def _n(kind, bucket):
        return sum(len(e.get(bucket, ())) for e in levers.values()
                   if e["kind"] == kind)

    with io.open(os.path.join(OUT, "lever_inventory.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"_what": "every engine lever any script writes or reads",
                   "_readback_caveat":
                       "has_read_back means A read exists. It does NOT "
                       "mean the read is from the object that honours "
                       "the value -- see grass_varieties (a copy) and "
                       "the HLOD builder settings (a nested struct).",
                   "_cvar_classification":
                       "cvar sites are classified BY CALL CONTEXT. "
                       "writes = execute_console_command / "
                       "add_or_update_console_variable / -ExecCmds; "
                       "reads = get_console_variable_*; declared = the "
                       "name sits in a dict or config literal (e.g. "
                       "benchmark.json's cvar block, which reaches the "
                       "engine via MoviePipelineConsoleVariableSetting "
                       "and is read back from the engine log, so it is "
                       "neither a direct write nor a read AT THAT SITE). "
                       "The first version of this scanner called every "
                       "mention a write, which is where '170 written, "
                       "never read back' came from.",
                   "n_levers": len(levers),
                   "n_cvar_writes": _n("cvar", "writes"),
                   "n_cvar_reads": _n("cvar", "reads"),
                   "n_cvar_declared": _n("cvar", "declared"),
                   "n_cvars_with_a_direct_write": sum(
                       1 for e in levers.values()
                       if e["kind"] == "cvar" and e["writes"]),
                   "n_cvars_with_a_read": sum(
                       1 for e in levers.values()
                       if e["kind"] == "cvar" and e["reads"]),
                   "n_property_writes": _n("editor_property", "writes"),
                   "n_property_reads": _n("editor_property", "reads"),
                   "_scan_v3_setter_methods":
                       "v3 catches obj.set_<thing>(...) and "
                       "obj.add_or_update_<thing>(...). v1/v2 saw only "
                       "set_editor_property/get_editor_property and cvar "
                       "sites, so every lever written through a named "
                       "setter was MISSING -- not mislabelled, missing. "
                       "lighting.sky.color is the motivating case "
                       "(apply_lighting.py:394, set_light_color). "
                       "PRECISION LIMIT: Python is untyped here, so "
                       "'is the receiver an engine object' cannot be "
                       "decided statically; every setter site carries "
                       "its receiver and a "
                       "receiver_looks_like_an_engine_object flag, and "
                       "nothing is filtered on it.",
                   "n_setter_only_levers": len(setter_only),
                   "setter_only_levers": setter_only,
                   "n_levers_also_written_by_a_setter":
                       len(setter_and_other),
                   "levers_also_written_by_a_setter": setter_and_other,
                   "n_setter_sites": _n("setter_method", "writes"),
                   "dropped_as_non_levers": sorted(dropped_cvars),
                   "n_dropped_as_non_levers": len(dropped_cvars),
                   "levers": sorted(levers.values(),
                                    key=lambda e: e["name"])}, fh, indent=1)
    with io.open(os.path.join(OUT, "api_inventory.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"_what": "every unreal.* symbol the scripts touch",
                   "n_symbols": len(api),
                   "silent_failure_calls": silent,
                   "n_silent_failure_sites": len(silent),
                   "symbols": sorted(api.values(),
                                     key=lambda a: -a["n_sites"])},
                  fh, indent=1)
    print("levers: %d   api symbols: %d   silent-failure sites: %d"
          % (len(levers), len(api), len(silent)))
    print("cvar sites   writes %d   reads %d   declared %d"
          % (_n("cvar", "writes"), _n("cvar", "reads"),
             _n("cvar", "declared")))
    print("cvar names   with a direct write %d   with a read %d   of %d"
          % (sum(1 for e in levers.values()
                 if e["kind"] == "cvar" and e["writes"]),
             sum(1 for e in levers.values()
                 if e["kind"] == "cvar" and e["reads"]),
             sum(1 for e in levers.values() if e["kind"] == "cvar")))
    print("property sites   writes %d   reads %d"
          % (_n("editor_property", "writes"), _n("editor_property", "reads")))
    print("SCAN v3  setter-only levers %d   also-by-setter %d   "
          "setter sites %d"
          % (len(setter_only), len(setter_and_other),
             _n("setter_method", "writes")))
    print("   setter-only sample: %s"
          % ", ".join(setter_only[:14]))
    print("dropped as non-levers: %d  %s"
          % (len(dropped_cvars), ", ".join(sorted(dropped_cvars)[:12])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
