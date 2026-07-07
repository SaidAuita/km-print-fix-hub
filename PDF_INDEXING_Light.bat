@echo off
title PDF Indexing Utility (Anonymized/Light)
echo ====================================================
echo [*] Starting Anonymized PDF manuals indexing pipeline...
echo ====================================================
echo.
echo Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Error: Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [*] Running anonymized index script...
python index_kb.py --anonymize
if %errorlevel% neq 0 (
    echo [!] Indexing error! Please check logs above.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo [+] Anonymized indexing completed successfully!
echo [+] Database saved to Index_anon folder.
echo ====================================================
pause
