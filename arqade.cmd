@echo off
rem Windows version of arqade.sh: start the Munich Quantum Arcade menu.
rem Needs uv (https://docs.astral.sh/uv/). Options go to the launcher.
rem Its own environment folder, so a checkout shared with WSL/Linux doesn't
rem have the two platforms overwrite each other's launcher\.venv.
set "UV_PROJECT_ENVIRONMENT=%~dp0launcher\.venv-windows"
uv run --quiet --project "%~dp0launcher" arqade %*
