@echo off
rem Tests the app, then builds dist\FL Studio Better Presence.exe.
rem
rem The first time, create the Python environment it uses:
rem     py -3.13 -m venv .venv
rem     .venv\Scripts\pip install PySide6-Essentials pyinstaller pytest

cd /d "%~dp0"
.venv\Scripts\python -m pytest -q || exit /b 1
.venv\Scripts\pyinstaller --noconfirm --clean "FL Studio Better Presence.spec" || exit /b 1
echo.
echo Built dist\FL Studio Better Presence.exe
