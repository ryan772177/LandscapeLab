"""item8_cleanup.py -- delete the Item-8 scratch assets, in-editor.

Removes /Game/Scratch/Item8/ through the asset registry (EditorAssetLibrary),
which is the sanctioned way to remove a UE asset -- NOT a filesystem rm -rf
(standing rule 2), and NOT a hand-deletion of .uasset on disk (rule 4). Reads
back that the directory no longer exists. Leaves the sibling
/Game/Scratch/C0House (another session's scratch) untouched.
"""
import json as _json

import unreal as _u

DIRP = "/Game/Scratch/Item8"
_out = {"ok": False, "error": None, "dir": DIRP}
try:
    _existed = _u.EditorAssetLibrary.does_directory_exist(DIRP)
    _before = _u.EditorAssetLibrary.list_assets(DIRP, recursive=True) \
        if _existed else []
    _deleted = False
    if _existed:
        _deleted = bool(_u.EditorAssetLibrary.delete_directory(DIRP))
    _still = _u.EditorAssetLibrary.does_directory_exist(DIRP)
    _after = _u.EditorAssetLibrary.list_assets(DIRP, recursive=True) \
        if _still else []
    _out.update({
        "existed": _existed,
        "assets_before": [str(a) for a in _before],
        "delete_directory_returned": _deleted,
        "dir_still_exists": _still,
        "assets_after": [str(a) for a in _after],
        "c0house_untouched": _u.EditorAssetLibrary.does_directory_exist(
            "/Game/Scratch/C0House"),
        "ok": (not _still) and (len(_after) == 0),
    })
except Exception as _e:
    import traceback as _tb
    _out["error"] = type(_e).__name__ + ": " + str(_e)
    _out["trace"] = _tb.format_exc()[-1200:]

print("__LL__" + _json.dumps(_out))
