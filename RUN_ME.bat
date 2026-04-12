@echo off
echo Starting upload...
python upload_to_github_and_hf.py
if errorlevel 1 (
    echo.
    echo Python not found. Trying py launcher...
    py upload_to_github_and_hf.py
)
pause
