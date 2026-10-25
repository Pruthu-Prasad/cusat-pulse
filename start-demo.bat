@echo off
setlocal
title CUSAT-Pulse launcher
cd /d "%~dp0"

echo.
echo  ===== CUSAT-Pulse demo launcher =====
echo.

rem ---- checks -------------------------------------------------------------
if not exist "backend\.venv\Scripts\python.exe" (
  echo  [!] Backend venv not found. Run once:
  echo      cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  goto :fail
)
if not exist "backend\.env" (
  echo  [!] backend\.env is missing. Copy backend\.env.example to backend\.env and add GEMINI_API_KEY.
  goto :fail
)
findstr /r /c:"^GEMINI_API_KEY=..*" "backend\.env" >nul || (
  echo  [!] GEMINI_API_KEY is empty in backend\.env - reports will fail until it is set.
)
if not exist "frontend\node_modules" (
  echo  [i] Installing frontend packages (first run only^)...
  pushd frontend & call npm install --no-audit --no-fund & popd
)
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul && (
  echo  [!] Port 8000 is already in use - a backend is probably still running.
  echo      Run stop-demo.bat first, then start again.
  goto :fail
)
netstat -ano | findstr /r /c:":5173 .*LISTENING" >nul && (
  echo  [!] Port 5173 is already in use - a frontend is probably still running.
  echo      Run stop-demo.bat first, then start again.
  goto :fail
)

rem ---- start --------------------------------------------------------------
echo  [1/3] Starting backend   (window: "CUSAT-Pulse Backend")
start "CUSAT-Pulse Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && python -m uvicorn main:app --port 8000 --reload --timeout-graceful-shutdown 3"

echo  [2/3] Building + starting frontend  (window: "CUSAT-Pulse Frontend")
rem Optimised build: one small bundle loads in seconds on phones over the tunnel (dev mode needs 30s+).
rem For live-reloading development use "npm run dev" in frontend\ instead.
start "CUSAT-Pulse Frontend" cmd /k "cd /d "%~dp0frontend" && npm run demo"

rem Find cloudflared on PATH, or at the winget install location (PATH may not be refreshed yet after installing).
rem No ( ) blocks below: the "(x86)" in the path would close them.
set "CLOUDFLARED="
for /f "delims=" %%C in ('where cloudflared 2^>nul') do if not defined CLOUDFLARED set "CLOUDFLARED=%%C"
if not defined CLOUDFLARED if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
if not defined CLOUDFLARED if exist "%ProgramFiles%\cloudflared\cloudflared.exe" set "CLOUDFLARED=%ProgramFiles%\cloudflared\cloudflared.exe"
set "TUNNEL_LOG=%TEMP%\cusat-pulse-tunnel.log"
if not defined CLOUDFLARED goto :no_tunnel
del "%TUNNEL_LOG%" >nul 2>nul
echo  [3/3] Starting tunnel    (window: "CUSAT-Pulse Tunnel")
rem --protocol http2: plain HTTPS on TCP 443. The default (QUIC on UDP 7844) is blocked on many campus/venue networks.
start "CUSAT-Pulse Tunnel" cmd /k ""%CLOUDFLARED%" tunnel --protocol http2 --url http://localhost:5173 --logfile "%TUNNEL_LOG%""
goto :after_tunnel
:no_tunnel
echo  [3/3] cloudflared not installed - skipping phone tunnel. Install: winget install Cloudflare.cloudflared
:after_tunnel

rem ---- wait for the backend, then open the app -----------------------------
echo.
echo  Waiting for the backend to come up...
set /a tries=0
:wait
rem ping as a 1s sleep: unlike timeout it also works when there's no console input
ping -n 2 127.0.0.1 >nul
curl -s -o nul http://localhost:8000/docs && goto :ready
set /a tries+=1
if %tries% lss 60 goto :wait
echo  [!] Backend did not answer within 60s - check the "CUSAT-Pulse Backend" window for errors.
goto :end

:ready
echo  Waiting for the frontend build...
set /a tries=0
:wait_frontend
curl -s -o nul http://localhost:5173 && goto :frontend_ready
ping -n 2 127.0.0.1 >nul
set /a tries+=1
if %tries% lss 90 goto :wait_frontend
echo  [!] Frontend did not answer within 90s - check the "CUSAT-Pulse Frontend" window for errors.
goto :end

:frontend_ready
start "" http://localhost:5173

rem ---- phone link: read it from the tunnel log (up to ~45s) ------------------
set "PHONE_URL="
if not defined CLOUDFLARED goto :show
echo  Waiting for the phone link...
set /a tries=0
:wait_tunnel
for /f "delims=" %%U in ('powershell -NoProfile -Command "$m = Select-String -Path $env:TUNNEL_LOG -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $m.Matches[0].Value }"') do set "PHONE_URL=%%U"
if defined PHONE_URL goto :show
ping -n 2 127.0.0.1 >nul
set /a tries+=1
if %tries% lss 45 goto :wait_tunnel

:show
echo.
echo  Ready on this laptop:   http://localhost:5173
if defined PHONE_URL echo %PHONE_URL%| clip
if defined PHONE_URL echo  Phone / judges link:    %PHONE_URL%   - copied to clipboard
if not defined PHONE_URL if defined CLOUDFLARED echo  [!] No phone link yet - look in the "CUSAT-Pulse Tunnel" window.
echo  Logins (code 000000):  admin estate@cusat.ac.in  ^|  students demo1..demo10@cusat.ac.in
echo  OTP codes, escalation notices and errors show in the Backend window.
echo  To stop everything: stop-demo.bat
goto :end

:fail
echo.
echo  Not started.
:end
echo.
pause
