@echo off
rem Drag a video onto this file to choose which language (sound track) it plays.
if "%~1"=="" (
  echo Drag video files onto "Fix-Audio.bat" instead of double-clicking it.
  echo.
  pause
  exit /b 1
)
call "%~dp0HERO-TV.bat" audio %*
echo.
pause
