@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".\Yisheng.exe" (
  start "" ".\Yisheng.exe"
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File ".\run.ps1"
if errorlevel 1 pause
