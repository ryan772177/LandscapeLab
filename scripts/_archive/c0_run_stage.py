"""Host side of the C0 stage build: inject the slot->role table, run, report."""
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    with io.open(os.path.join(REPO, "recipes", "c0_materials.json"),
                 encoding="utf-8") as fh:
        man = json.load(fh)
    slot_role = {}
    for role, spec in man["roles"].items():
        for s in spec["slots"]:
            slot_role[s] = role

    with io.open(os.path.join(REPO, "scripts",
                              "c0_build_stage_payload.txt"),
                 encoding="utf-8") as fh:
        tmpl = fh.read()
    assert "SLOT_ROLE_JSON" in tmpl, "payload lost its substitution point"
    out = os.path.join(REPO, "LandscapeLab", "Saved", "c0_stage_gen.txt")
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write(tmpl.replace("SLOT_ROLE_JSON", repr(slot_role)))

    p = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ue_exec.py"),
         out, "--timeout", "25"], capture_output=True, text=True)
    t = p.stdout or ""
    i, j = t.find("{"), t.rfind("}")
    if i < 0:
        print("NO RESULT FROM THE EDITOR -- that is 'could not look'.")
        print(t[-1500:])
        print((p.stderr or "")[-500:])
        return 5
    r = json.loads(t[i:j + 1])
    if r.get("error"):
        print("STAGE FAILED: " + str(r["error"])[:500])
    print("")
    print("  level      %s   saved %s" % (r.get("level"), r.get("saved")))
    print("  ground     %s m square, flat" % r.get("ground_scale_m"))
    ex = r.get("exposure_readback") or {}
    print("  exposure   %s bias %s overridden %s"
          % (ex.get("method"), ex.get("bias"), ex.get("bias_overridden")))
    for a in r.get("actors", []):
        print("  %-9s y %+8.1f  z %8.2f  base_z %6.2f  slots_bound %d"
              % (a["label"], a["y_cm"], a["z_cm"], a["base_z_cm"],
                 a["slots_bound"]))
    print("  bases equal   %s" % r.get("both_bases_equal"))
    print("  base on plane %s" % r.get("base_on_plane"))
    print("  bind failures %s" % r.get("bind_failures"))
    print("")
    print("STAGE %s" % ("OK" if r.get("ok") else "!! NOT OK"))
    return 0 if r.get("ok") else 4


if __name__ == "__main__":
    sys.exit(main())
