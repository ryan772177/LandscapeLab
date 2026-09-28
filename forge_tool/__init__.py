"""The forge: standalone image -> UE landscape project tool.

Wraps the repo's proven scripts (vendored by copy, hash-pinned) behind a
single CLI: a user supplies one 2D concept image and receives an Unreal
Engine 5.8 project whose landscape approximates it.

Modules:
    build_stamp_catalogue  shippable stamp catalogue (CC0 + operator seeds)
    brief_author           concept image -> layout brief (Claude vision)
    check_brief            semantic gate over authored briefs
    emit_project           fresh UE project + trimmed editor plugin
    package                dist assembly, vendor manifest, licence gate
    cli                    `python -m forge_tool.cli build <image>`
"""
