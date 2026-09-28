"""test_push_heightmap.py — regression tests for push_heightmap.py.

LOCAL ONLY. Contacts no editor, writes nothing, imports nothing into
Unreal. It renders the payload templates and asserts properties of the
rendered text plus the host-side arithmetic.

WHY THESE EXIST, specifically
Ryan's ruling of 2026-08-01: *"Confirm before push: TC_HDR_F32 change and
the hit_actor fix are both in and both exercised by a test that would fail
if reverted. A fix that only passes because the path isn't hit doesn't
count."*

That is the standard each test below is written to. Every assertion names
the reverted form it is guarding against, and each was confirmed to FAIL
when the fix is reverted — not merely to pass when it is present. A test
that passes both before and after a fix is measuring nothing.

Run: python scripts/test_push_heightmap.py
Exit 0 = all pass. Exit 1 = at least one failed (the failures are printed).
"""

from __future__ import annotations

import ast
import io
import json
import os
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landscape_spec              # noqa: E402
import make_landscape_material as mlm  # noqa: E402
import push_heightmap as ph        # noqa: E402

FAILURES = []


def code_only(text):
    """Return `text` with comments removed, so a 'must not contain X'
    assertion measures EXECUTABLE code and not the comment that explains
    why X is wrong.

    This is not fussiness. The first version of this file grepped raw
    payload text and reported three failures that were all comments
    documenting the very traps being guarded against — a test that fires
    on its own documentation is a test nobody will keep. Tokenising is
    exact where a regex would not be.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        # Fall back to the raw text rather than silently passing a check
        # on an empty string.
        return text
    return "\n".join(out)


def _executable_body(src):
    """`src` with the audit-record tuples blanked out, by AST range.

    The BLOCK records quote the defective code they describe — D1's text
    contains the literal `med * 3 + unit_cm`. A textual "the derived
    tolerance is gone" check therefore fires on the record of its own fix.
    Blanking by AST range is exact; the previous string-split version
    silently changed meaning the moment another record constant was added
    above it, which is how this test came to fail on a correct file.
    """
    tree = ast.parse(src)
    lines = src.split("\n")
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            name = getattr(t, "id", "")
            if name.endswith("_BLOCKS") or name.endswith("_RESOLVED"):
                for i in range(node.lineno - 1, node.end_lineno):
                    lines[i] = ""
    return "\n".join(lines)


def has_token(text, token):
    """True if `token` appears as a standalone token in executable code.

    Operates on the token STREAM, not on reconstructed text. code_only()
    joins tokens with newlines, so any substring test spanning more than
    one token silently becomes False against it — which is how the first
    version of the revert-proof below passed while testing nothing.
    """
    return token in code_only(text).split("\n")


def code_contains(text, needle):
    """True if `needle` appears anywhere in executable (non-comment) code,
    matched against the token stream joined WITHOUT separators so that
    multi-token needles work."""
    toks = code_only(text).split("\n")
    return needle.replace(" ", "") in "".join(toks).replace(" ", "")


# ---------------------------------------------------------------------
# GUARDS. Each takes the RAW payload text and returns True when the fix
# is present. Section G re-runs these EXACT predicates against reverted
# text and requires False — so a guard and its proof can never drift, and
# a guard that tests nothing is reported as broken rather than as a pass.
# ---------------------------------------------------------------------
GUARDS = {
    "no bare TC_HDR in executable code":
        lambda t: has_token(t, "TC_HDR_F32") and not has_token(t, "TC_HDR"),
    "no fp16 format in executable code":
        lambda t: not any(has_token(t, x) for x in
                          ("RTF_RGBA16F", "RTF_RGBA16f", "SAMPLERTYPE_HALF")),
    "render target format is 32-bit float":
        lambda t: has_token(t, "RTF_RGBA32F") or has_token(t, "RTF_RGBA32f"),
    "no hit_actor read in executable code":
        lambda t: not code_contains(t, "hit_actor"),
    "owner resolved via the hit component":
        lambda t: code_contains(t, "get_owner()"),
    "render target read back before import":
        lambda t: code_contains(t, "read_render_target_raw_pixel_area"),
    "readback passes bNormalize=False":
        lambda t: code_contains(t, "_block,_block,False)"),
    # The parameters the reflected signature calls MaxX/MaxY are WIDTH and
    # HEIGHT: ReadRenderTargetRawPixelArea (KismetRenderingLibrary.cpp:454)
    # forwards them into ReadRenderTargetHelper's Width/Height (:295-304),
    # which builds SampleRect(X, Y, X + Width, Y + Height) (:326). Passing
    # `x0 + block - 1` read a (x0+block-1)-wide rectangle — hundreds of
    # thousands of texels — and the `_i % _block` un-flattening then
    # attributed every sample past the first row to the wrong texel. The
    # call succeeded and the values landed; the meaning was wrong.
    "readback passes WIDTH/HEIGHT, not maxima":
        lambda t: code_contains(t, "_bx0,_by0,_block,_block,")
        and not code_contains(t, "_bx0+_block-1"),
    "readback refuses a short/clamped block":
        lambda t: code_contains(t, "len(_vals)!=_block*_block"),
    "blind read cannot be reported as a match":
        lambda t: code_contains(t, "not_unreadable"),
    "export gates the resident component census":
        lambda t: code_contains(t, "min_section_base")
        and code_contains(t, "_want_components"),
    # A raise anywhere in the payload used to produce NO marker line at
    # all, which upstream cannot tell apart from "the payload never ran".
    # The guaranteed-single-print shape is identified by its
    # unserialisable-result fallback, which only that shape has.
    "payload always prints exactly one result":
        lambda t: code_contains(t, '"result not serialisable: %s"'),
}


def check(name, condition, detail=""):
    if condition:
        print("  PASS  {0}".format(name))
    else:
        print("  FAIL  {0}{1}".format(name, ("  — " + detail) if detail else ""))
        FAILURES.append(name)


def render_push_payload():
    recipe, err = landscape_spec.load_recipe(ph.DEFAULT_RECIPE)
    assert err is None, err
    spec, errors = landscape_spec.derive_spec(recipe)
    assert not errors, errors
    res = int(spec["resolution"])
    ox, oy, az = [float(v) for v in recipe["landscape"]["location_cm"]]
    return ph.PUSH_SOURCE.format(
        res=res, spacing=spec["quads_per_component"],
        scale_xy=float(recipe["landscape"]["scale_xy_cm"]),
        scale_z=float(spec["scale_z"]), loc=[ox, oy, az],
        level=recipe["landscape"]["level_path"], tex=ph.HEIGHT_TEX,
        mat=ph.PUSH_MATERIAL, png="C:/repo/terrain/alpine_heightmap.png",
        want=ph.REQUIRED_TEXTURE_SETTINGS, block=ph.RT_BLOCK,
        blocks=[(0, 0)], expect=json.dumps({"0,0": 12345}),
        marker=ph.PROBE_MARKER), res, az, float(spec["scale_z"])


def render_export_payload():
    """Render EXPORT_SOURCE — the export read-back stage.

    It goes through the same transport as every other payload, so it needs
    the same rendering, ast.parse and '.py' checks. Leaving the newest and
    highest-stakes payload out of the harness is how a defect in it gets
    to the live editor first.
    """
    recipe, err = landscape_spec.load_recipe(ph.DEFAULT_RECIPE)
    assert err is None, err
    spec, errors = landscape_spec.derive_spec(recipe)
    assert not errors, errors
    ox, oy, az = [float(v) for v in recipe["landscape"]["location_cm"]]
    return ph.EXPORT_SOURCE.format(
        res=int(spec["resolution"]), spacing=spec["quads_per_component"],
        scale_xy=float(recipe["landscape"]["scale_xy_cm"]),
        scale_z=float(spec["scale_z"]), loc=[ox, oy, az],
        block=ph.RT_BLOCK, blocks=[(0, 0)],
        ncomp=spec["total_components"], marker=ph.PROBE_MARKER)


def main():
    print("push_heightmap regression tests (local only, no editor)")
    print("")
    payload, res, az, sz = render_push_payload()
    export = render_export_payload()

    # ---------------------------------------------------------------
    print("A. TC_HDR_F32 — the fp16 trap, one stage earlier")
    # Reverting to TC_HDR reintroduces RGBA16F: a 10-bit mantissa, integer
    # spacing of 32 across the top half of the range, terracing the terrain
    # in ~125 cm steps while every stage reports success.
    check("compression setting is TC_HDR_F32",
          ph.REQUIRED_TEXTURE_SETTINGS.get("compression_settings")
          == "TC_HDR_F32",
          "got {0!r}".format(
              ph.REQUIRED_TEXTURE_SETTINGS.get("compression_settings")))
    # The REQUIRED table is what the payload both SETS and READS BACK, so
    # this assertion is on the value that actually reaches the editor —
    # not on a comment.
    check("payload sets TC_HDR_F32 on the imported texture",
          "TC_HDR_F32" in payload)
    for g in ("no bare TC_HDR in executable code",
              "no fp16 format in executable code",
              "render target format is 32-bit float"):
        check(g, GUARDS[g](payload))
    print("")

    # ---------------------------------------------------------------
    print("B. hit_actor — the probe that could only ever report absence")
    trace = ph.TRACE_SOURCE.format(points=json.dumps([[0.0, 0.0]]),
                                   top=1.0, bottom=0.0,
                                   marker=ph.PROBE_MARKER)
    # FHitResult in 5.8 has no actor property (HitResult.h:126-131);
    # `hit_actor` is a break-node pin name. Reading it raises, the old bare
    # except swallowed every sample, and the run reported "no landscape hit
    # under any mapping" — "I couldn't look" as "I looked and it's absent".
    check("no hit_actor read in executable code",
          GUARDS["no hit_actor read in executable code"](trace))
    check("owner resolved via the hit component",
          GUARDS["owner resolved via the hit component"](trace))
    check("trace payload keeps break_hit_result as the fallback",
          "break_hit_result" in trace)
    # The distinguishing behaviour, not just the mechanism: a failed read
    # must be reportable as a failed read.
    check("trace payload distinguishes unreadable from missed",
          "UNREADABLE" in trace.upper() and "MISSED" in trace.upper(),
          "no distinct unreadable/missed outcomes found")
    print("")

    # ---------------------------------------------------------------
    print("C. D1 — the tolerance must not widen itself")
    src = open(ph.__file__, encoding="utf-8").read()
    body = _executable_body(src)
    check("TOLERANCE_UNITS exists and is 4",
          getattr(ph, "TOLERANCE_UNITS", None) == 4)
    check("no derived tolerance at the use site",
          "med * 3.0 + unit_cm" not in body and
          "med * 3 + unit_cm" not in body,
          "a pre-flight-derived tolerance is still live")
    check("tolerance is the named constant, not a bare literal",
          "tol = TOLERANCE_UNITS * unit_cm" in body)
    check("--expect-change exists and does not widen the budget",
          "--expect-change" in src and "expect_change" in body)
    print("")

    # ---------------------------------------------------------------
    print("D. D2 — the render target is measured before the write")
    check("render target read back before import",
          GUARDS["render target read back before import"](payload))
    # bNormalize=False is the entire point and is the opposite of what the
    # name suggests: True selects RCM_UNorm, which scales values outside
    # [0,1] INTO [0,1] and would crush 0..65535 to ~1.0.
    check("readback passes bNormalize=False",
          GUARDS["readback passes bNormalize=False"](payload))
    check("readback happens BEFORE the import call",
          payload.index("read_render_target_raw_pixel_area")
          < payload.index("landscape_import_heightmap_from_render_target"))
    check("an all-flat render target is refused",
          "FLAT" in payload)
    check("verify_rt is classified as before-the-write",
          "verify_rt" in ph.STAGES_BEFORE_WRITE and
          "draw" in ph.STAGES_BEFORE_WRITE and
          "import" not in ph.STAGES_BEFORE_WRITE)
    print("")

    # ---------------------------------------------------------------
    print("D2. The export read-back stage")
    # MaxX/MaxY are WIDTH/HEIGHT (KismetRenderingLibrary.cpp:454 forwards
    # them into ReadRenderTargetHelper's Width/Height at :295-304, which
    # builds SampleRect(X, Y, X + Width, Y + Height) at :326). The maxima
    # form read a rectangle hundreds of texels wide and mis-attributed
    # every sample past the first row while succeeding.
    for g in ("readback passes WIDTH/HEIGHT, not maxima",
              "readback passes bNormalize=False",
              "readback refuses a short/clamped block"):
        check("{0} [export]".format(g), GUARDS[g](export))
        check("{0} [push]".format(g), GUARDS[g](payload))
    # ExportBaseOffset is ComponentsExtent.Min over the components the
    # engine actually exported, i.e. the LOADED ones (LandscapeEdit.cpp
    # :8228, :8261, :2876-2882). "RT texel (gx,gy) IS vertex (gx,gy)" is
    # only true when that minimum is (0,0) and the census is complete.
    check("export gates the resident component census",
          GUARDS["export gates the resident component census"](export))
    check("export payload always prints exactly one result",
          GUARDS["payload always prints exactly one result"](export))
    check("push payload always prints exactly one result",
          GUARDS["payload always prints exactly one result"](payload))
    check("export payload reports the raw R range (decides the encoding)",
          code_contains(export, '"r_min"') and
          code_contains(export, '"r_max"'))
    print("")

    # ---------------------------------------------------------------
    print("E. Lesson 9 — a failed probe is not a negative result")
    ident = ph.IDENTIFY_SOURCE.format(
        res=res, spacing=63, scale_xy=400.0, scale_z=sz,
        loc=[0.0, 0.0, az], marker=ph.PROBE_MARKER)
    check("identify payload records unreadable section_base_x",
          "_unreadable" in ident)
    check("identify payload refuses distinctly when blind",
          "could not be COMPUTED" in ident)
    check("push payload refuses distinctly when blind",
          "could not be COMPUTED" in payload)
    check("blind read cannot be reported as a match",
          GUARDS["blind read cannot be reported as a match"](ident))
    # Two live runs were lost to INVENTED reflected names. Both payloads
    # must now use only names proven live in another script or read at an
    # engine source line. `landscape_components` and `landscape_actor` are
    # the two that failed; `LandscapeActorRef` carries
    # DisplayName="Landscape Actor", which is what made the second one look
    # right (LandscapeStreamingProxy.h:29-36).
    for bad in ('get_editor_property("landscape_components")',
                'get_editor_property("landscape_actor")'):
        check("no invented name {0}".format(bad[21:-1]),
              not code_contains(ident, bad) and
              not code_contains(payload, bad) and
              not code_contains(export, bad))
    check("components enumerated via the proven get_components_by_class",
          code_contains(ident, "get_components_by_class") and
          code_contains(payload, "get_components_by_class") and
          code_contains(export, "get_components_by_class"))
    # section_base_y is UPROPERTY(VisibleAnywhere, BlueprintReadOnly) at
    # LandscapeComponent.h:441 — read at the source line, not guessed, and
    # the export origin gate depends on it.
    check("export reads section_base_y, the reflected name",
          code_contains(export, 'get_editor_property("section_base_y")'))
    print("")

    # ---------------------------------------------------------------
    print("F. Transport and arithmetic invariants")
    for name, text in (("IDENTIFY", ident), ("TRACE", trace),
                       ("PUSH", payload), ("EXPORT", export)):
        ast.parse(text)
        mlm._guard_payload(text)
        check("{0} payload parses and carries no '.py'".format(name),
              ".py" not in text)
    check("datum: v=32768 maps to the actor Z",
          abs(ph.expected_world_z(32768, az, sz) - az) < 1e-9)
    check("datum: v=0 maps to world Z 0",
          abs(ph.expected_world_z(0, az, sz) - 0.0) < 1e-6)
    check("one height unit is scale_z/128",
          abs((ph.expected_world_z(1, az, sz)
               - ph.expected_world_z(0, az, sz)) - sz / 128.0) < 1e-9)
    check("all 8 square symmetries are enumerated",
          len(ph.MAPPINGS) == 8 and len(set(ph.MAPPINGS)) == 8,
          "got {0}".format(len(ph.MAPPINGS)))
    # The mappings must be genuinely distinct as functions, not just as
    # names — a copy-paste that duplicated a lambda would pass a name check.
    seen = {}
    for m in ph.MAPPINGS:
        sig = tuple(ph.texel_to_world(m, c, r, res, 0.0, 0.0, 1.0)
                    for (c, r) in ((0, 1), (2, 0), (3, 5)))
        seen.setdefault(sig, []).append(m)
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    check("no two mappings are the same function", not dupes,
          "duplicates: {0}".format(list(dupes.values())))
    check("D1 and D2 are recorded as RESOLVED",
          len(ph.RESOLVED_BLOCKS) == 2 and
          ph.RESOLVED_BLOCKS[0].startswith("D1") and
          ph.RESOLVED_BLOCKS[1].startswith("D2"))
    # D3 (the export encoding) and D4 (--expect-change is unreachable) were
    # raised by the 2026-08-01 audit of the export read-back stage and need
    # Ryan's ruling. Conduct rule 8: a rewrite does not retire them.
    # This test does NOT assert the tuple is empty — it asserts the GATE
    # works, so it keeps passing once Ryan empties it.
    if ph.UNRESOLVED_BLOCKS:
        # Every entry must carry its own full text, not a label
        # (conduct rule 9): "D3" alone is an index, not content.
        check("each unresolved BLOCK carries its full text inline",
              all(len(b) > 400 for b in ph.UNRESOLVED_BLOCKS),
              "shortest is {0} chars".format(
                  min(len(b) for b in ph.UNRESOLVED_BLOCKS)))
        # The gate must actually stop the run, and must do so BEFORE any
        # editor is contacted. main() is safe to call here for exactly
        # that reason: with UNRESOLVED_BLOCKS non-empty it returns before
        # the recipe is read or a connection is opened.
        check("an unresolved BLOCK refuses at exit 6 before any editor "
              "contact", ph.main([]) == 6)
    else:
        check("UNRESOLVED_BLOCKS is empty (all ruled)", True)
    print("")

    # ---------------------------------------------------------------
    # THE PART THAT MAKES THE ABOVE COUNT.
    # "A fix that only passes because the path isn't hit doesn't count."
    # Each guard is re-run against a REVERTED copy of the text it guards,
    # and must FAIL. A guard that passes on the reverted form is measuring
    # nothing and is reported here as broken.
    print("G. Revert-proofs — each guard must FAIL on the reverted form")
    # Each entry: (guard name, raw text, exact substitution that undoes the
    # fix). The revert is applied to RAW text and the SAME predicate from
    # GUARDS is re-run, so guard and proof cannot drift. Every revert is
    # first asserted to actually change the text — a substitution that
    # matches nothing would make the proof vacuous while printing PASS,
    # which is precisely the failure mode this section exists to prevent.
    reverts = [
        ("no bare TC_HDR in executable code", payload,
         "TC_HDR_F32", "TC_HDR"),
        ("no fp16 format in executable code", payload,
         "RTF_RGBA32F", "RTF_RGBA16F"),
        ("render target format is 32-bit float", payload,
         "RTF_RGBA32F", "RTF_RGBA8"),
        ("no hit_actor read in executable code", trace,
         '_hit.get_editor_property("component")',
         '_hit.get_editor_property("hit_actor")'),
        ("owner resolved via the hit component", trace,
         "_comp.get_owner()", "None"),
        ("render target read back before import", payload,
         "read_render_target_raw_pixel_area", "read_nothing_at_all"),
        ("readback passes bNormalize=False", payload,
         "_block, _block, False)", "_block, _block, True)"),
        ("readback passes bNormalize=False", export,
         "_block, _block, False)", "_block, _block, True)"),
        # The exact defect: the maxima form. This revert restores it, and
        # the guard must reject it.
        ("readback passes WIDTH/HEIGHT, not maxima", export,
         "_bx0, _by0, _block, _block,",
         "_bx0, _by0, _bx0 + _block - 1, _by0 + _block - 1,"),
        ("readback passes WIDTH/HEIGHT, not maxima", payload,
         "_bx0, _by0, _block, _block,",
         "_bx0, _by0, _bx0 + _block - 1, _by0 + _block - 1,"),
        ("readback refuses a short/clamped block", export,
         "len(_vals) != _block * _block", "False"),
        ("readback refuses a short/clamped block", payload,
         "len(_vals) != _block * _block", "False"),
        ("export gates the resident component census", export,
         "_want_components", "-1"),
        ("payload always prints exactly one result", export,
         '"result not serialisable: %s"', '"x"'),
        ("payload always prints exactly one result", payload,
         '"result not serialisable: %s"', '"x"'),
        ("blind read cannot be reported as a match", ident,
         "not _unreadable", "False"),
    ]
    for name, raw, old, new_text in reverts:
        reverted = raw.replace(old, new_text)
        if reverted == raw:
            check("revert for '{0}' actually changes the code".format(name),
                  False,
                  "substitution {0!r} matched nothing — the proof would be "
                  "vacuous".format(old[:40]))
            continue
        check("guard '{0}' FAILS when reverted".format(name),
              not GUARDS[name](reverted),
              "the guard still passes on the reverted form, so it is not "
              "testing anything")
    print("")

    print("=" * 62)
    if FAILURES:
        print("FAILED: {0}".format(", ".join(FAILURES)))
        print("=" * 62)
        return 1
    print("ALL PASS")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
