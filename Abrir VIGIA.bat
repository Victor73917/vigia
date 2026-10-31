@echo off
rem Abre VIGIA con datos en vivo. Usa un servidor local para que el navegador acepte las imagenes del globo.
cd /d "%~dp0"
start "VIGIA (cierra esta ventana para apagarlo)" /min py -m http.server 8765 --bind 127.0.0.1
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8765/
