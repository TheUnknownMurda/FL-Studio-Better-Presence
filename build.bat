@echo off
rem Tests the app, builds it in dist\FL-Studio-Better-Presence\, then its installer,
rem dist\FL-Studio-Better-Presence-Setup.exe.
rem
rem The first time, create the Python environment it uses:
rem     py -3.13 -m venv .venv
rem     .venv\Scripts\pip install PySide6-Essentials pyinstaller pytest
rem and install Inno Setup 6, which makes the installer: https://jrsoftware.org/isdl.php

cd /d "%~dp0"
.venv\Scripts\python -m pytest -q || exit /b 1
rem The single .exe of the versions before 1.2, which the installer replaced
if exist "dist\FL-Studio-Better-Presence.exe" del "dist\FL-Studio-Better-Presence.exe"
.venv\Scripts\pyinstaller --noconfirm --clean "FL Studio Better Presence.spec" || exit /b 1

set "ISCC="
for /f "delims=" %%f in ('where ISCC.exe 2^>nul') do set "ISCC=%%f"
for %%f in ("%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do (
    if not defined ISCC if exist %%f set "ISCC=%%~f"
)
if not defined ISCC (
    echo Inno Setup 6 is needed to make the installer: https://jrsoftware.org/isdl.php
    exit /b 1
)
"%ISCC%" /Q installer\setup.iss || exit /b 1
echo.
echo Built dist\FL-Studio-Better-Presence-Setup.exe
