"""groom_property_probe.py -- read the exporter's ATTRIBUTE POINTERS, per object.

    blender --background <blend> --python this.py --

The ABC diff says `groom_root_uv` is written for the groom that draws and not
for the groom that does not. The source says why it COULD be, and this reads
whether it IS -- because a mechanism that explains the evidence is a hypothesis
until the field it names has been looked at.

    AlembicGroomExporter.py:282   resolves the root-UV attribute by the NAME
                                  held in obj.GroomProperty.att_groom_root_uv
    ExporterOperators.py:39-48    getAttribute() returns att_valid=False when
                                  that name is not among the object's attributes
    AlembicGroomExporter.py:349   `if att_surface_uv_valid:` -- the ABC gets
                                  groom_root_uv ONLY then. No warning otherwise.
    GroomPanel.py:211             the addon-pref default is
                                  "surface_uv_coordinate"

Note the type theory is DEAD: line 282 accepts BOTH "FLOAT2" and
"FLOAT_VECTOR", so FLOAT2-vs-FLOAT_VECTOR cannot be the discriminator. It is
the NAME POINTER, which is per-object and which a freshly constructed
`bpy.data.hair_curves.new()` object never had set.
"""

import json

import bpy

FIELDS = ("att_groom_root_uv", "att_groom_width", "att_groom_color",
          "att_groom_roughness", "att_groom_knots", "att_groom_orders",
          "att_groom_guide", "att_groom_id", "att_groom_closest_guides",
          "att_groom_guide_weights", "att_groom_ao", "att_groom_cards_name")

rep = {}
for o in bpy.data.objects:
    if o.type != "CURVES":
        continue
    gp = getattr(o, "GroomProperty", None)
    row = {"has_GroomProperty": gp is not None,
           "attributes_present": [a.name for a in o.data.attributes]}
    if gp is not None:
        for f in FIELDS:
            row[f] = getattr(gp, f, "ABSENT: no such property")
        # the decisive derived fact, stated rather than left to be inferred
        nm = getattr(gp, "att_groom_root_uv", "")
        row["root_uv_pointer_resolves"] = (nm != "" and nm in o.data.attributes)
    rep[o.name] = row

print("__GP__" + json.dumps(rep, default=str))
