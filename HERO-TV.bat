@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HERO TV
set "PY="

rem ---- the built application (made once by Build-App.bat) is used when it is here; no Python needed then ----
if exist "%~dp0HERO-TV.exe" goto :exe

rem ---- find a real Python 3.9+ (the Microsoft Store "python" shortcut does not count) ----
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
  )
)
if not defined PY goto :nopython

rem ---- no arguments = start the TV; otherwise pass them on (doctor, convert, ...) ----
if "%~1"=="" goto :start
%PY% -m herotv %*
goto :done
:start
%PY% -m herotv launch
:done
set "RC=%ERRORLEVEL%"
goto :after

:exe
"%~dp0HERO-TV.exe" %*
set "RC=%ERRORLEVEL%"

:after
if not "%RC%"=="0" (
  echo.
  echo HERO TV stopped because of a problem - read the messages above.
  pause
)
exit /b %RC%

:nopython
echo ============================================================
echo  HERO TV needs Python 3.9 or newer, and it is not installed.
echo ============================================================
echo.
where winget >nul 2>nul
if errorlevel 1 goto :manualpython
choice /C YN /M "Install Python now using Windows' built-in installer (winget)"
if errorlevel 2 goto :manualpython
winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto :manualpython
echo.
echo Python is installed. CLOSE this window, then double-click HERO-TV.bat again.
pause
exit /b 1

:manualpython
echo   1. A web page is opening: https://www.python.org/downloads/
echo      Click the big yellow Download button and run the installer.
echo   2. On the first installer screen, TICK  "Add python.exe to PATH".
echo   3. When it finishes, double-click HERO-TV.bat again.
start "" https://www.python.org/downloads/
pause
exit /b 1
