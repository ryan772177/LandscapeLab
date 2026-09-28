"""ll_must.py -- the four calls whose FAILURE RETURNS A VALUE, made loud.

    python scripts/ll_must.py --selftest        (offline, no editor)

⛔ THE CLASS OF DEFECT. Some engine calls report failure by RETURNING
something rather than raising. A caller that consumes the return as a
VERDICT -- "does it exist", "did it save", "did it connect" -- turns a
failure into a confident wrong answer, and the audit found 94 such sites
(does_asset_exist 47, save_asset 26, connect_material_expressions 21).

Each function here answers the question the call site actually asks, and
RAISES when the answer is no. None of them returns a bool for the caller
to forget to check.

IMPORTED, NOT INJECTED. `ue_exec` copies this module into the payload
stage directory, and a payload reaches it with

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ll_must

`_ll_wire` used to be a source STRING pasted into each builder, which is
how three builders ended up with three copies and one of them without
the fix. `must_connect` is that same check, once.

⭐ WHY EACH CHECK IS MORE THAN THE CALL IT REPLACES

  must_exist   `does_asset_exist` answers a REGISTRY question. An entry
               can exist and the asset still fail to load (a broken
               reference, a missing class). "Exists" and "usable" are
               different claims and the call sites want the second.
  must_save    `save_asset` returns a bool that is True on paths where
               nothing reached disk. The only evidence that a save
               happened is the FILE, so this re-loads from disk and
               compares -- a read-back from a different instrument than
               the setter (NN8).
  must_connect `connect_material_expressions` returns false on an
               unresolvable pin name and connects NOTHING, and the
               material still compiles because an unconnected input is
               legal (MaterialEditingLibrary.cpp:928-943).
  cvar_must    the int/float getters return 0 both for "absent" and for
               "present and zero" -- the same number for two different
               facts. Only the STRING getter distinguishes them, and it
               is trustworthy only if its controls discriminate.
"""
from __future__ import annotations

import argparse
import os
import sys

# The engine module is absent offline; every function takes its engine
# handles as arguments so the module imports either way and the selftest
# can drive it with fakes.
try:
    import unreal as _unreal
except Exception:                                    # pragma: no cover
    _unreal = None


class MustError(RuntimeError):
    """Raised when a checked call did not do what it was asked."""


# --------------------------------------------------------------- exists --
def must_exist(path, eal=None, load=True):
    """The asset at `path` exists AND loads. Returns the loaded object.

    `eal` is EditorAssetLibrary (or anything with the same two methods),
    injectable so the selftest can drive it.
    """
    if eal is None:
        if _unreal is None:
            raise MustError("must_exist needs EditorAssetLibrary; no "
                            "`unreal` module and none passed in")
        eal = _unreal.EditorAssetLibrary
    if not isinstance(path, str) or not path.startswith("/"):
        raise MustError(
            "must_exist: %r is not a content path. Content paths start "
            "with /Game/ or /Engine/; a filesystem path here means the "
            "caller built the wrong string." % (path,))
    try:
        present = bool(eal.does_asset_exist(path))
    except Exception as exc:
        raise MustError("must_exist: does_asset_exist raised on %s: %s: %s"
                        % (path, type(exc).__name__, exc))
    if not present:
        raise MustError(
            "must_exist: %s DOES NOT EXIST. The asset registry has no "
            "entry for it -- check the path, and check that whatever "
            "was supposed to create it actually ran." % path)
    if not load:
        return None
    try:
        obj = eal.load_asset(path)
    except Exception as exc:
        raise MustError("must_exist: %s exists but load_asset raised: "
                        "%s: %s" % (path, type(exc).__name__, exc))
    if obj is None:
        raise MustError(
            "must_exist: %s EXISTS IN THE REGISTRY BUT DID NOT LOAD. "
            "That is the case does_asset_exist cannot see: a registry "
            "entry whose object is unusable (broken reference, missing "
            "class, failed cook). Treating the registry answer as a "
            "verdict is what this check exists to stop." % path)
    return obj


