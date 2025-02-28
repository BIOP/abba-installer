@echo off
:CHECK_INTERNET
echo ===== Checking internet connection =====
ping pypi.org -n 1 > nul

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
pip install abba-python==0.10.4

REM Install pip dependencies in extra env: DeepSlice
set CONDA_DEEPSLIVEENV_PATH=%PREFIX%\env\deep

REM Activate extra Conda environment
call %CONDA_ENV_PATH%\Scripts\activate %PREFIX%\envs\deepslice
pip install DeepSlice==1.1.5
pip install urllib3==1.26.6

echo ===== Unpack extra files (DeepSlice models, logos...) =====

REM untar extra files into the install folder (deepslice model, deepslice cli script)
tar -xzvf "%PREFIX%\abba-pack-win.tar.gz" -C "%PREFIX%"
rm "%PREFIX%\abba-pack-win.tar.gz"

echo ===== Create ABBA shortcut =====

set shortcutPath='%userprofile%\Desktop\ABBA-0.10.4.lnk'
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

REM Check if the VC++ Redistributable is installed and get the version number
for /f "tokens=2" %%i in ('reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version ^| findstr /i "^[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*$"') do set installed_version=%%i

if defined installed_version (
    echo Found installed version %installed_version%

    REM Compare installed version with the required version
    if "%installed_version%" geq "%REQUIRED_VERSION%" (
        echo Visual C++ Redistributable version is up to date. Skipping installation.
        goto :EOF
    ) else (
        echo Installed version is older than required. Proceeding with installation.
    )
) else (
    echo Visual C++ Redistributable is not installed. Proceeding with installation.
)

REM Download the VC++ Redistributable installer if not already present
if not exist "%VC_REDIST_EXE%" (
    echo Downloading VC++ Redistributable installer...
    powershell -Command "Invoke-WebRequest -Uri %VC_REDIST_URL% -OutFile %VC_REDIST_EXE%"
)

REM Execute the installer
if exist "%VC_REDIST_EXE%" (
    echo Installing VC++ Redistributable...
    "%VC_REDIST_EXE%" /install /quiet /norestart
    if %ERRORLEVEL% equ 0 (
        echo Installation successful.
    ) else (
        echo Installation failed with error code %ERRORLEVEL%.
    )
) else (
    echo Failed to download the installer.
)

:end
endlocal
