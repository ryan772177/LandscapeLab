@echo off
rem The Forge launcher. Lives at the distribution ROOT (package.py
rem copies it there); everything runs relative to that root.
rem   forge doctor
rem   forge build <image> --layout examples\my.layout.json --name myworld
rem   forge polish --name myworld
cd /d "%~dp0"
python -m forge_tool.cli %*