# ----------------------------------------------------------------- save --
def must_save(path, eal=None, reload_check=True, only_if_is_dirty=False):
    """Save `path`, then RE-LOAD FROM DISK and confirm it is really there.

    The return value of `save_asset` is not the evidence; the file is.

    ⛔ `only_if_is_dirty` DEFAULTS TO FALSE HERE, WHICH IS NOT THE
    ENGINE'S DEFAULT. `EditorAssetLibrary.save_asset` defaults it to
    True, i.e. "skip if the package is not marked dirty" -- and every
    call site this replaces passed False explicitly, because a builder
    that has just rewritten a graph wants the write to happen whatever
    the dirty flag says. Defaulting to the engine's True here would have
    silently converted forced saves into conditional ones: the exact
    class of defect this module exists to stop, introduced by the fix.
    """
    if eal is None:
        if _unreal is None:
            raise MustError("must_save needs EditorAssetLibrary")
        eal = _unreal.EditorAssetLibrary
    if not isinstance(path, str) or not path.startswith("/"):
        raise MustError("must_save: %r is not a content path" % (path,))
    try:
        returned = eal.save_asset(path, only_if_is_dirty)
    except Exception as exc:
        raise MustError("must_save: save_asset raised on %s: %s: %s"
                        % (path, type(exc).__name__, exc))
    if returned is False:
        raise MustError(
            "must_save: save_asset returned False for %s -- it did not "
            "save. Nothing downstream may assume this asset is on disk."
            % path)
    if not reload_check:
        return True
    # ⭐ THE READ-BACK IS A DIFFERENT INSTRUMENT FROM THE SETTER. A True
    # return says the call ran. Loading the path again says the content
    # system can find it. On 2026-09-12 a builder printed "saved after
    # the verdict" for five weeks while saving nothing, because only the
    # return value was ever consulted.
    try:
        present = bool(eal.does_asset_exist(path))
        obj = eal.load_asset(path) if present else None
    except Exception as exc:
        raise MustError("must_save: %s saved but the read-back raised: "
                        "%s: %s" % (path, type(exc).__name__, exc))
    if obj is None:
        raise MustError(
            "must_save: save_asset reported success for %s but the "
            "asset does not load back. The save did not reach disk."
            % path)
    return True


# -------------------------------------------------------------- connect --
def must_connect(mel, from_expr, from_pin, to_expr, to_pin):
    """connect_material_expressions, CHECKED. Raises on a failed connect.

    Identical in substance to the `_ll_wire` that was pasted into three
    builders as a source string; this is that check as an import.

    MaterialEditingLibrary.cpp:928-943 (UE 5.8) returns false when a pin
    name does not resolve and connects nothing. The input keeps its
    default -- 0 for a scalar, black for a colour -- and the material
    COMPILES CLEAN, because an unconnected input is legal. That is the
    project's worst failure shape: a wiring mistake that reports success
    and renders plausibly.
    """
    try:
        ok = mel.connect_material_expressions(from_expr, from_pin,
                                              to_expr, to_pin)
    except Exception as exc:
        raise MustError("must_connect raised: %s: %s"
                        % (type(exc).__name__, exc))
    if not ok:
        raise MustError(
            "connect FAILED: {0}.{1!r} -> {2}.{3!r}. The pin name did "
            "not resolve, so NOTHING was connected and the input kept "
            "its default. Check both pin names against the node class."
            .format(type(from_expr).__name__, from_pin,
                    type(to_expr).__name__, to_pin))
    return True


# ----------------------------------------------------------------- cvar --
CONTROL_POSITIVE = "r.ScreenPercentage"
CONTROL_NEGATIVE = "r.ThisCVarCannotPossiblyExist_zzz"
_CONTROLS_CHECKED = {}


