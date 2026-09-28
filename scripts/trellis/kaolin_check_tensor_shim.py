"""kaolin.utils.testing.check_tensor -- a faithful shim, not a stub.

WHY THIS EXISTS
    TRELLIS's FlexiCubes mesh extractor -- which is ON the critical path for
    geometry -- imports exactly one symbol from kaolin:

        trellis/representations/mesh/flexicubes/flexicubes.py:17
            from kaolin.utils.testing import check_tensor

    and uses it in six assertions, all with throw=False. Every other kaolin
    reference in that subtree is in examples/ (notebooks, a renderer, an
    optimisation demo) which the pipeline never imports. Verified by grepping
    the whole trellis/ package, 2026-08-16.

    kaolin publishes wheels pinned to specific torch builds and has none for
    torch 2.11+cu128. Building it from source to obtain one shape-checking
    helper is a large amount of risk for no capability.

WHY IT IS IMPLEMENTED AND NOT STUBBED
    `def check_tensor(*a, **k): return True` would satisfy the import and
    SILENTLY DISABLE all six assertions. A check that cannot fail is not a
    check -- this project's non-negotiable 2 says a gate that has only seen
    good input has not been tested, and one that structurally cannot refuse is
    worse than absent, because it reads as coverage.

    So this implements the real contract: shape with None as a per-dimension
    wildcard, optional dtype and device, throw semantics. It is PROVEN to
    refuse in the selftest at the bottom.

CONTRACT (kaolin.utils.testing.check_tensor)
    check_tensor(tensor, shape=None, dtype=None, device=None, throw=True)
      -> bool
    Returns True if the tensor matches. On mismatch: raises ValueError when
    throw is True, otherwise returns False.
"""

import torch


def check_tensor(tensor, shape=None, dtype=None, device=None, throw=True):
    def _fail(msg):
        if throw:
            raise ValueError(msg)
        return False

    if not torch.is_tensor(tensor):
        return _fail("expected a torch.Tensor, got %r" % type(tensor))

    if shape is not None:
        if len(tensor.shape) != len(shape):
            return _fail("expected %d dimensions, got %d (shape %s)"
                         % (len(shape), len(tensor.shape), tuple(tensor.shape)))
        for i, (want, got) in enumerate(zip(shape, tensor.shape)):
            # None is a wildcard for that dimension -- this is the part a
            # naive implementation gets wrong, and flexicubes relies on it
            # (it passes (None, 3) and (None, 8)).
            if want is not None and want != got:
                return _fail("dimension %d: expected %s, got %s (shape %s)"
                             % (i, want, got, tuple(tensor.shape)))

    if dtype is not None and tensor.dtype != dtype:
        return _fail("expected dtype %s, got %s" % (dtype, tensor.dtype))

    if device is not None:
        want = torch.device(device)
        got = tensor.device
        # 'cuda' must match 'cuda:0'; compare type when no index was asked for.
        if want.index is None:
            if want.type != got.type:
                return _fail("expected device %s, got %s" % (want, got))
        elif want != got:
            return _fail("expected device %s, got %s" % (want, got))

    return True


if __name__ == "__main__":
    # PROVEN IN BOTH DIRECTIONS. A shim nobody tested is a shim nobody can
    # trust, and this one stands in for a gate.
    t = torch.zeros(7, 3)
    checks = [
        ("accepts exact shape",        check_tensor(t, (7, 3)) is True),
        ("accepts None wildcard",      check_tensor(t, (None, 3)) is True),
        ("refuses wrong dim size",     check_tensor(t, (None, 8), throw=False) is False),
        ("refuses wrong rank",         check_tensor(t, (7, 3, 1), throw=False) is False),
        ("refuses wrong dtype",        check_tensor(t, (7, 3), dtype=torch.int64, throw=False) is False),
        ("refuses non-tensor",         check_tensor([1, 2], (2,), throw=False) is False),
    ]
    raised = False
    try:
        check_tensor(t, (1, 1), throw=True)
    except ValueError:
        raised = True
    checks.append(("throw=True raises", raised))

    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n)
    print("SHIM SELFTEST:", "PASS" if not bad else "FAIL " + repr(bad))
    raise SystemExit(1 if bad else 0)
