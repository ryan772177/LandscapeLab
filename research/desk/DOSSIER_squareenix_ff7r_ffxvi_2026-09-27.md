# Square Enix FF7 Remake / Rebirth / FFXVI: Technical Dossier for a UE 5.8 Alpine Open-World Pipeline

The main lesson from all three games is that Square Enix got its density and quality from project-wide physical standards and automation, not from any single engine feature. FFVII Rebirth ran a heavily modified UE4 with a Nanite-like meshlet renderer, whole-level FarLand HLOD meshes, lighting baked only into probes, and collision generated automatically in Houdini.\[1\]\[2\] FFXVI's in-house engine used an irradiance volume, real-time shadows, Houdini terrain tiles 1–4 km across, and vegetation placed by ecological rules. Most of these map onto UE 5.8 features (Nanite, World Partition HLOD, PCG, Lumen/VSM, Niagara). The parts worth copying are the rules and tooling around those features.

## TL;DR
- **Rebirth (UE4, heavily customised) is the closest match to your 8 km alpine map.** Its key pieces:
  - A custom meshlet renderer, so artists made no LODs. Only a few skeletal meshes have LODs, at most 2 levels and under 10% of assets.
  - FarLand whole-level proxy meshes for the far field.
  - Load/unload driven by compute-shader visibility.
  - All lighting baked into probes, with no lightmaps.
  - Collision built automatically in Houdini: voxelise, merge, smooth, then turn back into polygons.
  - Layered materials: non-repeating "flavor" textures, repeating tiling textures, and detail maps.
- **FFXVI (in-house engine) supplies the terrain and vegetation recipe.**
  - Terrain: World Machine → 5–8 × 8K Substance Designer textures per map → Houdini tiles about 1–4 km across, with a distance-based "merge grid".
  - Scale: a playable area about 2 km square, with a far field about 10× larger.
  - Vegetation: a dedicated team, ecological placement rules, and a Houdini Vegetation Placing Tool driven by elevation, slope and occlusion masks.
  - Lighting: irradiance-volume GI, real-time shadows, and light levels anchored to measured real-world brightness (fire, moon, torches).
- **Nothing here is a UE5 recipe.** Every UE 5.x mapping below is a candidate only. Several key numbers are known only from secondhand reports or sit behind CEDiL logins: flame luminance, wind speeds, and Rebirth EV values. Rebirth's probe counts and spacing are now confirmed by CGWORLD. The rest are flagged below.

## (A) Source register

