@echo off
REM Clip Factory - one-time setup for Windows. Double-click this file.
setlocal
cd /d "%~dp0"
echo == Clip Factory setup (Windows) ==
echo.

REM ---- Python ----
where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python is not installed. Installing it with winget...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
      echo.
      echo Could not install Python automatically.
      echo Go to https://www.python.org/downloads/ , install Python, and TICK "Add python.exe to PATH".
      echo Then double-click setup.bat again.
      pause
      exit /b 1
    )
    echo Python installed. Close this window, then double-click setup.bat again.
    pause
    exit /b 0
  )
)

REM ---- ffmpeg ----
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo ffmpeg is not installed. Installing it with winget...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo.
    echo Could not install ffmpeg automatically.
    echo Go to https://www.gyan.dev/ffmpeg/builds/ , download the "release essentials" zip,
    echo unzip it, and add its bin folder to your PATH. Then double-click setup.bat again.
    pause
    exit /b 1
  )
  echo ffmpeg installed. Close this window, then double-click setup.bat again.
  pause
  exit /b 0
)

REM ---- Python packages ----
echo -- Python packages (this takes a few minutes the first time)
if not exist .venv (
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package install failed. Copy the last few lines above and send them to David.
  pause
  exit /b 1
)

REM ---- Web app ----
if exist frontend\dist\index.html (
  echo -- Web app is already built.
) else (
  echo -- Building the web app
  where npm >nul 2>&1
  if errorlevel 1 (
    echo Node is not installed and the web app is not pre-built.
    echo Install Node LTS from https://nodejs.org , then double-click setup.bat again.
    pause
    exit /b 1
  )
  pushd frontend
  call npm ci --no-audit --no-fund
  call npm run build
  popd
)

echo.
echo Setup done. Start it any time by double-clicking start.bat
pause
