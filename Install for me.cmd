@echo off
rem  Installs ABBA for you, then opens the ABBA window. Double-click it.
rem
rem  The one thing it needs that Windows does not have is uv, which builds the
rem  launcher's Python environment; if it is missing, this installs it. Then an
rem  ABBA shortcut goes next to this file, into your Start Menu and onto your
rem  Desktop, and the window opens: "Install everything" there downloads Java,
rem  ABBA, Fiji, DeepSlice, Elastix and BrainGlobe, with a progress bar. Or skip
rem  it: "Start ABBA" downloads what it needs when it first needs it.
rem
rem  Run it again to update. To install ABBA for every user of this computer,
rem  run "Install for all users.cmd" instead.
rem
rem  Without a window (a script, CI), say what to install; the progress is printed:
rem      "Install for me.cmd" --all                    everything
rem      "Install for me.cmd" --elastix --brainglobe   some of it
rem      "Install for me.cmd" --none                   Java, ABBA and Fiji only
rem
rem  Leave this console window open: it is where a crash would be readable.

setlocal
cd /d "%~dp0"
title Install ABBA

set "UV="
for /f "delims=" %%I in ('where uv 2^>nul') do if not defined UV set "UV=%%I"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"

if not defined UV (
    echo uv is not installed yet. Installing it -- this takes a moment.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
)

if not defined UV (
    echo.
    echo Could not install uv automatically. Install it by hand from
    echo     https://docs.astral.sh/uv/getting-started/installation/
    echo and run this again.
    echo.
    pause
    exit /b 1
)

echo Preparing the launcher's Python environment (the first time: about a minute)...
"%UV%" sync --frozen --no-dev --quiet
if errorlevel 1 goto :failed

rem  uv's pythonw.exe in a venv is a console program that starts python.exe, so
rem  the shortcut would open a console beside the window. Python's own windowed
rem  venv launcher - what `python -m venv` puts there - starts pythonw.exe instead.
".venv\Scripts\python.exe" -c "import sys, shutil, pathlib; nt = pathlib.Path(sys.base_prefix, 'Lib', 'venv', 'scripts', 'nt'); shutil.copyfile(next(p for p in (nt / 'venvwlauncher.exe', nt / 'pythonw.exe') if p.exists()), pathlib.Path(sys.prefix, 'Scripts', 'pythonw.exe'))"
if errorlevel 1 goto :failed

rem  Shortcuts with ABBA's icon, straight to the window: next to this file, in
rem  your Start Menu and on your Desktop. A shortcut cannot ship in the zip,
rem  because it holds absolute paths, so they are written here - and rewritten
rem  by every run, to follow the folder if it moves. The paths travel as
rem  environment variables, so that a quote in a folder name cannot break them.
set "ABBA_HOME=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; foreach ($folder in $env:ABBA_HOME, [Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) { $s = $w.CreateShortcut((Join-Path $folder 'ABBA.lnk')); $s.TargetPath = Join-Path $env:ABBA_HOME '.venv\Scripts\pythonw.exe'; $s.Arguments = '-m abba_installer.gui'; $s.WorkingDirectory = $env:ABBA_HOME; $s.IconLocation = (Join-Path $env:ABBA_HOME 'src\abba_installer\assets\app.ico') + ',0'; $s.Description = 'ABBA - Aligning Big Brains and Atlases'; $s.Save() }" >nul 2>&1
if errorlevel 1 echo WARNING: the ABBA shortcuts could not be written; run this file to open ABBA instead.

if "%~1"=="" goto :window
set "WHAT=%*"
if /i "%~1"=="--none" set "WHAT="
"%UV%" run --frozen --no-dev abba prepare %WHAT%
if errorlevel 1 goto :failed
exit /b 0

:window
echo Opening the ABBA window. From now on, use the ABBA shortcut.
"%UV%" run --frozen --no-dev python -m abba_installer.gui
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Something went wrong; the reason is above.
echo.
pause
exit /b 1
