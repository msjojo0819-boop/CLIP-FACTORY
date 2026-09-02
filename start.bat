@echo off
REM Clip Factory - start it. Double-click this file. Close the window to stop.
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist frontend\dist\index.html (
  echo The web app isn't built. Run setup.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
REM Speech model size: tiny (fastest) / base (default) / small (more accurate, slower)
if "%CLIP_FACTORY_WHISPER_MODEL%"=="" set CLIP_FACTORY_WHISPER_MODEL=base
if "%PORT%"=="" set PORT=8000
set URL=http://127.0.0.1:%PORT%/ui/
echo Clip Factory is starting at  %URL%
echo Leave this window open while you use it. Close it to stop.
REM open the browser after the server has had a moment to come up
start "" cmd /c "timeout /t 3 /nobreak >nul && start "" %URL%"
REM 127.0.0.1 only: this app has no login, so it must never be exposed beyond this computer.
uvicorn app.main:app --host 127.0.0.1 --port %PORT%
pause
