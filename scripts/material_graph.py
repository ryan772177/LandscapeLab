"""material_graph.py — the ONE material-graph clear/verify utility.

WHY THIS EXISTS (class-level promotion, ruled 2026-08-03).

The "incomplete clear, then append debris" trap reached its THIRD
recurrence across THREE DIFFERENT tools:

  1. R2 / make_landscape_material  — delete_all_material_expressions
     leaves custom outputs behind; rebuilds accumulated 80 -> 158
     expressions.
  2. the landscape material again  — fixed locally, in that script only.
  3. make_foliage_material         — never swept. 7 expressions survived
     on M_fir_bark and 8 on M_fir_twig, and the survivors stayed WIRED,
     so a rebuild with the correct bark textures left the old twig
     samplers feeding BaseColor. Every conifer trunk rendered the wrong
     texture while the run reported success.

Per-script fixes did not contain it. Each was correct, each was logged,
and the next tool repeated it. **Individually-patched clear logic in a
builder script is now itself a REJECTED pattern** — see RECIPES.md R2
and R3.

WHAT THIS PROVIDES. Two source fragments, injected verbatim into any
in-editor payload (the builders run their work as remote-executed Python
in the editor, so a host-side import is not reachable from there):

  CLEAR_SRC   defines _ll_clear_graph(_mel, _mat)
              -> {"survived": n, "remaining": n}
              Total clear: delete_all, then delete every survivor
              explicitly, then re-read. A nonzero `remaining` is the
              caller's cue to REFUSE.

  ASSERT_SRC  defines _ll_assert_graph(_mel, _mat, _want)
              -> {"got": [...], "extra": [...], "missing": [...],
                  "exact": bool}
              MANDATORY POST-BUILD ASSERTION. The sampled texture set
              must EXACTLY equal spec. EXTRA NODES FAIL LOUDLY — that is
              the whole point, because the failure mode was never a
              missing node, it was a surviving one.

USAGE in a builder payload:

    PAYLOAD = material_graph.CLEAR_SRC + material_graph.ASSERT_SRC + '''
    ...
    _c = _ll_clear_graph(_mel, _mat)
    _out["clear"] = _c
    if _c["remaining"]:
        raise RuntimeError("graph not empty after total clear")
    ...build...
    _a = _ll_assert_graph(_mel, _mat, _want_texture_paths)
    _out["assert"] = _a
    if not _a["exact"]:
        raise RuntimeError("graph does not match spec")
    '''

The host side then calls `report(result)` to print both, so a nonzero
survivor count is visible on EVERY run rather than only when someone
goes looking.

NOTE ON BRACES. These fragments are concatenated into payload templates
that are themselves passed through str.format(). Any literal brace in
here must be DOUBLED, or format() consumes it — a logged trap
("Replacement index 0 out of range"). The fragments below therefore use
no single braces in format strings; they build messages by
concatenation instead.
"""

from __future__ import annotations

# --------------------------------------------------------------------
# Injected into the editor payload. Deliberately dependency-free.
# --------------------------------------------------------------------

CLEAR_SRC = '''
def _ll_clear_graph(_mel, _mat):
    """Total clear of a material graph. Returns survivor counts.

    delete_all_material_expressions does NOT delete all material
    expressions -- custom outputs and some node types survive it. This
    deletes every survivor explicitly and re-reads, so the caller can
    refuse rather than build on debris.
    """
    _mel.delete_all_material_expressions(_mat)
    _survivors = list(_mel.get_material_expressions(_mat))
    for _e in _survivors:
        try:
            _mel.delete_material_expression(_mat, _e)
        except Exception:
            pass
    _remaining = list(_mel.get_material_expressions(_mat))
    return {"survived": len(_survivors), "remaining": len(_remaining)}

'''

