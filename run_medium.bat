@echo off
echo ============================================
echo Running MEDIUM task only (Qwen 3.6 Plus FREE)
echo ============================================

set API_BASE_URL=https://openrouter.ai/api/v1
set MODEL_NAME=qwen/qwen3.6-plus:free
set HF_TOKEN=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

cd /d "%~dp0data_cleaning_env_project\data_cleaning_env"

python inference.py --env-url https://Deepak1819-data-cleaning-env.hf.space --task medium_product_inventory

echo ============================================
echo Medium task complete! Check results.json
echo ============================================
pause
