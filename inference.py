#!/usr/bin/env python3
"""
Baseline inference script for the Data Cleaning Environment.

Runs an LLM agent against data cleaning tasks via HTTP API.
Emits structured [START], [STEP], [END] stdout logs as required by
the Meta PyTorch OpenEnv Hackathon evaluation pipeline.

Supports both atomic actions (fix_cell, delete_row) and batch
operations (fill_missing, standardize_column, deduplicate).

Required environment variables:
    API_BASE_URL  - The API endpoint for the LLM
    MODEL_NAME    - The model identifier
    HF_TOKEN      - Your API key (also accepts OPENAI_API_KEY)

Usage:
    python inference.py
    python inference.py --task easy_customer_contacts
    python inference.py --env-url http://localhost:8000
"""

import argparse
import json
import os
import sys
import time
from typing import List, Optional

import requests
from openai import OpenAI, RateLimitError


# ── Configuration ──

DEFAULT_ENV_URL = "http://localhost:8000"
BENCHMARK = "data_cleaning_env"

API_BASE_URL = os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen/qwen3.6-plus:free")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")

TASKS = [
    "easy_customer_contacts",
    "medium_product_inventory",
    "hard_sales_reconciliation",
    "expert_financial_records",
]

SYSTEM_PROMPT = """You are an expert data cleaning agent. You analyze dirty datasets and systematically clean them to match a gold-standard clean version.

## Strategy

1. **Scan & Identify**: Examine the data snapshot and issues_detected list carefully. Understand every issue before acting.
2. **Plan Efficiently**: Use batch operations when many cells in one column share the same problem.
3. **Prioritize Fixes**: Fix problems in this order:
   a. Use batch operations first when applicable:
      - deduplicate: Remove duplicate rows by key column (e.g., order_id, txn_id)
      - standardize_column: Fix case/format for entire columns at once
      - fill_missing: Fill empty/null values in a column with a default
   b. Then use atomic operations for remaining specific fixes:
      - fix_cell: Fix individual cell values
      - delete_row: Remove specific rows
   c. Delete rows last (since deletion shifts row indices)
4. **Verify**: After each action, check the updated issues_detected to confirm progress.
5. **Mark Complete**: When all issues are resolved or quality_score > 0.95, call mark_complete.

## Available Actions

Respond with ONLY a single JSON action object. No explanations, no markdown, no extra text.

### Atomic Operations
{"action_type": "fix_cell", "row": <int>, "column": "<string>", "value": "<string>"}
{"action_type": "delete_row", "row": <int>}

### Batch Operations (efficient for column-wide fixes)
{"action_type": "fill_missing", "column": "<string>", "value": "<default_value>"}
{"action_type": "standardize_column", "column": "<string>", "rule": "<rule_name>"}
  Rules: "title_case", "upper_case", "lower_case", "strip_whitespace", "date_iso", "numeric_clean"
{"action_type": "deduplicate", "column": "<string>"}

### Control
{"action_type": "mark_complete"}

## Common Patterns

- Names: Title Case ("John Doe"), trim whitespace
- Dates: YYYY-MM-DD format ("2024-01-15")
- Emails: user@domain.tld, fix double @@, add missing .com
- Numbers: Remove "$", convert text ("forty-five" -> "45.00"), negative stock -> "0"
- Categories: Exact canonical names ("Electronics", "Stationery", "Home & Office")
- Duplicates: Use deduplicate action on the key column, or delete_row for specific rows
- Status: "Shipped", "Delivered", "Pending", "Cancelled", "Completed", "Failed"
- Currency: ISO 4217 uppercase codes ("USD", "EUR", "GBP", "JPY")
- Amounts: Always positive, with 2 decimal places ("15000.00")
- Transaction dates: settle_date must be >= txn_date

## Rules

- Respond with a SINGLE JSON action object only. No other text.
- After deleting a row, row indices shift immediately — be careful with subsequent indices.
- Batch operations are more efficient but less precise — use them for column-wide patterns.
- If quality_score > 0.95, consider marking complete.
"""


# ── Mandatory Structured Logging ──

def log_start(task: str, env: str, model: str) -> None:
    """Emit [START] line."""
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    """Emit [STEP] line."""
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Emit [END] line."""
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )
