@echo off
setlocal

cd /d "%~dp0"

set "PYTHON="

rem 1) Active venv
if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
    )
)

rem 2) Local .venv
if not defined PYTHON (
    if exist ".venv\Scripts\python.exe" (
        set "PYTHON=.venv\Scripts\python.exe"
    )
)

rem 3) Local env
if not defined PYTHON (
    if exist "env\Scripts\python.exe" (
        set "PYTHON=env\Scripts\python.exe"
    )
)

rem 4) Create .venv if none found
if not defined PYTHON (
    echo [INFO] No virtual environment found. Creating .venv...
    py -3 -m venv .venv 2>nul
    if errorlevel 1 (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
    set "PYTHON=.venv\Scripts\python.exe"
)

if not exist "%PYTHON%" (
    echo [ERROR] Python executable not found: %PYTHON%
    pause
    exit /b 1
)

echo [INFO] Using Python: %PYTHON%

"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :build_failed

"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :build_failed

rem Optional: refresh requirements from this exact env if --freeze was passed
if /I "%~1"=="--freeze" (
    "%PYTHON%" -m pip freeze > requirements.txt
    if errorlevel 1 goto :build_failed
    echo [INFO] requirements.txt regenerated from current env.
)

"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --console ^
  --name CS2BanChecker ^
  --collect-submodules utils ^
  --hidden-import utils.logger ^
  --hidden-import utils.config ^
  --hidden-import utils.Inventory ^
  --hidden-import utils.PriceChecker ^
  --hidden-import utils.steam_rate_limiter ^
  BanChecker.py

if errorlevel 1 goto :build_failed

echo.
echo Build completed: dist\CS2BanChecker.exe
pause
exit /b 0

:build_failed
echo.
echo Build failed.
pause
exit /b 1