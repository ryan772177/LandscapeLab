# Gemini app prompt sheet (free tier)

Status 2026-10-10. The free Gemini app (gemini.google.com, no Google AI plan) is the only free source of generated images: the Gemini API free tier offers no image-generation model (Google pricing page, 2026-10-09). The app generates with Nano Banana 2, downloads at 1K as `Gemini_Generated_Image_<id>.jpg` (measured here: 1024×1024, 1408×768, 1375×768, 1304×816), and every image carries an invisible SynthID watermark plus Content Credentials. Google's help pages state a daily quota exists but publish no number; limits refresh every five hours.

Before generating anything for the pipeline:

1. Settings → Media Watermark → off, so no visible sparkle lands in textures or reference views. SynthID stays and is acceptable.
2. Keep Activity: decide knowingly. With it on, prompts, uploads and generated images are used for training and may be human-reviewed (Gemini Apps Privacy Hub). Never upload Fab assets marked "Allows usage with AI: No" (see `recipes/ai_restrictions.json`).
3. One subject per conversation. Google's consistency guidance is to upload reference images, name each character or object, ask for views "from different angles and distances", and keep "facial features exactly the same as Image 1". Start a fresh conversation when drift appears.

After each download: `python scripts/intake_image.py --latest-download --kind <kind> --name <name> --prompt-file <the prompt you used>`.

## A. Prop or landmark reference set (feeds TRELLIS)

The numbers come from the measured view spec in `UE5LandscapePipeline/_verify/20260830_bakeoff/GENERATION_VIEW_SPEC.md`: four views at azimuth 0/90/180/270, elevation about +15 to +20 degrees, plain uniform background, flat even lighting, subject filling 55–97 % of the frame, whole object in every view, no cast shadow crossing the outline. `scripts/check_generation_input.py --set` judges the set; rotations must share the ground line within ±3 % of the master view.

First message (establishes the object):

> Create a product-style reference image of a single [OBJECT: e.g. weathered stone footbridge with two arches], centred, on a plain uniform light-grey background, flat even studio lighting with no cast shadow on the background, no other objects, no text, no watermark. Camera slightly above eye level (about 15 degrees), looking at the object straight from the front. The object fills about 80 % of the square frame. Square image.

Follow-ups, one per view, in the same conversation:

> Same object, same size, same camera height and distance, same background and lighting. Rotate the object 90 degrees to show its right side.

> Same object, same size, same camera height and distance. Show it from directly behind (180 degrees).

> Same object, same size, same camera height and distance. Show its left side (270 degrees).

If a view fails the input check (subject under 150,000 pixels, ground line off by more than 3 %), ask for that view again with "keep the object exactly the same size in frame as the previous image". A two-view set (front + 45°) is enough for TRELLIS; the bridge in `data/forge/SM_Bridge_Forge` was forged from two views.

## B. Character sheet (feeds the head crop and the body conform)

Portrait for the face (what the proven hero route consumed): front view, neutral expression, bald or hair pulled back, no hat, neutral grey background under flat light, head and neck filling the frame. `scripts/prepare_hero_input.py` crops it by chroma.

> Studio photograph of [CHARACTER], front view, neutral expression, looking straight at the camera, no hair covering the face, plain neutral grey background, soft even lighting, no shadows on the background, head and shoulders only.

Body turnaround (feeds the full-body conform or the non-MetaHuman route):

> Full-body character turnaround sheet of [CHARACTER] in a relaxed A-pose, arms slightly away from the body, three views side by side: front, side, back. Keep the clothing, proportions and face exactly the same in all three views. Plain white background, flat even lighting, no shadows, no text.

Then, in the same conversation, request each view alone at full frame ("Show only the front view, full body, filling the frame").

## C. Top-down map (feeds the landscape and town lanes)

> Top-down orthographic map of a [small medieval river valley town], viewed straight down with no perspective, no shading from a low sun, painted in flat distinct colours: deep blue water, dark green forest, light green meadow, grey rock, white snow on peaks, light tan roads, red-brown roofs for buildings. North is up. No text, no labels, no compass rose, no legend inside the picture. Square image.

Keep the palette flat and distinct: `scripts/classify_topdown.py` separates the classes by colour, and anti-aliased gradients or painted shadows blur the classes. Ask for a second image "exactly the same map, but as a greyscale height map: white is the highest ground, black is the lowest, water is black, smooth gradients, no outlines" if you want a terrain base; the output is 8-bit JPEG, so `scripts/heightmap_from_8bit.py` smooths and expands it, and the result is a base shape only.

## D. Tileable texture

> Seamless tileable texture of [valley grass with small clover, slightly dry], photographic, viewed straight down, even lighting, no shadows, no visible repetition, no text. Square image.

The app does not guarantee tileable edges. `scripts/texture_from_gemini.py` makes the edges seamless by offset-and-blend and measures the result against the adjacent-pixel floor.

## E. Concept painting (feeds the scene lane)

> Concept painting of [SCENE], wide shot, eye level, [time of day and weather], [style]. Clear silhouettes for the main objects, uncluttered foreground, horizon visible.

Keep the horizon visible and avoid heavy fog: the camera solver (GeoCalib) and the depth model (Depth Anything 3) are documented on photographs, and a readable horizon is what they key on.
