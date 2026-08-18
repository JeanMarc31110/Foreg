@echo off
setlocal
if "%~1"=="" (
  set INSTALLER=Forge_Installer.exe
) else (
  set INSTALLER=%~1
)

rem Resolve script directory
set SCRIPT_DIR=%~dp0
if exist "%SCRIPT_DIR%%INSTALLER%" (
  set INSTALLER_PATH=%SCRIPT_DIR%%INSTALLER%
) else (
  set INSTALLER_PATH=%INSTALLER%
)

echo Running installer: "%INSTALLER_PATH%" /VERYSILENT /NORESTART
"%INSTALLER_PATH%" /VERYSILENT /NORESTART
if errorlevel 1 (
  echo Installation failed with exit code %ERRORLEVEL%
  exit /b %ERRORLEVEL%
)

echo Installation complete.
endlocal
