@echo off
title AURELIA FORGE - Installation
cd /d "%~dp0"
echo ==========================================
echo       AURELIA FORGE - INSTALLATION
echo ==========================================
echo.
where py >nul 2>&1
if errorlevel 1 (
    echo Python n'est pas installe ou n'est pas dans le PATH.
    echo Installez Python 3.11 ou plus recent puis relancez ce fichier.
    pause
    exit /b 1
)
if not exist ".venv" (
    echo Creation de l'environnement Python...
    py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo IMPORTANT : ouvrez .env et ajoutez votre cle API OpenAI.
)
echo.
echo Installation terminee.
echo Lancez start.bat
pause
