@echo off
echo ============================================================
echo   KupkaProd Cinema Pipeline
echo   Powered by LTX 2.3
echo ============================================================
echo.
echo Starting application...
echo.
python video_director_agent/gui.py
echo.
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with an error.
    echo   Make sure you ran setup.bat first.
    echo   Make sure Python is on your PATH.
    echo.
)
echo.
echo Application closed.
pause
