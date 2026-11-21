@echo off
setlocal
cd /d "%~dp0.."
".venv\Scripts\python.exe" "tools\xiaomi-tokens\token_extractor.py"
set "LUZ_RESULT=%ERRORLEVEL%"
pause
exit /b %LUZ_RESULT%
