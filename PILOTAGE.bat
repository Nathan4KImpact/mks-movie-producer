@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title MKS Movie Producer
where py >nul 2>nul && (py -3 pilotage.py) || (python pilotage.py)
pause
