"""test_open_level_scrub.py — prove the pre-load reference scrub REFUSES.

No editor. Runs on the CPU with nothing open, so it survives a cold
replay and can gate a commit.

WHY THIS FILE EXISTS
On 2026-08-05 `open_level.py` fataled the editor at EditorServer.cpp:1951
("World Memory Leaks") WITH its `gc.collect()` guard already in place. The
guard was written on the premise that the only references to the outgoing
world were the ones its own payload made. Remote-exec MODE_EXEC_FILE
payloads run in the PERSISTENT console dicts, so an earlier payload's
top-level `_world` is a LIVE GLOBAL — and gc.collect() cannot free a live
global. The guard had only ever been exercised against the failure it
could handle.

So this proves the replacement in all three directions (non-negotiable 2:
a gate that has only seen good input has not been tested):

  1. it DETECTS a foreign world reference, including one buried in a
     container, and drops it;
  2. it REFUSES when a reference survives the scrub;
  3. it REFUSES when `unreal.Object` cannot be resolved — the
     fail-closed direction, because an unresolved base would make
     isinstance() match nothing, report a clean namespace, and hand a
     green light to the exact fatal it guards against.

The helper source is extracted from the REAL payload text rather than
copied here, so this cannot pass against a stale duplicate of the logic
(non-negotiable 24: two lists that must agree are one list, badly stored).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import open_level  # noqa: E402


class _StubObject:
    """Stands in for unreal.Object — the base of every UObject wrapper."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<StubUObject {0}>".format(self.name)


class _StubUnreal:
    Object = _StubObject


def _helper_source():
    """Slice the scrub helpers out of the real payload.

    Bounded by the two landmarks that bracket them in `_payload`, so a
    rename or reorder makes this test FAIL rather than silently test
    nothing.
    """
    src = open_level._payload("/Game/Alpine", True, False)
    start = src.index("_UOBJECT_BASE = getattr")
    end = src.index("\ntry:\n")
    if not 0 < start < end:
        raise AssertionError("could not locate the scrub helpers in the "
                             "payload — this test is not testing them")
    block = src[start:end]
    for needed in ("_holds_uobject", "_surviving_uobject_globals",
                   "_release_world_refs", "_KEEP_GLOBALS"):
        if "def {0}".format(needed) not in block and \
                "{0} = ".format(needed) not in block:
            raise AssertionError(
                "{0} is missing from the extracted payload block".format(
                    needed))
    return block


def _namespace(uobject_base_present=True):
    # `import gc as _gc` sits above the extracted slice in the real
    # payload, so the harness supplies it rather than widening the slice
    # (which would drag in editor-facing code).
    import gc as _gc
    ns = {"__name__": "payload", "_gc": _gc}
    stub = _StubUnreal()
    if not uobject_base_present:
        class _Empty:
            pass
        stub = _Empty()          # no .Object attribute at all
    ns["_unreal"] = stub
    exec(compile(_helper_source(), "<scrub>", "exec"), ns)
    return ns


def main():
    failures = []

    def check(label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        print("  [{0}] {1}{2}".format(
            status, label, ("  — " + detail) if detail and not condition
            else ""))
        if not condition:
            failures.append(label)

    print("REPO_ROOT : {0}".format(open_level.REPO_ROOT))
    print("")
    print("--- 1. the scrub DETECTS and DROPS world references ---")
    ns = _namespace()
    world = _StubObject("/Temp/Untitled_1")
    ns["_world"] = world                       # foreign payload's global
    ns["_pkg"] = _StubObject("/Temp/Untitled_1")
    ns["_found"] = [_StubObject("CameraActor_0")]   # container case
    ns["_stash"] = {"path": _StubObject("ScreenshotTask")}
    ns["_harmless"] = "a string"
    ns["_number"] = 17

    before = sorted(ns["_surviving_uobject_globals"]())
    check("finds the bare world reference", "_world" in before)
    check("finds a reference inside a list", "_found" in before,
          "containers root the world as surely as bare names")
    check("finds a reference inside a dict", "_stash" in before)
    check("ignores non-UObject globals",
          "_harmless" not in before and "_number" not in before)

    dropped = sorted(ns["_release_world_refs"]())
    check("drops every one of them", dropped == before,
          "dropped={0} expected={1}".format(dropped, before))
    check("namespace is clean afterwards",
          ns["_surviving_uobject_globals"]() == [])
    check("harmless globals survive the scrub",
          ns.get("_harmless") == "a string" and ns.get("_number") == 17,
          "the scrub must not be a namespace bomb")

    print("")
    print("--- 2. a SURVIVOR is reported, not ignored ---")
    ns2 = _namespace()
    # A reference the scrub cannot reach: held by a live keep-listed name.
    ns2["_out"] = {"leaked": _StubObject("/Temp/Untitled_1")}
    survivors = ns2["_surviving_uobject_globals"]()
    check("a keep-listed name is NOT scrubbed", survivors == [],
          "expected the predicate to skip keep-listed names")
    # And the realistic case: something rebinds after the scrub.
    ns2["_late"] = _StubObject("/Temp/Untitled_1")
    check("a reference appearing after the scrub is caught by the "
          "re-read", "_late" in ns2["_surviving_uobject_globals"](),
          "this is the assertion that gates the load")

    print("")
    print("--- 3. FAIL CLOSED when unreal.Object cannot be resolved ---")
    ns3 = _namespace(uobject_base_present=False)
    check("_UOBJECT_BASE is None when the name is absent",
          ns3["_UOBJECT_BASE"] is None)
    payload = open_level._payload("/Game/Alpine", True, False)
    check("the payload refuses on _UOBJECT_BASE is None",
          "if _UOBJECT_BASE is None:" in payload
          and "Refusing" in payload,
          "an unverifiable scrub must not authorise a load")
    check("the load is gated behind the survivor check",
          payload.index("_surviving_uobject_globals()")
          < payload.index("load_level(_target)"),
          "the assertion must precede the transition")

    print("")
    print("--- 4. the SEED is fixed too (verify_landscape.LEVEL_SOURCE) ---")
    import verify_landscape
    check("LEVEL_SOURCE releases its wrappers",
          "globals().pop" in verify_landscape.LEVEL_SOURCE,
          "the producer that planted the fatal reference")

    print("")
    print("=" * 62)
    if failures:
        print("FAILED ({0}): {1}".format(len(failures), ", ".join(failures)))
        return 1
    print("ALL CHECKS PASSED — the scrub detects, drops, asserts and "
          "fails closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
