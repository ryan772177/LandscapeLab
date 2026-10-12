"""town_kit_verify.py -- census the placed kit town FROM THE WORLD against the manifest (read-only, 2026-10-08).

    python scripts/town_kit_verify.py

Re-enumerates every actor carrying the manifest tag (LandscapeLab.TownKit) in the open level and, per actor, sums
the instance counts of its InstancedStaticMeshComponents. Compared with city/alpine_basin_town_kit_manifest.json
in BOTH directions: every manifest label present once with exactly its piece count, and no tagged actor that the
manifest does not name. A different instrument from the placer's own per-batch read-back (that one reads the
components it just wrote; this one finds the actors by tag, after the fact). Run before and after the save.
Exit 0 = exact match; 4 = any difference or nothing counted (rule 13).
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bootstrap  # noqa: E402

PAYLOAD = r'''
import json as _json, unreal as _u
CFG = _json.loads(r"""__CFG__""")
_out = {"ok": False}
_w = _u.get_editor_subsystem(_u.UnrealEditorSubsystem).get_editor_world()
_out["level"] = _w.get_path_name().split(".")[0]
_rows = {}
_ovs = {}
if _out["level"] == CFG["level"]:
    for _a in _u.get_editor_subsystem(_u.EditorActorSubsystem).get_all_level_actors():
        if CFG["tag"] not in [str(t) for t in _a.tags]:
            continue
        _n = 0
        _ov = {}
        for _c in _a.get_components_by_class(_u.InstancedStaticMeshComponent):
            _n += _c.get_instance_count()
            _om = [(_m.get_path_name().split(".")[0] if _m is not None else None)
                   for _m in (_c.get_editor_property("override_materials") or [])]
            if _om:
                _ov[_c.get_name()] = _om
        _rows.setdefault(_a.get_actor_label(), []).append(_n)
        _ovs.setdefault(_a.get_actor_label(), []).append(_ov)
    _out["ok"] = True
_out["rows"] = _rows
_out["overrides"] = _ovs
print("__LL__" + _json.dumps(_out))
'''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    man = json.load(io.open(os.path.join(bootstrap.REPO_ROOT, "city", "alpine_basin_town_kit_manifest.json"),
                            encoding="utf-8"))
    want = {h["label"]: len(h["pieces"]) for h in man["houses"]}
    # 2026-10-11 roof variety: exactly the ISM material overrides the manifest asks for, and NO other (a stale
    # grade left on a reused ISM is what this catches)
    want_ov = {h["label"]: dict(("ISM_" + p["mesh"][3:], [p["material"]]) for p in h["pieces"] if p.get("material"))
               for h in man["houses"]}
    import ue_exec
    cfg = {"level": man["level_path"], "tag": man["tag"]}
    code, out, raw = ue_exec.run(PAYLOAD.replace("__CFG__", json.dumps(cfg)), marker="__LL__", timeout=25,
                                 stage_name="town_kit_verify")
    if not isinstance(out, dict) or not out.get("ok"):
        print("COULD NOT LOOK (code %s): %s" % (code, out if isinstance(out, dict) else (raw or "")[-800:]))
        return 4
    got = out["rows"]
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    dup = sorted(k for k, v in got.items() if len(v) != 1)
    wrong = sorted(k for k in set(want) & set(got) if len(got[k]) == 1 and got[k][0] != want[k])
    n_inst = sum(sum(v) for v in got.values())
    gov = out.get("overrides", {})
    wrong_ov = sorted(k for k in set(want) & set(got) if len(got[k]) == 1 and gov.get(k, [{}])[0] != want_ov[k])
    n_ov = sum(len(v[0]) for v in gov.values() if len(v) == 1)
    print("level %s  tag %s" % (out["level"], man["tag"]))
    print("manifest houses %d, pieces %d" % (len(want), sum(want.values())))
    print("world    actors %d, instances %d" % (sum(len(v) for v in got.values()), n_inst))
    print("material overrides: manifest %d, world %d, houses differing %d"
          % (sum(len(v) for v in want_ov.values()), n_ov, len(wrong_ov)))
    print("missing %d  extra %d  duplicate labels %d  wrong instance count %d"
          % (len(missing), len(extra), len(dup), len(wrong)))
    for name, lst in (("missing", missing), ("extra", extra), ("dup", dup), ("wrong", wrong), ("wrong_ov", wrong_ov)):
        if lst:
            print("  %s: %s" % (name, lst[:10]))
    ok = got and not (missing or extra or dup or wrong or wrong_ov)
    print("VERDICT: %s" % ("EXACT MATCH" if ok else "DIFFERS"))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
