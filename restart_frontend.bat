@echo off
cd C:\Users\DATA-MESACNTL3\scrapper\Scrapper\webPlatform
echo Deteniendo procesos Node anteriores...
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul
echo Iniciando Vite frontend...
call npm run dev