| Title | Event / date | Speakers | URL | Slides / video | Tier |
|---|---|---|---|---|---|
| How Square Enix leveraged Unreal Engine to modernize FFVII REMAKE | Epic developer interview, June 2020 | Naoki Hamaguchi | https://www.unrealengine.com/en-US/developer-interviews/how-square-enix-leveraged-unreal-engine-to-modernize-final-fantasy-vii-remake | Web article | official |
| How Square Enix impressively optimized FFVII REMAKE INTERGRADE for next-gen | Epic developer interview, Aug 5 2021 | Hamaguchi; Shuichi Ikeda (Lead Rendering Programmer); Tomohito Hano (Lead Technical Programmer)\[3\] |\[3\] https://www.unrealengine.com/en-US/developer-interviews/how-square-enix-impressively-optimized-final-fantasy-vii-remake-intergrade-for-next-gen | Web article | official |
| 『FINAL FANTASY VII REMAKE』におけるキャラクターアニメーション技術 (FF7R character animation technology) | CEDEC 2020, Sep 2 2020 | Ryo Hara (Lead Animation Programmer), Akira Iwasawa (Facial Director)\[4\] | http://cedec.cesa.or.jp/2020/session/detail/s5e58c8811bc98 ; https://cedil.cesa.or.jp/cedil_sessions/view/2304 | CEDiL .zip (login) | official page; report by Famitsu https://www.famitsu.com/news/202009/02205099.html = verified-secondary |
| "FINAL FANTASY VII REMAKE"における自動QAシステムの構築と運用 (building and running FF7R's automated QA system) | CEDEC 2020 | Kenichiro Ota\[5\] | https://www.jp.square-enix.com/tech/publications.html | Public PDF + MP4 | official |
| 機械学習によるリップシンクアニメーション自動生成技術とFF7Rのアセットを訓練データとした実装実例 (ML lip-sync generation trained on FF7R assets) | CEDEC 2022 | Masato Nakada, Leandro Graciá Gil, Ryo Hara, Akira Iwasawa\[5\] | same library page | Public PDF | official |
| Lip-Sync ML: Machine Learning-based Framework to Generate Lip-sync Animations in FFVII REBIRTH | ACM SIGGRAPH 2024 Talks, 22:1–22:2\[5\] | Nakada, Graciá Gil, Iwasawa, Hara | same library page | Public abstract + slides PDF | official |
| Shadow Techniques from Final Fantasy XVI | SE Technical Report, 2023\[5\] | Sammy Fatnassi | same library page | Public PDF (17.9 MB) + BibTeX | official |
| Velocity-based compression of 3D rotation, translation, and scale animations | ACM SIGGRAPH 2020 Talks, 45:1–45:2\[5\] | David Goodhue | same library page | Abstract + video | official (the link to a specific game is not stated, so treat it as a general SE technique) |
| コール＆レスポンス！FF7R インターグレード (Call & Response! FF7R INTERGRADE, music) | CEDEC 2021 | SE Sound | https://cedec.cesa.or.jp/2021/session/detail/s604eec308ef77.html ; https://cedil.cesa.or.jp/cedil_sessions/view/2410 | pptx (login) | official (audio only; no Intergrade rendering session was found) |
| 『FFVII REBIRTH』における背景コリジョン及びナビメッシュの生成事例 (background collision and navmesh generation in Rebirth) | CEDEC 2024, Aug 22 2024, 14:40–15:40,\[6\]\[7\] Room 2\[6\] | 西山 慶 Kei Nishiyama, 冨板 亮佑 Ryosuke Tomiita (CS1 programmers); co-developers 北出 智, 黒田 英寛\[6\] | https://cedec.cesa.or.jp/2024/session/detail/s660146be981eb/ ; https://cedil.cesa.or.jp/cedil_sessions/view/2980 | pptx (login) | official |
| 『FFVII REBIRTH』における会話イベントの量産とアニメーションワークフロー (mass-producing dialogue events and the animation workflow in Rebirth) | CEDEC 2024, Aug 21 2024 | Ryo Hara\[8\] | https://cedec.cesa.or.jp/2024/session/detail/s65cdfb727bdd6/ ; https://cedil.cesa.or.jp/cedil_sessions/view/2910 | CEDiL (login) | official |
| ミッドガルを飛び出せ！ FFVII REBIRTH 泥沼サウンド制作秘話 (the "quagmire" of Rebirth's sound production) | CEDEC 2024, Aug 22 2024 | 伊勢 誠, 河盛 慶次, 谷山 輝, 岡田 滉太朗\[9\]\[10\] | https://cedec.cesa.or.jp/2024/session/detail/s6604ee9324bd1/ | CEDiL (login) | official; 4Gamer report = verified-secondary |
| VFXを物理的な数値を基準に作ろう「FINAL FANTASY XVI」環境開発 (building VFX on physical values: FFXVI environment work) | CEDEC 2024, Aug 23 2024, 16:40–17:40, Room 1\[11\] | 山下 広美 Hiromi Yamashita (Lead Environment VFX Artist); co-developers 本多 圭 Kei Honda, Peter Buck, 三好 竜希\[11\]\[12\] | https://cedec.cesa.or.jp/2024/session/detail/s65effb23ea7f1/ ; https://cedil.cesa.or.jp/cedil_sessions/view/2974 | PDF (login)\[11\] | official (abstract only; numbers not public) |
| GameSurvey … AtoR from FINAL FANTASY XVI | CEDEC 2024, Aug 21 2024 | 藤巻 尚樹, 関屋 亮太\[13\] | 4Gamer report https://www.4gamer.net/games/529/G052958/20240823057/ | CEDiL (login) | verified-secondary |
| FFXVIでのTA業務紹介 ～暴れる召喚獣に破壊されまくるステージをつくるには～ (FFXVI technical-art work: stages wrecked by Eikons) | CEDEC 2023, Aug 24 2023, 16:30–17:30\[14\] | 畠山 亮太 Ryota Hatakeyama, 和田 光 Hikaru Wada, 長谷川 千瑛 Chie Hasegawa (Vegetation Lead)\[14\]\[15\] | https://cedec.cesa.or.jp/2023/session/detail/s641834a0c4c40.html ; https://cedil.cesa.or.jp/cedil_sessions/view/2839 | CEDiL (login) | official; CGWORLD report https://cgworld.jp/article/202310-cedec04-ff.html = verified-secondary |
| FFXVIにおける召喚獣とキャラクターモデルの制作舞台裏 (behind the scenes of FFXVI's Eikon and character models) | CEDEC 2023, Aug 25 2023\[16\] |\[16\] 園部 淳 Jun Sonobe, 南條 和哉 Kazuya Nanjo\[16\]\[17\] | reports: https://gamemakers.jp/article/2023_10_17_52272/ ; https://www.4gamer.net/games/529/G052958/20230827005/ | CEDiL (login) | verified-secondary |
| FFXVI：大規模ゲーム開発に向けて開発環境の取り組み (FFXVI: development-environment work for large-scale production)\[18\] | CEDEC 2023, Aug 24 2023, 10:00–11:00\[19\] | CBU3 (names not re-verified here) | https://cedil.cesa.or.jp/cedil_sessions/view/2797 ; CGWORLD report https://cgworld.jp/article/202310-cedec-ff16-01.html | CEDiL (login) | official page / verified-secondary |
| FFXVI：カットシーン制作のためのツールパイプライン (FFXVI: tool pipeline for cutscene production) | CEDEC 2023 | Eitaro Iwabuchi (Cutscene Tech Lead)\[20\] | https://cedec.cesa.or.jp/2023/session/detail/s6400827d08665.html | CEDiL (login) | official |
| FFXVI：フルリモート体制での超大規模カットシーン制作 (FFXVI: very large-scale cutscene production with a fully remote team) | CEDEC 2023 | FFXVI cutscene team lead (ex-FromSoftware)\[21\] | https://cedec.cesa.or.jp/2023/session/detail/s6428d03e92120 | CEDiL (login) | official |
| FFXVI オールレンジのプレイヤーに向けたコンバットデザイン (FFXVI combat design for players of every skill level) | CEDEC 2023 | Ryota Suzuki (Battle Director)\[22\]\[23\] | https://cedec.cesa.or.jp/2023/session/detail/s64285321a8d39.html | CEDiL (login) | official |
| FFXVI サウンド開発日誌 (FFXVI sound development diary) | CEDEC 2023\[24\] | SE Sound | https://cedec.cesa.or.jp/2023/session/detail/s64254f1d6ccd8 | CEDiL (login) | official |
| FFXVIの植物アセット制作事例 (FFXVI plant-asset production case study) | CGWORLD Creative Conference 2023, Nov 8 2023, 20:00–21:00 | SE Vegetation Lead Designer / TA (CBU3) | https://cgworld.jp/special/cgwcc2023/event/square-enix-02/ | Time-limited archive video |\[25\] verified-secondary (named-staff talk) |
| 『FFVII REBIRTH』フェイシャルアニメーションの制作事例 (Rebirth facial animation case study) | CGWORLD Creative Conference 2024 | Akira Iwasawa | https://cgworld.jp/special/cgwcc2024/detail/squareenix/ | Archive video | verified-secondary |
| SQUARE ENIX delivers standout visuals for FFXVI (Autodesk) | Autodesk blog, Jun 27 2024 (cites a GDC 2024 Autodesk Developer Summit talk)\[26\] | Iwabuchi, Sakamoto, Suzuki, Sawada, Higashikawa\[26\] | https://blogs.autodesk.com/media-and-entertainment/2024/06/27/square-enix-delivers-standout-visuals-for-final-fantasy-xvi-with-the-help-of-autodesk-solutions/ | Web + YouTube clips | official (vendor case study) |
| CGWORLD vol.311/312 Rebirth making-of, parts 1–5 | CGWORLD, Aug 2024 |\[2\] Miyake, Ichihara, Nishiyama, Tsunoda, Takai, Kazeno, D. Suzuki, Nakamura, Soma, Nagatsuka, Iwasawa, Yamaguchi, Hamaguchi | https://cgworld.jp/article/202408-ff7reb-01.html … -05.html | Web | verified-secondary |
| CGWORLD vol.268 Remake making-of, parts 1–3 | CGWORLD, Dec 2020 |\[27\] Ikeda, Soma, Iwasawa, Hara, et al. | https://cgworld.jp/feature/202012-ffvll-01.html (-02, -03) | Web | verified-secondary |
| CGWORLD vol.301 FFXVI making-of, parts 1–2 | CGWORLD, Sep 2023 | Takai, Minagawa, Kei Honda, Yusuke Hashimoto\[28\] | https://cgworld.jp/article/202309-cgw301-ff16-01.html | Web | verified-secondary |
| FFVII REBIRTH official site (PC FAQ and specs) | square-enix.com | — | https://www.square-enix.com/ffvii/en-us/games/rebirth/ | Web | official |
| FFXVI update log | square-enix-games.com\[29\] | — | https://www.square-enix-games.com/en_US/documents/update-final-fantasy-xvi | Web | official |
| Hamaguchi on staying with UE4 | AUTOMATON, Feb 26 2026 (direct interview) | Naoki Hamaguchi |\[30\] https://automaton-media.com/en/interviews/final-fantasy-7-remake-trilogys-third-entry-is-progressing-very-smoothly-we-ask-director-naoki-hamaguchi-why-the-team-chose-not-to-switch-to-unreal-engine-5/ | Web | verified-secondary |
| FFVII REMAKE INTERGRADE Switch 2 interview | Nintendo UK, Jan 2026 | Naoki Hamaguchi | https://www.nintendo.com/en-gb/News/2026/January/FINAL-FANTASY-VII-REMAKE-INTERGRADE-Interview-Naoki-Hamaguchi-Director-3010151.html | Web | official (platform holder) |
| GDC 2024 "Wrangling Complexity…" (Iwabuchi); "Designing Active Time Lore" (Aono) | GDC 2024 | per brief | gdcvault.com (not re-fetched this pass) | Vault (partly paywalled) | official (URL not re-verified) |

## (B) Hard-numbers table

| Item | Value | Game | Source |
|---|---|---|---|
| Remake base engine version | UE 4.18\[3\] | Remake / Intergrade | Epic Intergrade interview (Hamaguchi) |\[3\]
| Intergrade load time | about 12 s → 6 s (custom serialisation) → about 2 s (Unversioned Property Serialization + IOStore back-ported from UE 4.25) | Intergrade | Epic Intergrade interview (Hano) |\[3\]
| Intergrade modes | 4K graphics mode at 30 fps; performance mode at 60 fps\[3\]\[31\] | Intergrade |\[3\] Epic Intergrade interview; PlayStation.Blog Feb 25 2021 |
| Main-character polygon increase | about 2× Remake for lead characters\[32\] | Rebirth | CGWORLD part 2 (Dai Suzuki / Kazeno) |
| Polygon counts | Cloud: FFVII approx. 900, Remake approx. 110,000, Rebirth approx. 220,000. Red XIII approx. 120,000; Cait Sith approx. 100,000; Moogle approx. 230,000; Buster Sword approx. 8,000; Midgardsormr approx. 260,000. Smallest object 12, largest approx. 2,300,000. Hair "accounted for half of the total polygon count" of Remake's Cloud | Rebirth | PlayStation.Blog, Mar 21 2024 (Dai Suzuki, Lead Character Artist). Verified. |
| Artist-made LODs | none for static meshes; some skeletal meshes have 2 LOD levels, under 10% of assets\[1\] | Rebirth | CGWORLD part 4 (Miyake) |
| Frame rate target | 30 → 60 fps (VFX texture resolution raised under that budget)\[1\] | Rebirth | CGWORLD part 4 (Tsunoda) |
| VFX source textures | general-purpose smoke and explosion sheets at 4K / 8K\[1\] | Rebirth | CGWORLD part 4 (Tsunoda) |
| Visuals-to-gameplay tuning ratio | about 8:2 in Remake → about 5:5 in Rebirth\[1\] | Rebirth | CGWORLD part 4 (Ichihara) |
| Feeler horde | 3 tiers: hero skeletal model → VAB mid-ground → GPU particles far\[1\] | Rebirth | CGWORLD part 4 |
| Light probes | about 270,000 with Remake-style even spacing → about 40,000 by varying density with asset detail; spacing about 2 m in towns, about 10 m in open fields. EV 14–15 sunny / 4–8 indoor per user brief | Rebirth | CGWORLD part 5 (Aug 21 2024): probe count and spacing confirmed. EV values UNVERIFIED. |
| Cutscenes | about 700 | Rebirth | CGWORLD, per user brief (not re-verified) |
| PC presets and caps | 3 presets; up to 120 fps; DLSS; VRR; background-model LOD and background-texture MIP adjustable\[33\] | Rebirth PC | square-enix.com Rebirth page |
| PC specs | Min: RTX 2060 / RX 6600 / Arc A580, 1080p 30 fps Low. Rec: RTX 2070 / RX 6700 XT, 1080p 60 fps Medium. Ultra: RTX 4080 / RX 7900 XTX, 2160p 60 fps High. 16 GB RAM, 155 GB SSD, Shader Model 6.6 + DX12 Ultimate required, 12–16 GB VRAM for 4K\[33\] | Rebirth PC | square-enix.com Rebirth page |
| PS5 Pro | v1.050 adds a "Versatility Mode" using PSSR and High CPU Frequency Mode\[33\] | Rebirth | square-enix.com Rebirth page |
| Switch 2 / Xbox release | June 3 2026\[33\] | Rebirth |\[30\] square-enix.com Rebirth page |
| Terrain textures | 5–8 × 8K Substance Designer textures per map | FFXVI | CEDEC 2023 TA session (via CGWORLD) |\[15\]
| Terrain tile mesh size | about 1–4 km square per mesh | FFXVI | CEDEC 2023 TA session (via CGWORLD) |\[15\]
| Playable area vs far field | about 2 km square playable; far field about 10× | FFXVI | CEDEC 2023 TA session (via CGWORLD) |\[15\]
| Destruction pieces | small meshes up to about 10; large meshes 300–400 per FBX; assembled modules under about 3,000 ran on hardware | FFXVI | CEDEC 2023 TA session Q&A (via CGWORLD) |\[15\]
| Streaming memory | full-resolution everything ≈ +3 GB vs about 300 MB with streaming | FFXVI | CGWORLD vol.301 part 1 (Kei Honda) |\[28\]
| Early Eikon battle | over 100M polygons in scene, 1–0.5 fps before optimisation | FFXVI | CGWORLD vol.301 part 1 |\[28\]
| Shadows | close-up 2048 shadow maps; Oriented Depth Bias 2 mm; 5.73 → 3.94 ms | FFXVI | SE tech report (Fatnassi, 2023), per brief; PDF listed on the library page |
| Emissive scroll | up to 3 scroll patterns + flow map\[16\] | FFXVI | CEDEC 2023 characters session (via gamemakers.jp) |\[16\]
| PC specs | Min 720p 30 fps (GTX 1070 / RX 5700 / Arc A580); Rec 1080p 60 fps (RTX 2080 / RX 6700 XT); 16 GB RAM; 170 GB SSD; 8 GB+ VRAM | FFXVI PC | jp.finalfantasyxvi.com (via subagent) |\[34\]
| 240 fps cap; DLSS 3 / FSR 3 / XeSS 1.3 | Tom's Hardware's FFXVI PC benchmark confirms "DLSS3, FSR3, and XeSS 1.3 are present and accounted for" (secondary). The 240 fps cap is stated only by Famitsu and thehikaku | FFXVI PC | Upscalers: verified-secondary. 240 fps cap: UNVERIFIED on an official SE page |
| Flame luminance (cd/m²/EV); wind speeds (m/s) | not public | FFXVI | CEDEC 2024 Yamashita slides (CEDiL login) |\[11\]

## (C) How they built it

### FINAL FANTASY VII REMAKE (2020) / INTERGRADE (2021)

**Rendering and lighting.**
- UE4 was used as a framework. The team wrote its own light probes, reflections, light baking, skinning, particles, post effects, tone mapping, materials and lighting. All image processing is written directly in shaders, not as post-process materials. (Hamaguchi, Epic 2020.)\[35\]
- Lead Rendering Programmer Ikeda says the rendering, lighting and post-processing were entirely rewritten, so they are "completely different from standard UE4" (CGWORLD vol.268 part 1).\[36\]
- Static and dynamic lights followed a strict placement policy. Backgrounds used lightmaps and characters used light probes.\[2\]\[35\]

**Intergrade upgrades (Ikeda, Epic 2021).**
- More lights in towns and a higher-resolution environment map for neon reflections.\[3\]
- Static-light colour burn and probe luminance correction were reworked.\[3\]
- Volumetric fog was rebuilt with no arbitrary parameters, on a PBR basis:\[3\]
  - Artists paint density into world space.\[3\]
  - The density is stored as probe data and injected at runtime into voxels inside the camera frustum.\[3\]
  - The fog is lit by point lights and by probes, uses Mie scattering, and includes heat haze.\[3\]
  - Effects can inject fog (for example Nero's attacks).\[3\]
- Bloom combines volumetric fog with post-processing, using revised decimation and kernels.\[3\]
- SSR also traces rough surfaces. It stores the polygon-surface vectors in a buffer to fix tracing errors caused by normal maps. It keeps two history images, with and without fog, so fog is not applied twice in reflections.\[3\]
- SSAO is used for micro-shadowing, with a rewritten denoiser.\[3\]
- Shadow buffers were reallocated and sampling jitter and bias were fixed.\[3\]
- Oodle Texture + Kraken allowed higher-resolution textures and lightmaps within the disc budget.\[3\]

**Characters.**
- Tools: Maya 2017 (standardised), ZBrush, Substance Painter, and Simplygon 7 for LODs.\[37\]
- An in-house checker validates bones, topology and attributes before import into UE4.\[37\]
- AO is baked in Substance with values matched to the environment team.\[37\]
- Cutscenes use the same assets as gameplay but render only LOD0. (CGWORLD vol.268 part 1.)\[37\]

**Animation (CEDEC 2020, Hara / Iwasawa; via Famitsu and CGWORLD).**
- Built on UE4 by combining established techniques rather than inventing new ones.\[4\]
- Inertial interpolation (慣性補間) blends from the last pose, so action inputs respond instantly without breaking the animation.\[4\]
- Layered procedural animation cut the number of motion assets needed for field events and battle.\[38\]
- Facial animation had the most procedural work:
  - Lip-sync used SE's "Happy Sad Face", updated for this game. It maps phonemes to shapes that are bone animations made by facial animators, not blend shapes.\[27\]
  - Adjustments react to volume and emotion, with emotion detected by AGI's ST Emotion SDK.\[27\]
  - This covers 4 languages for field and battle. Cutscenes are hand-keyed in Japanese and English.\[27\]

**Production.**
- A dedicated lighting team was formed around the time the project moved into mass production, which CGWORLD calls unusual for a Japanese title.\[39\]
- An automated QA system with replay was presented at CEDEC 2020 (public PDF and video).\[5\]

### FINAL FANTASY VII REBIRTH (2024; PC 2025; Switch 2 / Xbox 2026)

**Engine strategy.**
- Hamaguchi says the team chose UE4 early in Rebirth's development. Tying milestones to UE5's roadmap risked a stall if the engine slipped. An in-house graphics pipeline makes optimisation and porting easier. Part 3 stays on UE4 to reuse that pipeline. (AUTOMATON, Feb 2026.)\[30\]\[40\]\[41\]
- For the Switch 2 port of Remake, lighting was kept identical across platforms to protect how the characters look (Nintendo UK, Jan 2026).\[42\]

**Rendering, LOD and streaming (CGWORLD part 4).**
- A custom meshlet-based renderer makes large object counts cheap. CGWORLD calls it Nanite-like. Artists author no LODs.\[1\]
- FarLand models turn a whole town or island level into one lightweight far mesh. This is effectively HLOD.\[1\]
- Objects load and unload instantly by combining compute-shader visibility tests, spatial volumes and pre-measured data. The team credits PS5 hardware for making this work.\[1\]
- Terrain was made however each artist preferred: UE Landscape, ZBrush sculpting, or Maya.\[1\]

**Lighting (CGWORLD part 5, Yamaguchi).**
- Lightmaps were dropped for the field because baking them was too costly in time and data size. Backgrounds now use light probes like characters.\[2\]
- The probe tools were heavily upgraded to fight flat shading and light leaks.\[2\]
- Lighting Director 山口 威一郎 (Iichiro Yamaguchi) describes a "subtractive" approach (引き算の考え方): start from a bright day and work out where to create shadow. Remake was additive, adding lights into darkness.
- The new renderer changed the cost of lights. Even shadowless lights became expensive if they covered a wide area.\[2\]
  - A debug view for lighting cost was added.\[2\]
  - Light counts were capped in some locations.\[2\]
  - Probes sometimes turned out to be the cost hotspot.\[2\]
- Some locations got dedicated sky domes (for example Cosmo Canyon's dusk), although every extra sky dome costs memory.\[2\]
- Simple dialogue events moved from Excel-driven lights to the Dialogue Editor + Sequencer.\[2\]
- CGWORLD part 5 confirms the probe numbers. Remake-style even spacing would have needed about 270,000 probes. Varying density with asset detail brought that down to about 40,000, spaced about 2 m apart in towns and about 10 m in open fields. The EV figures in the brief are still unverified.

**Materials.**
- Layered materials combine non-repeating "flavor" textures with repeating tiling textures.\[1\]
- Detail maps are tuned so that small and large rocks read with the same apparent detail density.\[1\]

**Collision and navmesh (CGWORLD part 4 + CEDEC 2024 page).**
- Per-actor UE parameters control generation: whether an actor is included, whether to smooth it, how many smoothing passes, and a planting-specific setting.\[1\]
- Houdini rebuilds the UE layout, voxelises the actors, merges and smooths them, then converts them back to polygons. This removes internal overlaps.\[1\]
- Output comes back through a normal UE import, or through Landscape import when set up as a heightmap.\[1\]
- The CEDEC abstract adds split management and runtime handling for a seamless world.\[6\] It also notes memory limits during both production and runtime.\[6\]

**Characters (CGWORLD part 2).**
- Cloud was fully rebuilt. Other leads were detailed up with Remake meshes as guides, so their faces keep the same look.\[32\]
- Barret got only a costume upgrade, because detail was focused where it paid off most.\[32\]
- The eye shader was rebuilt:
  - A normal map from a sculpted iris (iris frill and ciliary structures).\[32\]
  - Shading values taken from real-world measurement data.\[32\]
  - Refraction caustics and in-eye shadowing.\[32\]
- Hair still uses hair cards, not strands, with finer detail for 4K and HDR.\[32\]
- Multi-part enemies (with breakable parts) use an automated tool tracked in ShotGrid. On commit it splits the model, builds LODs and updates the UE assets.\[32\]

**VFX (CGWORLD part 4).**
- Cascade was replaced by Niagara, and almost every Remake effect was rebuilt. Programmers supplied optimised custom modules.\[1\]
- User parameters let one system cover many variants, which cut the number of background effect files (for example the Lifesprings).\[1\]
- VAT was replaced by VAB (Vertex Animation Buffer):
  - A ByteAddressBuffer packs data at the bit level.\[1\]
  - There is no power-of-two limit and any frame count is allowed.\[1\]
  - A Houdini exporter was provided.\[1\]
- Field wind drives chimney smoke and death-effect motion.\[1\]

**Animation.**
- Lip-Sync ML (SIGGRAPH 2024) generates mouth movement from audio for cutscenes and planner events.\[5\]\[43\]
- Destruction is simulated in Houdini by TA and checked by animation.\[43\]
- Tentacles are animated automatically.\[43\]
- Grass and tree sway, rivers and waterfalls use vertex animation made with the environment and TA teams.\[43\]
- Cutscene layout goes from Blender 3D storyboards straight into MotionBuilder.\[1\]

### FINAL FANTASY XVI (2023; PC 2024; Xbox 2025)

**Engine and rendering (CGWORLD vol.301 part 1: Takai, Minagawa, Honda, Hashimoto).**
- A newly designed in-house engine. Luminous was rejected because its development timeline overlapped and it did not fit the CBU3 workflow.\[28\]
- GI uses an irradiance volume, giving real-time bounce light in nearly every scene.\[28\]
- Shadows are all real-time so that destruction works. Techniques in the Fatnassi report: tiled deferred shadows, close-up 2048 maps, and Oriented Depth Bias 2 mm.
- Light levels are anchored to measured real-world brightness: moonlight, torches, candles and campfires, filmed in a fire-permitted studio. They were exaggerated with VFX only where gameplay needed it.\[28\]
- A VFX "boost" adjusts effect brightness to the surrounding light.\[28\]
- Streaming brings memory down from about +3 GB to about 300 MB.\[28\]
- No official public source was found for sky/atmosphere, volumetric fog, water shading or terrain-material layering (see Gaps).

**Terrain and far field (CEDEC 2023 TA session).**
1. World Machine makes the terrain shape.
2. Substance Designer makes 5–8 × 8K textures per map.
3. Houdini automatically splits the data into tiles (the single-texture heightmaps and masks exceeded tool limits).
4. Asset Editor converts the tiles to binary, at about 1–4 km per mesh.
5. The tiles are placed in MapEditor.
6. An automatic "merge grid" build merges tiles and reduces polygon and texture budgets by distance from the playable area.\[15\]

The playable area is about 2 km square, with a far field about 10× larger.\[15\]

**Vegetation (CEDEC 2023 TA session; CGWCC 2023).**
- A dedicated vegetation team was created at the art director's request.\[15\]
- Ecological rules:
  - Broadleaf trees in warm areas, conifers in cold ones.\[15\]
  - Forest edges follow ecology concepts: mantle communities (マント群落) and sun-loving trees (陽樹).\[15\]
- The Houdini Vegetation Placing Tool builds elevation, slope and occlusion masks from the terrain. It adds plant-community masks, places chosen species, and exports positions to the engine.\[15\]
- Grass is painted by layout artists with an in-engine brush.\[15\]
- Branch and leaf cards come mainly from SpeedTree, with some made in ZBrush/Maya or from photos.\[15\]
- A Substance Designer atlas tool and autumn-foliage rules were used.\[15\]
- Species variants were kept to a minimum and grass polygon counts were cut hard.\[15\]
- CGWCC 2023 lists the tools as SpeedTree 8.2.1, Substance Designer 2019, Maya 2018 and Houdini 18.\[25\]

**Destruction.**
- Maya → Houdini tools → simulation → FBX → Maya → engine.\[15\]
- Separate tools for stone, wood (splinters follow the grain), line cuts, and Zantetsuken slices.\[15\]
- Piece budgets are in table B.

**Characters and Eikons (CEDEC 2023, Sonobe / Nanjo).**
- No separate cinematic models: every model must run in real time.\[16\]\[44\]
- Concept art comes first, and clothing is built in Marvelous Designer rather than from photogrammetry.\[16\]
- Pipeline: Maya → Marvelous Designer → ZBrush → Maya retopology/UV/skinning → Substance 3D Painter → in-engine Chara Editor (IBL look-dev and submit).\[16\]
- Block models let downstream work start before the final models are done.\[16\]
- Eikon detail comes from pattern models (surface meshes) and blended tiling textures of different densities, with blend weight capped at 100%.\[16\]
- Emissive, metallic, roughness and normal scroll animations use up to 3 patterns plus a flow map.\[16\]
- SSS gives a translucent look without real transparency (Shiva's cape).\[16\]

**Rigging and cutscenes (Autodesk case study).**
- The facial rig is built on FACS with extra poses. Driven-key curves remove linear in-betweens.\[26\]
- Cloth uses Bonamik (bone-based physics) plus KineDriver (corrective helper bones).\[26\]
- A primary rig handles the body and a secondary rig handles sway.\[26\]
- Maya and MotionBuilder with a "Send To Maya" bridge.\[26\]
- A cutscene checker catches frame-rate, naming and key errors.\[26\]
- An "Add Voice" tool made a three-step voice-placement task a single step.\[26\]
- Mocap uses real-time previs inside MotionBuilder layouts.\[26\]

**PC options (official update log).**
- DLSS, FSR and XeSS.\[29\]
- Dynamic Resolution.\[29\]
- SSR.\[29\]
- VRS.\[29\]
- Shadow quality low/medium/high, which includes cloud quality.\[29\]
- Tom's Hardware's PC benchmark confirms DLSS 3, FSR 3 and XeSS 1.3 (secondary source). The 240 fps cap is stated only by Famitsu and third-party sites and is UNVERIFIED on an official SE page.

## (D) Transfer to a UE 5.8 open-world pipeline (candidate mappings only)

| SE technique | Closest UE 5.x concept | Recommendation for your project |
|---|---|---|
| Rebirth meshlet renderer, no artist LODs | Nanite (static meshes, Nanite landscape, Nanite foliage) | Adopt. Still keep Rebirth's rule of occasional 2-level LODs for skeletal meshes (under 10% of assets). |
| FarLand whole-level proxy | World Partition HLOD (merged / simplified / approximated layers) | Adopt. Build per-region HLOD layers. Treat far peaks as "FarLand"-style single proxies. |
| Compute-shader visibility streaming | World Partition streaming + Nanite culling | Use stock systems. Profile I/O on consoles as the Intergrade team did. |
| Probe-only baked lighting, 2 m / 10 m spacing | Lumen (dynamic) or Volumetric Lightmaps / probe placement | For a dynamic time of day, use Lumen. Borrow the idea of density rules per area and a lighting-cost debug view. |
| Measured real-world light levels / EV (14–15 sun) | Physical light units, Exposure Compensation, fixed EV per biome | Adopt. Lock the sun EV range and anchor emissives (fire) to measured values, as FFXVI VFX did. |
| FFXVI irradiance volume GI | Lumen GI | Lumen replaces it. The discipline of measured values still transfers. |
| FFXVI tiled shadows, 2048 close-up maps | Virtual Shadow Maps | VSM covers this. Use contact/character shadow settings to match the close-up quality. |
| World Machine → Substance 8K → Houdini 1–4 km tiles | Landscape (Nanite) + Houdini Engine / Gaea import; World Partition cells | For 8 km, a few 2–4 km import regions look reasonable. Automate the splitting as FFXVI did. |
| Vegetation Placing Tool (ecology masks) | PCG graphs (slope/height/occlusion samplers, biome rules) | Adopt directly. Encode alpine zonation (conifer bands, treeline, mantle edges) as PCG rules. |
| Houdini collision voxel/merge/smooth | Houdini Engine or Geometry Script + simplified collision; Chaos | Adopt for rock and cliff clusters. Stops overlapping collision from hurting memory and navigation. |
| Flavor + tiling + detail-map materials | Landscape layers, Runtime Virtual Texture, detail textures, Substrate | Adopt. Match apparent texel density across asset scales. |
| VAB instead of VAT | Niagara + Houdini VAT plugin, or custom buffers | VAT is fine in UE5. Consider buffers only if power-of-two limits bite. |
| Wind drives VFX | Niagara parameter collections / global wind | Adopt one project-wide wind speed in m/s feeding foliage, cloth and VFX. |
| Hair cards (Rebirth), generic hair texture + extra occlusion (FFXVI) | MetaHuman Groom (strands), card LODs | Use groom strands for close-ups and cards for far LODs. |
| Eye shader from sculpted iris normals | MetaHuman eye / Substrate eye | Compare against MetaHuman defaults. Add an iris normal map if needed. |
| FACS rig + Bonamik/KineDriver | MetaHuman Control Rig, Chaos Cloth, ML Deformer | Use the stock systems. Keep the primary/secondary rig split. |
| Lip-Sync ML, Happy Sad Face | MetaHuman Animator / Audio-to-Face | Use the stock tools. Hand-key hero cutscenes, as both games did. |

## (E) Gaps
- **Behind the CEDiL login:** slides for all CEDEC 2020–2024 sessions listed above, including:
  - Yamashita's flame luminance and wind-speed values\[11\]
  - Rebirth collision memory budgets and navmesh partition sizes
  - Hara's 2020/2024 animation-layer structure and asset-count reductions
- **Not found:**
  - Any Unreal Fest talk on Rebirth.
  - Any CEDEC 2025/2026 session on Rebirth or FFXVI ports.
  - Any SIGGRAPH Advances course on these games.
  - A CEDEC 2021 Intergrade rendering session (only the music session was found).
- **FFXVI rendering gaps:** no official source found for sky/atmosphere, volumetric fog, water or terrain materials.
- **Items from the brief not re-read this pass:** the GDC 2024 Vault entries and the CGWORLD Rebirth EV figures. They are attributed to their stated sources and still need verification against the original page or PDF. The PlayStation.Blog polygon counts (Dai Suzuki, Mar 21 2024) and the CGWORLD part 5 probe count and spacing are now verified.
- **UNVERIFIED claims:**
  - The FFXVI 240 fps cap (official SE page not found). The DLSS 3 / FSR 3 / XeSS 1.3 support is confirmed by Tom's Hardware, a secondary source, not an official SE page.
  - The settings list from DSOGaming's FFXVI PC Performance Analysis ("Textures, Terrain, Shadows, Water, Clutter Density and NPC Quantity"). This is a secondary source, not an official one.

## Sources

1. [広大な世界を描き出す画づくりの粋〜『FINAL FANTASY VII REBIRTH』（4）ワールドマップ・エフェクト編](https://cgworld.jp/article/202408-ff7reb-04.html)
2. [広大な世界を描き出す画づくりの粋〜『FINAL FANTASY VII REBIRTH』（5）ライティング・カットシーン篇](https://cgworld.jp/article/202408-ff7reb-05.html)
3. [How Square Enix impressively optimized FINAL FANTASY VII REMAKE INTERGRADE for next-gen - Unreal Engine](https://www.unrealengine.com/en-US/developer-interviews/how-square-enix-impressively-optimized-final-fantasy-vii-remake-intergrade-for-next-gen)
4. [『FFVII リメイク』はセリフや音声から、クラウドたちの表情を自動生成。より豪華でリアルなキャラクターモーションを大量に制作する自動生成の手法【CEDEC 2020】 | ゲーム・エンタメ最新情報のファミ通.com](https://www.famitsu.com/news/202009/02205099.html)
5. [LIBRARY | テクノロジー推進部 ADVANCED TECHNOLOGY DIVISION | SQUARE ENIX](https://www.jp.square-enix.com/tech/publications.html)
6. [『FINAL FANTASY VII REBIRTH』における背景コリジョン及びナビメッシュの生成事例 ～広がった世界への対応と発生した問題、その対策について～ | CEDEC2024](https://cedec.cesa.or.jp/2024/session/detail/s660146be981eb/)
7. [『FINAL FANTASY VII REBIRTH』における背景コリジョン及びナビメッシュの生成事例 ～広がった世界への対応と発生した問題、その対策について～](https://cedil.cesa.or.jp/cedil_sessions/view/2980)
8. [「FFVII リバース」のアニメーションに迫る。自動生成を上手く取り入れ、手動調整の負担を軽減【CEDEC2024】 | Gamer](https://www.gamer.ne.jp/news/202408220021/)
9. [最終的に必要だったのは“気合い”。「FINAL FANTASY VII REBIRTH」のサウンド制作はなぜ“泥沼”にはまり，どうやって完成をみたのか［CEDEC 2024］](https://www.4gamer.net/games/638/G063881/20240825027/)
10. [「FFVII リバース」のサウンド制作を支えたのは「気合い」。ワールドマップの実装でより深みにハマったサウンド制作【CEDEC2024】 | Gamer](https://www.gamer.ne.jp/news/202408220085/)
11. [VFXを物理的な数値を基準に作ろう「FINAL FANTASY XVI」環境開発](https://cedil.cesa.or.jp/cedil_sessions/view/2974)
12. [VFXを物理的な数値を基準に作ろう「FINAL FANTASY XVI」環境開発 | CEDEC2024](https://cedec.cesa.or.jp/2024/session/detail/s65effb23ea7f1/)
13. [「FF16」の開発・デバッグを支えたシステム“GameSurvey”とは？ 導入の経緯から機能の解説，成果が語られたセッションをレポート［CEDEC 2024］](https://www.4gamer.net/games/529/G052958/20240823057/)
14. [FINAL FANTASY XVIでのTA業務紹介 ～暴れる召喚獣に破壊されまくるステージをつくるには～](https://cedil.cesa.or.jp/cedil_sessions/view/2839)
15. [『FINAL FANTASY XVI』の召喚獣に破壊されるステージをつくりあげた背景関連TAたちの取り組み総まとめ～CEDEC2023（4）](https://cgworld.jp/article/202310-cedec04-ff.html)
16. [『ファイナルファンタジーXVI』のキャラクターモデル制作手法を解説。PS5上で快適に動く軽量さを保ちつつ、カットシーンで映えるディテールをどう生み出すか【CEDEC2023】｜ゲームメーカーズ](https://gamemakers.jp/article/2023_10_17_52272/)
17. [『FF16』召喚獣＆キャラモデル制作舞台裏。ゲームパートもムービーパートもひとつのモデルでこなせる仕組みを解説【CEDEC2023】 | ゲーム・エンタメ最新情報のファミ通.com](https://www.famitsu.com/news/202308/26314649.html)
18. [大規模ゲームの開発をより効率的に、『FINAL FANTASY XVI』に向けた開発環境の取り組み～CEDEC2023（2）](https://cgworld.jp/article/202310-cedec-ff16-01.html)
19. [FINAL FANTASY XVI：大規模ゲーム開発に向けて開発環境の取り組み](https://cedil.cesa.or.jp/cedil_sessions/view/2797)
20. [FINAL FANTASY XVI：カットシーン制作のためのツールパイプライン | CEDEC2023](https://cedec.cesa.or.jp/2023/session/detail/s6400827d08665.html)
21. [FINAL FANTASY XVI：フルリモート体制での超大規模カットシーン制作 | CEDEC2023](https://cedec.cesa.or.jp/2023/session/detail/s6428d03e92120)
22. [FINAL FANTASY XVI ～オールレンジのプレイヤーに向けたコンバットデザイン～ | CEDEC2023](https://cedec.cesa.or.jp/2023/session/detail/s64285321a8d39.html)
23. [「FFXVI」の全プレーヤーに成功体験をもたらすコンバットデザイン【CEDEC2023】 - GAME Watch](https://game.watch.impress.co.jp/docs/news/1525973.html)
24. [FINAL FANTASY XVI：サウンド開発日誌 ～迫力の演出の裏の、地味な実装の工夫たち～ | CEDEC2023](https://cedec.cesa.or.jp/2023/session/detail/s64254f1d6ccd8.html)
25. [FINAL FANTASY XVIの植物アセット制作事例 | CGWORLD 2023 CREATIVE CONFERENCE](https://cgworld.jp/special/cgwcc2023/event/square-enix-02/)
26. <https://blogs.autodesk.com/media-and-entertainment/2024/06/27/square-enix-delivers-standout-visuals-for-final-fantasy-xvi-with-the-help-of-autodesk-solutions/>
27. [キャラクター性や世界観を損なわずリアルに表現～『FINAL FANTASY VII REMAKE』（2）アニメーション&エンバイロンメント](https://cgworld.jp/feature/202012-ffvll-02.html)
28. [独自エンジンによる、アートとリアルの中間をねらった画づくり〜『FINAL FANTASY XVI』（1） 開発環境・画づくり篇](https://cgworld.jp/article/202309-cgw301-ff16-01.html)
29. [SQUARE ENIX | The Official SQUARE ENIX Website - Update to FINAL FANTASY XVI](https://www.square-enix-games.com/en_US/documents/update-final-fantasy-xvi)
30. [Final Fantasy 7 Remake trilogy’s third entry is progressing “very smoothly.” We ask director Naoki Hamaguchi why the team chose not to switch to Unreal Engine 5 - AUTOMATON WEST](https://automaton-media.com/en/interviews/final-fantasy-7-remake-trilogys-third-entry-is-progressing-very-smoothly-we-ask-director-naoki-hamaguchi-why-the-team-chose-not-to-switch-to-unreal-engine-5/)
31. [Final Fantasy VII Remake Intergrade arrives on PS5 June 10, 2021 – PlayStation.Blog](https://blog.playstation.com/2021/02/25/final-fantasy-vii-remake-intergrade-arrives-on-ps5-june-10-2021/)
32. [PS5の恩恵を得てより詳細に描かれる『FFVII』のキャラクターたち〜『FINAL FANTASY VII REBIRTH』（2）キャラクター制作編](https://cgworld.jp/article/202408-ff7reb-02.html)
33. <https://www.square-enix.com/ffvii/en-us/games/rebirth/>
34. [FINAL FANTASY XVI （ファイナルファンタジー16）| SQUARE ENIX](https://jp.finalfantasyxvi.com/)
35. [How Square Enix leveraged Unreal Engine to modernize FINAL FANTASY VII REMAKE](https://www.unrealengine.com/en-US/developer-interviews/how-square-enix-leveraged-unreal-engine-to-modernize-final-fantasy-vii-remake)
36. [UE4の大規模カスタマイズが支えた"懐かしくも新しい『FFVII』"～『FINAL FANTASY VII REMAKE』（1）開発体制&キャラクター制作](https://cgworld.jp/feature/202012-ffvll-01.html)
37. [UE4の大規模カスタマイズが支えた"懐かしくも新しい『FFVII』"～『FINAL FANTASY VII REMAKE』（1）開発体制&キャラクター制作 | 特集 | CGWORLD.jp](https://cgworld.jp/feature/202012-ffvll-01-2.html)
38. [『FINAL FANTASY VII REMAKE』におけるキャラクターアニメーション技術](https://cedil.cesa.or.jp/cedil_sessions/view/2304)
39. [実在感を支える画づくりの妙〜『FINAL FANTASY VII REMAKE』（3）VFX＆ライティング](https://cgworld.jp/feature/202012-ffvll-03.html)
40. [『ファイナルファンタジーVII』リメイクシリーズ最終作も、ゲームエンジンは「Unreal Engine 4」。あえてUE5に移行しない“メリット” - AUTOMATON](https://automaton-media.com/articles/newsjp/20260127-411814/)
41. [『ファイナルファンタジーVII』リメイクシリーズの三部作目はスムーズに開発中らしい。なぜ順調なのか、UEバージョンを上げない理由などを開発者に訊いた - AUTOMATON](https://automaton-media.com/articles/newsjp/ff7-20260226-424531/)
42. [FINAL FANTASY VII REMAKE INTERGRADE Interview – Naoki Hamaguchi, Director | News | Nintendo UK](https://www.nintendo.com/en-gb/News/2026/January/FINAL-FANTASY-VII-REMAKE-INTERGRADE-Interview-Naoki-Hamaguchi-Director-3010151.html)
43. [PS5の恩恵を得てより詳細に描かれる『FFVII』のキャラクターたち〜『FINAL FANTASY VII REBIRTH』（3）モーション編](https://cgworld.jp/article/202408-ff7reb-03.html)
44. [［CEDEC2023］「FINAL FANTASY XVI」のキャラクターモデルアーティストが明かす，巨大な召喚獣や高精細なキャラクターをリアルタイムで動かすための工夫とは](https://www.4gamer.net/games/529/G052958/20230827005/)
