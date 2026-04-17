@echo off
echo ============================================================
echo   KupkaProd Cinema Pipeline - Setup
echo   Powered by LTX 2.3
echo ============================================================
echo.
echo Installing Python dependencies...
echo.
pip install -r requirements.txt
echo.
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to install dependencies. Make sure Python and pip are on your PATH.
    echo.
    pause
    exit /b 1
)
echo.
echo ============================================================
echo   Setup complete!
echo.
echo   Next steps:
echo     1. Make sure ComfyUI is installed and working
echo     2. Open the app settings and set your Hugging Face model IDs
echo     3. On first run, allow Transformers to download model weights
echo     4. Run start.bat to launch the application
echo ============================================================
echo.
pause
