# Multi-Region Open Worlds in Unreal Engine 5: A Source-Verified Dossier and a UE 5.8 Framework for an Alpine-Centred Fantasy RPG

The studios that have shipped distinct regions in UE5 do not rely on one hidden trick. They follow three rules. First, geography separates the regions: mountains, valleys and chokepoints. Second, each region gets its own signature in terrain, materials, vegetation, atmosphere and lighting, all built on one shared pipeline. Third, World Partition, Data Layers, HLOD and (from 5.6) Fast Geometry Streaming keep region changes seamless or near-seamless. For a UE 5.8 project the pieces now exist as documented engine features: PCG Biome Core with priority-based biome blending, Nanite Foliage, Landscape edit layers, Post Process Volume blending, Local Fog Volumes, Lumen/Lumen Lite, and the experimental Mesh Terrain. But no studio has published a complete "region recipe" with numbers. Every mapping below is a candidate, not a tested recipe.

## TL;DR

- **How the shipped games did it:** they separate regions with landforms, not engine tricks. Obsidian says Avowed's Living Lands are "carved up by mountains and valleys" so that different biomes and climates can sit next to each other. Ninja Theory stitched drone photogrammetry into low-resolution DEM data in Houdini. GSC used Data Layers to swap whole location visuals as the story progresses. Square Enix's FFVII Rebirth team rebuilt its placement and lighting pipeline so that one shared system could handle many areas.
- **Which UE 5.8 levers to use:** PCG Biome Core, which gives you biome volumes/splines, attribute-table asset lists, priority-based difference between overlapping biomes and biome blending controls. Add Landscape edit layers (8 by default), Nanite Landscape (Epic's doc says twice the data is streamed and both sets stay resident in memory), Nanite Foliage/PVE, PPV blend radius and priority for per-region looks, Local Fog Volumes for caves and valleys, and WP HLOD/FastGeo for far-field views of other regions. Several of these are still Experimental in 5.8.
- **What to do:** treat each region as a "region pack" with one fixed checklist: terrain signature → material layer set → PCG biome table → atmosphere/exposure preset → water preset → streaming/HLOD setup → acceptance stills. Author the transitions as explicit ecotone bands that sit on geographic features. Build a roster of 7–9 regions around the alpine core, arranged along a gradient of altitude and moisture.

---

## (A) Source Register

| Title / subject | Event / date | Speakers / named staff | URL | Slides/video | Tier |
|---|---|---|---|---|---|
| UE 5.8 Release Notes | Epic docs, 2026 | Epic | https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes?lang=en-US | Text | Official |
| UE 5.8 launch post | Epic news, 2026 | Epic | https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available | Text | Official |
| City Sample 5.8 PCG update | Epic learning, 2026 (Unreal Fest Chicago 2026 talk referenced) | Epic | https://www.unrealengine.com/learning/city-sample-gets-a-major-update-with-pcg-and-unreal-mcp-workflows | Text + talk | Official |
| PCG Biome Core overview / reference / quick start / glossary | Epic docs 5.8 | Epic | https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-quick-start-guide-in-unreal-engine ; https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-glossary-in-unreal-engine?lang=en-US | Text | Official |
| Electric Dreams Environment sample | GDC 2023 demo; docs 5.8 | Epic | https://www.unrealengine.com/electric-dreams-environment ; https://dev.epicgames.com/documentation/unreal-engine/electric-dreams-environment-in-unreal-engine | Project + docs | Official |
| The Witcher 4 UE5 tech demo blog | CDPR blog, 13 Jun 2025 | Sebastian Kalemba, Jan Hermanowicz, Kajetan Kapuściński, Adrianna Bielak | https://www.cdprojektred.com/en/blog/149/working-with-epic-to-debut-the-witcher-4-unreal-engine-5-tech-demo-at-unreal-fest | Links to talk VODs | Official |
| Streaming Improvements for Dense Worlds (W4 demo) | Unreal Fest Orlando 2025 | Jarosław Rudzki (CDPR) | https://dev.epicgames.com/community/learning/talks-and-demos/KWGD/streaming-improvements-for-dense-worlds-in-the-witcher-4-unreal-engine-5-tech-demo-unreal-fest-orlando-2025 | Video (page body did not render for me) | Official (content not reviewed) |
| State of Unreal 2025 news | Epic, Jun 2025 | Epic | https://www.unrealengine.com/news/all-the-big-news-and-announcements-from-the-state-of-unreal-2025 | Text | Official |
| W4 "infinite forest" interview | Creative Bloq, 2025 | Michał Janiszewski (CDPR Env. Art Director), Wyeth Johnson (Epic) | https://www.creativebloq.com/3d/video-game-design/how-the-witcher-4s-infinite-forest-is-being-built-one-branch-at-a-time-using-unreal-engine-5-6 | Text | Verified-secondary |
| Avowed: Living Lands | Xbox Wire, 7 Feb 2025 | Carrie Patel, Dennis Presnell | https://news.xbox.com/en-us/2025/02/07/avowed-living-lands-next-great-frontier-for-obsidian/ | Text | Official |
| Avowed: A GPU Technical Retrospective | Unreal Fest Orlando 2025 | Matthew Campbell (Obsidian)\[1\] | https://dev.epicgames.com/community/learning/talks-and-demos/mjeq/unreal-engine-avowed-a-gpu-technical-retrospective-unreal-fest-orlando-2025 ; https://www.youtube.com/watch?v=BKaAzhMHJZ0 | Video (not reviewed) | Official (content not reviewed) |
| Avowed art direction (Hansen) | Summer Game Fest interview via Screen Rant, reported by Wccftech | Matt Hansen\[2\] | https://wccftech.com/avowed-art-director-explains-why-the-studio-went-with-a-vibrant-colorful-style/ | Text | Verified-secondary |
| Avowed Region Director portfolio | Personal portfolio, 2025 | Berto Ritger | https://bertoritger.com/portfolio/avowed-first-person-rpg-level-quest-design/ | Text | Verified-secondary (named staff, self-published) |
| Black Myth: Wukong UE5 interview | unrealengine.com, 2021 | Feng Ji, Zhao Wenyong | https://www.unrealengine.com/en-US/developer-interviews/black-myth-wukong-wows-with-ue5-early-access-visuals | Text | Official |
| Hellblade II "The Wanderers" | Xbox Wire, 20 May 2024 | Dan Attwell, Dom Matthews | https://news.xbox.com/en-us/2024/05/20/hellblade-2-environmental-design-inspired-by-iceland/ | Text | Official |
| Hellblade II tech interview | Digital Foundry / Eurogamer, 2024 (the copy I found is a mirror) | Dan Attwell, Mark Slater-Tunstill | http://www.nontonanimeindo.net/digitalfoundry-2024-the-big-senuas-saga-hellblade-2-tech-interview.html | Text + DF video | Verified-secondary (mirror; the original Eurogamer page was not fetched) |
| Hellblade II dev diary report | TechRadar | Dan Attwell | https://www.techradar.com/news/this-xbox-exclusive-had-their-devs-travel-2500km-for-photorealistic-gameplay | Text | Verified-secondary |
| S.T.A.L.K.E.R. 2 UE5 interview | unrealengine.com, 2024 | Andrii Levkovskyi, Maksym Yanchyi | https://www.unrealengine.com/developer-interviews/balancing-nostalgia-with-innovation-in-s-t-a-l-k-e-r-2-heart-of-chornobyl?lang=en-US | Text | Official |
| S.T.A.L.K.E.R. 2 Gamescom interview | Screen Rant | Evgeniy Kulik | https://screenrant.com/stalker-2-heart-chornobyl-interview/ | Text | Verified-secondary |
| S.T.A.L.K.E.R. 2 handcrafted world | PC Gamer | Evgeniy Kulik | https://www.pcgamer.com/games/fps/despite-being-one-of-the-biggest-unreal-engine-5-games-ever-stalker-2-s-locations-are-almost-entirely-hand-crafted-it-took-a-lot-of-time-took-a-lot-of-effort-but-we-re-happy-with-the-result/ | Text | Verified-secondary |
| Clair Obscur: Expedition 33 interviews | unrealengine.com, 2025 | Tom Guillermin | https://www.unrealengine.com/developer-interviews/clair-obscur-expedition-33-autonomy-creativity-and-community-key-to-sandfall-interactives-success ; https://www.unrealengine.com/developer-interviews/inside-the-development-journey-of-clair-obscur-expedition-33 | Text + video | Official |
| Sandfall GDC 2026 talk ("Four Programmers") | GDC 2026 via 80.lv | Sandfall | https://80.lv/articles/sandfall-interactive-used-ue5-blueprints-for-all-gameplay-systems-in-clair-obscur | Slide photos | Verified-secondary |
| Hogwarts Legacy rendering | GDC Vault | Avalanche | https://gdcvault.com/play/1034811/Open-World-Rendering-Techniques-in | Vault (members) | Official (paywalled) |
| Hogwarts Legacy UE extensions | GDC 2024 | Avalanche | https://dev.epicgames.com/community/learning/talks-and-demos/xp8z/an-inside-look-at-hogwarts-legacy-unreal-engine-extensions-gdc-2024 | Video | Official |
| Hogwarts Legacy design interview | unrealengine.com | Kelly Murphy | https://www.unrealengine.com/en-US/developer-interviews/why-avalanche-worked-to-deliver-a-hogwarts-game-with-soul | Text | Official |
| Fortnite Chapter 4 on UE 5.1 | Epic blog / fortnite.com | Epic | https://www.unrealengine.com/blog/battle-testing-unreal-engine-5-1-s-new-features-on-fortnite-battle-royale-chapter-4 ; https://www.fortnite.com/news/drop-into-the-next-generation-of-fortnite-battle-royale-powered-by-unreal-engine-5-1 | Text | Official |
| FFVII Rebirth making-of (4) World map/VFX, (5) Lighting | CGWORLD vol.312 (Aug 2024), web reprint 20–21 Aug 2024 | Takako Miyake, Mana Ichihara, Iichiro Yamaguchi, et al. | https://cgworld.jp/article/202408-ff7reb-04.html ; https://cgworld.jp/article/202408-ff7reb-05.html | Text (partial) | Verified-secondary (named staff) |
| Horizon Zero Dawn vegetation | GDC Vault | Gilbert Sanders (Guerrilla) | https://www.gdcvault.com/play/1025530/Between-Tech-and-Art-The | Vault | Official (paywalled) |
| Horizon Forbidden West settlements | GDC 2022 Art Direction Summit | Roland Ijzermans | https://www.youtube.com/watch?v=LRQCmIHbq14 | Video (not reviewed) | Official (content not reviewed) |

---

## (B) Hard-Numbers Table

| Datapoint | Value | Source |
|---|---|---|
| S.T.A.L.K.E.R. 2 world size | 64 km², 20 regions\[3\] | Evgeniy Kulik, Screen Rant Gamescom interview |
| S.T.A.L.K.E.R. 2 engine version | UE 5.1 at launch (Nanite, Lumen, World Partition); the current official FAQ says the team is upgrading to UE 5.5.4 (Update 2.0) | GSC Steam FAQ post ([GSC]Super_PropheT); stalker2.com/faq |
| Hellblade II photogrammetry | 370+ photogrammetry pieces vs. one in the first game\[4\] | Dan Attwell, Xbox Wire, 20 May 2024 |
| Hellblade II base DEM resolution | "maybe seven pixels per metre" (Attwell's own hedge) for the Iceland cut-out of Arctic DEM data\[5\] | Attwell, DF/Eurogamer interview |
| Hellblade II reference trip | 21 locations, 2,500 km, 11 days\[6\] | Attwell dev diary via TechRadar |
| Clair Obscur environment team | 3–5 people depending on phase\[7\] | Tom Guillermin, unrealengine.com interview |
| Clair Obscur studio / programmers | ~30 full-time staff; four programmers\[8\]\[9\] | Guillaume Broche via Automaton/TheGamer; GDC 2026 talk title via 80.lv |
| W4 demo performance | 60 fps on base PS5 with ray tracing\[10\] | CDPR blog; Epic State of Unreal 2025 |
| W4 foliage screen share | "95% of our screen is often foliage"\[11\] | Michał Janiszewski, Creative Bloq |
| Nanite Foliage assembly savings | Largest demo tree 3.5 GB → ~29 MB on disk; one tree's streaming memory ~36 MB → ~2.7 MB; enables 500k instances of dozens of variants at 1–10M polys each\[12\] | Nanite Foliage doc (UE 5.8) |
| Electric Dreams procedural level | 4 km × 4 km, built from "a handful" of Quixel assets\[13\]\[14\] | Epic Electric Dreams page/docs |
| Fortnite Ch.4 tree density | ~300,000 polygons per tree (fortnite.com); Nanite trees ~300–500k vertices vs ~10–20k for non-Nanite versions (Epic tech blog "Bringing Nanite to Fortnite Battle Royale in Chapter 4"); 60 fps target | fortnite.com Chapter 4 post; Epic tech blog (UE 5.1) |
| FFVII Rebirth art-vs-gameplay tuning ratio | ~8:2 in Remake → ~5:5 in Rebirth\[15\] | Mana Ichihara, CGWORLD vol.312 |
| Landscape edit layers | Default max 8 (Project Setting "Max Number of Layers"); minimum 1 | Landscape Edit Layers doc (5.8)\[16\] |
| Nanite Landscape memory | Twice the data streamed—one set for Nanite, one for texture streaming—with both resident in memory (the non-Nanite data is kept for RVT/water) | Nanite Landscape doc (5.8) |
| Lumen budgets | 8 ms (30 fps) and 4 ms (60 fps) at 1080p on consoles | Lumen Performance Guide (5.8)\[17\] |
| Lumen Lite | Twice as fast as Lumen high quality (which targets 60 fps on PS5); new default for current-gen handhelds (Beta, 5.8) | UE 5.8 release notes |
| VSM virtual resolution | 16k × 16k | VSM doc (5.8)\[18\] |
| Sky Atmosphere lights | Up to 2 atmospheric directional lights (index 0 sun, 1 moon) | Sky Atmosphere doc (5.8)\[19\] |
| Height fog cost | About 2 layers of constant-density fog; far Start Distance can cut cost to ≤50% | Exponential Height Fog doc (5.8)\[20\] |
| Local Fog Volume falloff floor | Height Fog Falloff 1.0 = lowest value before horizon artifacts | Local Fog Volumes doc (5.8)\[21\] |
| Auto Exposure | 64-bin histogram default; adaptation switches linear→exponential at 1.5 stops; no default EV100 min/max published | Auto Exposure doc (5.8)\[22\] |
| PPV example values | Blend Radius 1500 (world units), Priority 200; the PP-material doc example uses radius 1000 | "Add Post Process Volumes" tutorial; Post Process Materials doc\[23\]\[24\] |
| WP HLOD example | LoadingRange=30000 for default and tree HLOD layers (ini example)\[25\] | WP HLOD doc (5.8)\[25\] |
| WP example loading range | 12800 (navmesh tutorial example, not a recommendation)\[26\] | WP Navmesh doc (5.8) |
| Water spline resample | r.Water.WaterSplineResampleMaxDistance = 50 cm default | Water debugging/scalability doc\[27\] |
| PCG GPU runtime scatter | "Same performance range" as landscape GPU grass\[28\] | UE 5.8 release notes |

**What is missing:** no source I found published per-region EV targets, WP cell sizes, VRAM or ms budgets per region, or asset counts per biome for any of the titles. Those rows are left empty on purpose rather than estimated.

---

## (C) Per-Title: How They Built Their Regions

### Avowed (Obsidian, UE5; reportedly UE 5.3 per Windows Central's Jez Corden on X, 25 May 2024—not confirmed by Obsidian)
- **Structure:** a handful of large open zones (Dawnshore, Emerald Stair, Shatterscarp, Galawain's Tusks, plus The Garden).\[29\] It is not one seamless continent. The zones are linked by story travel, and Emerald Stair is reached through a gate.\[30\]\[31\] Carrie Patel (Xbox Wire) says the land is carved up by mountains and valleys so that distinct biomes and climates can exist close together.\[32\] The geography does the separating.
- **Identity:** Patel describes Emerald Stair as very lush but slightly gloomy, and Shatterscarp as a high desert.\[32\] Art Director Matt Hansen (Summer Game Fest interview) says the design principle was contrast between neighbours: a gloomy swamp, then a vibrant red desert, then an ashy waste. The aim was that one continent would feel like crossing a whole planet. Palette saturation was a deliberate part of each region's identity; some areas are intentionally muted so the vivid ones stand out.\[2\]
- **Production:** Obsidian used a **Region Director** role. Berto Ritger's portfolio describes directing level and quest design across Dawnshore, Emerald Stair and The Garden with an interdisciplinary team per region.\[33\] That is a strike-team-per-region model. Lead Environment Artist Dennis Presnell describes an iterative process in which artists built on each other's assets toward one cohesive world, with detail placed off the main paths.\[32\]
- **Rendering specifics:** the Unreal Fest 2025 "GPU Technical Retrospective" (Matthew Campbell) is the primary source,\[1\] but I could not review its content. Claims about Lumen, Nanite and VSM plus screen-space shadows are UNVERIFIED (secondary summaries only).\[34\]

### Black Myth: Wukong (Game Science, UE4 → UE5)
- In Epic's 2021 interview, Feng Ji and Zhao Wenyong say the move to UE5 was smoother than their earlier 4.24→4.26 upgrade. They name Nanite and Lumen as the favourite features, both for image quality and for faster art-asset creation.\[35\]
- Chapter-based structure: each chapter is its own biome (forest, desert, snow, volcanic). This is region separation by progression gating rather than seamless streaming.
- Scanning real Chinese heritage sites (for example in Shanxi) is widely reported. The figure of "36 landmarks" and polygon counts such as 5–6M or 20–50M faces come from secondary sources and are UNVERIFIED.\[36\]\[37\]

### Senua's Saga: Hellblade II (Ninja Theory, UE5)
- **Terrain pipeline, a three-tier approach** (Dan Attwell, DF/Eurogamer interview):
  1. Arctic-Circle DEM data with Iceland cut out, at roughly 7 px/m by his own estimate, as the background tier.\[5\]
  2. Grid-based drone photogrammetry (DroneDeploy) over the play spaces, turned into height fields.\[5\]
  3. Post-processing in Houdini, stitched into the low-resolution DEM, exported as heightmaps into UE, then edited for gameplay.\[5\]
- This is the most transferable published method for putting a detailed playable region inside a coarse vista region.
- 370+ photogrammetry pieces were used (Xbox Wire).\[4\] The team made two reference trips; the dev diary cites 21 locations over 2,500 km in 11 days.\[6\]\[38\] Studio Head Dom Matthews says real Icelandic geography feels "alien" yet believable, which argues for real-world reference as the anchor of each biome.\[4\]
- VSM was adopted mid-production as it matured (Creative Bloq).\[39\] The game is linear, so its "regions" are story chapters.

### The Witcher 4 UE 5.6 Tech Demo (CDPR + Epic)
- **What was announced:** five technologies—FastGeo Streaming, Nanite Foliage, Mass, ML Deformer and the Unreal Animation Framework—running on base PS5 at 60 fps with ray tracing.\[10\]\[40\] CDPR's blog says FastGeo lets everything in Kovir (dense forests, snowy mountains, the trading hub Valdrest) load without hitches, and that all five tools will be available to every UE5 developer.\[40\]
- **What it shows for multi-region design:** the demo shows one region (Kovir) containing sub-biomes: spruce forest, snow mountain and a port town.\[41\] That is a town-inside-nature hand-off streamed through one pipeline. Wyeth Johnson (Epic) calls the northern spruce forest "the hard part"; the modular biome is scaled with voxelised Nanite Foliage and HLOD blending (Creative Bloq).\[11\]
- **Status in 5.8:** FastGeo remains Experimental (the 5.8 notes add support for lights and decals, plus fixes).\[28\] Nanite Foliage and the Procedural Vegetation Editor are documented in 5.8;\[42\] PVE is Experimental, and 5.7 PVE assets cannot be opened in 5.8.\[43\]
- **"Unified Data Layers":** I found no official source for this term. It is UNVERIFIED.

### S.T.A.L.K.E.R. 2 (GSC Game World, UE 5.1)
- 64 km² seamless zone with 20 regions (Kulik). Biome and "corruption" intensity rise with depth into the Zone, so the region gradient carries the narrative gradient.\[3\]
- Epic interview (Maksym Yanchyi): One File Per Actor removed conflicts between artists working through greybox and beautification at the same time. **Data Layers** were used to radically change the visuals of locations as the story progresses.\[44\] This is the clearest official precedent for region-state swaps.
- Almost all of it is handcrafted. GSC tried procedural generation and rejected it on quality grounds (PC Gamer).\[45\]

### Clair Obscur: Expedition 33 (Sandfall, UE4 → UE5)
- An environment team of 3–5 people built many surreal, distinct areas. Guillermin credits World Partition for letting several artists work in one world at once while keeping memory and CPU/GPU use down, and says that locking whole levels would have been a major point of contention.\[7\] Sandfall relied on stock engine features, Fab assets and Blueprint (GDC 2026 talk: four programmers).\[9\]\[46\]
- **Lesson for scoping:** a small team scopes regions by strong art direction and stock tech, not by custom systems. The regions are separate maps linked by an overworld, not one seamless landscape.

### Hogwarts Legacy (Avalanche, UE4)
- GDC Vault's "Open World Rendering Techniques" talk covers adapting UE for a seamless indoor/outdoor castle, hundreds of shadow-casting lights, and batching light probes, reflections and foliage.\[47\] The video is paywalled; I read only the abstract.
- Lead Designer Kelly Murphy describes filling the Highlands with overlapping systemic goals such as Merlin Trials.\[48\] Region identity comes partly from gameplay density.

### Fortnite (Epic, UE5)
- Chapter 4 moved to UE 5.1 with Nanite, Lumen, VSM and TSR at 60 fps.\[49\] Fortnite.com says individual trees have around 300,000 polygons, and Epic's tech blog "Bringing Nanite to Fortnite Battle Royale in Chapter 4" puts Nanite trees at ~300–500k vertices versus ~10–20k for the non-Nanite versions; stones and flowers are modelled geometry.
- I found no official Epic write-up of biome transitions or seasonal terrain swaps: UNVERIFIED/gap.

### Palworld (Pocketpair, UE5)
- No official source on biome construction was found: gap.

### FFVII Rebirth (Square Enix, customised UE4)
- **Placement (CGWORLD vol.312 part 4):** Environment Director Takako Miyake says the rendering system was rebuilt for mass placement. Artists no longer think about LODs, and collision is generated automatically. Houdini procedural placement became more central. Objects load and unload by compute-shader visibility, spatial volumes and pre-measurement.\[15\]
- **Tuning ratio:** Supervisor Mana Ichihara says the art-to-gameplay tuning ratio moved from about 8:2 in Remake to about 5:5 in Rebirth.\[15\] Open regions demand much more gameplay-driven iteration.
- **Lighting (part 5):** Lighting Director Iichiro Yamaguchi describes a subtractive approach for bright open fields: carving shadows into daylight, the reverse of Midgard's additive approach. The team baked light probes instead of lightmaps for backgrounds (lightmaps were too costly across the whole map), then strengthened the probe tools against flatness and light leaks. At Gold Saucer they staged a "contrast of atmosphere": a dim arrival that builds to spectacle. The environment and lighting teams co-designed where lights would go from the start.\[50\]
- **Carried from prior research, not re-verified in this pass:** per-region sky domes and lighting themes, and the "area character" concept (Grasslands, Junon, Corel, Gongaga, Cosmo Canyon, Nibel), attributed to the CEDEC 2023 TA session. FFXVI's vegetation team building ecological rules per region (warm broadleaf vs cold conifer, mantle communities). Treat both as previously sourced.

### Non-UE technique references
- Guerrilla's GDC vegetation talk (Gilbert Sanders, HZD) and the HFW settlements talk (Roland Ijzermans) exist on GDC Vault/YouTube.\[51\]\[52\] I did not review their content.
- No official talk describing multi-biome methods was found for Ghost of Yōtei, AC Shadows, KCD2 or Elden Ring: gap.

---

## (D) Synthesized Multi-Region Framework for a UE 5.8 Fantasy RPG

All UE levers below are **candidate mappings from documentation, not tested recipes**. Every page listed carries the "Unreal Engine 5.8 Documentation" label unless noted.

### D1. Principles drawn from the evidence
1. **Separate regions with landforms.** Put boundaries on ridges, passes, gorges, rivers, coastlines and tunnels, following Avowed's "mountains and valleys" approach.\[32\] Landforms give you streaming chokepoints, visual occluders and a believable excuse for sharp climate change.
2. **Contrast neighbours on purpose.** Following Hansen, alternate saturation and value between adjacent regions (muted wetland next to a vivid desert) so each one reads as distinct.
3. **Keep one pipeline and swap the data per region.** Use the same PCG graph, master landscape material and atmosphere rig everywhere, and change only the tables and presets. This matches FFVII Rebirth's shared placement system and the data-asset design of PCG Biome Core.\[53\]
4. **Tier each region's terrain like Hellblade II:** a coarse vista DEM/Gaea base, a high-resolution play-space tier, then gameplay edits.
5. **Use Data Layers for region state, not only for streaming.** This is the S.T.A.L.K.E.R. 2 precedent: story-driven visual swaps such as an ashfall state or a thawed state.\[54\]

### D2. Per-Region Production Checklist ("Region Pack")

| Step | Deliverable | UE 5.8 lever (candidate) | Doc URL |
|---|---|---|---|
| 1. Region kickoff doc | Identity sheet: 3 key materials, silhouette language (spiky/rounded/flat), palette plus value range, 2–3 hero landmarks visible from neighbouring regions, weather set, time-of-day bias, audio bed, gameplay density target | — | — |
| 2. Terrain signature | Gaea/forge graph per region (erosion type, slope profile, strata), vista tier plus play tier stitched at a ridge or river boundary | Landscape Edit Layers (one layer per region/pass; default max 8, raise in Project Settings)\[16\] | https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-edit-layers-in-unreal-engine |
| 2b. Overhangs, caves, sea stacks | Non-heightfield terrain | Mesh Terrain (Experimental—prototype only)\[55\] | https://dev.epicgames.com/documentation/unreal-engine/mesh-terrain-in-unreal-engine?lang=en-US |
| 2c. Nanite landscape / displacement | Enable Nanite and skirts; budget for twice the streamed landscape data resident in memory (per the Nanite Landscape doc) | Nanite Landscape | https://dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine?lang=en-US |
| 3. Material layer set | Per-region subset of a master landscape material (e.g. alpine: rock/scree/snow/grass/moss; desert: sand/hardpan/strata rock/salt). Use Landscape Layer Switch so unused layers cost nothing | Landscape Materials (weight vs. alpha vs. height blend)\[56\] | https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine |
| 3b. Blending props to ground | RVT for terrain-to-mesh blending and far-field cost | Runtime Virtual Texturing\[57\]\[58\] | https://dev.epicgames.com/documentation/unreal-engine/runtime-virtual-texturing-in-unreal-engine?lang=en-US |
| 4. PCG biome table | One Biome definition per region: asset attribute table (mesh/assembly/actor), generator subtypes driven by landscape layer weights, filters for height/density/flow, priority, blend settings\[53\]\[59\] | PCG Biome Core (Experimental); PCG with World Partition (Data Layer/HLOD layer inheritance)\[60\]\[61\]\[62\] | https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine ; https://dev.epicgames.com/documentation/unreal-engine/using-pcg-with-world-partition-in-unreal-engine?lang=en-US |
| 4b. Hero vegetation | Nanite Foliage assets (assemblies, voxel far field); PVE for species (Experimental; no 5.7→5.8 asset compatibility)\[43\] | Nanite Foliage; PVE; Nanite | https://dev.epicgames.com/documentation/unreal-engine/nanite-foliage ; https://dev.epicgames.com/documentation/unreal-engine/procedural-vegetation-editor-in-unreal-engine?lang=en-US ; https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine |
| 5. Atmosphere preset | Sky Atmosphere (scattering/absorption: dusty desert, humid jungle, thin alpine), Volumetric Cloud material instance per region, EHF plus Local Fog Volumes for valleys/swamps | Sky Atmosphere; Volumetric Clouds; Exponential Height Fog; Local Fog Volumes\[21\]\[63\] | https://dev.epicgames.com/documentation/unreal-engine/sky-atmosphere-component-in-unreal-engine?lang=en-US ; https://dev.epicgames.com/documentation/en-us/unreal-engine/volumetric-cloud-component-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/exponential-height-fog-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/local-fog-volumes-in-unreal-engine |
| 5b. Exposure/grade preset | Per-region PPV: auto-exposure min/max in EV100 (turn on "extend default luminance range"), local exposure (the doc says always set it up with Lumen), LUT/grade | Post Process Effects; Blendables; Auto Exposure\[22\] | https://dev.epicgames.com/documentation/unreal-engine/post-process-effects-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/blendables-in-unreal-engine ; https://dev.epicgames.com/documentation/unreal-engine/auto-exposure-in-unreal-engine?lang=en-US |
| 5c. GI/shadows | Lumen HQ for hero regions, evaluate Lumen Lite (Beta) for dense jungle/towns;\[28\] VSM with Nanite | Lumen GI; Lumen Performance Guide; VSM\[18\]\[64\] | https://dev.epicgames.com/documentation/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-performance-guide-for-unreal-engine ; https://dev.epicgames.com/documentation/unreal-engine/virtual-shadow-maps-in-unreal-engine?lang=en-US |
| 6. Water preset | Water Body material per region (glacial: low turbidity, cyan absorption; tropical: high clarity; swamp: high scattering, dark albedo); shoreline wetness via material parameter | Water System; Water Body Actors\[65\]\[66\] | https://dev.epicgames.com/documentation/en-us/unreal-engine/water-system-in-unreal-engine ; https://dev.epicgames.com/documentation/unreal-engine/water-body-actors-in-unreal-engine |
| 7. Streaming/HLOD | One 2D runtime grid for the whole world (the doc warns that extra grids cost performance); per-biome HLOD layers (instancing for trees, merged/simplified for rock/town);\[25\]\[67\] Data Layers for region states; FastGeo evaluation | World Partition; WP HLOD; Data Layers\[25\]\[54\]\[68\] | https://dev.epicgames.com/documentation/unreal-engine/world-partition-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---data-layers-in-unreal-engine |
| 8. Profiling | Per-cell streaming analysis\[28\] | WP Insights (new in 5.8, via release notes) | https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes?lang=en-US |
| 9. Acceptance stills | A fixed camera set per region: noon, golden hour, overcast, night; ecotone crossing; vista toward two neighbouring regions; interior/cave entry; hero landmark at 1 km and at 5 km. Each still is signed off against the kickoff palette and a GPU capture against the budget | — | — |

### D3. Transition / Ecotone Authoring Pattern (candidate)
1. **Put the boundary on a landform** (ridge crest, river, gorge, tunnel). Where a gradual ecotone is needed, such as alpine to meadow-forest, author it as a band 200–600 m wide. That width is a design suggestion, not a sourced number.
2. **Terrain:** give both regions' Gaea outputs a shared overlap mask. Blend them in a dedicated "ecotone" edit layer, then mix the material layers of both sets through a height blend.
3. **Vegetation:** overlap two PCG Biome Core biome volumes or splines. Resolve the overlap with the documented priority-based difference plus the local biome blending controls.\[59\]\[69\] Taper each biome's density table across the band: species drop out in ecological order (for example, conifers thin out and broadleaf takes over with altitude and aspect). This follows the FFXVI-style ecological rule sets.
4. **Atmosphere and grade:** use two region PPVs with blend radius, weighted by priority (the docs say blending is linear and recommend one low-priority unbound global volume).\[70\]\[71\] Blend fog density and colour through Local Fog Volumes in valleys. Keep sky atmosphere changes small, and drive larger shifts through weather and time-of-day parameters instead of swapping sky actors.
5. **Global material parameters:** use a Material Parameter Collection for snow, wetness and dust coverage that is lerped by the player's position along the band. This is standard UE practice; I did not find a doc page for it this pass.
6. **Validate** with a fixed-path flythrough capture across every ecotone.

### D4. Recommended Region Roster (alpine-centred)

| # | Region | Relation to alpine core | Boundary device | Signature (terrain/material/light) | Rationale |
|---|---|---|---|---|---|
| 1 | Alpine/conifer (existing, 8 km) | Core | — | Glacial erosion, scree, snow/rock; crisp blue-shifted light | Already built; the reference region |
| 2 | Lowland meadow-forest | Downslope | Treeline ecotone band | Rolling hills, broadleaf, warm, saturated | Gradual ecotone; tutorial/starter region |
| 3 | Towns (as sub-regions inside 1 and 2) | Embedded | Walls, valleys | Handcrafted, Lumen-heavy interiors | W4 demo shows a town inside a nature region on one pipeline |
| 4 | Coast/cliffs | Meadows reach the sea | Cliff line | Sea stacks (Mesh Terrain candidate), Water ocean, salt haze | Strong silhouette contrast with the peaks |
| 5 | Tundra/snowfield | Beyond the high passes | Pass/tunnel | Flat, white, very bright—the exposure stress test | Reuses alpine materials; low asset cost |
| 6 | Wetland/jungle | Lowland basin | River delta | Dense fog, dark water, high humidity | Muted/gloomy counterweight (Avowed pattern) |
| 7 | Desert/badlands | Rain shadow of the range | Ridge crest | Stratified rock, sand; warm, high contrast | Rain shadow is a believable climate reason; maximum palette contrast |
| 8 | Volcanic/ash | Far flank | Gorge or lava field | Basalt, ash; ember-lit fog | Late-game "corrupted" state; Data Layer state swaps |
| 9 | Caves/underground | Beneath 1, 7, 8 | Tunnels | Local exposure, Local Fog Volumes, Lumen-dependent | Connects regions and hides streaming transitions |

**Why this roster works:** the altitude/moisture gradient makes every neighbour pair ecologically believable. Alpine, tundra and coast share rock and snow kits, which keeps asset cost down. The rain-shadow desert and the basin wetland give the strongest contrast at the lowest geographic implausibility.

### D5. Caves and towns (candidate handling)
- **Caves:** give each cave an unbound-off PPV with a higher priority than the region PPV and a short blend radius at the mouth. Widen the EV100 lower bound and enable local exposure. Add Local Fog Volumes for depth; the docs explain how they layer with height fog and volumetric fog.\[21\] Lumen is required for bounce light; test Lumen Lite in large caverns.
- **Towns:** give each town its own HLOD layers and consider FastGeo for dense static geometry. Borrow FFVII Rebirth's practice of having lighting and environment co-design light placement from the blockout stage.

### D6. Team structure
- **Region strike teams:** give each region a Region Director (Avowed's model) leading level design, environment, lighting and quest staff.
- **Central tech-art owners:** keep the master material, the PCG Biome Core fork, the atmosphere rig and the streaming/HLOD policy with a small central tech-art group.
- **Workflow:** mockup → greybox → beautification passes in parallel, as OFPA allowed at GSC.
- **Small-team scaling:** Sandfall shows that 3–5 environment artists can deliver many regions if the tech stays stock.
- **Scope pressure:** expect the gameplay-tuning share per region to approach half the effort once regions are open (Ichihara's 5:5).

---

## (E) Gaps, Paywalls and UNVERIFIED Items

- **Paywalled/login:** GDC Vault videos (Hogwarts Legacy rendering; Guerrilla vegetation), Game File's Avowed making-of (paywalled after the intro),\[72\] CGWORLD print vol.312 (the web reprints are partial).
- **Found but not reviewed:** Avowed GPU Technical Retrospective (Unreal Fest 2025), the W4 "Streaming Improvements for Dense Worlds" and "Road to 60FPS" talks, and the HFW settlements talk. These are the highest-value next watches for numbers such as cell sizes and ms budgets.
- **Not found:** any official per-region EV100, WP cell size, VRAM or ms budget, or per-biome asset counts for any title. Palworld and Fortnite biome methods. Official multi-biome talks for Ghost of Yōtei, AC Shadows, KCD2 and Elden Ring. The "Unified Data Layers" term for W4. A documented max-landscape-layers-per-component figure (it appears only in a forum thread).\[73\]
- **UNVERIFIED:**
  - Avowed on UE 5.3 (sourced only to Windows Central's Jez Corden on X, 25 May 2024, who said it moved to 5.3 with support from The Coalition; not confirmed by Obsidian) and its Lumen/Nanite/VSM usage.
  - Black Myth's "36 landmarks" and polygon counts.
  - S.T.A.L.K.E.R. 2 engine version: now sourced to GSC's Steam FAQ post (UE 5.1 at launch) and stalker2.com/faq (upgrade to UE 5.5.4 in Update 2.0).
  - Clair Obscur "95% Blueprint."\[74\]
  - Dawnshore "about 15 hours."\[31\]
  - Hansen's 30 fps statement (secondary wiki).\[75\]
- **Carried forward without re-verification:** the CEDEC 2023 TA session details (FFVII Rebirth sky domes and area character) and the FFXVI vegetation ecological rules.
- **Version flags:** every Epic doc listed carries the 5.8 label. Two were surfaced under 5.7 labels in search results: the Biome Core landing page and Nanite Assemblies.\[76\]\[77\] Their 5.8 counterparts exist or are likely; check before relying on specific parameters. PCG Biome Core, PVE, FastGeo, Mesh Terrain and FSSS are Experimental in 5.8; Lumen Lite is Beta.\[28\]

## Sources

1. [Avowed: A GPU Technical Retrospective | Unreal Fest Orlando 2025 | Talks and demos](https://dev.epicgames.com/community/learning/talks-and-demos/mjeq/unreal-engine-avowed-a-gpu-technical-retrospective-unreal-fest-orlando-2025)
2. [Avowed Art Director Explains Why the Studio Went with a Vibrant, Colorful Style](https://wccftech.com/avowed-art-director-explains-why-the-studio-went-with-a-vibrant-colorful-style/)
3. [S.T.A.L.K.E.R. 2: Heart of Chornobyl Is A "Huge" Game With A LOT Of Content To Explore, Says Dev](https://screenrant.com/stalker-2-heart-chornobyl-interview/)
4. [The Wanderers – The Team Behind Senua’s Saga: Hellblade II’s Incredible Landscapes - XBOX Wire](https://news.xbox.com/en-us/2024/05/20/hellblade-2-environmental-design-inspired-by-iceland/)
5. [The making of Senua's Saga: Hellblade 2 - the Ninja Theory interview | Eurogamer.net](http://www.nontonanimeindo.net/digitalfoundry-2024-the-big-senuas-saga-hellblade-2-tech-interview.html)
6. [This Xbox exclusive had its devs travel 2,500km for photorealistic gameplay](https://www.techradar.com/news/this-xbox-exclusive-had-their-devs-travel-2500km-for-photorealistic-gameplay)
7. [Clair Obscur: Expedition 33: autonomy, creativity, and community key to Sandfall Interactive’s success - Unreal Engine](https://www.unrealengine.com/developer-interviews/clair-obscur-expedition-33-autonomy-creativity-and-community-key-to-sandfall-interactives-success)
8. [Clair Obscur: Expedition 33 Didn't Need A Big Team Thanks To Unreal Engine 5](https://www.thegamer.com/clair-obscur-expedition-33-unreal-engine-5-small-team/)
9. [Sandfall Reveals at GDC That Clair Obscur Was Built Using Blueprints](https://80.lv/articles/sandfall-interactive-used-ue5-blueprints-for-all-gameplay-systems-in-clair-obscur)
10. [All the big news and announcements from the State of Unreal 2025 - Unreal Engine](https://www.unrealengine.com/news/all-the-big-news-and-announcements-from-the-state-of-unreal-2025)
11. [How The Witcher 4's "infinite forest" is being built one branch at a time using Unreal Engine 5.6 | Creative Bloq](https://www.creativebloq.com/3d/video-game-design/how-the-witcher-4s-infinite-forest-is-being-built-one-branch-at-a-time-using-unreal-engine-5-6)
12. [Nanite Foliage | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/nanite-foliage)
13. [Electric Dreams Environment | PCG Sample Project - Unreal Engine](https://www.unrealengine.com/electric-dreams-environment)
14. [Download Epic Games’ free Electric Dreams sample | CG Channel](https://www.cgchannel.com/2023/06/download-epic-games-free-electric-dreams-sample-project/)
15. [広大な世界を描き出す画づくりの粋〜『FINAL FANTASY VII REBIRTH』（4）ワールドマップ・エフェクト編](https://cgworld.jp/article/202408-ff7reb-04.html)
16. [Landscape Edit Layers in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-edit-layers-in-unreal-engine)
17. [Lumen Performance Guide for Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-performance-guide-for-unreal-engine)
18. [Virtual Shadow Maps in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/virtual-shadow-maps-in-unreal-engine?lang=en-US)
19. [Sky Atmosphere Component in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/sky-atmosphere-component-in-unreal-engine?lang=en-US)
20. [Exponential Height Fog in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/exponential-height-fog-in-unreal-engine)
21. [Local Fog Volumes in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/local-fog-volumes-in-unreal-engine)
22. [Auto Exposure in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/auto-exposure-in-unreal-engine?lang=en-US)
23. [Add Post Process Volumes | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/add-post-process-volumes)
24. [Post Process Materials | Unreal Engine 4.27 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-materials?application_version=4.27)
25. [World Partition - Hierarchical Level of Detail in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine)
26. [World Partitioned Navigation Mesh | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partitioned-navigation-mesh)
27. [Water Debugging and Scalability Options in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/water-debugging-and-scalability-options-in-unreal-engine)
28. [Unreal Engine 5.8 Release Notes | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes?lang=en-US)
29. [Avowed - Official Pillars of Eternity Wiki](https://pillarsofeternity.fandom.com/wiki/Avowed)
30. [Avowed - Full Emerald Stair Map And Points Of Interest - GameSpot](https://www.gamespot.com/articles/avowed-full-emerald-stair-map-and-points-of-interest/1100-6529569/)
31. [Avowed biomes: List of every region we've seen so far | AltChar](https://www.altchar.com/guides/avowed-biomes-list-of-every-region-weve-seen-so-far-a2bqL6S26WxU)
32. [Avowed and the Living Lands Are the Next Great Frontier for Obsidian - XBOX Wire](https://news.xbox.com/en-us/2025/02/07/avowed-living-lands-next-great-frontier-for-obsidian/)
33. [Avowed: First-Person RPG Level & Quest Design – Berto Ritger](https://bertoritger.com/portfolio/avowed-first-person-rpg-level-quest-design/)
34. [Obsidian Entertainment Uses Unreal Engine 5 To Its Advantage In 'Avowed' - uGames](https://ugames.tv/obsidian-entertainment-uses-unreal-engine-5-to-its-advantage-in-avowed/)
35. [Black Myth: Wukong wows with UE5 early access visuals - Unreal Engine](https://www.unrealengine.com/en-US/developer-interviews/black-myth-wukong-wows-with-ue5-early-access-visuals)
36. [Black Myth: Wukong — The Science Behind It’s Highly Detailed Environments | by Joe Chiang 江効儒 | The VFX & Animation Journal | Medium](https://medium.com/the-vfx-animation-journal/black-myth-wukong-the-science-behind-its-highly-detailed-environments-7e1ca8bdc47e)
37. [Sue's TALK | How does Black Myth: Wukong manage to recreate real-world scenes? | GDToday](https://www.newsgd.com/node_d36b0ef83f/a92f49969d.shtml)
38. [The making of Senua's Saga: Hellblade 2 - Ninja Theory's views on Unreal Engine 5, experimentation and what's next | Creative Bloq](https://www.creativebloq.com/3d/video-game-design/the-making-of-senua-s-saga-hellblade-2)
39. [\[DF\] Inside Senua's Saga: Hellblade 2 - An Unreal Engine 5 Masterpiece - The Ninja Theory Breakdown | ResetEra](https://www.resetera.com/threads/df-inside-senuas-saga-hellblade-2-an-unreal-engine-5-masterpiece-the-ninja-theory-breakdown.948147/)
40. [WORKING WITH EPIC TO DEBUT THE WITCHER 4 UNREAL ENGINE 5 TECH DEMO AT UNREAL FEST](https://www.cdprojektred.com/en/blog/149/working-with-epic-to-debut-the-witcher-4-unreal-engine-5-tech-demo-at-unreal-fest)
41. [CD PROJEKT RED and Epic Games Present The Witcher 4 Unreal Engine 5 Tech Demo at The State of Unreal 2025! - CD PROJEKT RED Press Center](https://press.cdprojektred.com/en/news/1778/cd-projekt-red-and-epic-games-present-the-witcher-4-unreal-engine-5-tech-demo-at-the-state-of-unreal-2025)
42. [Nanite Virtualized Geometry in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
43. [Procedural Vegetation Editor in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/procedural-vegetation-editor-in-unreal-engine?lang=en-US)
44. [Balancing nostalgia with innovation in S.T.A.L.K.E.R. 2: Heart of Chornobyl - Unreal Engine](https://www.unrealengine.com/developer-interviews/balancing-nostalgia-with-innovation-in-s-t-a-l-k-e-r-2-heart-of-chornobyl?lang=en-US)
45. [Despite being one of the biggest Unreal Engine 5 games ever, Stalker 2's locations are almost entirely hand-crafted: 'It took a lot of time, took a lot of effort, but we're happy with the result' | PC Gamer](https://www.pcgamer.com/games/fps/despite-being-one-of-the-biggest-unreal-engine-5-games-ever-stalker-2-s-locations-are-almost-entirely-hand-crafted-it-took-a-lot-of-time-took-a-lot-of-effort-but-we-re-happy-with-the-result/)
46. [The Role Of Unreal Engine 5 In Clair Obscur: Expedition 33](https://80.lv/articles/clair-obscur-expedition-33-dev-shares-how-ue5-shaped-the-game)
47. [GDC Vault - Open World Rendering Techniques in 'Hogwarts Legacy'](https://gdcvault.com/play/1034811/Open-World-Rendering-Techniques-in)
48. [Why Avalanche worked to deliver a Hogwarts game with soul - Unreal Engine](https://www.unrealengine.com/en-US/developer-interviews/why-avalanche-worked-to-deliver-a-hogwarts-game-with-soul)
49. [Virtual Shadow Maps in ‘Fortnite Battle Royale’ Chapter 4 - Unreal Engine](https://www.unrealengine.com/en-US/tech-blog/virtual-shadow-maps-in-fortnite-battle-royale-chapter-4)
50. [広大な世界を描き出す画づくりの粋〜『FINAL FANTASY VII REBIRTH』（5）ライティング・カットシーン篇](https://cgworld.jp/article/202408-ff7reb-05.html)
51. [GDC Vault - Between Tech and Art: The Vegetation of 'Horizon Zero Dawn'](https://www.gdcvault.com/play/1025530/Between-Tech-and-Art-The)
52. [Designing the Settlements in the World of 'Horizon Forbidden West' - YouTube](https://www.youtube.com/watch?v=LRQCmIHbq14)
53. [Procedural Content Generation (PCG) Biome Core and Sample Plugins Overview Guide in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-overview-guide-in-unreal-engine)
54. [World Partition - Data Layers in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition---data-layers-in-unreal-engine)
55. [Mesh Terrain in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/mesh-terrain-in-unreal-engine?lang=en-US)
56. [Landscape Materials in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine)
57. [Runtime Virtual Texturing | Unreal Engine 4.27 Documentation | Epic Developer Community](https://docs.unrealengine.com/4.27/en-US/RenderingAndGraphics/VirtualTexturing/Runtime)
58. [Virtual Texturing | Unreal Engine 4.27 Documentation | Epic Developer Community](https://docs.unrealengine.com/4.26/en-US/RenderingAndGraphics/VirtualTexturing)
59. [Procedural Content Generation (PCG) Biome Core and Sample Plugins Reference Guide in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine)
60. [Procedural Content Generation (PCG) Biome Core and Sample Plugins in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-in-unreal-engine?lang=en-US)
61. [Using PCG with World Partition in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-with-world-partition-in-unreal-engine?lang=en-US)
62. [Using PCG with World Partition in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-pcg-with-world-partition-in-unreal-engine)
63. [Environmental Light with Fog, Clouds, Sky and Atmosphere in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/environmental-light-with-fog-clouds-sky-and-atmosphere-in-unreal-engine)
64. [Lumen Global Illumination and Reflections in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine)
65. [Water System in Unreal Engine | Unreal Engine 5.0 Documentation](https://docs.unrealengine.com/5.0/en-US/water-system-in-unreal-engine/)
66. [Water Body Actors in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/water-body-actors-in-unreal-engine)
67. [World Partition in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/world-partition-in-unreal-engine)
68. [World Partition in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine)
69. [Procedural Content Generation (PCG) Biome Core and Sample Plugins Glossary in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-glossary-in-unreal-engine?lang=en-US)
70. [Post Process Effects | Unreal Engine Documentation](https://dq8iqaixvew1d.cloudfront.net/en-US/Engine/Rendering/PostProcessEffects/index.html)
71. [Blendables in Unreal Engine | Unreal Engine 5.8 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/blendables-in-unreal-engine)
72. [Behind the scenes of Avowed's beautiful world](https://www.gamefile.news/p/avowed-obsidian-making-of-living-lands)
73. [Max Landscape Layers per Component - World Creation - Epic Developer Community Forums](https://forums.unrealengine.com/t/max-landscape-layers-per-component/3791)
74. [Clair Obscur Expedition 33: How 30 Devs Built an 8M RPG](https://studiokrew.com/blog/clair-obscur-expedition-33-unreal-engine-5-case-study/)
75. [Matt Hansen - Former art director of Obsidian Entertainment](https://baike.baidu.com/en/item/Matt%20Hansen/4469272)
76. [Biome Core | Unreal Engine 5.7 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/biome-core)
77. [Nanite Assemblies | Unreal Engine 5.7 Documentation | Epic Developer Community](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-assemblies)
