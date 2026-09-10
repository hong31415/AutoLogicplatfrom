@echo off
chcp 65001 >nul
title AutoLogic Studio
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
if errorlevel 1 (
  echo.
  echo Startup failed. Check the message above or the logs in the .run folder.
  pause
)
