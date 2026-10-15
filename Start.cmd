@echo off
rem  Double-click this. It opens the ABBA window, which starts Fiji with ABBA.
rem
rem  The one thing it needs that Windows does not have is uv, which builds the
rem  Python environment; if it is missing, this installs it. Everything else -
rem  Python, Java, ABBA and Fiji - is downloaded on first use, for this user.
rem  To install ABBA for every user of this computer, run Install.cmd instead.
rem
rem  Leave this console window open: it is where a crash would be readable.

setlocal
cd /d "%~dp0"
title ABBA

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

rem  Shortcuts with ABBA's icon, next to this file and in this user's Start
rem  Menu. A .cmd cannot carry an icon of its own, and a shortcut cannot ship in
rem  the zip, because it holds absolute paths - so they are written here, and
rem  rewritten on every start to follow the folder if it moves. In the
rem  background: they must not delay the window, and nothing depends on them.
rem  The paths travel as environment variables, so that a quote in a folder
rem  name cannot break them.
set "ABBA_HOME=%~dp0"
set "ABBA_SELF=%~f0"
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; foreach ($path in (Join-Path $env:ABBA_HOME 'ABBA.lnk'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'ABBA.lnk')) { $s = $w.CreateShortcut($path); $s.TargetPath = $env:ABBA_SELF; $s.WorkingDirectory = $env:ABBA_HOME; $s.IconLocation = $env:ABBA_HOME + 'src\abba_installer\assets\app.ico,0'; $s.Description = 'ABBA - Aligning Big Brains and Atlases'; $s.Save() }" >nul 2>&1

echo Starting. The window will appear in a few seconds.
"%UV%" run python -m abba_installer.gui
if errorlevel 1 (
    echo.
    echo The window closed with an error. The reason is above.
    pause
)
