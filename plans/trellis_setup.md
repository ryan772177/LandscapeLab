# TRELLIS setup — image-to-3D for the hero's face

*Started 2026-08-15. Goal: turn Ryan's rogue-warrior portrait into a 3D head
mesh, which Unreal's **Mesh to MetaHuman** conform then reads as SHAPE to
produce a matching MetaHuman face.*

**Why this exists:** `MetaHumanGenerator` cannot do it. Its complete surface
is nine tool calls — create, begin/end edit, and get/set for body shape, skin
tone and eye colour. No image input, no face generation (searched: zero
matches for image/photo/reference/conform/face/scan/mesh/sculpt). Ryan's
original instinct — TRELLIS → mesh → conform — is the only automated route
from the reference image to a matching face.

---

## THE RULING: ORIGINAL TRELLIS, NOT TRELLIS.2

Ryan asked for TRELLIS.2 with original TRELLIS as a pre-authorised fallback.
**Taking the fallback, on two measured grounds:**

| | TRELLIS.2-4B | TRELLIS-image-large |
|---|---|---|
| stated min VRAM | **24 GB** | **16 GB** |
| this machine | 16,303 MiB | 16,303 MiB |
| params | 4B | 1.2B |
| verified on | A100, H100 | A100, A6000 |

TRELLIS.2's stated minimum is above this card. That is a model-size fact, not
a build problem to engineer around.

---

## THE REAL RISK IS THE CUDA EXTENSIONS, NOT THE MODEL

**TRELLIS is tested on CUDA 11.8 / 12.2 and installs PyTorch 2.4.0+cu118 by
default. This GPU is Blackwell — `sm_120` — which needs CUDA 12.8+.**
PyTorch 2.4/cu118 has no `sm_120` support at all, so **the documented install
path cannot work here** and neither project mentions Blackwell.

So the plan is a newer PyTorch (cu128+) with all seven extensions built
against it:

    xformers  flash-attn  diffoctreerast  spconv  mip-splatting
    kaolin    nvdiffrast

Several are older projects meeting a toolchain years newer than they expect.
**Expect some to fail and to need substitution or patching.** `xformers` can
stand in for `flash-attn`; the renderers are the ones with no easy substitute.

**This is the honest failure mode: not "the model won't fit" but "extension N
won't compile".**

---

## PROGRESS — updated 2026-08-16, post-reboot

| Step | State |
|---|---|
| Blender | **DONE** — 5.2.0 LTS, `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`, `--version` verified |
| WSL optional features | **DONE** — both read `Enabled` after the reboot |
| WSL core | **DONE** — Microsoft.WSL 2.7.11 via winget, kernel 6.18.33.2 |
| 1. distro | **DONE** — `Ubuntu-24.04`, and see the switch below |
| 2. GPU inside WSL | **PASSED** — the gate; numbers below |
| 3. CUDA toolkit | **DONE** — 12.8.93, `nvcc` verified, gcc 13.3.0 |
| 4. PyTorch cu128 + sm_120 gate | in flight |
| 5. TRELLIS + 7 extensions | not started — **this is the risk** |
| 6. weights | not started |
| 7. pipeline + Blender pass + e2e | not started |
| hero input | **DONE** — `hero/reference/`, adopted and hash-proven |

**Install root:** `/opt/trellis` inside WSL, with miniforge at `/opt/miniforge3`
and the env `trellis` on **Python 3.11**. A Linux-filesystem path, because
building CUDA extensions across `/mnt/c` is slow and permission-fragile.
Outside both project roots — standing rule 1 — authorised by Ryan for this task.

### The gate, passed

    nvidia-smi (inside WSL)   RTX 5080 Laptop GPU, 16303 MiB
                              KMD 610.88  — the WINDOWS driver, as designed
                              CUDA UMD 13.3 — well ahead of the 12.8 floor
    /dev/dxg                  present
    /usr/lib/wsl/lib          libcuda.so + full stack + nvidia-smi

