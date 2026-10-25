@echo off
title CUSAT-Pulse stop
echo Stopping CUSAT-Pulse (backend, frontend, tunnel)...

rem Close the windows start-demo.bat opened, with everything running inside them.
for %%T in ("CUSAT-Pulse Backend" "CUSAT-Pulse Frontend" "CUSAT-Pulse Tunnel") do (
  taskkill /fi "WINDOWTITLE eq %%~T*" /t /f >nul 2>nul
)

rem Anything still holding the backend or frontend port (e.g. started by hand).
for %%P in (8000 5173) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:":%%P .*LISTENING"') do taskkill /pid %%I /t /f >nul 2>nul
)

rem The phone tunnel, if its window was closed some other way.
taskkill /im cloudflared.exe /f >nul 2>nul

echo Done. Backend, frontend and tunnel are stopped.
ping -n 4 127.0.0.1 >nul