def _string_getter(sys_lib=None):
    if sys_lib is not None:
        return sys_lib
    if _unreal is None:
        raise MustError("cvar_must needs SystemLibrary")
    return _unreal.SystemLibrary


def check_cvar_controls(sys_lib=None, force=False):
    """The positive must resolve and the negative must not.

    Run once per process and cached. If a getter cannot tell a real cvar
    from an invented one, then NO existence answer from it means
    anything, and every verdict built on it is unsupported (NN6:
    degrade naming the gap).
    """
    key = id(sys_lib) if sys_lib is not None else "engine"
    if not force and key in _CONTROLS_CHECKED:
        return _CONTROLS_CHECKED[key]
    lib = _string_getter(sys_lib)
    pos = lib.get_console_variable_string_value(CONTROL_POSITIVE)
    neg = lib.get_console_variable_string_value(CONTROL_NEGATIVE)
    ok = bool(pos) and not bool(neg)
    _CONTROLS_CHECKED[key] = ok
    if not ok:
        raise MustError(
            "cvar controls FAILED: %r returned %r (expected non-empty) "
            "and %r returned %r (expected empty). The string getter is "
            "not discriminating present from absent, so no cvar "
            "existence verdict is supported."
            % (CONTROL_POSITIVE, pos, CONTROL_NEGATIVE, neg))
    return ok


def cvar_must(name, sys_lib=None):
    """`name` is a real console variable. Returns its STRING value.

    ⛔ THE STRING GETTER, NOT THE INT OR FLOAT ONE. The numeric getters
    return 0 for an absent name and 0 for a name whose value is zero --
    one number for two different facts. Only the string getter returns
    "" for absent and "0" for present-and-zero.
    """
    lib = _string_getter(sys_lib)
    check_cvar_controls(sys_lib)
    value = lib.get_console_variable_string_value(name)
    if value == "" or value is None:
        raise MustError(
            "cvar_must: %r DOES NOT EXIST in this build. The controls "
            "passed, so this is the variable's absence and not a broken "
            "getter. A write to it would set nothing and report nothing."
            % name)
    return value


# ------------------------------------------------------------- selftest --
class _FakeEAL(object):
    """Minimal EditorAssetLibrary stand-in, so the checks are testable
    with no editor. Each behaviour it models is one the real API has
    actually exhibited in this project."""

    def __init__(self, existing=(), unloadable=(), save_returns=True,
                 save_reaches_disk=True, raise_on=()):
        self.existing = set(existing)
        self.unloadable = set(unloadable)
        self.save_returns = save_returns
        self.save_reaches_disk = save_reaches_disk
        self.raise_on = set(raise_on)
        self.saved = []

    def does_asset_exist(self, p):
        if "does_asset_exist" in self.raise_on:
            raise RuntimeError("boom")
        return p in self.existing

    def load_asset(self, p):
        if p in self.unloadable:
            return None
        return object() if p in self.existing else None

    def save_asset(self, p, only_if_is_dirty=True):
        # The flag is RECORDED, so the selftest can assert that
        # must_save forces the write rather than inheriting the
        # engine's conditional default.
        self.saved.append((p, only_if_is_dirty))
        if self.save_reaches_disk:
            self.existing.add(p)
        return self.save_returns


class _FakeMEL(object):
    def __init__(self, ok=True, raises=False):
        self.ok, self.raises = ok, raises

    def connect_material_expressions(self, a, ap, b, bp):
        if self.raises:
            raise RuntimeError("boom")
        return self.ok


class _FakeSys(object):
    def __init__(self, table):
        self.table = table

    def get_console_variable_string_value(self, n):
        return self.table.get(n, "")


