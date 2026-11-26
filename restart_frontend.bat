@echo off
cd /d "%~dp0..\store"
echo Deteniendo procesos Node anteriores...
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul
echo Iniciando Vite frontend en http://localhost:5174...
call npm run dev
