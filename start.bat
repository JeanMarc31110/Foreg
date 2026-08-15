@echo off
title AURELIA FORGE
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call install.bat
)
call .venv\Scripts\activate.bat
python main.py
pause
