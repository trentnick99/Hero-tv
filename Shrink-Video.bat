@echo off
rem Drag video files OR whole folders onto this file. Re-encodes them smaller (standard H.264) after checking the result.
if "%~1"=="" (
  echo Drag video files or folders onto "Shrink-Video.bat" instead of double-clicking it.
  echo.
  pause
  exit /b 1
)
call "%~dp0HERO-TV.bat" shrink %*
echo.
pause
