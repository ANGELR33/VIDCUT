@echo off
title AetherCut AI Studio (Con Enlace Ngrok)
chcp 65001 >nul
cd /d "%~dp0"

echo ====================================================================
echo    Iniciando AetherCut AI Studio con Enlace Ngrok...
echo ====================================================================
echo.

start "Ngrok Tunnel" ngrok http 8000
python run_studio.py
if errorlevel 1 (
    echo.
    echo [ERROR] Hubo un problema al iniciar el servidor.
    pause
)
