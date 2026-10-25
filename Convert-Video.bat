@echo off
rem Drag one or more video files onto this file. Makes them playable in HERO TV (fixes "no sound / skipped" movies).
if "%~1"=="" (
  echo Drag video files onto "Convert-Video.bat" instead of double-clicking it.
  echo.
  pause
  exit /b 1
)
call "%~dp0HERO-TV.bat" convert %*
echo.
pause
