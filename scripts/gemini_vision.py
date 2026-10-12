# COPIED 2026-10-10 from C:/Users/Admin/Gemini2UE/scripts/gemini_vision.py (sha256 e702079edf4755c6...), the Gemini2UE proving ground.
# Free Gemini API vision (gemini-3.8-flash) for detect / segment / judge; depends on scripts/ai_input_guard.py (R-AIGATE).
# Dependency recorded per standing rule 5: google-genai==2.29.0 (host Python 3.12, pip), key in user env GEMINI_API_KEY.
"""gemini_vision.py - free-tier Gemini API vision: detect, segment, or judge an image as JSON.

What is verified (Google pages dated 2026-10-09, see docs/research_findings.json,
area gemini-free): the API FREE tier has no image generation, but vision-capable
text models such as gemini-3.8-flash are free of charge and support structured
JSON output. Object detection returns box_2d = [ymin, xmin, ymax, xmax]
normalised to 0-1000; segmentation returns a polygon of [x, y] points normalised
to 0-1000. Free-tier inputs and outputs are used by Google to improve products
and may be human-reviewed: send only material you are willing to disclose, and
never send assets listed in recipes/ai_restrictions.json.

SDK: google-genai 2.29.0 (installed on the host). This tool uses
client.models.generate_content with response_mime_type='application/json' and
response_json_schema, the path Google documents as fully supported, and the
GEMINI_API_KEY environment variable (create a free key at
https://aistudio.google.com/apikey). Per-model free rate limits are only shown
in the AI Studio dashboard; this tool does not assume any.

Modes:
    detect   objects as boxes:           {"objects":[{"label","box_2d":[ymin,xmin,ymax,xmax],"confidence"}]}
    segment  objects as polygons:        {"objects":[{"label","polygon":[[x,y],...]}]}
    judge    compare a render to a reference: scores and concrete fixes
    custom   your own prompt + JSON schema file

Every mode writes <out>.json and, for detect/segment, <out>.overlay.png with the
shapes drawn on the image in source pixels (0-1000 coordinates descaled).
--fixture <json> skips the API and runs the parsing and overlay on a saved
response, so the tool can be tested without a key.

Usage:
    python scripts/gemini_vision.py detect refs/concept/sample_concept_01.jpg --out data/vision/sample_concept_01
    python scripts/gemini_vision.py judge render.png --reference refs/concept/x.jpg --out data/vision/judge01
    python scripts/gemini_vision.py detect img.jpg --out x --fixture data/vision/fixture_detect.json

Exit codes: 0 ok, 2 bad arguments / no key / guard refusal, 1 API or parse failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = "gemini-3.8-flash"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMAS = {
    "detect": {
        "type": "object",
        "properties": {
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "box_2d": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4,
                                   "description": "[ymin, xmin, ymax, xmax] normalised to 0-1000"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["label", "box_2d"],
                },
            }
        },
        "required": ["objects"],
    },
    "segment": {
        "type": "object",
        "properties": {
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "polygon": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                                    "description": "outline as [x, y] points normalised to 0-1000"},
                    },
                    "required": ["label", "polygon"],
                },
            }
        },
        "required": ["objects"],
    },
    "judge": {
        "type": "object",
        "properties": {
            "overall_similarity_0_100": {"type": "integer"},
            "composition_0_100": {"type": "integer"},
            "lighting_0_100": {"type": "integer"},
            "materials_0_100": {"type": "integer"},
            "scale_0_100": {"type": "integer"},
            "differences": {"type": "array", "items": {"type": "object", "properties": {
                "what": {"type": "string"}, "where_in_render": {"type": "string"}, "fix": {"type": "string"},
                "cause": {"type": "string", "enum": ["terrain shape/erosion", "material layering", "texture scale/tiling", "projection",
                                                     "lighting", "atmosphere/fog", "foliage density/colour", "post-process/grade", "composition", "other"]},
                "severity": {"type": "string", "enum": ["high", "medium", "low"]}}, "required": ["what", "fix", "severity", "cause"]}},
            "keep": {"type": "array", "items": {"type": "string"}, "description": "what already works and must not change"},
            "one_thing_for_realism": {"type": "string"},
        },
        "required": ["overall_similarity_0_100", "differences", "keep"],
    },
}

PROMPTS = {
    "detect": ("Detect every distinct object, building, vehicle, character, tree group, rock and terrain feature in this image. "
               "Return JSON with 'objects': for each, a short English label and box_2d as [ymin, xmin, ymax, xmax] normalised to 0-1000. "
               "Include large background features (mountain, lake, sky) as well as foreground objects. Up to 40 objects."),
    "segment": ("Segment every distinct object and terrain feature in this image. Return JSON with 'objects': for each, a short label and "
                "its outline polygon as a list of [x, y] points normalised to 0-1000, going around the object, 8-40 points each. Up to 25 objects."),
    "judge": ("Image 1 is a rendered 3D scene. Image 2 is the reference concept painting it is meant to reproduce. "
              "Score the render against the reference (0-100) for overall similarity, composition, lighting, materials and scale. "
              "Then list the concrete differences, where they appear in the render, a specific fix (what to move, resize, recolour, relight, add or remove) and a severity. "
              "Judge only what is visible; do not invent objects that are in neither image."),
}


def guard(paths):
    r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "ai_input_guard.py"), "--strict", *paths],
                       capture_output=True, text=True, errors="replace")
    return r.returncode == 0, r.stdout[-800:]


def descale_box(b, w, h):
    ymin, xmin, ymax, xmax = b
    return [xmin / 1000.0 * w, ymin / 1000.0 * h, xmax / 1000.0 * w, ymax / 1000.0 * h]


def draw_overlay(image_path, data, mode, out_png):
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    dr = ImageDraw.Draw(im)
    for i, o in enumerate(data.get("objects", [])):
        colour = ((i * 67) % 256, (i * 131 + 60) % 256, (i * 199 + 120) % 256)
        if mode == "detect" and o.get("box_2d"):
            x0, y0, x1, y1 = descale_box(o["box_2d"], w, h)
            dr.rectangle([x0, y0, x1, y1], outline=colour, width=3)
            dr.text((x0 + 3, y0 + 3), f"{i}:{o.get('label', '')}", fill=colour)
        elif mode == "segment" and o.get("polygon"):
            pts = [(x / 1000.0 * w, y / 1000.0 * h) for x, y in o["polygon"]]
            if len(pts) >= 3:
                dr.polygon(pts, outline=colour)
                dr.text(pts[0], f"{i}:{o.get('label', '')}", fill=colour)
    im.save(out_png)


def call_api(model, parts, schema, thinking_minimal=False):
    from google import genai
    from google.genai import types
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("REFUSE: GEMINI_API_KEY not set (create a free key at https://aistudio.google.com/apikey)")
    client = genai.Client(api_key=key)
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema, temperature=0.2)
    if thinking_minimal:
        try:
            cfg.thinking_config = types.ThinkingConfig(thinking_level="minimal")
        except Exception:
            pass
    resp = client.models.generate_content(model=model, contents=parts, config=cfg)
    text = resp.text
    usage = getattr(resp, "usage_metadata", None)
    return json.loads(text), {"prompt_tokens": getattr(usage, "prompt_token_count", None),
                              "output_tokens": getattr(usage, "candidates_token_count", None)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("detect", "segment", "judge", "custom"))
    ap.add_argument("image")
    ap.add_argument("--reference", help="judge mode: the reference image")
    ap.add_argument("--prompt", help="custom mode: prompt text or @file")
    ap.add_argument("--schema", help="custom mode: JSON schema file")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", required=True, help="output stem (no extension)")
    ap.add_argument("--fixture", help="saved response JSON; skips the API")
    ap.add_argument("--context", default=None, help="judge mode: scene facts text or @file, prepended to the prompt (LandscapeLab: research/gemini_judge_context.txt)")
    ap.add_argument("--no-guard", action="store_true")
    a = ap.parse_args(argv)

    paths = [a.image] + ([a.reference] if a.reference else [])
    for p in paths:
        if not os.path.isfile(p):
            print(f"REFUSE: not found: {p}")
            return 2
    if not a.no_guard:
        ok, txt = guard(paths)
        if not ok:
            print("REFUSE: AI-input guard did not clear the inputs")
            print(txt)
            return 2

    if a.mode == "custom":
        if not a.prompt or not a.schema:
            print("REFUSE: custom mode needs --prompt and --schema")
            return 2
        prompt = open(a.prompt[1:], "r", encoding="utf-8").read() if a.prompt.startswith("@") else a.prompt
        with open(a.schema, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
    else:
        prompt, schema = PROMPTS[a.mode], SCHEMAS[a.mode]
    if a.mode == "judge" and not a.reference:
        print("REFUSE: judge mode needs --reference")
        return 2
    if a.mode == "judge" and a.context:
        ctx = open(a.context[1:], "r", encoding="utf-8").read() if a.context.startswith("@") else a.context
        prompt = ctx.strip() + "\n\n" + prompt

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    meta = {"mode": a.mode, "model": a.model, "image": os.path.abspath(a.image), "reference": a.reference and os.path.abspath(a.reference),
            "prompt": prompt, "fixture": a.fixture}
    if a.fixture:
        with open(a.fixture, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        usage = {"fixture": True}
    else:
        parts = [Image.open(p) for p in paths] + [prompt]
        try:
            data, usage = call_api(a.model, parts, schema, thinking_minimal=(a.mode == "segment"))
        except SystemExit as e:
            print(e)
            return 2
        except Exception as e:  # noqa: BLE001
            print(f"API FAILED: {type(e).__name__}: {str(e)[:600]}")
            return 1
    meta["usage"] = usage
    meta["result"] = data
    with open(a.out + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, ensure_ascii=False)
    if a.mode in ("detect", "segment"):
        draw_overlay(a.image, data, a.mode, a.out + ".overlay.png")
        im = Image.open(a.image)
        print(f"{len(data.get('objects', []))} objects; image {im.size[0]}x{im.size[1]}; overlay {a.out}.overlay.png")
        for i, o in enumerate(data.get("objects", [])[:40]):
            print(f"  {i:02d} {o.get('label')}: {o.get('box_2d') or (str(len(o.get('polygon', []))) + ' pts')}")
    else:
        print(json.dumps(data, indent=1, ensure_ascii=False)[:3000])
    print("wrote", a.out + ".json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
