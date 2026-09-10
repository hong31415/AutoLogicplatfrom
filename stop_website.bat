@echo off
chcp 65001 >nul
title AutoLogic Studio
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_all.ps1"
