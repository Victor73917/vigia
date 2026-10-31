@echo off
cd /d "%~dp0"
py recolectar.py
py construir.py
pause
