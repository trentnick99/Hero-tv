@echo off
rem Drag movie files onto this file, then pick the channel(s). Fixes "it will not go into its channel".
if "%~1"=="" (
  echo Drag video files onto "Add-Movies.bat" instead of double-clicking it.
  echo.
  pause
  exit /b 1
)
call "%~dp0HERO-TV.bat" add %*
echo.
pause
