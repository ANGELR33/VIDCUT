@echo off
title AetherCut AI Studio
chcp 65001 >nul
cd /d "%~dp0"

echo ====================================================================
echo        Iniciando AetherCut AI Studio en tu computadora...
echo ====================================================================
echo.

python run_studio.py
if errorlevel 1 (
    echo.
    echo [ERROR] Hubo un problema al iniciar el servidor.
    pause
)
