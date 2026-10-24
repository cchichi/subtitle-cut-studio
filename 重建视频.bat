@echo off
chcp 65001 >nul
title 字幕剪辑台 - 重建成片
cd /d "%~dp0"
python cut.py build
echo.
pause
