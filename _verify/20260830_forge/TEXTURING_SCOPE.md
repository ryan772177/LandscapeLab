# Church texturing — scoped, and two facts that change the plan

**Measured before building, because both would have been discovered halfway
through and neither is visible from the brief.**

## FACT 1 — THE FORGED MESH HAS **ONE** MATERIAL SLOT

    /Game/Scratch/ForgeChurch/SM_Church_Forge
    material_slots     ["Material_0"]      <- ONE
    sections at LOD0   1
    LODs               1
    UV channels        1  (smart_project, machine unwrap)
    triangles          60,000
    bbox               [-38.15, -19.75, 0.0] .. [38.15, 19.75, 91.47]

The brief is "plaster nave/tower, stone base, dark copper dome" — **three
materials on a mesh that can address one.** TRELLIS emits a single unsplit
surface, and nothing in forge stages 1-10 creates sections.

The bbox also re-confirms the orientation fix held: Z runs 0 → 91.47, base at
origin.

### THE TWO WAYS OUT

**A. Split the mesh into 3 sections in Blender** (forge stage 4c), assigning
material indices by Z band plus a radial test for the dome, then 3 real slots.
*Costs* a forge change and a re-import; *buys* independent materials, correct
tiling per region, and an asset that behaves normally forever after.

**B. One master material that blends by OBJECT-SPACE Z.** No mesh change.
*Costs* a more complex graph and blend bands that must be tuned by eye against
a render; *buys* no re-forge, and it matches how `M_Alpine8K` already works
(height/triplanar blending is established practice here, not a new idea).

**Recommendation: B for this asset, A as the general rule.** B gets the
landmark finished today against a mesh that is already reviewed and committed
(the .fbx is the artefact of record and re-forging produces a *different*
mesh). A is the right shape for the forge going forward and should be stage 4c
when the wood stacks arrive, because a stack of logs will want per-region
materials far more than a church does.

**A caution for B that the render will decide:** a pure Z blend puts copper on
anything as high as the dome. The dome is the tallest element, but the nave
ridge is close, so the copper band's lower edge is the one number that needs a
frame to set rather than arithmetic.

## FACT 2 — THE v1 TEXTURE SET HAS NO STONE

`Free/_measured/c0_textures_v1.json`, five roles, all 1024x1024:

    beam_wood        plaster_wall     roof_tiles
    wall_planks_a    wall_planks_b

Staged in `refs/textures_v1/` with `_graded` and `_tiled` variants.

    plaster nave/tower   plaster_wall        HAVE
    roof                 roof_tiles          HAVE (not in the brief, but the
                                             church has a large pitched roof
                                             and it will read as something)
    stone base           -- MISSING --       needs generating
    dark copper dome     -- MISSING --       needs generating (brief says so)

**The brief names one generated tile; two are needed.** Stone is as absent as
copper. Options: generate both in one pass, or substitute — but nothing in the
set reads as stone, and using plaster for a base would erase exactly the
grounding the base is there to give.

## WHAT IS READY, AND WHAT IS OWED

    ready    the mesh, UV'd and correctly scaled and oriented
    ready    plaster_wall and roof_tiles, already graded
    owed     an operator decision on A vs B above
    owed     TWO generated tiles: stone, and copper/patina
    owed     the generation guard runs on them like everything else --
             ai_input_guard --strict before any weights load (R-AIGATE)

Nothing here is blocked on difficulty; it is blocked on two inputs that do not
exist and one structural choice that is the operator's.
