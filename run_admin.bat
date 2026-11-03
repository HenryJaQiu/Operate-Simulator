@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "Start-Process pythonw -ArgumentList 'game_assistant.py' -Verb RunAs"