def _selftest():
    fails = []

    def check(label, fn, should_raise):
        try:
            fn()
            raised = False
        except MustError:
            raised = True
        except Exception as exc:
            fails.append("%s: wrong exception %s" % (label, type(exc).__name__))
            print("  %-58s UNEXPECTED %s" % (label, type(exc).__name__))
            return
        ok = (raised == should_raise)
        if not ok:
            fails.append(label)
        print("  %-58s %s" % (label, "PASS" if ok else "FAIL"))

    print("must_exist")
    eal = _FakeEAL(existing={"/Game/Real"}, unloadable={"/Game/Ghost"})
    eal.existing.add("/Game/Ghost")
    check("POSITIVE: an asset that exists and loads",
          lambda: must_exist("/Game/Real", eal), False)
    check("NEGATIVE: an asset that does not exist",
          lambda: must_exist("/Game/Missing", eal), True)
    check("NEGATIVE: registry entry that does NOT load (the real trap)",
          lambda: must_exist("/Game/Ghost", eal), True)
    check("NEGATIVE: a filesystem path instead of a content path",
          lambda: must_exist("C:/Game/Real", eal), True)
    check("NEGATIVE: the underlying call raises",
          lambda: must_exist("/Game/Real",
                             _FakeEAL(existing={"/Game/Real"},
                                      raise_on={"does_asset_exist"})), True)

    print("must_save")
    check("POSITIVE: saves and reads back",
          lambda: must_save("/Game/New", _FakeEAL()), False)
    check("NEGATIVE: save_asset returns False",
          lambda: must_save("/Game/New",
                            _FakeEAL(save_returns=False)), True)
    check("NEGATIVE: returns True but nothing reached disk",
          lambda: must_save("/Game/New",
                            _FakeEAL(save_reaches_disk=False)), True)
    # The forced-save contract: must_save must NOT inherit the engine's
    # only_if_is_dirty=True default, or every call site it replaces
    # quietly becomes conditional.
    _fe = _FakeEAL()
    must_save("/Game/Forced", _fe)
    forced_ok = _fe.saved and _fe.saved[-1][1] is False
    if not forced_ok:
        fails.append("must_save forced-write contract")
    print("  %-58s %s" % ("POSITIVE: save is FORCED, not only-if-dirty",
                          "PASS" if forced_ok else "FAIL"))

    print("must_connect")
    check("POSITIVE: connect succeeds",
          lambda: must_connect(_FakeMEL(True), 1, "A", 2, "B"), False)
    check("NEGATIVE: connect returns false (pin did not resolve)",
          lambda: must_connect(_FakeMEL(False), 1, "A", 2, "B"), True)
    check("NEGATIVE: connect raises",
          lambda: must_connect(_FakeMEL(raises=True), 1, "A", 2, "B"), True)

    print("cvar_must")
    good = _FakeSys({CONTROL_POSITIVE: "100", "r.Real": "1"})
    bad_pos = _FakeSys({"r.Real": "1"})
    bad_neg = _FakeSys({CONTROL_POSITIVE: "100",
                        CONTROL_NEGATIVE: "something", "r.Real": "1"})
    check("POSITIVE: a present cvar with passing controls",
          lambda: cvar_must("r.Real", good), False)
    check("NEGATIVE: an absent cvar with passing controls",
          lambda: cvar_must("r.Nope", good), True)
    check("NEGATIVE: controls fail -- positive control empty",
          lambda: cvar_must("r.Real", bad_pos), True)
    check("NEGATIVE: controls fail -- negative control answers",
          lambda: cvar_must("r.Real", bad_neg), True)
    # A present-but-ZERO cvar must PASS: this is the case the int getter
    # cannot distinguish from absence, and the whole reason for the
    # string getter.
    zero = _FakeSys({CONTROL_POSITIVE: "100", "r.Zero": "0"})
    check("POSITIVE: a cvar whose value is 0 is PRESENT, not absent",
          lambda: cvar_must("r.Zero", zero), False)

    print("")
    if fails:
        print("selftest: FAIL (%d)" % len(fails))
        for f in fails:
            print("   ", f)
        return 1
    print("selftest: PASS")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
