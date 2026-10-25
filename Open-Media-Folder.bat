@echo off
rem Opens the folder where your videos go (creates it, with an Inbox and channel folders, the first time).
if defined HEROTV_MEDIA (set "M=%HEROTV_MEDIA%") else (set "M=%USERPROFILE%\hero-tv-media")
if not exist "%M%" mkdir "%M%"
call "%~dp0HERO-TV.bat" folders
start "" explorer "%M%"
