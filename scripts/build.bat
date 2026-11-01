@echo off
rem Builds dist\DanceRMD.exe after installing the build dependencies.
cd /d "%~dp0.."
python -m pip install -r requirements-dev.txt || goto :error
python scripts\build.py || goto :error
echo.
echo Done: dist\DanceRMD.exe
pause
exit /b 0
:error
echo Build failed, see the errors above.
pause
exit /b 1
