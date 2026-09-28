"""verify_landscape.py — the route-B tripwire.

Step 3 of the bracket (LESSONS.md, "Import route"). The landscape
is created by hand, once, from landscape_spec.py's printout. This script
reads the LIVE landscape back and compares it against the same
recipe-derived spec, exiting non-zero on any disagreement.

**Run this at the top of every scene script**, the same way bootstrap.py
guards on UE_PROJECT_ROOT existing. Route B's danger was that a hand-made
landscape becomes undocumented state the recipe does not govern; this is
what converts it into verified state. A fat-fingered dialog entry must
stop everything downstream rather than silently produce a wrong world.

Both ends of the bracket import `derive_spec` from landscape_spec.py, so
the printed spec and the verified spec are the same derivation and cannot
drift.

READ-ONLY against the editor. THREE payloads are sent, all read-only and
all to an already-verified node: bootstrap.py's project-identity probe
(CONFIRM_PROBE), this module's LEVEL_SOURCE (which level is open), and
then one expression reading landscape properties. Nothing is spawned,
modified, or saved, and no file on disk is written.

TWO gates run before the landscape is read, and both fail closed.
Conduct rule 7 — which PROJECT — is delegated to bootstrap.py's audited
gate; nothing reaches a node that has not matched UE_PROJECT_ROOT. The
level gate — which LEVEL — then requires the editor's open level package
to equal the recipe's `landscape.level_path`, and exits 7 without reading
the landscape when it does not. Rule 7 passing says nothing about which
world is open: on 2026-08-01 an unsaved `/Temp/Untitled_1` inside the
correct project made every scene-facing script read the wrong world.

A NOTE ON WHAT UNREAL WILL TELL US
`ULandscapeComponent::SectionBaseX/Y` are UPROPERTY(VisibleAnywhere,
BlueprintReadOnly) (LandscapeComponent.h:436-441) and are reliably
readable. `ComponentSizeQuads`, `SubsectionSizeQuads` and `NumSubsections`
are bare UPROPERTY() (LandscapeComponent.h:444-453) with no Blueprint or
editor flags, so `get_editor_property` may refuse them depending on
build. This script therefore:
  - reads what it can,
  - DERIVES component size and count from SectionBase spacing, which
    needs only the reliably-readable properties,
  - and treats any spec field it could not confirm as a FAILURE, not a
    pass. An unverifiable tripwire is not a tripwire.
If `sections_per_component` proves unreadable, measured spacing determines
(section_size, sections_per_component) UNIQUELY over the dialog-legal
values — the twelve legal spacings are all distinct (D3 ruling (a)) — and
resolved rows are labelled DERIVED in the output. (An older claim here of
a 63x2-vs-126x1 blind spot predated the D3 ruling; Pass 3 2026-09-16.)

Exit codes:
  0  live landscape matches the recipe-derived spec on every field
  1  unexpected error / bad arguments
  2  recipe missing, outside REPO_ROOT, unparseable, or geometrically
     illegal
  3  editor identity gate refused (conduct rule 7)
  4  landscape actor missing, duplicated, or ambiguous
  5  MISMATCH — the live landscape disagrees with the spec
  6  INCOMPLETE — one or more fields could not be read back
  7  LEVEL GATE REFUSED — the editor has a different level open than
     `landscape.level_path`. Distinct from 6 on purpose: "I read the
     wrong world" is not "I could not read a field" (schema v1.2,
     signed off 2026-08-01).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap        # noqa: E402 — audited rule 7 gate, reused
import landscape_spec   # noqa: E402 — shared derivation, single source

REPO_ROOT = bootstrap.REPO_ROOT
DEFAULT_RECIPE = landscape_spec.DEFAULT_RECIPE
PROBE_MARKER = "__LANDSCAPELAB_VERIFY__"

# Scales are floats through a JSON round trip; compare with a tolerance
# rather than for equality. 1e-4 is far tighter than any dialog entry.
TOLERANCE = 1e-4

# World-position checks accumulate transform round-off across actors at
# coordinates up to ~10^5 cm, where 1e-4 would false-alarm on double
# noise. Half a centimetre on an 8 km landscape is unambiguous either way.
POSITION_TOLERANCE_CM = 0.5


def _probe_source(actor_name):
    """Read-only probe. Sent ONLY to an already-verified node.

    World Partition: the engine parcels landscape components onto
    LandscapeStreamingProxy actors rather than the ALandscape itself, so
    the probe enumerates both and unions their components, matching
    proxies to the landscape by LandscapeActorRef first (EditAnywhere,
    reliably readable) and LandscapeGuid second (bare UPROPERTY, may be
    refused). The first run against a real landscape returned
    component_total 0, which is what this resolves (audit finding D1).

    Only LOADED actors are enumerable: with World Partition regions
    unloaded, component_total will undershoot the spec and the run fails
    as a mismatch — or as INCOMPLETE (exit 6) when NOTHING is loaded at
    all: empty section bases cannot be compared, so the total-components
    check is skipped rather than judged. Load the full landscape before
    verifying.

    Inventory is always reported, not only on the not-found path: a
    match says nothing about what else is in the level, and "exactly one
    landscape actor" is part of the contract.
    """
    return '''
import json as _json
import unreal as _unreal

_target = {actor!r}
# UnrealEditorSubsystem is the 5.0+ home of get_editor_world; the old
# EditorLevelLibrary.get_editor_world is deprecated across UE5.
_world = _unreal.get_editor_subsystem(
    _unreal.UnrealEditorSubsystem).get_editor_world()

_out = {{"landscapes": [], "proxies": [], "matching": 0, "found": False}}

_all = list(_unreal.GameplayStatics.get_all_actors_of_class(
    _world, _unreal.Landscape))
for _a in _all:
    _out["landscapes"].append(_a.get_actor_label())

_matches = [_a for _a in _all if _a.get_actor_label() == _target]
_out["matching"] = len(_matches)

_proxies = []
try:
    _proxies = list(_unreal.GameplayStatics.get_all_actors_of_class(
        _world, _unreal.LandscapeStreamingProxy))
except Exception as _exc:
    _out["proxy_lookup_error"] = "{{0}}: {{1}}".format(
        type(_exc).__name__, _exc)
for _p in _proxies:
    _out["proxies"].append(_p.get_actor_label())

if len(_matches) == 1:
    _a = _matches[0]
    _out["found"] = True
    _scale = _a.get_actor_scale3d()
    _loc = _a.get_actor_location()
    _out["scale"] = [_scale.x, _scale.y, _scale.z]
    _out["location"] = [_loc.x, _loc.y, _loc.z]

    _guid = None
    try:
        _guid = _a.get_editor_property("landscape_guid")
    except Exception:
        pass

    # Proxy attribution, strongest key first:
    #   1. LandscapeActorRef — UPROPERTY(EditAnywhere), reliably readable
    #      (LandscapeStreamingProxy.h:35-36); resolves to the ALandscape.
    #   2. LandscapeGuid — bare UPROPERTY(meta=(LandscapeInherited))
    #      (LandscapeProxy.h:480-481); may be refused depending on build.
    #   3. Neither readable: include the proxy so its components are not
    #      silently dropped, but mark attribution unverified — the caller
    #      treats that as INCOMPLETE, never as a pass.
    _sources = [_a]
    _attr_verified = True
    _excluded = 0
    for _p in _proxies:
        _member = None
        try:
            _ref = _p.get_editor_property("landscape_actor_ref")
            if _ref is not None:
                _member = (_ref == _a)
        except Exception:
            _member = None
        if _member is None and _guid is not None:
            try:
                _member = (_p.get_editor_property("landscape_guid") == _guid)
            except Exception:
                _member = None
        if _member is None:
            _sources.append(_p)
            _attr_verified = False
        elif _member:
            _sources.append(_p)
        else:
            _excluded += 1
    _out["proxy_attribution_verified"] = _attr_verified
    _out["proxies_excluded"] = _excluded
    _out["source_actors"] = len(_sources)

    _bases_x, _bases_y = set(), set()
    _num_sub, _sub_quads, _comp_quads = set(), set(), set()
    _unreadable = []
    _total = 0
    _origin_min = [None, None, None]
    _origin_max = [None, None, None]
    for _src in _sources:
        for _c in _src.get_components_by_class(_unreal.LandscapeComponent):
            _total += 1
            _bx = int(_c.get_editor_property("section_base_x"))
            _by = int(_c.get_editor_property("section_base_y"))
            _bases_x.add(_bx)
            _bases_y.add(_by)
            # World-origin cross-check: aligned proxies satisfy
            # proxy_tm = FTransform(SectionBase) * landscape_tm
            # (ULandscapeInfo::FixupProxiesTransform, Landscape.cpp:6164),
            # so component_world - scale * section_base must equal the
            # landscape actor origin for EVERY component.
            try:
                _wl = _c.get_world_location()
                _org = [_wl.x - _scale.x * _bx,
                        _wl.y - _scale.y * _by,
                        _wl.z]
                for _i in range(3):
                    if _origin_min[_i] is None or _org[_i] < _origin_min[_i]:
                        _origin_min[_i] = _org[_i]
                    if _origin_max[_i] is None or _org[_i] > _origin_max[_i]:
                        _origin_max[_i] = _org[_i]
            except Exception:
                if "world_location" not in _unreadable:
                    _unreadable.append("world_location")
            for _prop, _sink in (("num_subsections", _num_sub),
                                 ("subsection_size_quads", _sub_quads),
                                 ("component_size_quads", _comp_quads)):
                try:
                    _sink.add(int(_c.get_editor_property(_prop)))
                except Exception:
                    if _prop not in _unreadable:
                        _unreadable.append(_prop)

    _out["component_total"] = _total
    _out["section_base_x"] = sorted(_bases_x)
    _out["section_base_y"] = sorted(_bases_y)
    _out["num_subsections"] = sorted(_num_sub)
    _out["subsection_size_quads"] = sorted(_sub_quads)
    _out["component_size_quads"] = sorted(_comp_quads)
    _out["implied_origin_min"] = _origin_min
    _out["implied_origin_max"] = _origin_max
    _out["unreadable"] = _unreadable

print("{marker}" + _json.dumps(_out))
'''.format(actor=actor_name, marker=PROBE_MARKER)


LEVEL_MARKER = "__LANDSCAPELAB_LEVEL__"

LEVEL_SOURCE = '''
import json as _json
import unreal as _unreal

# Which LEVEL is open, as opposed to which PROJECT. Conduct rule 7 answers
# the project question; this answers the one that bit us on 2026-08-01,
# when an unsaved /Temp/Untitled_1 was open inside the correct project and
# every scene-facing script was reading the wrong world.
#
# Reported via the world's package rather than its display name: an
# unsaved level's package path begins with /Temp/, which is precisely the
# state that must be refused, and a display name of "Untitled_1" could be
# mistaken for a legitimate map called Untitled_1.
#
# WHICH path name is compared, and why. For a UWorld the outer chain is
# World -> UPackage, and UPackage::GetPathName() returns the package name
# itself ("/Game/Alpine") because a package has no outer to prefix. The
# WORLD's own path name is "/Game/Alpine.Alpine" — object path, not
# package path — and would never equal a recipe level_path, so it is
# reported as a DIAGNOSTIC only and never compared. `outermost` is
# reported alongside for the same reason: for a UWorld it must equal
# `level`, and if it ever does not, the refusal message says so in one
# run instead of costing the conduct-rule-6 attempt budget to bisect.
_out = {{"ok": False, "level": None, "world": None, "outermost": None,
         "error": None}}
try:
    _world = _unreal.get_editor_subsystem(
        _unreal.UnrealEditorSubsystem).get_editor_world()
    if _world is None:
        _out["error"] = "no editor world"
    else:
        try:
            _out["world"] = _world.get_path_name()
        except Exception:
            pass
        try:
            _om = _world.get_outermost()
            _out["outermost"] = (_om.get_path_name()
                                 if _om is not None else None)
        except Exception:
            pass
        # No fallback to the world's own path name: that value can never
        # match a recipe level_path, so substituting it would turn "I
        # could not read the package" into a plain wrong-level refusal
        # and hide the real cause. Absent stays absent.
        _pkg = _world.get_outer()
        _out["level"] = (_pkg.get_path_name() if _pkg is not None
                         else None)
        _out["ok"] = _out["level"] is not None
        # RETAIN NOTHING. MODE_EXEC_FILE payloads run in the PERSISTENT
        # console dicts, so these names stay bound as live globals after
        # this command ends - and a live global is not garbage, so a
        # later gc.collect() cannot free it. On 2026-08-05 the `_world`
        # bound here (an unsaved /Temp/Untitled_1) survived into the
        # map transition in open_level and fataled the editor at
        # EditorServer.cpp:1951, "World Memory Leaks", via
        # FPyReferenceCollector. This probe reports STRINGS; it has no
        # reason to outlive them.
        # NOTE: no file extensions in this payload - a '.p'+'y' substring
        # makes UE treat the whole script as a filename
        # (PythonScriptPlugin.cpp:813-830).
        # Deleted defensively by NAME: `_om` is bound inside an inner
        # try/except above and can legitimately be unbound here, and a
        # NameError raised while tidying up would surface as a failure of
        # the level probe itself.
        for _n in ("_pkg", "_om", "_world"):
            globals().pop(_n, None)
except Exception as _exc:
    _out["error"] = "{{0}}: {{1}}".format(type(_exc).__name__, _exc)

print("{marker}" + _json.dumps(_out))
'''.format(marker=LEVEL_MARKER)


def gate_level(remote_exec, remote, node_id, expected_level, runner):
    """Refuse unless the editor's CURRENT level is `expected_level`.

    Returns (ok, detail). Fails CLOSED: an unreadable level, an absent
    world, or a probe that returns nothing are all refusals, never passes.
    "I could not determine the level" is not "the level is correct" —
    that distinction is the whole point (lesson 2.7).

    `runner` is the caller's own remote-exec function, taking
    (source, marker) — passed in so this does not duplicate connection
    handling that each script already has.

    The EXPECTED value is validated here rather than at the call sites.
    No caller on any gate_level path runs
    import_heightmap._validate_landscape (six callers today — this file,
    capture, apply_lighting, enable_landscape_nanite,
    make_landscape_material, place_foliage — verified 2026-09-16), so without
    this a recipe carrying `"level_path": "/Temp/Untitled_1"` would make
    the gate pass on exactly the world it exists to refuse, and a missing
    key would raise KeyError upstream. A gate that cannot state what
    "correct" is must refuse, not proceed.
    """
    if not isinstance(expected_level, str) or not expected_level:
        return False, (
            "recipe landscape.level_path is missing or not a string "
            "(required since schema v1.2). Nothing can run: there is no "
            "statement of which level is correct, and 'unknown' is never "
            "'yes'.")
    if not expected_level.startswith("/Game/") or expected_level.endswith("/"):
        return False, (
            "recipe landscape.level_path {0!r} is not a content path under "
            "/Game/ without a trailing '/'. A level_path outside /Game/ "
            "(e.g. a /Temp/ path) would make this gate approve the very "
            "state it exists to refuse.".format(expected_level))

    res = runner(LEVEL_SOURCE, LEVEL_MARKER)
    if res is None:
        return False, "the level probe returned nothing"
    if res.get("error"):
        return False, "level unreadable: {0}".format(res["error"])
    live = res.get("level")
    if not live:
        return False, (
            "editor reported no current level — the world's outer package "
            "could not be read (world path {0!r}, outermost {1!r}). That "
            "is 'I could not look', not 'the level is wrong'.".format(
                res.get("world"), res.get("outermost")))
    # `live` is the world's PACKAGE path: "/Game/Alpine" for a saved map,
    # "/Temp/Untitled_1" for an unsaved one. Compared for exact equality
    # against the recipe; the world/outermost paths are diagnostics only.
    if live != expected_level:
        alt = ""
        if res.get("outermost") and res["outermost"] != live:
            alt = ("  (world path {0!r}, outermost package {1!r} — outermost "
                   "disagreeing with outer on a UWorld is unexpected and "
                   "means this comparison is reading the wrong "
                   "object)".format(res.get("world"), res["outermost"]))
        return False, (
            "recipe targets {0!r} but the editor has {1!r} open{2}{3}".format(
                expected_level, live,
                " — that is an UNSAVED level; opening another would "
                "discard it" if live.startswith("/Temp/") else "", alt))
    return True, live


def _parse_probe(text, marker=PROBE_MARKER):
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker):].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _run_probe(remote_exec, remote, node_id, source, marker=PROBE_MARKER):
    """Run one read-only probe on an ALREADY-VERIFIED node.

    `marker` is parameterised so the level gate can reuse this connection
    handling with its own LEVEL_MARKER rather than duplicating it. Default
    preserves every existing caller unchanged.
    """
    try:
        remote.open_command_connection(node_id)
    except Exception as exc:
        print("  probe connection failed: {0}: {1}".format(
            type(exc).__name__, exc))
        return None
    try:
        result = remote.run_command(source, unattended=True,
                                    exec_mode=remote_exec.MODE_EXEC_FILE)
        if not result or not result.get("success"):
            print("  probe did not succeed: {0}".format(
                (result or {}).get("result")))
            return None
        return _parse_probe(bootstrap._collect_output(result), marker)
    except Exception as exc:
        print("  probe errored: {0}: {1}".format(type(exc).__name__, exc))
        return None
    finally:
        try:
            remote.close_command_connection()
        except Exception:
            pass


def _select_verified_node(remote_exec, remote, expected, timeout):
    """Conduct rule 7 gate. Returns (node, reason).

    Mirrors bootstrap.main()'s classification, reusing its primitives.
    Extracting a shared helper into bootstrap.py remains the correct fix
    and is a design decision for Ryan; duplicated here rather than
    modifying a signed-off script unilaterally.
    """
    nodes = bootstrap._discover(remote, timeout)
    if not nodes:
        return None, "no editor nodes answered discovery"

    matches, malformed = [], []
    for node in nodes:
        raw = node.get("project_root")
        if raw is None:
            status = "no project loaded"
        elif not isinstance(raw, str) or not os.path.isabs(raw):
            malformed.append(node)
            status = "MALFORMED project_root: {0!r}".format(raw)
        elif bootstrap._norm(raw) == expected:
            matches.append(node)
            status = "MATCH"
        else:
            status = "other project -> {0}".format(raw)
        print("  - {0}: {1}".format(bootstrap._describe(node), status))

    if malformed:
        return None, "{0} node(s) reported an unparseable project path".format(
            len(malformed))
    if not matches:
        return None, "no reachable editor has UE_PROJECT_ROOT open"
    if len(matches) > 1:
        return None, "{0} editors claim UE_PROJECT_ROOT — ambiguous".format(
            len(matches))

    node = matches[0]
    info = bootstrap._confirm(remote_exec, remote, node["node_id"])
    if not info or not info.get("project_dir"):
        return None, "could not confirm the selected editor's project"
    if bootstrap._norm(info["project_dir"]) != expected:
        return None, "editor reported {0}, not UE_PROJECT_ROOT".format(
            info["project_dir"])
    return node, None


def _single(values):
    """Collapse a set of per-component values to one, or None."""
    return values[0] if isinstance(values, list) and len(values) == 1 else None


def compare(spec, live):
    """Compare the live landscape to the spec.

    Returns (mismatches, unverified). Both empty means a clean pass.
    """
    mismatches, unverified = [], []

    # Every geometry number below is only as trustworthy as the probe's
    # proxy-to-landscape attribution. Absent or False fails closed: a
    # union that may contain another landscape's components (or may have
    # been built blind) verifies nothing.
    if not live.get("proxy_attribution_verified", False):
        unverified.append(
            "proxy attribution: streaming proxies could not all be "
            "attributed to this landscape (LandscapeActorRef and "
            "LandscapeGuid both unreadable on at least one proxy)")

    def check(label, expected, actual, tol=None):
        if actual is None:
            unverified.append("{0}: could not be read back".format(label))
            return
        ok = (abs(actual - expected) <= tol) if tol is not None \
            else (actual == expected)
        if not ok:
            mismatches.append("{0}: recipe expects {1}, live is {2}".format(
                label, expected, actual))

    # Component grid, derived from SectionBase spacing. Needs only the
    # reliably-readable BlueprintReadOnly properties. Both axes are
    # checked symmetrically, and the derived resolution uses the
    # MEASURED spacing, never the spec's own value — a derivation that
    # feeds the expected number back into itself verifies nothing.
    bases_x = live.get("section_base_x") or []
    bases_y = live.get("section_base_y") or []
    if len(bases_x) < 1 or len(bases_y) < 1:
        unverified.append("component grid: no section bases returned")
    else:
        check("components per side (X)", spec["component_count"],
              len(bases_x))
        check("components per side (Y)", spec["component_count"],
              len(bases_y))
        check("total components", spec["total_components"],
              live.get("component_total"))
        for axis, bases in (("X", bases_x), ("Y", bases_y)):
            if len(bases) < 2:
                continue
            spacings = {bases[i + 1] - bases[i]
                        for i in range(len(bases) - 1)}
            if len(spacings) != 1:
                mismatches.append(
                    "component spacing ({0}) is not uniform: {1}".format(
                        axis, sorted(spacings)))
                continue
            spacing = spacings.pop()
            check("quads per component (from {0} spacing)".format(axis),
                  spec["quads_per_component"], spacing)
            span = bases[-1] - bases[0] + spacing
            check("overall resolution (derived, {0})".format(axis),
                  spec["resolution"], span + 1)
            # Recorded for the D3 derivation below. Both axes must agree
            # or the earlier per-axis checks have already failed.
            measured_spacing = spacing
            live["_measured_spacing"] = measured_spacing

    # Direct geometry properties. UE 5.8's get_editor_property REFUSES
    # bare UPROPERTY() fields, which these three are
    # (LandscapeComponent.h:444-453), so in practice they come back empty
    # — confirmed empirically by scripts/landscape_inventory.py.
    #
    # Per Ryan's D3 ruling (option (a), LESSONS.md), when a
    # property cannot be read the measured component spacing stands as
    # confirmation instead. This is an ARITHMETIC independent
    # confirmation, not a weakening: over the dialog-legal values
    # (section_size in {7,15,31,63,127,255} x sections_per_component in
    # {1,2}) the twelve possible spacings — 7,14,15,30,31,62,63,126,127,
    # 254,255,510 — are all distinct, so a measured spacing determines
    # (section_size, sections_per_component) uniquely. A spacing of 126
    # can only be 63x2; the feared 63x2-vs-126x1 ambiguity would need
    # section_size 126, which the dialog cannot produce.
    #
    # Rows resolved this way are labelled DERIVED so no reader mistakes
    # them for property reads. When the route-A C++ plugin exposes a
    # direct accessor (option (c)), these labels retire.
    derived = []

    def check_or_derive(label, expected, actual, derived_actual,
                        derived_from):
        if actual is not None:
            check(label, expected, actual)
            return
        if derived_actual is None:
            unverified.append(
                "{0}: unreadable, and no spacing measurement to derive "
                "it from".format(label))
            return
        if derived_actual != expected:
            mismatches.append(
                "{0}: recipe expects {1}, DERIVED {2} (from {3})".format(
                    label, expected, derived_actual, derived_from))
        else:
            derived.append("{0} = {1}  DERIVED from {2}".format(
                label, derived_actual, derived_from))

    spacing = live.get("_measured_spacing")
    spacing_note = "measured component spacing {0}".format(spacing) \
        if spacing is not None else None

    check_or_derive(
        "quads per component", spec["quads_per_component"],
        _single(live.get("component_size_quads")), spacing, spacing_note)
    check_or_derive(
        "section size (subsection quads)", spec["section_size"],
        _single(live.get("subsection_size_quads")),
        (spacing // spec["sections_per_component"]
         if spacing is not None
         and spacing % spec["sections_per_component"] == 0 else None),
        spacing_note)
    check_or_derive(
        "sections per component", spec["sections_per_component"],
        _single(live.get("num_subsections")),
        (spacing // spec["section_size"]
         if spacing is not None and spacing % spec["section_size"] == 0
         else None),
        spacing_note)
    live["_derived_rows"] = derived

    for name, values in (("component_size_quads",
                          live.get("component_size_quads")),
                         ("subsection_size_quads",
                          live.get("subsection_size_quads")),
                         ("num_subsections", live.get("num_subsections"))):
        if isinstance(values, list) and len(values) > 1:
            mismatches.append(
                "{0} is not uniform across components: {1}".format(
                    name, values))

    scale = live.get("scale") or [None, None, None]
    check("scale X", spec["scale_x"], scale[0], TOLERANCE)
    check("scale Y", spec["scale_y"], scale[1], TOLERANCE)
    check("scale Z", spec["scale_z"], scale[2], TOLERANCE)

    location = live.get("location") or [None, None, None]
    for i, axis in enumerate("XYZ"):
        check("location {0}".format(axis), spec["location_cm"][i],
              location[i], TOLERANCE)

    # Component world origin. The actor location above reads only the
    # ALandscape parent; in World Partition the terrain itself lives on
    # proxy actors that follow the parent ONLY through the editor's
    # interactive-move hook (ALandscape::PostEditMove ->
    # FixupProxiesTransform, LandscapeEdit.cpp:5138-5147). A scripted
    # move tears them apart, and the parent's location alone cannot see
    # that — this check can: every component's implied origin
    # (world - scale * section_base) must agree, and must equal the
    # recipe origin.
    origin_min = live.get("implied_origin_min") or [None, None, None]
    origin_max = live.get("implied_origin_max") or [None, None, None]
    for i, axis in enumerate("XYZ"):
        lo = origin_min[i] if i < len(origin_min) else None
        hi = origin_max[i] if i < len(origin_max) else None
        if lo is None or hi is None:
            unverified.append(
                "component world origin ({0}): could not be read "
                "back".format(axis))
            continue
        if hi - lo > POSITION_TOLERANCE_CM:
            mismatches.append(
                "component world origins disagree on {0} by {1:.1f} cm — "
                "landscape and proxy transforms are torn".format(
                    axis, hi - lo))
            continue
        check("landscape origin from component positions ({0})".format(axis),
              spec["location_cm"][i], lo, POSITION_TOLERANCE_CM)

    return mismatches, unverified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress banners and the pass summary. Node "
                             "classification and DERIVED provenance always "
                             "print (by design -- see the DERIVED block); "
                             "failures always print.")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    recipe_path = os.path.abspath(args.recipe)
    recipe, err = landscape_spec.load_recipe(recipe_path)
    if err:
        print("REFUSE: {0}".format(err))
        return 2

    spec, errors = landscape_spec.derive_spec(recipe)
    if errors:
        print("REFUSE: recipe geometry is not buildable:")
        for e in errors:
            print("  - {0}".format(e))
        return 2

    if not args.quiet:
        print("REPO_ROOT       : {0}".format(REPO_ROOT))
        print("UE_PROJECT_ROOT : {0}".format(bootstrap.UE_PROJECT_ROOT))
        print("Recipe          : {0}".format(recipe_path))
        print("Landscape       : {0}".format(spec["actor_name"]))
        print("")
        print("--- editor identity gate (conduct rule 7) ---")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        expected = bootstrap._norm(bootstrap.UE_PROJECT_ROOT)
        node, reason = _select_verified_node(
            remote_exec, remote, expected, args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}. Not executing.".format(reason))
            return 3
        if not args.quiet:
            print("  VERIFIED: {0}".format(bootstrap._describe(node)))
            print("")

        # Level gate (schema v1.2), exit 7. Signed off 2026-08-01.
        #
        # This script is editor-touching and defines gate_level, yet did not
        # call it: run against the wrong world it would read a stranger's
        # level. It failed closed only by luck, because the label
        # 'Landscape_Alpine' would not match — the same accident that
        # limited the 2026-08-01 wrong-level incident.
        #
        # A NEW exit code, deliberately. 6 already means INCOMPLETE ("one or
        # more fields could not be read back"), and "I read the wrong world"
        # is not "I could not read a field". Collapsing them would destroy
        # the distinction the whole fail-closed design rests on, and would
        # make a wrong-level run look like a bare-UPROPERTY refusal.
        if not args.quiet:
            print("--- level gate (recipe landscape.level_path) ---")

        def _lvl_runner(source, marker):
            return _run_probe(remote_exec, remote, node["node_id"],
                              source, marker)

        want_level = (recipe.get("landscape") or {}).get("level_path")
        ok_level, detail = gate_level(remote_exec, remote, node["node_id"],
                                      want_level, _lvl_runner)
        if not ok_level:
            print("REFUSE (level gate): {0}".format(detail))
            print("  Conduct rule 7 verified the PROJECT; this checks the")
            print("  LEVEL. Nothing was read from the landscape.")
            return 7
        if not args.quiet:
            print("  level {0}".format(detail))
            print("")
            print("--- reading live landscape ---")

        live = _run_probe(remote_exec, remote, node["node_id"],
                          _probe_source(spec["actor_name"]))
        if live is None:
            print("FAIL: the landscape probe returned nothing.")
            return 6
        # Inventory is reported unconditionally — a match says nothing
        # about what else is in the level.
        inventory = live.get("landscapes") or []
        proxies = live.get("proxies") or []
        matching = live.get("matching", 0)
        if not args.quiet or matching != 1 or len(inventory) != 1:
            print("")
            print("--- landscape inventory ---")
            print("  Landscape actors ({0}): {1}".format(
                len(inventory),
                ", ".join(repr(a) for a in inventory) if inventory
                else "none"))
            print("  StreamingProxy actors ({0}){1}".format(
                len(proxies), ": WP level" if proxies else ""))
            if live.get("proxy_lookup_error"):
                print("  proxy lookup error: {0}".format(
                    live["proxy_lookup_error"]))
            print("  matching {0!r}: {1}".format(
                spec["actor_name"], matching))
            if live.get("found"):
                print("  attributed sources (landscape + proxies): "
                      "{0}".format(live.get("source_actors")))
                if live.get("proxies_excluded"):
                    print("  proxies excluded (not this landscape's): "
                          "{0}".format(live["proxies_excluded"]))

        # Exactly one, or nothing runs. Two landscapes sharing a label,
        # or a stale survivor from an earlier attempt, is precisely the
        # undocumented state this gate exists to refuse.
        if matching == 0:
            print("")
            print("FAIL: no landscape actor labelled {0!r}.".format(
                spec["actor_name"]))
            print("  Create it from: python scripts/landscape_spec.py")
            return 4
        if matching > 1:
            print("")
            print("FAIL: {0} landscape actors are labelled {1!r}. Exactly "
                  "one is required — delete the extras.".format(
                      matching, spec["actor_name"]))
            return 4
        if len(inventory) != 1:
            print("")
            print("FAIL: {0} landscape actors exist in the level; exactly "
                  "one is required.".format(len(inventory)))
            print("  A stale landscape from an earlier attempt is "
                  "undocumented state — delete it before proceeding.")
            return 4
        if not live.get("found"):
            # Defensive only — unreachable: the payload sets found=True
            # exactly when one landscape matched, and this branch is only
            # reached after matching==1; a payload exception surfaces as
            # probe-returned-nothing above (Pass 3 2026-09-16).
            print("")
            print("FAIL: landscape matched but returned no data.")
            return 6

        mismatches, unverified = compare(spec, live)

        # DERIVED rows are printed on EVERY outcome, and before the
        # verdict, so a reader can never mistake an arithmetic derivation
        # for a property the engine confirmed.
        derived_rows = live.get("_derived_rows") or []
        if derived_rows:
            print("")
            print("*** DERIVED — not read from the engine ***")
            for d in derived_rows:
                print("  ~ {0}".format(d))
            print("  UE 5.8 refuses get_editor_property on these bare")
            print("  UPROPERTY() fields, so they are derived from measured")
            print("  component spacing, which determines them uniquely over")
            print("  the dialog-legal values (D3 ruling (a), decisions.md).")
            if live.get("unreadable"):
                print("  engine refused: {0}".format(
                    ", ".join(live["unreadable"])))

        if mismatches:
            print("")
            print("MISMATCH — the live landscape disagrees with the recipe:")
            for m in mismatches:
                print("  x {0}".format(m))
            if unverified:
                print("  (also unverified:)")
                for u in unverified:
                    print("    ? {0}".format(u))
            print("")
            print("Nothing downstream should run. Either the dialog entry")
            print("was wrong, or the recipe changed after creation.")
            return 5

        if unverified:
            print("")
            print("INCOMPLETE — these fields could not be read back:")
            for u in unverified:
                print("  ? {0}".format(u))
            if live.get("unreadable"):
                print("  engine refused: {0}".format(
                    ", ".join(live["unreadable"])))
            print("")
            print("Treating unverifiable as failure: a tripwire that cannot")
            print("read the thing it guards is not a tripwire.")
            return 6

        if not args.quiet:
            # If the geometry rows were derived rather than read, say so
            # again HERE — the summary is what gets pasted into reports,
            # and it must not launder a derivation into a read.
            qual = "  (DERIVED, see above)" if derived_rows else ""
            print("  components   {0} ({1} x {1})".format(
                live.get("component_total"), spec["component_count"]))
            print("  quads/comp   {0}{1}".format(
                spec["quads_per_component"], qual))
            print("  resolution   {0} x {0}".format(spec["resolution"]))
            print("  scale        X {0}  Y {1}  Z {2}".format(
                *(live.get("scale") or [])))
            print("")
            print("PASS: live landscape matches the recipe-derived spec.")
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