WIRE_SRC = '''

def _ll_wire(_mel, _from, _from_pin, _to, _to_pin):
    """connect_material_expressions, CHECKED. Raises on a failed connect.

    SHARED INFRASTRUCTURE under CLAUDE.md non-negotiable 4a: the same
    silent-failure surface exists in every builder in this repo (93
    connections in the landscape material, 30 in the layer debug
    material, 10 in the foliage material), so it is fixed once here
    rather than patched per tool.

    THE DEFECT IT CLOSES, read at the source rather than inferred
    (MaterialEditingLibrary.cpp:928-943, UE 5.8):

        bool UMaterialEditingLibrary::ConnectMaterialExpressions(...)
        {
            bool bResult = false;
            if (FromExpression && ToExpression)
            {
                FExpressionInput* Input = GetExpressionInputByName(...);
                int32 FromIndex = GetExpressionOutputIndexByName(...);
                if (Input && FromIndex != INDEX_NONE)
                {
                    Input->Connect(FromIndex, FromExpression);
                    bResult = true;
                    ...

    **An unresolvable pin name returns false and connects nothing.** The
    input keeps its default -- 0 for a scalar, black for a colour -- and
    the material COMPILES CLEAN, because an unconnected input is legal.
    Every builder in this repo discarded that return value.

    That is the project's worst failure shape: a wiring mistake that
    reports success and renders plausibly. A mask input left at 0 blends
    nothing; a height input left at 0 turns a height blend into a linear
    lerp with no error anywhere.

    Pin names are also exactly the thing non-negotiable 23 says not to
    trust from memory, and this is the check that makes a wrong guess
    LOUD instead of silent.
    """
    if not _mel.connect_material_expressions(_from, _from_pin, _to,
                                             _to_pin):
        raise RuntimeError(
            "connect FAILED: {0}.{1!r} -> {2}.{3!r}. The pin name did "
            "not resolve, so NOTHING was connected and the input kept "
            "its default. Check both pin names against the node class."
            .format(type(_from).__name__, _from_pin,
                    type(_to).__name__, _to_pin))

'''

ASSERT_SRC = '''
def _ll_assert_graph(_mel, _mat, _want, _distinct=False):
    """Post-build assertion: the sampled texture set must EQUAL spec.

    _want is a list of texture object paths (or short asset names).
    EXTRA samplers are a failure, not a warning: the defect this guards
    against is a SURVIVING node, never a missing one.

    _distinct=False (default) compares MULTISETS -- a texture sampled
    twice must be declared twice. Use this wherever the sampler count is
    fixed and known; it is the stricter check.

    _distinct=True compares DISTINCT SETS. Use only where one texture is
    legitimately sampled a variable number of times -- the landscape
    material samples each surface at a detail AND a macro scale, so its
    multiplicities are a function of the recipe, not a constant. The set
    check still catches a texture that should not be present at all,
    which is the debris signature.
    """
    _got = []
    for _e in _mel.get_material_expressions(_mat):
        if type(_e).__name__ != "MaterialExpressionTextureSample":
            continue
        _t = _e.get_editor_property("texture")
        if _t is None:
            _got.append("<none>")
            continue
        _got.append(_t.get_path_name().split("/")[-1].split(".")[0])

    def _norm(_x):
        return _x.split("/")[-1].split(".")[0]

    _wn = [_norm(_w) for _w in _want]
    # Multiset comparison by default; distinct-set when the caller says
    # the multiplicity is recipe-dependent rather than fixed.
    if _distinct:
        _g = sorted(set(_got))
        _w = sorted(set(_wn))
    else:
        _g = sorted(_got)
        _w = sorted(_wn)
    _extra = list(_g)
    for _x in _w:
        if _x in _extra:
            _extra.remove(_x)
    _missing = list(_w)
    for _x in _g:
        if _x in _missing:
            _missing.remove(_x)
    return {"got": _g, "want": _w, "extra": _extra, "missing": _missing,
            "exact": (not _extra) and (not _missing)}

'''


def report(result, prefix="  "):
    """Print the clear and assert blocks from a builder's result dict.

    Printed on EVERY run. A nonzero survivor count is the signature of
    the class this module exists to contain, and it must not require
    anyone to go looking for it.
    """
    out = []
    c = (result or {}).get("clear")
    if c:
        out.append(
            "{0}graph clear  : {1} survived delete_all_material_expressions,"
            " {2} remaining after the explicit total clear"
            .format(prefix, c.get("survived"), c.get("remaining")))
        if c.get("remaining"):
            out.append("{0}  *** graph was NOT emptied ***".format(prefix))
    a = (result or {}).get("assert")
    if a:
        out.append("{0}graph assert : {1}".format(
            prefix, "EXACT match to spec" if a.get("exact")
            else "*** DOES NOT MATCH SPEC ***"))
        if a.get("extra"):
            out.append("{0}  EXTRA samplers (debris): {1}".format(
                prefix, ", ".join(a["extra"])))
        if a.get("missing"):
            out.append("{0}  MISSING samplers: {1}".format(
                prefix, ", ".join(a["missing"])))
        if not a.get("exact"):
            out.append("{0}  got : {1}".format(prefix,
                                               ", ".join(a.get("got", []))))
            out.append("{0}  want: {1}".format(prefix,
                                               ", ".join(a.get("want", []))))
    for line in out:
        print(line)
    return out


def verdict(result):
    """True only if the graph was emptied AND matches spec exactly."""
    c = (result or {}).get("clear") or {}
    a = (result or {}).get("assert") or {}
    return (c.get("remaining") == 0) and bool(a.get("exact"))
