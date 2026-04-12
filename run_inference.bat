@echo off
echo ============================================
echo Running Data Cleaning Env Inference
echo Using: Qwen 3.6 Plus (FREE) on OpenRouter
echo ============================================

set API_BASE_URL=https://openrouter.ai/api/v1
set MODEL_NAME=qwen/qwen3.6-plus:free
set HF_TOKEN=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

cd /d "%~dp0data_cleaning_env_project\data_cleaning_env"

echo.
echo Installing openai package if needed...
pip install openai requests >nul 2>&1

echo.
echo Running inference against HF Space...
echo Environment URL: https://Deepak1819-data-cleaning-env.hf.space
echo Model: %MODEL_NAME%
echo.

python inference.py --env-url https://Deepak1819-data-cleaning-env.hf.space

echo.
echo ============================================
echo Inference complete! Check results.json
echo ============================================
pause
