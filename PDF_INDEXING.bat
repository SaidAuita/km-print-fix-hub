@echo off
title PDF Indexing Utility
echo ====================================================
echo [*] Starting PDF manuals indexing pipeline...
echo ====================================================
echo.
echo Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Error: Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [*] Running index script...
python index_kb.py
if %errorlevel% neq 0 (
    echo [!] Indexing error! Please check logs above.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo [+] Indexing completed successfully!
echo [+] You can now delete source files from Service_manuals folder.
echo ====================================================
pause
