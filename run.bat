@echo off
title High Dividend Stock Analyzer
echo Starting High Dividend Stock Analyzer...
cd /d "%~dp0"
python -m streamlit run app.py
pause
