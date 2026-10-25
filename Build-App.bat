@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Build HERO TV application
echo.
echo  BUILD THE HERO TV APPLICATION  (one time, takes a few minutes, needs the Internet)
echo  ---------------------------------------------------------------------------------
echo  This turns HERO TV into a real program,  HERO-TV.exe,  in this same folder.
echo  Afterwards HERO-TV.bat, the desktop shortcut and everything else use it, and Python is no longer needed to run it.
echo  Your movies, channels and settings are not touched. To go back, just delete HERO-TV.exe and the _internal folder.
echo.
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python 3.9 or newer is needed ONCE to build the program. Install it from https://www.python.org/downloads/
  echo ^(tick "Add python.exe to PATH"^), then run this again.
  pause
  exit /b 1
)
echo Closing HERO TV if it is running ^(its files cannot be replaced while it is open^)...
taskkill /f /im HERO-TV.exe >nul 2>nul
%PY% -c "from herotv import launcher; launcher.stop_old_server(launcher.Config())" >nul 2>nul
timeout /t 2 /nobreak >nul
echo Installing the build tool ^(PyInstaller^)...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo.
  echo Could not install PyInstaller. Check the Internet connection ^(or antivirus web shield^) and try again.
  pause
  exit /b 1
)
if not exist "assets\hero-tv.ico" %PY% -c "from herotv import icon; icon.make_ico('assets/hero-tv.ico')"
echo.
echo Building... ^(this is the slow part^)
%PY% -m PyInstaller --noconfirm --clean --onedir --name HERO-TV --icon "%~dp0assets\hero-tv.ico" --collect-submodules herotv --distpath "%~dp0build-app\dist" --workpath "%~dp0build-app\work" --specpath "%~dp0build-app" "%~dp0app_entry.py"
if errorlevel 1 (
  echo.
  echo The build failed - read the messages above. Antivirus software sometimes blocks it: allow this folder and try again.
  pause
  exit /b 1
)
echo.
echo Putting the new program in place...
if exist HERO-TV.exe del /f /q HERO-TV.exe
if exist HERO-TV.exe goto :locked
if exist _internal rmdir /s /q _internal
if exist _internal goto :locked
xcopy /e /i /y /q "build-app\dist\HERO-TV\*" "." >nul
if errorlevel 1 goto :locked
fc /b "build-app\dist\HERO-TV\HERO-TV.exe" "HERO-TV.exe" >nul 2>nul
if errorlevel 1 goto :locked
rmdir /s /q build-app
%PY% -c "from herotv import updater; updater.write_stamp()"
echo.
echo  DONE.  HERO-TV.exe is ready in this folder.
echo  - Double-click  HERO-TV.bat  or  HERO-TV.exe  to start the TV.
echo  - Run  Create-Desktop-Shortcut.bat  again so the desktop icon points at the new program.
echo  - Windows may warn "unknown publisher" the first time, because the program is not code-signed.
echo    Choose "More info" then "Run anyway". It is your own copy, built on your own PC.
echo  - ffmpeg is still needed for converting videos ^(Check-Setup.bat installs it^).
echo  - Rebuild with this file again after you update HERO TV's program files.
echo.
pause
exit /b 0

:locked
echo.
echo  NOT FINISHED: Windows would not let the old program be replaced, because it is still open or being scanned.
echo  1. Close HERO TV completely ^(also in Task Manager: end "HERO-TV.exe"^).
echo  2. Wait a few seconds ^(antivirus may be scanning the new files^), then double-click Build-App.bat again.
echo  The new program is kept in the "build-app" folder, so the second try is quick.
echo.
pause
exit /b 1
