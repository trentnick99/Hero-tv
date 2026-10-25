@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Update HERO TV
rem Installs the newest hero-tv-windows.zip from your Downloads folder over this one (or drag a zip onto this file).
rem Your videos, favorites, resume points and your own settings are kept.
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python is needed to update. Install it from https://www.python.org/downloads/ and try again.
  pause
  exit /b 1
)
%PY% -m herotv update %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="2" (
  call "%~dp0Build-App.bat"
  goto :end
)
echo.
pause
:end
exit /b
