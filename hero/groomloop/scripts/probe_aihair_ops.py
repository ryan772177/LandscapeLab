"""probe_aihair_ops.py -- what does the AI Hair Toolkit actually expose?

    blender --background --python probe_aihair_ops.py -- <out.json>

The operator found the panel and ran a generation through it, so the operator
surface exists. This asks it what it is rather than inferring it from the UI:
every operator in its namespace, with its arguments and their types, so a
decision about "use the add-on's loader" can be made against a signature
instead of a screenshot.

The question that decides the plan: does any loader take a FILEPATH? If it does,
the hash-pinned repo npz can go through the add-on's own import and optimizer.
If it only reads the runtime's session output, then the add-on path is bound to
whichever generation is live in that session -- and this project's payload is
the one in the repo.

An API remembered is an API guessed; this one is enumerated.
"""

import json
import os
import sys

import bpy


def main():
    a = sys.argv
    out = (a[a.index("--") + 1:] or ["aihair_ops.json"])[0]
    rep = {"addons_enabled": [], "namespaces": {}, "panels": []}

    try:
        import addon_utils
        for m in addon_utils.modules():
            n = m.__name__
            if addon_utils.check(n)[1]:
                rep["addons_enabled"].append(n)
    except Exception as e:
        rep["addon_error"] = str(e)[:200]

    # Every operator namespace, then anything that smells like this add-on.
    for ns in sorted(dir(bpy.ops)):
        if ns.startswith("_"):
            continue
        mod = getattr(bpy.ops, ns)
        names = [x for x in dir(mod) if not x.startswith("_")]
        if not names:
            continue
        if any(k in ns.lower() for k in ("hair", "groom", "ai", "strand")):
            entry = {}
            for nm in names:
                op = getattr(mod, nm)
                try:
                    rna = op.get_rna_type()
                    props = []
                    for p in rna.properties:
                        if p.identifier == "rna_type":
                            continue
                        props.append("%s:%s" % (p.identifier, p.type))
                    entry[nm] = {"label": rna.name, "props": props}
                except Exception as e:
                    entry[nm] = {"error": str(e)[:120]}
            rep["namespaces"][ns] = entry

    for t in dir(bpy.types):
        if t.startswith("_"):
            continue
        try:
            cls = getattr(bpy.types, t)
            lbl = getattr(cls, "bl_label", None)
            if lbl and any(k in str(lbl).lower()
                           for k in ("hair", "groom", "strand")):
                rep["panels"].append(
                    {"class": t, "label": str(lbl),
                     "category": str(getattr(cls, "bl_category", "")),
                     "space": str(getattr(cls, "bl_space_type", ""))})
        except Exception:
            pass

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    json.dump(rep, open(out, "w", encoding="utf-8"), indent=2)
    print("__OPS__" + json.dumps(rep))


if __name__ == "__main__":
    main()
