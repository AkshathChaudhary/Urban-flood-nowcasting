@echo off
setlocal
cd /d "%~dp0"
title FLOWS Urban Flood Nowcasting Dev Server

echo =================================================================
echo   FLOWS Urban Flood Nowcasting - Dev Launcher
echo =================================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_dev.py %*
) else (
    python run_dev.py %*
)
