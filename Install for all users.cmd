@echo off
rem  Installs ABBA for every user of this computer.
rem  Double-click it: it asks for administrator rights itself.
rem
rem      "Install for all users.cmd" [folder] [/quiet]
rem
rem      folder    default: %ProgramFiles%\ABBA
rem      /quiet    no window and no pause, for unattended deployment: the
rem                progress is printed here instead; the exit code says
rem                whether it worked
rem
rem  Everything goes into that one folder, all downloaded now so that no user
rem  has anything to fetch: the launcher and its own Python, a JDK, ABBA and
rem  Fiji's jars, and the Python environments of DeepSlice, Elastix and
rem  BrainGlobe (about 6 GB, 10 to 20 minutes). The ABBA window shows the
rem  progress. Users can read the folder but not write to it. Atlases,
rem  downloaded when first opened, go to %ProgramData%\ABBA (or
rem  ABBA_SHARED_DATA, see below), which every user can write. An ABBA shortcut
rem  goes into the Start Menu and onto the Desktop of every user.
rem
rem  Running it again updates the installation: run the one of a new version
rem  to move every user to it.
rem  To uninstall, delete the folder, the two shortcuts and, with the atlases,
rem  %ProgramData%\ABBA.

setlocal
set "SRC=%~dp0"
set "APP="
set "QUIET="

rem  The arguments, in any order. Labels rather than ( blocks ), see below.
:arguments
if "%~1"=="" goto :arguments_done
if /i "%~1"=="/quiet" goto :quiet_argument
set "APP=%~1"
shift
goto :arguments
:quiet_argument
set "QUIET=1"
shift
goto :arguments
:arguments_done
if not defined APP set "APP=%ProgramFiles%\ABBA"
title Install ABBA for all users

rem  No folder name inside a ( block ) here: one holding a ")" would end it.

rem  fltmc only works for an administrator, and needs no service running.
fltmc >nul 2>&1
if not errorlevel 1 goto :elevated
echo Asking for administrator rights...
set "ABBA_SELF=%~f0"
set "ABBA_ARGS=%*"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$a = @{FilePath = $env:ABBA_SELF; Verb = 'RunAs'}; if ($env:ABBA_ARGS) { $a.ArgumentList = $env:ABBA_ARGS }; Start-Process @a"
exit /b
:elevated

rem  An elevated process does not see the drives mapped by the user.
if exist "%SRC%pyproject.toml" goto :readable
echo Cannot read the installer from %SRC%
echo If that is a network drive, copy the folder to a local disk first.
goto :failed
:readable

echo Installing into %APP%
echo.
robocopy "%SRC%src" "%APP%\src" /MIR /XD __pycache__ /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :failed
robocopy "%SRC%." "%APP%" pyproject.toml uv.lock README.md LICENSE.txt /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :failed

rem  uv is only needed here, to build the environment. If the machine has none,
rem  it goes into the installation folder rather than onto the administrator's PATH.
set "UV="
for /f "delims=" %%I in ('where uv 2^>nul') do if not defined UV set "UV=%%I"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV if exist "%APP%\uv\uv.exe" set "UV=%APP%\uv\uv.exe"
if defined UV goto :sync
echo Installing uv into %APP%\uv
set "UV_INSTALL_DIR=%APP%\uv"
set "UV_NO_MODIFY_PATH=1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if exist "%APP%\uv\uv.exe" set "UV=%APP%\uv\uv.exe"
if defined UV goto :sync
echo Could not install uv. Install it by hand from
echo     https://docs.astral.sh/uv/getting-started/installation/
echo and run this again.
goto :failed

:sync

rem  The environment, and the Python it runs on, inside the installation
rem  folder: by default uv keeps Python in the administrator's profile, which
rem  other users cannot read. Copies rather than uv's usual hard links into its
rem  cache, for the same reason: a hard link keeps the permissions of the cached
rem  file. Not editable, so that the environment does not depend on src - and
rem  so rebuilt every time: uv would otherwise only notice a new pyproject.toml.
set "UV_PYTHON_INSTALL_DIR=%APP%\python"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_LINK_MODE=copy"
set "UV_PROJECT_ENVIRONMENT=%APP%\.venv"
"%UV%" sync --project "%APP%" --frozen --no-dev --no-editable --compile-bytecode --reinstall-package abba-installer
if errorlevel 1 goto :failed

