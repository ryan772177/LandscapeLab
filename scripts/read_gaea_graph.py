"""read_gaea_graph.py — what does the Gaea project actually COMPUTE?

READ-ONLY. Opens a Gaea 2 `.terrain` file and reports the node graph:
dimensions, every node with its TOP-LEVEL parameters (a node's `Modifiers`
list is treated as structure and NOT expanded), the wiring, and which nodes
export files. Nothing is written.

WHY THIS EXISTS
---------------
The terrain this entire project rests on was, until now, a BINARY BLOB as
far as the repo was concerned — "what does AlpineLab_v1 compute?" could
only be answered by opening Gaea and looking. That makes the single most
upstream input in the pipeline the one thing that cannot be reviewed,
diffed, or checked in CI.

It turns out `.terrain` is plain JSON (Newtonsoft, with `$id`/`$ref`
object graphs), so none of that opacity was necessary.

THE THREE THINGS IT IS FOR
--------------------------
1. PROVENANCE. The graph is 6 nodes; now they are printable, diffable,
   and quotable in a recipe.

2. THE `Height` TRAP, MADE MACHINE-READABLE. R-GAEA records that Gaea's
   declared `Terrain/Height` is the PROJECT range, NOT the span the build
   occupies — reading it as the span makes a landscape 2.7x too tall and
   entirely plausible. That number is right here in the JSON, and this
   tool prints it WITH the warning attached, so the trap arrives with its
   own antidote instead of as a bare figure someone can misuse.

3. A GATE THAT DID NOT EXIST. The Gaea graph declares which files it
   exports (`SaveDefinition`), and `verify_build.SPEC` declares which
   files the package must contain. THOSE ARE TWO LISTS THAT MUST AGREE
   and nothing compared them (NN24). Disable a save node in the Gaea GUI
   and the next build silently omits a map; verify_build then refuses
   with "missing file", which is true but points at the package instead
   of at the cause. `--check-spec` compares them directly.

WHAT THIS TOOL DELIBERATELY DOES NOT DO
---------------------------------------
It does not WRITE. The file carries 23 `$ref` back-references — Newtonsoft
object cycles, e.g. every Port's `Parent` pointing at its node by id. That
makes the safe editing envelope narrow and worth stating before anyone
assumes it is wide:

  * CHANGING A PARAMETER VALUE is safe. No id is created or destroyed, so
    every `$ref` still resolves.
  * ADDING OR REMOVING A NODE IS NOT SAFE without id-allocation logic.
    `$id` values are assigned in document order and `$ref` points at them
    by number; inserting a node means either appending ids carefully or
    renumbering, and getting it wrong produces a file that still parses
    as JSON and is a different graph — or no graph.

So `--check-refs` exists now: it proves every `$ref` resolves to a real
`$id`. That is the acceptance test any future writer has to pass, and it
is available before the writer is written rather than after.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bootstrap        # noqa: E402
import verify_build     # noqa: E402  -- the declared package SPEC

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_PROJECT = (r"C:\Dev\LandscapeLab\TerrainData\AlpineLab_v1"
                   r"\AlpineLabe_v1.terrain")

# Parameters are everything that is not structure. Listed once so the
# report cannot drift from what it claims to be showing.
_STRUCTURAL = {"$id", "$type", "Id", "Name", "Position", "Ports",
               "Modifiers", "NodeSize", "Version", "SaveDefinition"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def terrain_of(doc):
    return doc["Assets"]["$values"][0]["Terrain"]


def nodes_of(terrain):
    return {k: v for k, v in terrain["Nodes"].items() if k != "$id"}


def short_type(node):
    return str(node.get("$type", "?")).split(",")[0].split(".")[-1]


def collect_ids_and_refs(obj, ids, refs):
    """Every `$id` defined and every `$ref` used, anywhere in the tree."""
    if isinstance(obj, dict):
        if "$id" in obj:
            ids.add(str(obj["$id"]))
        if "$ref" in obj:
            refs.append(str(obj["$ref"]))
        for v in obj.values():
            collect_ids_and_refs(v, ids, refs)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids_and_refs(v, ids, refs)


def edges_of(nodes):
    """(from_node, from_port, to_node, to_port, is_valid) for every wired
    input (is_valid is bool(Record.IsValid))."""
    out = []
    for _k, n in nodes.items():
        ports = (n.get("Ports") or {}).get("$values") or []
        for p in ports:
            rec = p.get("Record")
            if not isinstance(rec, dict):
                continue
            out.append((rec.get("From"), rec.get("FromPort"),
                        rec.get("To"), rec.get("ToPort"),
                        bool(rec.get("IsValid"))))
    return out


def saves_of(nodes):
    """filename -> (node id, node name, format, enabled)."""
    out = {}
    for k, n in nodes.items():
        sd = n.get("SaveDefinition")
        if not isinstance(sd, dict):
            continue
        out[str(sd.get("Filename"))] = (k, n.get("Name"),
                                        sd.get("Format"),
                                        bool(sd.get("IsEnabled")))
    return out


def predicted_files(nodes):
    """Filenames a build of this graph will actually emit.

    THE RULE, DERIVED FROM THE DATA AND CONTROLLED AGAINST A REAL BUILD --
    not guessed, because the first version of this check guessed and was
    WRONG in the dangerous direction.

    A `SaveDefinition` carries a BASE name, not a filename. Gaea emits one
    file per EXPORTING OUTPUT PORT, named `{base}_{PortName}.png`:

        port Type contains "Out"   ("Out" or "PrimaryOut")
        AND IsExporting is True

    Both halves are load-bearing, and each is what excludes a real case:
      * Erosion2's `Out` is PrimaryOut with IsExporting None -> excluded,
        which is why there is no Erosion2_Out.png;
      * Snow's `Out` IS PrimaryOut with IsExporting True -> INCLUDED,
        which is why Snow_Out.png exists. So "skip PrimaryOut" would have
        been a plausible rule and a wrong one.
      * Snow's `Hard` and `Depth` are Out with IsExporting None -> excluded.
      * The `In` ports also carry IsExporting True, which is why the Type
        test cannot be dropped.

    Predicts exactly the 6 files build 006 produced.

    WHY THE FIRST VERSION WAS WORTH LOGGING: it compared the three BASE
    names against the SPEC's six FILENAMES and refused, reporting that the
    Gaea graph was missing five required exports. The graph was correct
    and the gate was wrong -- and the refusal was confident enough to send
    someone editing a terrain project that had nothing wrong with it. A
    gate that refuses good input is not a safe failure (NN2).
    """
    out = {}
    for k, n in nodes.items():
        sd = n.get("SaveDefinition")
        if not isinstance(sd, dict):
            continue
        base = str(sd.get("Filename"))
        enabled = bool(sd.get("IsEnabled"))
        for p in (n.get("Ports") or {}).get("$values") or []:
            if "Out" not in str(p.get("Type") or ""):
                continue
            if p.get("IsExporting") is not True:
                continue
            out["{0}_{1}.png".format(base, p.get("Name"))] = (
                k, n.get("Name"), sd.get("Format"), enabled)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--check-refs", action="store_true",
                    help="prove every $ref resolves to a real $id")
    ap.add_argument("--check-spec", action="store_true",
                    help="compare the graph's exported filenames against "
                         "verify_build.SPEC")
    ap.add_argument("--against-build", default=None, metavar="DIR",
                    help="POSITIVE CONTROL: compare the filenames predicted "
                         "from the graph against a build that actually "
                         "happened. A prediction rule never checked against "
                         "an artefact is a story about port names.")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable summary")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.project):
        print("REFUSE: no such project file: {0}".format(args.project))
        return 2
    doc = load(args.project)
    try:
        t = terrain_of(doc)
        nodes = nodes_of(t)
    except (KeyError, IndexError, TypeError) as exc:
        print("REFUSE: {0} is not a readable Gaea graph ({1}: {2}).".format(
            args.project, type(exc).__name__, exc))
        return 2
    if not nodes:
        # NN13: zero nodes is not a graph to report on -- refuse rather than
        # print "NODES (0)" and exit 0 as though an empty file were valid.
        print("REFUSE: 0 nodes parsed -- not a Gaea graph (or an empty one).")
        return 2
    saves = saves_of(nodes)

    if args.json:
        print(json.dumps({
            "project": args.project,
            "width": t.get("Width"), "height": t.get("Height"),
            "ratio": t.get("Ratio"),
            "nodes": {k: {"type": short_type(n), "name": n.get("Name"),
                          "params": {kk: vv for kk, vv in n.items()
                                     if kk not in _STRUCTURAL}}
                      for k, n in nodes.items()},
            "saves": saves,
        }, indent=2))
        return 0

    print("project : {0}".format(args.project))
    print("bytes   : {0}".format(os.path.getsize(args.project)))
    print("")
    print("DECLARED EXTENT")
    print("  Width  {0}   Height {1}   Ratio {2}".format(
        t.get("Width"), t.get("Height"), t.get("Ratio")))
    print("")
    print("  !! `Height` IS THE PROJECT RANGE, NOT THIS BUILD'S SPAN.")
    print("     Reading it as the span is how a landscape ends up 2.7x too")
    print("     tall and entirely plausible (R-GAEA). The SPAN comes from")
    print("     the exported height's occupancy, recorded by")
    print("     rebuild_terrain.py in height_normalization.json.")
    print("")
    print("  !! `Width` is the extent the graph was AUTHORED at. It is")
    print("     independent of export resolution and of the UE landscape")
    print("     size, so a mismatch is not an error -- but erosion")
    print("     parameters were tuned against THIS width, and importing")
    print("     at a different one stretches those features.")
    print("")

    print("NODES ({0})".format(len(nodes)))
    for k, n in sorted(nodes.items(), key=lambda kv: int(kv[0])):
        params = {kk: vv for kk, vv in n.items() if kk not in _STRUCTURAL}
        print("  [{0:>4}] {1:<12} name={2!r}".format(
            k, short_type(n), n.get("Name")))
        if params:
            for pk in sorted(params):
                print("           {0:<18} {1}".format(pk, params[pk]))
    print("")

    print("WIRING")
    ed = edges_of(nodes)
    if not ed:
        print("  (no wired inputs found)")
    for frm, fport, to, tport, valid in ed:
        name_of = {int(k): n.get("Name") for k, n in nodes.items()}
        print("  {0} ({1}).{2}  ->  {3} ({4}).{5}{6}".format(
            frm, name_of.get(frm), fport, to, name_of.get(to), tport,
            "" if valid else "   [MARKED INVALID]"))
    print("")

    print("EXPORTS ({0})".format(len(saves)))
    print("  (save-node BASE names; Gaea emits {base}_{Port}.png -- see")
    print("   predicted_files / --against-build for the actual filenames)")
    for fn, (nid, nm, fmt, enabled) in sorted(saves.items()):
        print("  {0:<16} <- node {1} ({2}), {3}{4}".format(
            fn, nid, nm, fmt, "" if enabled else "   [DISABLED]"))
    print("")

    rc = 0

    if args.check_refs:
        ids, refs = set(), []
        collect_ids_and_refs(doc, ids, refs)
        dangling = sorted({r for r in refs if r not in ids})
        print("REFERENCE INTEGRITY")
        print("  $id defined : {0}".format(len(ids)))
        print("  $ref used   : {0}".format(len(refs)))
        if not refs:
            # NN13: "every $ref resolves" is vacuously true over zero refs.
            # A Gaea graph is a Newtonsoft object graph and carries back-refs;
            # zero means this is not that file, not that integrity is proven.
            print("  REFUSE: 0 $ref found -- expected a Newtonsoft object "
                  "graph with back-references. Integrity is not PROVEN, it "
                  "is UNTESTED.")
            rc = max(rc, 3)
        elif dangling:
            print("  DANGLING    : {0}".format(", ".join(dangling)))
            print("  REFUSE: this graph has references to ids that do not "
                  "exist. It may still open, as a DIFFERENT graph.")
            rc = max(rc, 3)
        else:
            print("  every $ref resolves to a real $id.")
            print("  (This is the acceptance test any future WRITER must "
                  "pass. Parameter edits preserve it by construction; "
                  "adding or removing nodes does not.)")
        print("")

    if args.check_spec:
        # NN24: the graph says what it will EXPORT, verify_build says what
        # the package must CONTAIN. Two lists that must agree, and nothing
        # compared them until now.
        pred = predicted_files(nodes)
        want = set(verify_build.SPEC)
        # The normalized height and its alias are produced DOWNSTREAM by
        # rebuild_terrain from Gaea's Snow_Out, not exported by Gaea, so
        # they are correctly absent from the graph's prediction.
        derived = set(verify_build.ALIASES) | set(
            verify_build.ALIASES.values())
        expected_from_gaea = want - derived
        got_enabled = {fn for fn, (_i, _n, _f, en) in pred.items() if en}
        got_disabled = {fn for fn, (_i, _n, _f, en) in pred.items()
                        if not en}

        print("PREDICTED BUILD OUTPUT vs verify_build.SPEC")
        print("  (predicted = one file per exporting output port, "
              "{base}_{Port}.png)")
        for fn in sorted(expected_from_gaea):
            mark = "ok" if fn in got_enabled else (
                "SAVE NODE DISABLED" if fn in got_disabled
                else "NOT EXPORTED BY THE GRAPH")
            print("  {0:<40} {1}".format(fn, mark))
        # verify_build already declares which Gaea outputs are legitimately
        # NOT part of the package -- Snow_Out.png, the un-normalized height
        # that the normalized copy supersedes. Read that declaration rather
        # than inventing a second list here (NN24).
        excluded = set(verify_build.EXCLUDED)
        extra = sorted(got_enabled - want - excluded)
        for fn in sorted(got_enabled & excluded):
            print("  {0:<40} {1}".format(
                fn, "excluded by design: " + verify_build.EXCLUDED[fn][:44]))
        if extra:
            print("  predicted but not in SPEC: {0}".format(", ".join(extra)))
        print("")
        print("  derived downstream, not from Gaea: {0}".format(
            ", ".join(sorted(derived))))
        missing = sorted(expected_from_gaea - got_enabled)
        if missing or extra:
            print("")
            print("  REFUSE: the graph and the package SPEC disagree. "
                  "missing={0} extra={1}. A build from this project would "
                  "not match what verify_build requires, and the cause is "
                  "HERE rather than in the package."
                  .format(missing, extra))
            rc = 4
        else:
            print("  the graph predicts exactly the SPEC's Gaea-sourced "
                  "files.")
        print("")

    if args.against_build:
        # THE POSITIVE CONTROL. Predicting filenames from a graph is only
        # worth anything if the prediction is checked against a build that
        # actually happened -- otherwise the rule is just a story about
        # port names. Build 006 is 8192 and produced 6 files.
        pred = set(predicted_files(nodes))
        d = args.against_build
        if not os.path.isdir(d):
            print("COULD NOT LOOK: no such build directory: {0}".format(d))
            rc = max(rc, 5)
        else:
            actual = {f for f in os.listdir(d) if f.lower().endswith(".png")}
            # EXCLUDED outputs are MOVED to _archive/ by the resize step,
            # so a build that has been resized no longer has them at top
            # level. They were still emitted; look where they went, or the
            # control reports a correct prediction as a miss.
            arch = os.path.join(d, "_archive")
            if os.path.isdir(arch):
                actual |= {f for f in os.listdir(arch)
                           if f.lower().endswith(".png")}
            derived = set(verify_build.ALIASES) | set(
                verify_build.ALIASES.values())
            actual_gaea = actual - derived
            print("PREDICTION vs AN ACTUAL BUILD  ({0})".format(d))
            print("  predicted : {0}".format(len(pred)))
            print("  on disk   : {0}  (excluding {1} derived)".format(
                len(actual_gaea), len(actual & derived)))
            miss = sorted(pred - actual_gaea)
            unex = sorted(actual_gaea - pred)
            for fn in sorted(pred | actual_gaea):
                mark = ("ok" if fn in pred and fn in actual_gaea
                        else "PREDICTED, ABSENT" if fn in pred
                        else "ON DISK, NOT PREDICTED")
                print("    {0:<40} {1}".format(fn, mark))
            if not pred and not actual_gaea:
                # NN13: 0 predicted vs 0 on disk is not agreement -- a
                # positive control over an empty set proves nothing.
                print("  REFUSE: nothing to compare (0 predicted, 0 Gaea PNGs "
                      "on disk). A positive control over an empty set proves "
                      "nothing.")
                rc = max(rc, 6)
            elif miss or unex:
                print("  REFUSE: the export rule does not reproduce this "
                      "build. missing={0} unexpected={1}".format(miss, unex))
                rc = max(rc, 6)
            else:
                print("  THE RULE REPRODUCES THIS BUILD EXACTLY.")
            print("")

    print("READ-ONLY: nothing was written.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
