@echo off
rem Opens the two files you edit to change channels. Save in Notepad (Ctrl+S), then restart HERO TV.
start "" notepad "%~dp0config\channels.json"
start "" notepad "%~dp0config\auto-sort.json"
