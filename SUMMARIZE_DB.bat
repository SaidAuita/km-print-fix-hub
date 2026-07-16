@echo off
title KM Print Fix Hub - Database Chunk Summarization Utility (v 1.20)
echo =======================================================================
echo          KM Print Fix Hub - Database Summarization Tool
echo =======================================================================
echo.
echo [*] Starting incremental database chunk summarization...
echo [*] Defaulting to 4 parallel threads. You can pass arguments to control it,
echo [*] e.g. "SUMMARIZE_DB.bat --threads 1" (highly recommended for weak CPU without GPU).
echo.
python -u summarize_db.py %*
echo.
echo [*] Process finished.
pause
