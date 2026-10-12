# Gemini art-direction critique — prompt

**Input, not law.** Gemini's answers are advice to weigh, like a desk brief (rule 9: check every number before using it).

**Before sending any image**, run `python scripts/ai_input_guard.py <paths>`. Every path must print `ok`.
`recipes/ai_restrictions.json` bars some vendor assets, and renders of them, from ever going into a generation model.
Gemini is one. Rig frames under `_verify/lookdev/` passed on 2026-10-03.

## Attach (in this order)

1. **CURRENT** — newest hero frame, e.g. `_verify/lookdev/hero_r7*/hero_a.png`
2. **TARGET** — one or two frames you liked (e.g. picks 0061, 0013, 2476 from the stills export), or a real alpine photo
3. *(optional)* a close-up, e.g. `_verify/lookdev/hero_r6b_fade20_100/ground_rock.png`

## Prompt

```
You are a senior environment art director on an AAA open-world game made in Unreal Engine 5
(think Ghost of Tsushima, RDR2, Horizon). I am attaching render frames from our alpine
landscape test map.

Image 1 = CURRENT state. Image 2 (and 3) = the TARGET look we want.

Scene facts so you don't guess:
- Terrain is a heightfield at 1 m per vertex, with Nanite tessellated displacement
  (up to 2 m on rock).
- The terrain material blends 5 layers (snow, rock, scree, forest floor, grass) from a
  baked weightmap. Each layer is a photogrammetry scan (albedo/normal/roughness/height).
- Rock: a cliff scan tiled at 22 m plus the same scan at 140 m to break up repetition.
  Projection is triplanar on slopes over about 30 degrees. A sharper granite scan fades
  in within 20-100 m of the camera.
- Grass is UE landscape-grass instancing: dense blades to 50-60 m, thinner bands out to
  200 m and 512 m.
- Lighting: physical sky, sun 28 degrees up, real-time sky light, volumetric clouds
  frozen in place, manual exposure.
- Scattered rock MESHES on the cliffs were tried and rejected: they looked pasted on.

Please answer in this order, and be concrete:
1. The 5 biggest visual differences between CURRENT and TARGET, ranked by how much each
   would improve the image. For each, point to WHERE in the frame it shows (e.g. "upper
   right cliff face").
2. For each one, the likely TECHNICAL cause in a UE5 landscape pipeline. Pick from:
   terrain shape/erosion, material layering, texture scale/tiling, projection, lighting,
   atmosphere/fog, foliage density/colour, post-process/grade. Say which.
3. For each one, the specific fix you would try first, with numbers where you can
   (tiling metres, slope angles, colour values, fog density, sun angle, and so on).
4. What in CURRENT already works and must NOT be changed.
5. One thing that would make it read as a real place and not a game test map.

Do not generate a replacement image. I want a diagnosis and a ranked fix list I can test
one change at a time.
```

## Optional second turn (paint-over)

After the diagnosis, you can ask for a paint-over so the target is concrete. **Only for frames that passed the guard.**

```
Now make a paint-over of Image 1 showing your top 3 fixes applied. Keep the camera,
composition and terrain silhouette the same. Change only the surfaces, colour and
lighting you named. Label each change on the image.
```

A paint-over is a **reference to judge against, never an asset**. Do not import it, project it or use it as a texture.

## Bringing it back

Paste Gemini's ranked list into the chat. Each item gets one round: one variable, shot at the hero camera, compared side by side and logged in LESSONS/RECIPES if rejected.