### THE DISTRO WAS SWITCHED, 26.04 → 24.04, ON A MEASURED GROUND

`wsl --install -d Ubuntu` now installs **Ubuntu 26.04 LTS**, not 24.04.
26.04 ships **Python 3.14.3** and offers **no `python3.11` or `python3.12`
package at all** — `apt-cache policy` returns nothing for both. TRELLIS and its
seven extensions have no cp314 wheels and are tested on far older stacks.

**One assumption I made was WRONG and checking is what settled it:** I expected
NVIDIA to publish no `ubuntu2604` CUDA repo. **It does.** That was not the
problem; the Python floor was. Do not re-derive this as a repo issue.

24.04 was verified BEFORE 26.04 was touched — Python 3.12.3, glibc 2.39,
gcc 13.2, same GPU visible — then 26.04 unregistered, so exactly one distro
exists. Two plausible distros is the `LandscapeLab 5.8` duplicate hazard again.

**Python 3.11, not the distro's 3.12**, because **3.12 removed `distutils`** and
several of these older extensions still `import distutils` in `setup.py`.

### TWO INVOCATION TRAPS — both produced a wrong reading, both cost a retry

1. **PowerShell 5.1 mangles quoted arguments to `wsl.exe`.** A single-quoted
   `bash -lc` payload arrived split at the first space and bash died on an
   unterminated `if`. **Use the Bash tool with `MSYS2_ARG_CONV_EXCL='*'`.**
2. **Git Bash rewrites absolute paths** — `/usr/lib/wsl/lib/nvidia-smi` became
   `C:/Program Files/Git/usr/lib/...`. Same msys hazard this repo already hooks.
3. And once inside: **quote `$PATH`.** The WSL `PATH` inherits Windows entries
   containing `Program Files (x86)`, and an unquoted expansion makes bash choke
   on the parenthesis.

---

## REMAINING, IN ORDER

4. **Verify `torch.cuda.get_device_capability()` reports `(12, 0)`** — the
   sm_120 gate, and the whole reason for the version deviation. A `torch` that
   imports and reports a device is NOT the gate; it must report `(12, 0)` and
   actually execute a kernel.
5. Clone TRELLIS, install extensions **piecewise, never `setup.sh` whole**, so a
   failing extension is attributable to itself
6. Weights: `microsoft/TRELLIS-image-large` (~15 GB with deps)
7. The pipeline script, the Blender pass, then an end-to-end test

---

## THE INPUT IS SETTLED — `hero/reference/hero_face_bald_headcrop.png`

Four Gemini portraits adopted from Downloads into `hero/reference/`, copies at
stable names with SHA-256 proven equal to their sources at adoption time.
`hero/reference/README.md` carries the table.

**The BALD frontal is the input, and that is a geometry argument, not taste.**
Mesh to MetaHuman reads SHAPE. TRELLIS reconstructs hair as a solid volume
fused to the skull, corrupting the exact cranial silhouette the conform fits
against; a beard does the same to the mandible. The haired variant is the same
face and stays useful as the groom reference and as an independent check that
the result reads as one person.

`scripts/prepare_hero_input.py` crops it to head-and-neck **by measurement**
(chroma, because the grey background sits under a radial vignette that defeats
any luminance model), writing a sidecar with the full derivation. Gate proven
in both directions: it refuses both full-body images, passes both portraits.

Output: 636×636, box `(364, 0, 1000, 636)`, `c039ab4f…`.

## WHAT THE DELIVERABLE IS

A script taking one portrait and producing, in `/output`:

- **GLB** and **OBJ** from TRELLIS
- an **FBX** from a headless Blender pass
  (`blender --background --python`) that centres the mesh, strips loose
  geometry, and exports

**Geometry fidelity over texture quality** — Mesh to MetaHuman reads shape
only, so texture settings are the first thing to trade away for resolution.

**Acceptance: verified end-to-end on a test image before it is called done.**
