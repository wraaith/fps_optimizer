@echo off
title FPS Optimizer
cd /d "%~dp0"

:: Auto-elevate to Administrator if not already elevated
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FPS Optimizer] Elevating with Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\" %*\"' -Verb RunAs"
    exit /b
)

echo ===================================================
echo           FPS OPTIMIZER // LAUNCHER (ADMIN)
echo ===================================================

cd /d "%~dp0desktop-app\app"
python main.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FPS Optimizer] Process exited with code %ERRORLEVEL%.
    pause
)
