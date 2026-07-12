@echo off
title KM Print Fix Hub - Database Chunk Summarization Utility (v 1.10)
echo =======================================================================
echo          KM Print Fix Hub - Database Summarization Tool
echo =======================================================================
echo.
echo [*] Starting incremental database chunk summarization...
echo [*] Using unbuffered output stream for real-time progress updates.
echo.
python -u summarize_db.py
echo.
echo [*] Process finished.
pause
