@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
where py >nul 2>nul && (py -3 atelier.py) || (python atelier.py)
pause
