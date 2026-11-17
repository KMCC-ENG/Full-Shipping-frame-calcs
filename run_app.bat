@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app.py
) else (
    python -c "import sys" >nul 2>&1
    if errorlevel 1 (
        py -3 -m streamlit run app.py
    ) else (
        python -m streamlit run app.py
    )
)
if errorlevel 1 pause
