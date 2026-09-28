# READING THE TWO CONCEPTS — plain language, before any schema

**2026-08-29.** Written before the recipes, deliberately: the recipe is a
*derived record* and the reading is the thing it derives from. If the reading is
wrong the recipe is confidently wrong, and that is harder to catch.

Sources: `refs/alpine_village_01.jpg`, `refs/alpine_village_02.jpg`, both
1433×736, hash-proven against the operator's originals at adoption.

---

## ⭐ THE HEADLINE: THESE ARE ONE PLACE, NOT TWO SCENES

**Concept 01 is the approach. Concept 02 is standing in it.** The evidence is
specific and it is not a matter of taste:

- **The same mountain.** A single asymmetric horn peak with a steep left face
  and a long right-hand shoulder ridge, snow above roughly the top third. It
  reads identically in both.
- **The same church.** A slender white tower with a dark bulbous onion dome and
  a finial. In 01 it is a silhouette in the village cluster; in 02 it is
  front-and-centre and fully resolved.
- **The same building vocabulary.** Stone or masonry ground floor, heavy timber
  above, shallow-pitched wide-eaved shingled roofs, deep overhangs.
- **The same firewood.** Neat stacked log piles against the buildings, in both.

**This changes the architecture of the whole phase.** The layout recipe should
describe **ONE village** and the two concepts are **two CAMERAS into it**. That
is stronger than treating them as two scenes, and it hands us a free
cross-check: build the village once, and the two camera solves must both land.
If the mountain sits correctly in one view and wrongly in the other, the
*village-to-mountain* relationship is wrong — which no single view can tell you.

---

## CONCEPT 01 — THE APPROACH

**What the camera is doing.** Standing at the edge of a conifer wood, on open
sloping meadow, looking across a shallow basin at a village on the far rise.
Roughly eye level, very slightly elevated, near-level pitch. The horizon sits
about 45% up the frame. Moderate lens — the peak is prominent but not
compressed; there is real depth between foreground grass, midground village and
background mountain.

**Left third: backlit forest.** Tall conifers, trunks bare for most of their
height with foliage up top — the same silhouette as our Norway spruce and Scots
pine. Visible god rays / light shafts raking down between the trunks. The trees
are *in* the frame as a framing device, not the subject.

**Foreground: sunlit meadow.** Open grass, low and tussocky, running downhill
away from camera. Long tree shadows striping it. This is a CLEARING — the
village is seen across open ground, which is what gives the shot its depth.

**Midground right: the village.** Twelve to twenty structures clustered on a
slope that rises to the right. They step up the hillside rather than sitting on
a flat pad. Chalet form: masonry base, timber upper, broad shallow roofs. Wood
stacks visible against several. A track threads between them.

**The church** sits at the left-centre of the cluster — a pale tower with the
dark onion dome, standing perhaps half again the height of the houses around
it. It is the only vertical accent and it anchors the village visually.

**Background centre: the peak.** Snow-capped, dominating, slightly left of the
village. Heavy aerial haze — it is pale and desaturated against a clear sky.

**Bottom right: water.** A stream or beck running down out of the village
toward camera-right, with pale rocks along it.

**Light.** Low sun from behind and to the left, backlighting the trees. Measured
on the meadow band: **sunlit RGB 0.791/0.745/0.657 against shadow
0.102/0.143/0.169** — a 5.5× luminance ratio, warm light (R−B **+0.133**) and
distinctly **cool blue shadow** (R−B **−0.067**). That warm/cool split is the
single most characterful thing about the lighting and it is measurable, not a
matter of opinion.

---

## CONCEPT 02 — INSIDE THE VILLAGE

**What the camera is doing.** Street level, about eye height, standing on a dirt
track looking along it toward the church, with the mountain beyond. Buildings
left and right frame the view into a corridor. Pine branches intrude at the top
left — a deliberate framing device. The composition funnels: track → church →
peak, all on the centre line.

**Left: a large chalet.** Rough stone ground floor, heavy squared-log upper
storey, wide shingled roof with deep eaves, stone chimney. A wall lantern is
**lit**. Firewood stacked deep in the undercroft. A small wooden cart with
painted red detail at the frame edge.

**Right: a taller timber building.** Weathered plank and log construction over a
stone base, an upper balcony with turned railing, lanterns, crates and a bench
at ground level. Cobbled paving in front of it.

**Centre: the church, and it is the most detailed thing in either image.**
Cream plastered walls; an ornate painted or carved panel over the entrance in an
arched surround; pointed arched windows; a covered porch on posts with its own
shingled roof. The tower rises through a belfry stage with arched openings to a
**weathered copper onion dome**, dark red-brown, with a finial above it.

**Ground.** Dirt track, patches of cobble, grass verges, wildflowers in white
and red, and a scatter of rounded river stones. A rivulet of water crosses
left-of-centre. The ground is *busy* — this is where a lot of the richness lives.

**Background.** The same peak, heavily hazed, conifer forest on its lower slopes.

**Light.** Soft, diffuse, hazy — early morning. **The lanterns are lit**, which
is the strongest single clue to time of day. Warm light (R−B **+0.183**, warmer
than 01) against near-neutral shadow (**+0.004**).

**Haze, measured cleanly here.** Saturation rises from **0.145** in the far
field to **0.252** near camera — the far world is washed out to roughly **58%**
of near-field saturation, with luma falling 0.669 → 0.295 over the same span.
That is a strong, specific aerial-perspective target, and it is a number our fog
block can be tuned against instead of by eye.

---

## WHAT I MEASURED VERSUS WHAT I READ

Stated separately, because they carry different weight.

| Claim | How | Confidence |
|---|---|---|
| Warm light / cool shadow split | measured, both images | **high** |
| Haze strength (sat 0.145→0.252) | measured, concept 02 | **high** |
| Sun is LOW | read — long shadows, god rays, lit lanterns | high |
| Sun is behind-left | read — backlit trees, rays from upper left | **medium** |
| Sun azimuth as a NUMBER | **not established** | — |
| Same village, two cameras | read — peak, church, vocabulary, firewood | high |

**The shadow-bearing measurement did not earn its keep and I am not quoting it
as evidence.** The structure tensor returned 3.9° in concept 01 and 175.2° in
concept 02 — both near-horizontal — but at coherence **0.156** and **0.181** on
a 0–1 scale. That is close to isotropic. The meadow's own tussock texture and
the ground detail are as linear as the shadows are, so the estimator is not
separating them. **Reporting a bearing at that coherence would be a number with
no evidence behind it**, which is worse than no number.

**A world sun azimuth needs the camera solve anyway.** Everything above is
image-space. Converting a shadow bearing to a world azimuth requires knowing
where the camera is and which way it faces, and that is Phase B's job. The
atmosphere block therefore carries elevation and colour as usable now, and
azimuth as a bound to be solved.

---

## THE ONE THING I WOULD ASK ABOUT

**These are renders, not paintings.** Both have the depth-of-field, the god
rays, the tonemapping and the foliage cards of a real-time engine — most likely
Unreal. That matters in two directions and I would rather raise it than assume:

- **Good:** the look is *achievable*, not illustrative. Nothing here needs a
  painterly effect we cannot reproduce.
- **Careful:** if these came from an existing asset pack or a marketplace demo,
  then "match the concept" partly means "acquire that pack", and the honest
  answer to some gaps below may be a purchase rather than authoring.

It does not change the reading. It might change what the gap report *means*.
