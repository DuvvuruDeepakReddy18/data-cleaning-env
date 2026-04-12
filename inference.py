#!/usr/bin/env python3
"""
Baseline inference script for the Data Cleaning Environment.

Runs an LLM agent against all 3 tasks (easy, medium, hard) and reports scores.
Uses the OpenAI API client with configurable endpoint.

Required environment variables:
    API_BASE_URL  - The API endpoint for the LLM (e.g., https://api.openai.com/v1)
    MODEL_NAME    - The model identifier (e.g., gpt-4o-mini)
    HF_TOKEN      - Your Hugging Face / API key (used as OPENAI_API_KEY)

Usage:
    # Set environment variables
    export API_BASE_URL="https://api.openai.com/v1"
    export MODEL_NAME="gpt-4o-mini"
    export HF_TOKEN="your-api-key"

    # Run with environment server already running
    python inference.py

    # Or specify a custom server URL
    python inference.py --env-url http://localhost:8000
"""

import argparse
import json
import os
import sys
import time

import requests
from openai import OpenAI


# ── Configuration ──

DEFAULT_ENV_URL = "http://localhost:8000"

TASKS = [
    "easy_customer_contacts",
    "medium_product_inventory",
    "hard_sales_reconciliation",
]

SYSTEM_PROMPT = """You are an expert data cleaning agent. You are given a dirty dataset and must clean it by taking actions.

Available actions (respond with JSON):
1. {"action_type": "fix_cell", "row": <int>, "column": "<name>", "value": "<new_value>"}
   - Fix a single cell value
2. {"action_type": "delete_row", "row": <int>}
   - Delete a row (use for duplicates)
3. {"action_type": "mark_complete"}
   - Signal that you are done cleaning

IMPORTANT RULES:
- Analyze the data snapshot and issues carefully before acting.
- Fix one issue at a time with fix_cell or delete_row.
- After deleting a row, all subsequent row indices shift down by 1.
- When you believe all issues are fixed, use mark_complete.
- Respond with ONLY a single JSON action object, no other text.
- Think step by step about what needs fixing based on the issues listed.

Common cleaning patterns:
- Names: Use Title Case (e.g., "John Doe")
- Dates: Standardize to YYYY-MM-DD format
- Emails: Must have valid format (user@domain.tld)
- Numbers: Remove currency symbols, fix text-to-number
- Categories: Match exact canonical spelling and case
- Duplicates: Delete the duplicate row (usually the second occurrence)
- Missing values: Use sensible defaults (0 for stock, "Unknown Product" for names)
- Negative values: Use absolute value or 0 as appropriate
- Status fields: Use exact canonical values (Shipped, Delivered, Pending, Cancelled)
"""


def make_user_prompt(observation: dict) -> str:
    """Build the user prompt from an observation."""
    parts = [
        f"## Task: {observation.get('task_description', 'Clean the dataset')}",
        f"\n## Current Dataset ({observation.get('num_rows', 0)} rows):",
        f"```csv\n{observation.get('data_snapshot', '')}\n```",
        f"\n## Actions taken: {observation.get('actions_taken', 0)}/{observation.get('max_actions', 0)}",
        f"## Current quality score: {observation.get('quality_score', 0.0):.4f}",
    ]

    issues = observation.get("issues_detected", [])
    if issues:
        parts.append(f"\n## Remaining issues ({len(issues)}):")
        for issue in issues[:20]:  # Cap to avoid token overflow
            parts.append(f"- {issue}")

    parts.append("\n## Your next action (respond with JSON only):")
    return "\n".join(parts)


def parse_action(response_text: str) -> dict:
    """Parse an action from the LLM response."""
    text = response_text.strip()

    # Try to extract JSON from the response
    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Try direct JSON parse
    try:
        action = json.loads(text)
        if isinstance(action, dict) and "action_type" in action:
            return action
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
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
                            action = json.loads(text[i : j + 1])
                            if isinstance(action, dict) and "action_type" in action:
                                return action
                        except json.JSONDecodeError:
                            pass
                        break

    # Fallback: mark complete if we can't parse
    return {"action_type": "mark_complete"}