rem  uv's pythonw.exe in a venv is a console program that starts python.exe, so
rem  a console window would open beside the ABBA window. Python's own windowed
rem  venv launcher - what `python -m venv` puts there - starts pythonw.exe instead.
"%APP%\.venv\Scripts\python.exe" -c "import sys, shutil, pathlib; nt = pathlib.Path(sys.base_prefix, 'Lib', 'venv', 'scripts', 'nt'); shutil.copyfile(next(p for p in (nt / 'venvwlauncher.exe', nt / 'pythonw.exe') if p.exists()), pathlib.Path(sys.prefix, 'Scripts', 'pythonw.exe'))"
if errorlevel 1 goto :failed

rem  The java folder is what tells the launcher it is shared (launcher.SHARED):
rem  prepare then fills it - JDK, jars - with the Python environments next to
rem  it, and creates the atlas folders in ABBA_SHARED_DATA, which it records for
rem  the users' sessions. Set ABBA_SHARED_DATA before running this to keep the
rem  atlases elsewhere, on a larger disk for instance.
echo.
if not defined ABBA_SHARED_DATA set "ABBA_SHARED_DATA=%ProgramData%\ABBA"
rem  The jar archive (ABBA-<version>-jars.zip), if it was put next to this file:
rem  used instead of downloading it, for a computer without internet.
set "ABBA_JARS_DIR=%SRC%"
if not exist "%APP%\java" mkdir "%APP%\java"
if defined QUIET goto :prepare_quietly
echo Downloading everything; the ABBA window shows the progress. Leave this console open.
"%APP%\.venv\Scripts\python.exe" -m abba_installer.gui --install-all
if errorlevel 1 goto :failed
goto :prepared
:prepare_quietly
"%APP%\.venv\Scripts\python.exe" -m abba_installer prepare --all
if errorlevel 1 goto :failed
:prepared

rem  Whatever was moved in rather than created there - uv's Python, jars renamed
rem  from a download - kept its own permissions. Reset them all to the folder's,
rem  which in Program Files means: users read and run, never write.
echo.
echo Setting permissions...
icacls "%APP%" /reset /T /C /Q >nul
if errorlevel 1 echo WARNING: some permissions could not be reset; users may not read every file.

rem  Atlases are downloaded when a user first opens one: every user may write there.
icacls "%ABBA_SHARED_DATA%" /grant "*S-1-5-32-545:(OI)(CI)M" /Q >nul
if errorlevel 1 goto :failed

rem  Straight to the environment's pythonw: no console, no uv. Started in the
rem  installation folder, which users cannot write, since python -m imports from there.
set "ABBA_HOME=%APP%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $w = New-Object -ComObject WScript.Shell; foreach ($folder in [Environment]::GetFolderPath('CommonPrograms'), [Environment]::GetFolderPath('CommonDesktopDirectory')) { $s = $w.CreateShortcut((Join-Path $folder 'ABBA.lnk')); $s.TargetPath = Join-Path $env:ABBA_HOME '.venv\Scripts\pythonw.exe'; $s.Arguments = '-m abba_installer.gui'; $s.WorkingDirectory = $env:ABBA_HOME; $s.IconLocation = (Join-Path $env:ABBA_HOME 'src\abba_installer\assets\app.ico') + ',0'; $s.Description = 'ABBA - Aligning Big Brains and Atlases'; $s.Save(); Write-Host ('Shortcut: ' + $s.FullName) }"
if errorlevel 1 goto :failed

echo.
echo Installed. Every user of this computer can now start ABBA from the
echo Start Menu or the Desktop.
echo.
if not defined QUIET pause
exit /b 0

:failed
echo.
echo The installation did not complete. The reason is above.
echo.
if not defined QUIET pause
exit /b 1
