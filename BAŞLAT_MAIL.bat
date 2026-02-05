@echo off
chcp 65001 >nul
title Kepekçi Optik - Mail Watcher
echo.
echo ============================================
echo   Kepekçi Optik Mail Watcher
echo   Gmail'den otomatik fotoğraf indirme
echo ============================================
echo.
echo Durdurmak için: Ctrl+C
echo.
python mail_watcher.py
pause
