@echo off
REM Build script for Windows
echo Building ALX Sitemap Generator...
echo.

REM Check if PyInstaller is installed
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed. Installing...
    python -m pip install pyinstaller
)

REM Run the build script
python setup.py

echo.
echo Build complete! Check the 'dist' folder for the executable.
pause

