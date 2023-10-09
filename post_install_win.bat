@echo off
:CHECK_INTERNET
echo ===== Checking internet connection =====
ping google.com -n 1 > nul

if errorlevel 1 (
    echo You are not connected to the internet.
    echo Please connect to the internet and press any key to continue...
    pause > nul
    goto CHECK_INTERNET
) else (
    echo Internet connection detected.
    echo Your computer is connected to the internet.
)

echo ===== Install PIP dependencies =====

REM Install pip dependencies in main env: abba-python
set CONDA_ENV_PATH=%PREFIX%

REM Activate main Conda environment
call %CONDA_ENV_PATH%\Scripts\activate
pip install abba-python==0.5.0

REM Install pip dependencies in extra env: DeepSlice
set CONDA_DEEPSLIVEENV_PATH=%PREFIX%\env\deep

REM Activate extra Conda environment
call %CONDA_ENV_PATH%\Scripts\activate %PREFIX%\envs\deepslice
pip install DeepSlice==1.1.5

echo ===== Unpack extra files (DeepSlice models, logos...) =====

REM untar extra files into the install folder (deepslice model, deepslice cli script)
tar -xzvf "%PREFIX%\abba-pack-win.tar.gz" -C "%PREFIX%"

echo ===== Create ABBA shortcut =====

set shortcutPath='%userprofile%\Desktop\ABBA.lnk'
set shortcutTarget='%PREFIX%\win\run-abba.bat'
set shortcutIcon='%PREFIX%\img\logo256x256.ico'

REM '%PREFIX%\img\logo256x256.ico'

@echo off
REM set /p "id=Shortcut path: "

echo %shortcutPath%

@echo off
REM set /p "id=Shortcut target: "

echo %shortcutTarget%

@echo off
REM set /p "id=Installing shortcut: "

%SYSTEMROOT%\System32\WindowsPowerShell\v1.0\powershell.exe "$s=(New-Object -COM WScript.Shell).CreateShortcut("%shortcutPath%");$s.IconLocation="%shortcutIcon%";$s.TargetPath="%shortcutTarget%";$s.Save()"

REM add shortcut to C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu\Programs

set shortcutProgramsPath='%userprofile%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\ABBA.lnk'

%SYSTEMROOT%\System32\WindowsPowerShell\v1.0\powershell.exe "$s=(New-Object -COM WScript.Shell).CreateShortcut("%shortcutProgramsPath%");$s.IconLocation="%shortcutIcon%";$s.TargetPath="%shortcutTarget%";$s.Save()"

echo ABBA shortcuts installed

@echo off
REM set /p "id=Shortcut installed "

echo ===== Checking if Visual C++ redistributable is installed (elastix requirements) =====

if %errorlevel%==0 (
    for /f "tokens=2" %%i in ('reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version ^| findstr /i "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*$"') do set installed_version=%%i
    echo Found installed version %installed_version%
    if "%installed_version%" geq "14.0.0.0" (
        echo Visual C++ redistributable version is up to date. Skipping installation.
        goto end
    )
)

if %errorlevel%==0 (
    echo Visual C++ redistributable version %REDIST_VERSION% is already installed.
    goto end
)

echo Visual C++ redistributable version %REDIST_VERSION% is not installed. Downloading...

%SYSTEMROOT%\System32\WindowsPowerShell\v1.0\powershell.exe -Command "Invoke-WebRequest '%REDIST_URL%' -OutFile '%REDIST_EXE%'"

echo Installing Visual C++ redistributable version %REDIST_VERSION%...

start /wait %REDIST_EXE% /quiet /norestart

echo Visual C++ redistributable version %REDIST_VERSION% has been installed successfully.


:end
endlocal
