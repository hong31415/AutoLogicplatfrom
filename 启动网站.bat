@echo off
chcp 65001 >nul
title AutoLogic Studio
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
if errorlevel 1 (
  echo.
  echo 启动失败，请查看上方提示或 .run 文件夹中的日志。
  pause
)
