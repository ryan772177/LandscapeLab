"""audit_material_samplers.py — read a BUILT material and audit every sampler.

Reads the live material's graph, enumerates every TextureSample, and
compares each node's `sampler_type` against what the TEXTURE ASSET's own
import settings require. Reports, and exits non-zero on any mismatch.

WHY THIS EXISTS SEPARATELY FROM THE BUILDER
--------------------------------------------
`make_landscape_material` already refuses a sampler whose declared type
disagrees with the asset. That check runs INSIDE the build, from the same
declaration that chose the type — so it proves the builder is
self-consistent, not that the shipped material is correct.

CLAUDE.md non-negotiable 8: verify with a DIFFERENT instrument than the
one that made the claim. This reads the artefact after the fact and knows
nothing about the plan, the declaration, or the recipe. It asks the
material what it contains and asks each texture what it needs.

It therefore also covers materials this repo did NOT build — vendor
materials from a Fab pack, or anything hand-edited in the editor — which
is why it takes an arbitrary asset path.

WHAT A MISMATCH MEANS
---------------------
The compiler refuses most sampler mismatches by name
(MaterialExpressionUtils::VerifySamplerType, which errors on EVERY
mismatch and applies an EXTRA sRGB check for Normal and Masks). So a
mismatch found here on a COMPILING material usually means something
rewrote the node after the compile — most likely `AutoSetSampleType`,
which fires on texture assignment and silently overwrites the declared
type (MaterialExpressions.cpp:2625-2634).

Exit codes:
  0  every sampler agrees with its texture
  2  editor gate refused, or the material is missing
  4  at least one sampler disagrees
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap          # noqa: E402
import verify_landscape   # noqa: E402

MARKER = "__LANDSCAPELAB_SAMPLERAUDIT__"

# What each compression setting REQUIRES, derived from the engine's own
# rule (MaterialExpressionUtils.cpp:33-49): single-channel -> Grayscale
# or LinearGrayscale by sRGB; normal maps -> Normal; masks -> Masks;
# everything else -> Color or LinearColor by sRGB.
PAYLOAD = '''
import json as _json
import unreal as _unreal

_out = {{"rows": [], "error": None, "exists": False,
         "expr_before": None, "expr_after": None, "scratch_left": None}}
try:
    _p = {path!r}
    if _unreal.EditorAssetLibrary.does_asset_exist(_p):
        _out["exists"] = True
        _mat = _unreal.EditorAssetLibrary.load_asset(_p)
        _mel = _unreal.MaterialEditingLibrary
        # THIS AUDIT MUTATES A SHARED LIVE MATERIAL. It creates a scratch
        # TextureSample per sampler to ask the engine what each texture
        # needs, and deletes it again. Three separate defects in this
        # project have been orphaned nodes left in a graph
        # (8bbe231d, 9f5d573e, M_fir_bark->twig), and
        # `delete_all_material_expressions` has already been caught
        # leaving 7 wired survivors. So the count is taken BEFORE and
        # AFTER and the caller asserts they match — non-negotiable 25: a
        # claim worth making is a claim worth asserting.
        _out["expr_before"] = len(_mel.get_material_expressions(_mat))
        # isinstance, NOT an exact class-name match. The old form was
        #     type(_e).__name__ != "MaterialExpressionTextureSample"
        # which is blind to every SUBCLASS -- and the whole
        # TextureSampleParameter family are subclasses. Run against
        # M_C0_House, a material with three parameter samplers, it audited
        # ZERO and printed "0 sampler(s) audited, 0 mismatch(es)", which
        # reads as a clean pass and is actually "I could not look"
        # (non-negotiable 6). Found 2026-08-30.
        for _e in _mel.get_material_expressions(_mat):
            if not isinstance(_e,
                              _unreal.MaterialExpressionTextureSample):
                continue
            _row = {{"node": type(_e).__name__, "texture": None,
                     "declared": None, "compression": None, "srgb": None,
                     "engine_expects": None}}
            _t = _e.get_editor_property("texture")
            _row["declared"] = str(_e.get_editor_property("sampler_type"))
            if _t is not None:
                _row["texture"] = _t.get_path_name().split(".")[0]
                _row["compression"] = str(
                    _t.get_editor_property("compression_settings"))
                _row["srgb"] = bool(_t.get_editor_property("srgb"))
                # Ask the ENGINE what this asset needs, by assigning it to
                # a scratch node and reading what AutoSetSampleType picks.
                # That is the engine's own answer, not a transcription of
                # its switch statement.
                _scratch = _mel.create_material_expression(
                    _mat, _unreal.MaterialExpressionTextureSample, -9000,
                    -9000)
                _scratch.set_editor_property("texture", _t)
                _row["engine_expects"] = str(
                    _scratch.get_editor_property("sampler_type"))
                _mel.delete_material_expression(_mat, _scratch)
            _out["rows"].append(_row)
        _exprs = _mel.get_material_expressions(_mat)
        _out["expr_after"] = len(_exprs)
        _left = 0
        for _e in _exprs:
            try:
                if (int(_e.get_editor_property(
                        "material_expression_editor_x")) == -9000
                        and int(_e.get_editor_property(
                            "material_expression_editor_y")) == -9000):
                    _left += 1
            except Exception:
                pass
        _out["scratch_left"] = _left
except Exception as _exc:
    _out["error"] = str(_exc)[:400]

print("{marker}" + _json.dumps(_out))
'''


def _parse(text):
    i = (text or "").find(MARKER)
    if i < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(
            text[i + len(MARKER):].lstrip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--material", default="/Game/Materials/M_AutoLandscape")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    print("REPO_ROOT : {0}".format(bootstrap.REPO_ROOT))
    print("material  : {0}".format(args.material))
    print("")

    remote_exec = bootstrap._load_remote_execution()
    remote = remote_exec.RemoteExecution()
    remote.start()
    try:
        node, reason = verify_landscape._select_verified_node(
            remote_exec, remote, bootstrap._norm(bootstrap.UE_PROJECT_ROOT),
            args.timeout)
        if node is None:
            print("REFUSE (rule 7): {0}".format(reason))
            return 2
        try:
            remote.open_command_connection(node["node_id"])
            r = remote.run_command(
                PAYLOAD.format(path=args.material, marker=MARKER),
                unattended=True, exec_mode=remote_exec.MODE_EXEC_FILE)
            if not r or not r.get("success"):
                print("command failed: {0}".format((r or {}).get("result")))
                return 2
            data = _parse(bootstrap._collect_output(r))
        finally:
            try:
                remote.close_command_connection()
            except Exception:
                pass
    finally:
        remote.stop()

    if data is None:
        print("REFUSE: no parseable result from the editor.")
        return 2
    if data.get("error"):
        print("REFUSE: editor-side error: {0}".format(data["error"]))
        return 2
    if not data.get("exists"):
        print("REFUSE: material not found: {0}".format(args.material))
        return 2

    # POST-CONDITION FIRST: this audit added and removed scratch nodes in
    # a shared live material. If it did not clean up, the sampler verdict
    # is the less important half of what just happened.
    before, after = data.get("expr_before"), data.get("expr_after")
    left = data.get("scratch_left")
    print("graph expressions: before {0}, after {1}; scratch nodes left "
          "at (-9000,-9000): {2}".format(before, after, left))
    if before is None or after is None or left is None:
        print("REFUSE: could not verify scratch-node cleanup. The audit "
              "mutated a shared material and cannot prove it undid it.")
        return 2
    if before != after or left != 0:
        print("")
        print("REFUSE: THIS AUDIT LEFT DEBRIS IN A LIVE MATERIAL.")
        print("  {0} expression(s) added and not removed; {1} scratch "
              "node(s) still at the scratch position.".format(
                  after - before, left))
        print("  DO NOT SAVE this material. Reload the asset without")
        print("  saving to discard the in-memory graph, then fix the")
        print("  cleanup path before re-running.")
        return 2
    print("")

    rows = data["rows"]
    bad = []
    print("{0:<34} {1:<26} {2:<26} {3}".format(
        "texture", "declared", "engine expects", "verdict"))
    for row in sorted(rows, key=lambda r: (r["texture"] or "")):
        short = (row["texture"] or "<none>").split("/")[-1]
        dec = (row["declared"] or "").split(".")[-1].split(":")[0]
        exp = (row["engine_expects"] or "").split(".")[-1].split(":")[0]
        ok = (row["texture"] is None) or (dec == exp)
        if not ok:
            bad.append(row)
        print("{0:<34} {1:<26} {2:<26} {3}".format(
            short[:34], dec[:26], exp[:26], "ok" if ok else "MISMATCH"))

    print("")
    print("{0} sampler(s) audited, {1} mismatch(es).".format(
        len(rows), len(bad)))
    # ZERO AUDITED ON A NON-EMPTY GRAPH IS "I COULD NOT LOOK", NOT A PASS.
    # Added 2026-08-30 with the isinstance fix, because the two are the same
    # defect seen from opposite ends: the enumerator was blind to parameter
    # samplers, and the verdict happily printed "0 audited, 0 mismatches"
    # over a material carrying three of them. Fixing the blindness without
    # fixing the verdict would leave the next blind spot equally silent.
    if not rows and before:
        print("")
        print("REFUSE: the graph holds {0} expression(s) and NOT ONE was "
              "recognised as a".format(before))
        print("  texture sampler. That is a failed measurement, not a clean")
        print("  material — non-negotiable 6. Either this material genuinely")
        print("  samples nothing, in which case say so deliberately, or the")
        print("  enumerator is blind to the node class it uses.")
        return 5
    if bad:
        print("")
        print("A mismatch on a material that COMPILES usually means something")
        print("rewrote the node after the compile — most likely")
        print("AutoSetSampleType firing on a later texture assignment.")
        return 4
    print("")
    print("This audit read the BUILT graph and asked the ENGINE what each")
    print("asset needs. It shares no code with the builder's own check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