def run_task(
    client: OpenAI,
    model: str,
    env_url: str,
    task_id: str,
) -> dict:
    """Run a single task and return results."""
    print(f"\n{'='*60}")
    print(f"  Task: {task_id}")
    print(f"{'='*60}")

    # Reset the environment
    reset_resp = requests.post(
        f"{env_url}/reset",
        json={"task_id": task_id},
        timeout=30,
    )
    reset_resp.raise_for_status()
    obs = reset_resp.json()

    print(f"  Initial quality: {obs.get('quality_score', 0.0):.4f}")
    print(f"  Max actions: {obs.get('max_actions', 0)}")
    print(f"  Rows: {obs.get('num_rows', 0)}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    total_reward = 0.0
    step_count = 0

    while not obs.get("done", False):
        # Build prompt
        user_msg = make_user_prompt(obs)
        messages.append({"role": "user", "content": user_msg})

        # Call LLM
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=256,
            )
            response_text = completion.choices[0].message.content or ""
        except Exception as e:
            print(f"  LLM error: {e}")
            response_text = '{"action_type": "mark_complete"}'

        messages.append({"role": "assistant", "content": response_text})

        # Parse action
        action = parse_action(response_text)
        step_count += 1

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
            print(f"  Step error: {e}")
            break

        reward = obs.get("reward", 0.0) or 0.0
        total_reward = reward  # Use latest reward (cumulative in final step)

        if step_count % 5 == 0:
            print(
                f"  Step {step_count}: quality={obs.get('quality_score', 0):.4f} "
                f"reward={reward:.4f} action={action.get('action_type')}"
            )

        # Keep conversation manageable - trim old messages
        if len(messages) > 20:
            messages = [messages[0]] + messages[-18:]

    final_score = obs.get("quality_score", 0.0)
    final_reward = obs.get("reward", 0.0) or 0.0

    print(f"\n  Final quality score: {final_score:.4f}")
    print(f"  Final reward: {final_reward:.4f}")
    print(f"  Steps taken: {step_count}")

    return {
        "task_id": task_id,
        "final_quality_score": final_score,
        "final_reward": final_reward,
        "steps_taken": step_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Data Cleaning Environment Inference")
    parser.add_argument(
        "--env-url",
        default=os.environ.get("ENV_URL", DEFAULT_ENV_URL),
        help="URL of the environment server",
    )
    args = parser.parse_args()

    # Read configuration from environment
    api_base_url = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
    model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    api_key = os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("ERROR: Set HF_TOKEN or OPENAI_API_KEY environment variable.")
        sys.exit(1)

    print("=" * 60)
    print("  Data Cleaning Environment - Baseline Inference")
    print("=" * 60)
    print(f"  API Base URL: {api_base_url}")
    print(f"  Model: {model_name}")
    print(f"  Environment: {args.env_url}")

    # Check environment health
    try:
        health = requests.get(f"{args.env_url}/health", timeout=10)
        health.raise_for_status()
        print("  Environment: HEALTHY")
    except Exception as e:
        print(f"  ERROR: Cannot reach environment at {args.env_url}: {e}")
        print("  Start the environment first: uvicorn data_cleaning_env.server.app:app --port 8000")
        sys.exit(1)

    # Initialize OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=api_base_url,
    )

    # Run all tasks
    results = []
    start_time = time.time()

    for task_id in TASKS:
        result = run_task(client, model_name, args.env_url, task_id)
        results.append(result)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print(f"  {'Task':<35} {'Quality':>8} {'Reward':>8} {'Steps':>6}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*6}")

    total_quality = 0.0
    total_reward = 0.0

    for r in results:
        print(
            f"  {r['task_id']:<35} "
            f"{r['final_quality_score']:>8.4f} "
            f"{r['final_reward']:>8.4f} "
            f"{r['steps_taken']:>6}"
        )
        total_quality += r["final_quality_score"]
        total_reward += r["final_reward"]

    avg_quality = total_quality / len(results)
    avg_reward = total_reward / len(results)

    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*6}")
    print(f"  {'AVERAGE':<35} {avg_quality:>8.4f} {avg_reward:>8.4f}")
    print(f"\n  Total time: {elapsed:.1f}s")
    print("=" * 60)

    # Write results to file
    output = {
        "model": model_name,
        "api_base_url": api_base_url,
        "env_url": args.env_url,
        "total_time_seconds": round(elapsed, 1),
        "average_quality_score": round(avg_quality, 4),
        "average_reward": round(avg_reward, 4),
        "tasks": results,
    }

    with open("results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to results.json")


if __name__ == "__main__":
    main()
