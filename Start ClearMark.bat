@echo off
setlocal
title ClearMark Server
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo ClearMark is not installed yet.
  echo Follow the setup instructions in README.md.
  pause
  exit /b 1
)

set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

echo Starting ClearMark at http://127.0.0.1:8000
echo Keep this window open while using the app. Press Ctrl+C to stop it.
if /I not "%~1"=="--no-browser" (
  start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "for ($attempt = 0; $attempt -lt 60; $attempt++) { try { $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 'http://127.0.0.1:8000/api/health'; if ($response.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }"
)
".venv\Scripts\python.exe" -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000

set "CLEARMARK_EXIT=%ERRORLEVEL%"
if not "%CLEARMARK_EXIT%"=="0" (
  echo.
  echo ClearMark could not start. Error code: %CLEARMARK_EXIT%
  echo Copy the error shown above if you need help.
  pause
)

endlocal & exit /b %CLEARMARK_EXIT%

