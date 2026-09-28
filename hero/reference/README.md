# Hero reference images — the TRELLIS pipeline's input

Adopted 2026-08-15 from `C:\Users\Admin\Downloads` at Ryan's direction.
Copies at stable names, **SHA-256 proven equal to their sources at adoption
time** (non-negotiable 20). The Downloads originals are a location that gets
cleaned out; nothing downstream may point at them.

All four are Gemini-generated, 1375x768, Ryan's own.

| File | Original name | SHA-256 | Role |
|---|---|---|---|
| `hero_face_bald_frontal.jpg` | `Gemini_Generated_Image_3uwedd3uwedd3uwe.jpg` | `4cb7d442a87cee435262a0fc2e217709b9ee9c9d592242e4b3ef4238e018af1e` | **TRELLIS input** |
| `hero_face_haired_frontal.jpg` | `Gemini_Generated_Image_qv94jeqv94jeqv94.jpg` | `f62b53ff9e228f3119eb075fc695b63475e73533d874e591b6dd09a252a806b2` | Grooming / appearance reference |
| `hero_body_render_frontal.jpg` | `Gemini_Generated_Image_3fqr5y3fqr5y3fqr.jpg` | `7a48f8cab897cbaf482ab28509bfaaacbeaef5e0397c913c1e408d6d6218671a` | Outfit reference, later |
| `hero_body_concept.png` | `Gemini_Generated_Image_bi8lknbi8lknbi8l.png` | `632107bc4241b0f0204688f3fe1a30b09dfffac42c911f119347fe2865ade6cb` | Outfit reference, later |

---

## WHY THE BALD ONE IS THE INPUT, AND IT IS NOT A PREFERENCE

**Mesh to MetaHuman reads SHAPE, not appearance.** TRELLIS reconstructs
whatever the image shows as geometry, so hair becomes a solid volume fused to
the skull and the conform then fits a MetaHuman against a cranial silhouette
that is part hair. The bearded variant does the same to the jaw line, adding
false volume exactly where the conform reads chin and mandible.

`hero_face_bald_frontal.jpg` gives the landmarks the conform actually uses —
brow ridge, temples, cheekbones, mandible, ears — unoccluded. Its stubble is
light enough not to change the jaw silhouette.

`hero_face_haired_frontal.jpg` is the SAME face and stays valuable twice over:
as the groom reference once a MetaHuman exists, and as an independent
cross-check that the reconstructed face reads as the same person.

## KNOWN PREPROCESSING NEED — not yet done

All four frame the subject **with shoulders and armour collar**. TRELLIS will
reconstruct the bust, collar included. The pipeline should crop the input to
head-and-neck before inference rather than rely on the Blender pass to strip
armour geometry afterwards — removing it from the INPUT is cheaper and cannot
take skull geometry with it.

Recorded as a step, not as done.
