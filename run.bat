@echo off
cd /d "%~dp0"
if not exist .venv (
  echo [DocExtract] Creating virtual environment...
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python app.py
pause
