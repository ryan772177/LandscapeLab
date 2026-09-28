"""landscape_inventory.py — full actor-by-actor landscape census.

READ-ONLY. Diagnostic only: it reads and prints, and mutates nothing. No
actor is spawned, moved, renamed, deleted, or saved. Conduct rule 7
applies in full and is delegated to bootstrap.py's audited gate, so
nothing reaches a node that has not matched UE_PROJECT_ROOT.

WHY THIS EXISTS
`verify_landscape.py` answers one question — does the recipe's landscape
match the recipe — and refuses when the level holds more than one
landscape. It deliberately does not describe what else is there. When
two landscapes exist and it is not obvious which is which, deleting the
wrong one is unrecoverable, so the decision needs a full census first.

This script makes no judgement about which actor should survive. It
reports what is there and lets Ryan rule.

WHAT IT REPORTS, per actor
  - label and class (Landscape vs LandscapeStreamingProxy)
  - world transform: location, rotation, scale
  - component count actually attached to that actor
  - owning landscape, for proxies: LandscapeActorRef first
    (UPROPERTY(EditAnywhere), reliably readable), LandscapeGuid second
    (bare UPROPERTY, may be refused)
  - derived geometry where components allow it: section base extents,
    component spacing, implied overall resolution
  - the direct geometry properties where the engine permits reading them

A NOTE ON COMPLETENESS
Only LOADED actors are enumerable. With World Partition regions
unloaded, counts undershoot. The script reports what it saw and says so;
it does not present a partial census as complete.

Exit codes:
  0  census printed
  1  unexpected error / bad arguments
  3  editor identity gate refused (conduct rule 7)
  6  the probe returned nothing

Unreal APIs used (all long-stable for UE5; nothing 5.8-only):
  unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world
  unreal.GameplayStatics.get_all_actors_of_class
  unreal.Landscape / unreal.LandscapeStreamingProxy / unreal.LandscapeComponent
  Actor.get_actor_label / get_actor_location / get_actor_rotation
  Actor.get_actor_scale3d / get_components_by_class / get_editor_property
  Object.get_package (UE 5.0+, OFPA-aware) / get_outermost (fallback;
    outer-chain = map package) / get_path_name / is_package_external
    — all const accessors, all guarded, none 5.8-only
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402 — audited rule 7 gate
import verify_landscape   # noqa: E402 — shared node selection

REPO_ROOT = bootstrap.REPO_ROOT
PROBE_MARKER = "__LANDSCAPELAB_INVENTORY__"

# Set from --match-package. Read by _report to resolve an OFPA package
# name back to its owning actor.
MATCH_PACKAGE = ""

PROBE = '''
import json as _json
import unreal as _unreal

_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

_rows = []
_notes = []


def _describe(_a, _kind):
    _row = {{"label": _a.get_actor_label(), "kind": _kind}}
    try:
        _loc = _a.get_actor_location()
        _rot = _a.get_actor_rotation()
        _scl = _a.get_actor_scale3d()
        _row["location"] = [_loc.x, _loc.y, _loc.z]
        _row["rotation"] = [_rot.pitch, _rot.yaw, _rot.roll]
        _row["scale"] = [_scl.x, _scl.y, _scl.z]
    except Exception as _exc:
        _row["transform_error"] = "%s: %s" % (type(_exc).__name__, _exc)

    # Owning landscape. LandscapeActorRef is EditAnywhere and reliable;
    # LandscapeGuid is a bare UPROPERTY and may be refused.
    # LESSON 9. An inventory exists to make CLAIMS ABOUT THE WORLD, so
    # every "unknown" it prints has to say which kind of unknown it is:
    # "this proxy has no owner" and "I could not find out who owns it"
    # are different facts, and the triage principle only tolerates a
    # degraded field when the degradation is REPORTED. `pass` reported
    # nothing, so an unreadable ref and an absent ref rendered
    # identically.
    _row["owner_label"] = None
    _row["owner_source"] = None
    _row["owner_error"] = None
    try:
        _ref = _a.get_editor_property("landscape_actor_ref")
        if _ref is not None:
            _row["owner_label"] = _ref.get_actor_label()
            _row["owner_source"] = "landscape_actor_ref"
        else:
            _row["owner_source"] = "absent"
    except Exception as _exc:
        _row["owner_source"] = "unreadable"
        _row["owner_error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _row["guid_error"] = None
    try:
        _guid = _a.get_editor_property("landscape_guid")
        _row["guid"] = str(_guid)
        if _row["owner_source"] in (None, "absent"):
            _row["owner_source"] = "guid_only"
    except Exception as _exc:
        # A bare UPROPERTY refusal is EXPECTED here and is not a fault —
        # but it is still "I could not look", so it is recorded as such
        # rather than as a guid that is not there.
        _row["guid"] = None
        _row["guid_error"] = "%s: %s" % (type(_exc).__name__, _exc)

    # Owning PACKAGE. Under One File Per Actor each actor lives in its
    # own external package, which is what the dirty-package list reports
    # (/Game/__ExternalActors__/<map>/<x>/<y>/<hash>). Mapping actor ->
    # package is the only way to turn a hashed dirty-package name back
    # into something a human can act on.
    # ORDER MATTERS (audit finding F1): get_package() honours external
    # (OFPA) packages and returns the /Game/__ExternalActors__/... name;
    # get_outermost() walks the outer chain (Actor -> Level -> World)
    # and returns the MAP package, which for an externally-packaged
    # actor can NEVER match a dirty OFPA package name. get_package must
    # be tried first; get_outermost is a fallback only, and which one
    # answered is recorded so the report can caveat fallback values.
    _row["package"] = None
    _row["package_source"] = None
    _row["package_errors"] = []
    for _getter in ("get_package", "get_outermost"):
        try:
            _fn = getattr(_a, _getter, None)
            if _fn is None:
                _row["package_errors"].append(
                    "%s: not present on this object" % _getter)
                continue
            _pkg = _fn()
            if _pkg is not None:
                _row["package"] = _pkg.get_name()
                _row["package_source"] = _getter
                break
            _row["package_errors"].append("%s: returned None" % _getter)
        except Exception as _exc:
            # LESSON 9 again, and this one gated a DELETION lookup once
            # (lesson 2.1: get_outermost returns the MAP package where
            # get_package returns the actor's own, and the wrong one
            # guarantees a false "no match"). `continue` made "both
            # getters raised" look exactly like "this actor has no
            # package".
            _row["package_errors"].append(
                "%s: %s: %s" % (_getter, type(_exc).__name__, _exc))
            continue
    try:
        _row["package_is_external"] = bool(_a.is_package_external())
    except Exception:
        _row["package_is_external"] = None
    try:
        _row["object_path"] = _a.get_path_name()
    except Exception:
        _row["object_path"] = None

    _comps = []
    try:
        _comps = _a.get_components_by_class(_unreal.LandscapeComponent)
    except Exception as _exc:
        _row["component_error"] = "%s: %s" % (type(_exc).__name__, _exc)
    _row["component_count"] = len(_comps)

    _bx, _by = set(), set()
    _num_sub, _sub_quads, _comp_quads = set(), set(), set()
    _unreadable = []
    for _c in _comps:
        try:
            _bx.add(int(_c.get_editor_property("section_base_x")))
            _by.add(int(_c.get_editor_property("section_base_y")))
        except Exception:
            if "section_base" not in _unreadable:
                _unreadable.append("section_base")
        for _prop, _sink in (("num_subsections", _num_sub),
                             ("subsection_size_quads", _sub_quads),
                             ("component_size_quads", _comp_quads)):
            try:
                _sink.add(int(_c.get_editor_property(_prop)))
            except Exception:
                if _prop not in _unreadable:
                    _unreadable.append(_prop)

    _row["section_base_x"] = sorted(_bx)
    _row["section_base_y"] = sorted(_by)
    _row["num_subsections"] = sorted(_num_sub)
    _row["subsection_size_quads"] = sorted(_sub_quads)
    _row["component_size_quads"] = sorted(_comp_quads)
    _row["unreadable"] = _unreadable
    return _row


for _a in _unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.Landscape):
    _rows.append(_describe(_a, "Landscape"))

try:
    for _p in _unreal.GameplayStatics.get_all_actors_of_class(
            _world, _unreal.LandscapeStreamingProxy):
        _rows.append(_describe(_p, "StreamingProxy"))
except Exception as _exc:
    _notes.append("proxy enumeration failed: %s: %s" % (
        type(_exc).__name__, _exc))

print("{marker}" + _json.dumps({{"rows": _rows, "notes": _notes}}))
'''.format(marker=PROBE_MARKER)


def _parse(text):
    idx = text.find(PROBE_MARKER)
    if idx < 0:
        return None
    tail = text[idx + len(PROBE_MARKER):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run(remote_exec, remote, node_id):
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(PROBE, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  probe did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse(bootstrap._collect_output(result))
    except Exception as exc:
        print("  probe errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _v(values, fmt="{0:.1f}"):
    if not values:
        return "?"
    return "[" + ", ".join(fmt.format(v) for v in values) + "]"


def _span(bases):
    if not bases or len(bases) < 2:
        return None
    steps = {bases[i + 1] - bases[i] for i in range(len(bases) - 1)}
    if len(steps) != 1:
        return None
    return steps.pop()


def _report(payload):
    rows = payload.get("rows") or []
    landscapes = [r for r in rows if r["kind"] == "Landscape"]
    proxies = [r for r in rows if r["kind"] == "StreamingProxy"]

    print("=" * 74)
    print("LANDSCAPE CENSUS — {0} Landscape, {1} StreamingProxy "
          "(loaded actors only)".format(len(landscapes), len(proxies)))
    print("=" * 74)
    for note in payload.get("notes") or []:
        print("  NOTE: {0}".format(note))

    labels = [r["label"] for r in landscapes]
    if len(set(labels)) != len(labels):
        print("  WARNING: two or more Landscape actors share a label. The")
        print("  per-landscape proxy attribution below matches on label and")
        print("  MERGES them — those sections cannot be trusted. Distinguish")
        print("  the actors by guid before deleting anything.")

    for row in landscapes:
        print("")
        print("-" * 74)
        print("LANDSCAPE  {0!r}".format(row["label"]))
        print("-" * 74)
        print("  package         {0}{1}".format(
            row.get("package") or "?",
            "  (via {0})".format(row["package_source"])
            if row.get("package_source") else ""))
        print("  location        {0}".format(_v(row.get("location"))))
        print("  rotation        {0}".format(_v(row.get("rotation"))))
        print("  scale           {0}".format(_v(row.get("scale"), "{0:.4g}")))
        print("  guid            {0}".format(row.get("guid") or "unreadable"))
        if row.get("transform_error"):
            print("  WARNING: transform read failed: {0}".format(
                row["transform_error"]))
        print("  components ON this actor   {0}".format(
            row.get("component_count")))

        owned = [p for p in proxies if p.get("owner_label") == row["label"]]
        total = row.get("component_count", 0) + sum(
            p.get("component_count", 0) for p in owned)
        print("  streaming proxies owned    {0}".format(len(owned)))
        print("  components across all      {0}".format(total))
        failed = [p["label"] for p in [row] + owned
                  if p.get("component_error")]
        if failed:
            print("  WARNING: component reads FAILED on {0} actor(s); the "
                  "component counts above UNDERCOUNT: {1}".format(
                      len(failed), ", ".join(repr(f) for f in failed)))

        bx = sorted({b for p in owned for b in (p.get("section_base_x") or [])}
                    | set(row.get("section_base_x") or []))
        by = sorted({b for p in owned for b in (p.get("section_base_y") or [])}
                    | set(row.get("section_base_y") or []))
        step_x, step_y = _span(bx), _span(by)
        if bx:
            print("  section base X  {0} distinct, {1}..{2}, step {3}".format(
                len(bx), bx[0], bx[-1],
                step_x if step_x else
                ("n/a (single value)" if len(bx) < 2 else "NON-UNIFORM")))
        if by:
            print("  section base Y  {0} distinct, {1}..{2}, step {3}".format(
                len(by), by[0], by[-1],
                step_y if step_y else
                ("n/a (single value)" if len(by) < 2 else "NON-UNIFORM")))
        if bx and step_x:
            print("  implied resolution         {0}".format(
                bx[-1] - bx[0] + step_x + 1))

        merged = {}
        for key in ("num_subsections", "subsection_size_quads",
                    "component_size_quads"):
            vals = sorted({v for p in owned for v in (p.get(key) or [])}
                          | set(row.get(key) or []))
            merged[key] = vals
            print("  {0:<26} {1}".format(
                key, vals if vals else "unreadable"))

        unread = sorted({u for p in owned for u in (p.get("unreadable") or [])}
                        | set(row.get("unreadable") or []))
        if unread:
            print("  engine refused reads       {0}".format(
                ", ".join(unread)))

    # Split by WHY the owner is unknown. "This proxy has no owner" and
    # "I could not find out who owns it" are different facts about the
    # world, and only the first is a statement about the scene — the
    # second is a statement about the probe (lesson 9). Reported apart
    # so a reader cannot merge them, because the merged number is what
    # a deletion checklist would be built from.
    absent = [p for p in proxies
              if not p.get("owner_label")
              and p.get("owner_source") not in ("unreadable",)]
    unreadable_owner = [p for p in proxies
                        if p.get("owner_source") == "unreadable"]
    if absent:
        print("")
        print("-" * 74)
        print("PROXIES WITH NO OWNER  ({0})  — looked, and there is none"
              .format(len(absent)))
        print("-" * 74)
        for p in absent[:20]:
            print("  {0!r}  components {1}  location {2}".format(
                p["label"], p.get("component_count"), _v(p.get("location"))))
        if len(absent) > 20:
            print("  ... and {0} more".format(len(absent) - 20))
    if unreadable_owner:
        print("")
        print("-" * 74)
        print("PROXIES WHOSE OWNER COULD NOT BE READ  ({0})  — this is NOT "
              "'no owner'".format(len(unreadable_owner)))
        print("-" * 74)
        for p in unreadable_owner[:20]:
            print("  {0!r}  components {1}".format(
                p["label"], p.get("component_count")))
            print("     {0}".format(p.get("owner_error")))
        if len(unreadable_owner) > 20:
            print("  ... and {0} more".format(len(unreadable_owner) - 20))
        print("  Do not build a deletion list from this section. An "
              "unattributed proxy may belong to a landscape you intend to "
              "KEEP.")

    pkg_failed = [p for p in (proxies + landscapes)
                  if not p.get("package") and p.get("package_errors")]
    if pkg_failed:
        print("")
        print("-" * 74)
        print("ACTORS WHOSE PACKAGE COULD NOT BE RESOLVED  ({0})".format(
            len(pkg_failed)))
        print("-" * 74)
        for p in pkg_failed[:10]:
            print("  {0!r}".format(p.get("label")))
            for err in p.get("package_errors") or []:
                print("     {0}".format(err))
        print("  Under OFPA the package name is the only link from a dirty-"
              "package hash back to an actor; without it, that actor cannot "
              "be matched to a save.")

    # Full per-owner proxy label listing. This is the deletion checklist:
    # removing a landscape means removing its proxies, and picking them
    # out of an Outliner with 68 similarly-named actors needs the exact
    # labels, not a count.
    print("")
    print("=" * 74)
    print("PROXY LABELS BY OWNER — deletion checklist")
    print("=" * 74)
    print("  INCOMPLETE IF REGIONS ARE UNLOADED: only loaded proxies are")
    print("  listed. Load every World Partition region before deleting, or")
    print("  a doomed landscape's unloaded proxies will survive it.")
    by_owner = {}
    for p in proxies:
        by_owner.setdefault(p.get("owner_label") or "<unreadable>",
                            []).append(p)
    for owner in sorted(by_owner, key=lambda k: -len(by_owner[k])):
        group = sorted(by_owner[owner], key=lambda r: r["label"])
        print("")
        print("  owner {0!r} — {1} proxies:".format(owner, len(group)))
        for p in group:
            # repr, not bare: this is a deletion checklist, and invisible
            # whitespace in a label must be visible before anything is
            # deleted against it.
            print("    {0!r:<52} {1} comps".format(
                p["label"], p.get("component_count")))
            print("      pkg {0}".format(p.get("package") or "?"))

    # Package -> actor lookup. The dirty-package list reports hashed OFPA
    # package names with no actor identity; this resolves one back to the
    # actor that owns it, and to that actor's landscape if it is a proxy.
    if MATCH_PACKAGE:
        needle = MATCH_PACKAGE.replace("\\", "/").rsplit("/", 1)[-1]
        needle = needle.rsplit(".", 1)[0].upper()
        print("")
        print("=" * 74)
        print("PACKAGE LOOKUP — {0}".format(MATCH_PACKAGE))
        print("=" * 74)
        resolved = [r for r in rows if r.get("package")]
        # Actors whose package came from the get_outermost fallback and
        # are (or may be) externally packaged: their reported package is
        # the MAP package and structurally cannot match an OFPA name.
        outer_only = [r for r in resolved
                      if r.get("package_source") == "get_outermost"
                      and r.get("package_is_external") is not False]
        if not needle:
            print("  UNUSABLE QUERY: --match-package reduced to an empty")
            print("  package name (trailing slash?). No matching was")
            print("  attempted — nothing matches an empty name.")
        elif not resolved:
            print("  PACKAGE UNREADABLE ON ALL {0} LOADED LANDSCAPE".format(
                len(rows)))
            print("  ACTORS: neither get_package nor get_outermost")
            print("  answered on any of them. This is NOT a no-match —")
            print("  it means the lookup could not run at all. Do NOT")
            print("  conclude the dirty package belongs to a")
            print("  non-landscape actor. Stop and resolve the accessor")
            print("  problem first.")
        else:
            hits = [r for r in resolved
                    if needle in (r.get("package") or "").upper()]
            if not hits:
                print("  NO MATCH among {0} loaded landscape actors "
                      "({1} with readable packages).".format(
                          len(rows), len(resolved)))
                print("  The owning actor is either not a landscape actor,")
                print("  or not currently loaded (World Partition).")
                if outer_only:
                    print("  CAUTION: {0} actor(s) reported only their "
                          "outer-chain (map)".format(len(outer_only)))
                    print("  package via get_outermost; that value can NEVER")
                    print("  match an OFPA /Game/__ExternalActors__ name, so")
                    print("  this NO MATCH is NOT conclusive for them.")
            for r in hits:
                print("  label   {0!r}".format(r["label"]))
                print("  class   {0}".format(r["kind"]))
                print("  package {0}  (via {1})".format(
                    r.get("package"), r.get("package_source")))
                print("  path    {0}".format(r.get("object_path")))
                if r["kind"] == "StreamingProxy":
                    print("  OWNING LANDSCAPE: {0!r}".format(
                        r.get("owner_label") or "<unreadable>"))
                    print("  attribution via  : {0}".format(
                        r.get("owner_source") or "none"))

    print("")
    print("=" * 74)
    print("PROXY OWNERSHIP SUMMARY")
    print("=" * 74)
    owners = {}
    for p in proxies:
        owners[p.get("owner_label") or "<unreadable>"] = owners.get(
            p.get("owner_label") or "<unreadable>", 0) + 1
    for label, count in sorted(owners.items(), key=lambda kv: -kv[1]):
        print("  {0!r:<40} {1} proxies".format(label, count))
    print("")
    print("Only LOADED actors are counted. If World Partition regions are")
    print("unloaded, these numbers undershoot the true totals.")
    print("Read-only: nothing was modified.")


def main(argv=None):
    global MATCH_PACKAGE
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--match-package", default="",
                        help="An OFPA package name or path; resolve it "
                             "back to the actor that owns it, and to that "
                             "actor's landscape if it is a proxy.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    MATCH_PACKAGE = args.match_package

    print("REPO_ROOT       : {0}".format(REPO_ROOT))
    print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
    if MATCH_PACKAGE:
        print("Match package   : {0}".format(MATCH_PACKAGE))
    print("")
    print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        print("  VERIFIED: {0}".format(bootstrap._describe(node)))
        print("")

        payload = _run(remote_exec, remote, node["node_id"])
        if payload is None:
            print("FAIL: the census probe returned nothing.")
            return 6
        _report(payload)
        return 0
    finally:
        remote.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as exc:  # surface, never brute-force (conduct rule 6)
        print("ERROR: {0}: {1}".format(type(exc).__name__, exc))
        sys.exit(1)
