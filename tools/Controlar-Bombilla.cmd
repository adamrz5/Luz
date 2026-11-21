@echo off
setlocal
"%~dp0..\.venv\Scripts\python.exe" "%~dp0..\src\Controlar-Bombilla.py" %*
set "LUZ_RESULT=%ERRORLEVEL%"
pause
exit /b %LUZ_RESULT%
