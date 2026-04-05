#!/usr/bin/env python3
"""
Baseline inference script for the Data Cleaning Environment.

Runs an LLM agent against data cleaning tasks via HTTP API.
Emits structured [START], [STEP], [END] stdout logs as required by
the Meta PyTorch OpenEnv Hackathon evaluation pipeline.

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
]

SYSTEM_PROMPT = """You are an expert data cleaning agent. You analyze dirty datasets and systematically clean them to match a gold-standard clean version.

## Strategy

1. **Scan & Identify**: Examine the data snapshot and issues_detected list. Understand what's broken and why.
2. **Prioritize Fixes**: Fix problems in this order:
   - Formatting issues first (whitespace, capitalization, date formats) — easiest wins
   - Missing/empty values (fill with defaults)
   - Logical/semantic errors (consistency, ranges, validation)
   - Delete duplicates last (since deletion shifts row indices, complicating subsequent fixes)
3. **Verify**: After each action, check the updated issues_detected to confirm progress.
4. **Mark Complete**: When all issues are resolved or you've used most of your action budget, call mark_complete.

## Available Actions

Respond with ONLY a single JSON action object. No explanations, no markdown, no extra text.

### fix_cell
{"action_type": "fix_cell", "row": <int>, "column": "<string>", "value": "<string>"}

### delete_row
{"action_type": "delete_row", "row": <int>}

### mark_complete
{"action_type": "mark_complete"}

## Common Patterns

- Names: Title Case ("John Doe"), trim whitespace
- Dates: YYYY-MM-DD format ("2024-01-15")
- Emails: user@domain.tld, fix double @@, add missing .com
- Numbers: Remove "$", convert text ("forty-five" -> "45.00"), negative stock -> "0"
- Categories: Exact canonical names ("Electronics", "Stationery", "Home & Office")
- Duplicates: Delete duplicate rows by key fields
- Status: "Shipped", "Delivered", "Pending", "Cancelled"

## Rules

- Respond with a SINGLE JSON action object only. No other text.
- After deleting a row, row indices shift immediately.
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


# ── Helper Functions ──

def make_user_prompt(observation: dict) -> str:
    """Build the user prompt from an observation."""
    parts = [
        f"## Task: {observation.get('task_description', 'Clean the dataset')}",
        f"\n## Current Dataset ({observation.get('num_rows', 0)} rows):",
        f"```csv\n{observation.get('data_snapshot', '')}\n```",
        f"\n## Progress: {observation.get('actions_taken', 0)}/{observation.get('max_actions', 0)} actions used",
        f"## Quality: {observation.get('quality_score', 0.0):.4f} (0.0=dirty, 1.0=perfect)",
    ]

    issues = observation.get("issues_detected", [])
    if issues:
        parts.append(f"\n## Remaining Issues ({len(issues)}):")
        for issue in issues[:15]:
            parts.append(f"- {issue}")
        if len(issues) > 15:
            parts.append(f"... and {len(issues) - 15} more issues")

    parts.append("\n## Your next action (JSON only):")
    return "\n".join(parts)


def parse_action(response_text: str) -> dict:
    """Parse an action JSON from the LLM response."""
    text = response_text.strip()

    # Try markdown code blocks
    if "```json" in text:
        try:
            json_part = text.split("```json")[1].split("```")[0].strip()
            action = json.loads(json_part)
            if isinstance(action, dict) and "action_type" in action:
                return action
        except (json.JSONDecodeError, IndexError):
            pass

    if "```" in text:
        try:
            json_part = text.split("```")[1].split("```")[0].strip()
            action = json.loads(json_part)
            if isinstance(action, dict) and "action_type" in action:
                return action
        except (json.JSONDecodeError, IndexError):
            pass

    # Try direct JSON parse
    try:
        action = json.loads(text)
        if isinstance(action, dict) and "action_type" in action:
            return action
    except json.JSONDecodeError:
        pass

    # Find JSON object in text
    for i, char in enumerate(text):
        if char == "{":
            depth = 0
            for j in range(i, len(text)):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            candidate = text[i : j + 1]
                            action = json.loads(candidate)
                            if isinstance(action, dict) and "action_type" in action:
                                return action
                        except json.JSONDecodeError:
                            pass
                        break

    return {"action_type": "mark_complete"}


def action_to_str(action: dict) -> str:
    """Convert an action dict to a compact string for logging."""
    atype = action.get("action_type", "unknown")
    if atype == "fix_cell":
        row = action.get("row", "?")
        col = action.get("column", "?")
        val = action.get("value", "?")
        # Truncate long values
        if len(str(val)) > 20:
            val = str(val)[:20] + "..."
        return f"fix_cell(row={row},col='{col}',val='{val}')"
    elif atype == "delete_row":
        row = action.get("row", "?")
        return f"delete_row(row={row})"
    elif atype == "mark_complete":
        return "mark_complete()"
    else:
        return f"{atype}()"


