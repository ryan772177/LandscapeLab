"""probe_prop_descriptor.py -- what TYPE is a reflected UE property in Python?

READ-ONLY, one pass, no guessing. The exhaustive dump collapsed to
str(obj) because it tested `isinstance(descriptor, property)` and UE
does not use Python's `property`. Enumerate the surface instead of
guessing the type a second time.
"""
import json as _json

import unreal as _u

_o = _u.EditorAssetLibrary.load_asset("/Game/Alpine8K_HLODLayer_Landscape")
_t = type(_o)
_kinds = {}
_samples = {}
for _n in dir(_t):
    if _n.startswith("_"):
        continue
    _d = getattr(_t, _n, None)
    _k = type(_d).__name__
    _kinds.setdefault(_k, []).append(_n)
print("__LL__" + _json.dumps({
    "type": _t.__name__,
    "descriptor_kinds": {_k: {"n": len(_v), "sample": sorted(_v)[:12]}
                         for _k, _v in _kinds.items()},
}, indent=1, default=str))
