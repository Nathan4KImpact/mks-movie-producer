@echo off
cd /d "%~dp0"
chcp 65001 >nul
title MKS Movie Producer - mise a jour
echo Mise a jour du logiciel depuis GitHub...
git pull --ff-only
if errorlevel 1 (echo.& echo !! Mise a jour impossible : voir docs\MANUEL_INSTALLATION.pdf, section 11.) else (echo.& echo Termine. Relancer PILOTAGE.bat puis Ctrl+F5 dans le navigateur.)
pause
