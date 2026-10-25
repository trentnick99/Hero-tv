@echo off
rem Frees disk space by deleting the saved originals (.originals folders) left by Convert, Sort and Shrink. Asks first.
call "%~dp0HERO-TV.bat" cleanup
echo.
pause