def call_llm_with_retry(client: OpenAI, model: str, messages: list, max_retries: int = 6) -> str:
    """Call the LLM with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=256,
            )
            return completion.choices[0].message.content or ""
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = 30 * (attempt + 1)
                print(f"[DEBUG] Rate limited. Waiting {wait_time}s ({attempt+1}/{max_retries})...", flush=True)
                time.sleep(wait_time)
            else:
                print(f"[DEBUG] Failed after {max_retries} retries.", flush=True)
                return '{"action_type": "mark_complete"}'
        except Exception as e:
            print(f"[DEBUG] LLM error: {e}", flush=True)
            return '{"action_type": "mark_complete"}'

    return '{"action_type": "mark_complete"}'


# ── Main Task Runner ──

def run_task(client: OpenAI, model: str, env_url: str, task_id: str) -> dict:
    """Run a single task with mandatory structured logging."""
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    # Emit [START]
    log_start(task=task_id, env=BENCHMARK, model=model)

    try:
        # Reset environment
        reset_resp = requests.post(
            f"{env_url}/reset",
            json={"task_id": task_id},
            timeout=30,
        )
        reset_resp.raise_for_status()
        obs = reset_resp.json()

        # Initialize conversation
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        while not obs.get("done", False):
            # Build prompt
            user_msg = make_user_prompt(obs)
            messages.append({"role": "user", "content": user_msg})

            # Small delay for rate limit safety
            time.sleep(2)

            # Call LLM
            response_text = call_llm_with_retry(client, model, messages, max_retries=6)
            messages.append({"role": "assistant", "content": response_text})

            # Parse action
            action = parse_action(response_text)
            steps_taken += 1

            # Send action to environment
            try:
                step_resp = requests.post(
                    f"{env_url}/step",
                    json=action,
                    timeout=30,
                )
                step_resp.raise_for_status()
                obs = step_resp.json()
            except Exception as e:
                # Log the failed step and break
                log_step(
                    step=steps_taken,
                    action=action_to_str(action),
                    reward=0.0,
                    done=True,
                    error=str(e),
                )
                rewards.append(0.0)
                break

            reward = obs.get("reward", 0.0) or 0.0
            done = obs.get("done", False)
            error_msg = obs.get("message", "") if "Error:" in obs.get("message", "") else None

            rewards.append(reward)

            # Emit [STEP]
            log_step(
                step=steps_taken,
                action=action_to_str(action),
                reward=reward,
                done=done,
                error=error_msg,
            )

            # Manage conversation history: keep system + last 12 messages
            if len(messages) > 14:
                messages = [messages[0]] + messages[-12:]

        # Compute final score (quality_score is already 0-1)
        score = obs.get("quality_score", 0.0)
        score = min(max(score, 0.0), 1.0)
        success = score >= 0.5

    except Exception as e:
        print(f"[DEBUG] Task {task_id} error: {e}", flush=True)
        # If we had no steps, log one failed step
        if steps_taken == 0:
            steps_taken = 1
            rewards.append(0.0)
            log_step(step=1, action="error()", reward=0.0, done=True, error=str(e))

    finally:
        # Always emit [END]
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task_id": task_id,
        "final_quality_score": score,
        "final_reward": rewards[-1] if rewards else 0.0,
        "steps_taken": steps_taken,
        "rewards": rewards,
    }


def main():
    parser = argparse.ArgumentParser(description="Data Cleaning Environment Inference")
    parser.add_argument(
        "--env-url",
        default=os.environ.get("ENV_URL", DEFAULT_ENV_URL),
        help="URL of the environment server",
    )
    parser.add_argument(
        "--task",
        default=None,
        choices=TASKS,
        help="Run a specific task (default: all tasks)",
    )
    args = parser.parse_args()

    # Configuration
    api_base_url = API_BASE_URL
    model_name = MODEL_NAME
    api_key = API_KEY

    if not api_key:
        print("ERROR: Set HF_TOKEN or OPENAI_API_KEY environment variable.", flush=True)
        sys.exit(1)

    # Check environment health
    try:
        health = requests.get(f"{args.env_url}/health", timeout=10)
        health.raise_for_status()
    except Exception as e:
        print(f"[DEBUG] Cannot reach environment at {args.env_url}: {e}", flush=True)
        sys.exit(1)

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key, base_url=api_base_url)

    # Determine tasks
    tasks_to_run = [args.task] if args.task else TASKS

    # Run tasks
    results = []
    start_time = time.time()

    for task_id in tasks_to_run:
        result = run_task(client, model_name, args.env_url, task_id)
        results.append(result)

    elapsed = time.time() - start_time

    # Write results to file
    output = {
        "model": model_name,
        "api_base_url": api_base_url,
        "env_url": args.env_url,
        "total_time_seconds": round(elapsed, 1),
        "average_quality_score": round(
            sum(r["final_quality_score"] for r in results) / len(results) if results else 0.0, 4
        ),
        "tasks": results,
    }

    with open("results.json", "w") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
