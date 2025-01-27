@echo off
setlocal enabledelayedexpansion

:: Get the path to the parent folder of the script
for %%A in ("%~dp0..") do set "CONDA_ENV_PATH=%%~fA"

:: Adjust the path as needed if the Conda environment is not directly in the parent folder
:: Example: If the Conda environment is in a subfolder named 'env', you can use:
:: set "CONDA_ENV_PATH=!CONDA_ENV_PATH!\env"

cd /D "%~dp0"

:: Activate the Conda environment
call !CONDA_ENV_PATH!\condabin\activate.bat

:: Set the environment variables related to Java
set "JAVA_HOME=!CONDA_ENV_PATH!\Library\jre"
set "PATH=!CONDA_ENV_PATH!\Library\jre\bin;!PATH!"
:: line necessary or maven will not be in PATH
set "PATH=!CONDA_ENV_PATH!\Library\bin;!PATH!"

:: Verify Java version and environment
echo Activated Conda environment at: !CONDA_ENV_PATH!
echo Java Home: !JAVA_HOME!
echo Java Version: !java -version!

:: Run your Python script
..\python.exe ..\abba\start-abba.py

:: Deactivate the Conda environment when done
rem call !CONDA_ENV_PATH!\condabin\deactivate.bat
