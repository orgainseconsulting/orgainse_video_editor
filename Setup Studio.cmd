@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1" -ProductionExtras
if errorlevel 1 (
  pause
  exit /b 1
)
call "%~dp0Start Studio.cmd"
