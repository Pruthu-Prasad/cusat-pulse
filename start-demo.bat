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

echo  [2/3] Starting frontend  (window: "CUSAT-Pulse Frontend")
start "CUSAT-Pulse Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

where cloudflared >nul 2>nul && (
  echo  [3/3] Starting tunnel    (window: "CUSAT-Pulse Tunnel" - the https link for phones is printed there^)
  start "CUSAT-Pulse Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5173"
) || (
  echo  [3/3] cloudflared not installed - skipping phone tunnel. Install: winget install Cloudflare.cloudflared
)

rem ---- wait for the backend, then open the app -----------------------------
echo.
echo  Waiting for the backend to come up...
set /a tries=0
:wait
timeout /t 1 /nobreak >nul
curl -s -o nul http://localhost:8000/docs && goto :ready
set /a tries+=1
if %tries% lss 60 goto :wait
echo  [!] Backend did not answer within 60s - check the "CUSAT-Pulse Backend" window for errors.
goto :end

:ready
timeout /t 2 /nobreak >nul
start "" http://localhost:5173
echo.
echo  Ready:  http://localhost:5173
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
