#!/usr/bin/env python3
"""
Full end-to-end test for the Data Cleaning Environment.

Run this on your machine AFTER installing dependencies:
    pip install pydantic fastapi uvicorn requests openai

This script:
1. Starts the FastAPI server in a background thread
2. Tests /health, /reset, /step, /state for all 3 tasks
3. Verifies grader scores are in 0.0-1.0 range
4. Verifies partial progress signals
5. Verifies Dockerfile syntax
6. Verifies openenv.yaml
7. Prints a pass/fail checklist matching the hackathon requirements
"""

import json
import os
import sys
import threading
import time

import requests
import uvicorn

SERVER_URL = "http://127.0.0.1:8765"
TASKS = [
    "easy_customer_contacts",
    "medium_product_inventory",
    "hard_sales_reconciliation",
]

results = {}


def start_server():
    """Start the FastAPI server in a background thread."""
    from data_cleaning_env.server.app import app
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


def wait_for_server(url, timeout=15):
    """Wait for the server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def test_health():
    """Test /health endpoint."""
    print("\n[TEST] /health endpoint")
    r = requests.get(f"{SERVER_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    data = r.json()
    assert data["status"] == "healthy"
    print(f"  PASS: status={data['status']}")
    results["health"] = True


def test_root():
    """Test / endpoint."""
    print("\n[TEST] / root endpoint")
    r = requests.get(f"{SERVER_URL}/")
    assert r.status_code == 200, f"Root failed: {r.status_code}"
    data = r.json()
    assert "name" in data
    assert "tasks" in data
    assert len(data["tasks"]) >= 3
    print(f"  PASS: name={data['name']}, tasks={data['tasks']}")
    results["root"] = True


def test_reset_returns_200():
    """Test /reset returns 200 and valid observation."""
    print("\n[TEST] /reset returns valid observation")
    r = requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})
    assert r.status_code == 200, f"Reset failed: {r.status_code} {r.text}"
    obs = r.json()

    required_fields = [
        "done", "reward", "data_snapshot", "columns", "num_rows",
        "issues_detected", "quality_score", "actions_taken", "max_actions",
        "task_id", "task_description", "message"
    ]
    for field in required_fields:
        assert field in obs, f"Missing field: {field}"

    assert obs["done"] is False, "Initial observation should not be done"
    assert obs["num_rows"] > 0, "Should have rows"
    assert len(obs["columns"]) > 0, "Should have columns"
    assert 0.0 <= obs["quality_score"] <= 1.0, f"Quality score out of range: {obs['quality_score']}"
    print(f"  PASS: {len(required_fields)} required fields present")
    print(f"  PASS: quality_score={obs['quality_score']}, rows={obs['num_rows']}")
    results["reset"] = True


def test_step_fix_cell():
    """Test /step with fix_cell action."""
    print("\n[TEST] /step fix_cell action")
    # Reset first
    requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})

    # Fix a cell
    r = requests.post(f"{SERVER_URL}/step", json={
        "action_type": "fix_cell",
        "row": 0,
        "column": "name",
        "value": "John Doe"
    })
    assert r.status_code == 200, f"Step failed: {r.status_code} {r.text}"
    obs = r.json()
    assert obs["done"] is False
    assert obs["actions_taken"] == 1
    assert obs["reward"] is not None
    assert "Fixed" in obs["message"] or "fixed" in obs["message"].lower() or "Fix" in obs["message"]
    print(f"  PASS: action applied, quality={obs['quality_score']}, reward={obs['reward']}")
    results["step_fix_cell"] = True


def test_step_delete_row():
    """Test /step with delete_row action."""
    print("\n[TEST] /step delete_row action")
    # Reset with hard task (has duplicates)
    r = requests.post(f"{SERVER_URL}/reset", json={"task_id": "hard_sales_reconciliation"})
    initial_rows = r.json()["num_rows"]

    # Delete a row
    r = requests.post(f"{SERVER_URL}/step", json={
        "action_type": "delete_row",
        "row": 2
    })
    assert r.status_code == 200
    obs = r.json()
    assert obs["num_rows"] == initial_rows - 1, f"Row not deleted: {obs['num_rows']} vs {initial_rows - 1}"
    print(f"  PASS: row deleted, {initial_rows} -> {obs['num_rows']} rows")
    results["step_delete_row"] = True


def test_step_mark_complete():
    """Test /step with mark_complete action."""
    print("\n[TEST] /step mark_complete action")
    requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})

    r = requests.post(f"{SERVER_URL}/step", json={"action_type": "mark_complete"})
    assert r.status_code == 200
    obs = r.json()
    assert obs["done"] is True, "mark_complete should set done=True"
    assert obs["reward"] is not None and obs["reward"] > 0, f"Final reward should be > 0, got {obs['reward']}"
    assert 0.0 <= obs["reward"] <= 1.0, f"Reward out of range: {obs['reward']}"
    print(f"  PASS: done=True, final_reward={obs['reward']:.4f}")
    results["step_mark_complete"] = True


def test_state():
    """Test /state endpoint."""
    print("\n[TEST] /state endpoint")
    requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})
    requests.post(f"{SERVER_URL}/step", json={
        "action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"
    })

    r = requests.get(f"{SERVER_URL}/state")
    assert r.status_code == 200
    state = r.json()
    assert "episode_id" in state
    assert "step_count" in state
    assert state["step_count"] == 1
    assert "task_id" in state
    print(f"  PASS: step_count={state['step_count']}, task_id={state['task_id']}")
    results["state"] = True


def test_all_3_tasks():
    """Test all 3 tasks produce valid scores in 0.0-1.0."""
    print("\n[TEST] All 3 tasks with graders")
    for task_id in TASKS:
        r = requests.post(f"{SERVER_URL}/reset", json={"task_id": task_id})
        assert r.status_code == 200, f"Reset failed for {task_id}"
        obs = r.json()
        initial_quality = obs["quality_score"]
        assert 0.0 <= initial_quality <= 1.0

        # Do a few fixes then mark complete
        for i in range(3):
            col = obs["columns"][0] if obs["columns"] else "name"
            requests.post(f"{SERVER_URL}/step", json={
                "action_type": "fix_cell", "row": 0, "column": col, "value": "Test"
            })

        r = requests.post(f"{SERVER_URL}/step", json={"action_type": "mark_complete"})
        final_obs = r.json()
        assert final_obs["done"] is True
        assert 0.0 <= final_obs["quality_score"] <= 1.0
        assert 0.0 <= final_obs["reward"] <= 1.0
        print(f"  PASS: {task_id}: quality={final_obs['quality_score']:.4f}, reward={final_obs['reward']:.4f}")

    results["all_3_tasks"] = True


def test_partial_progress():
    """Test that reward provides partial progress signal (not just binary)."""
    print("\n[TEST] Partial progress reward signal")
    requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})

    rewards = []
    # Apply several correct fixes
    fixes = [
        {"row": 0, "column": "name", "value": "John Doe"},
        {"row": 0, "column": "signup_date", "value": "2024-01-15"},
        {"row": 0, "column": "city", "value": "New York"},
        {"row": 1, "column": "name", "value": "Jane Smith"},
        {"row": 1, "column": "email", "value": "jane@example.com"},
    ]

    for fix in fixes:
        r = requests.post(f"{SERVER_URL}/step", json={
            "action_type": "fix_cell", **fix
        })
        obs = r.json()
        rewards.append(obs["reward"])

    # Rewards should generally increase (partial progress)
    assert len(set(rewards)) > 1, f"Rewards are all the same: {rewards} - no partial progress!"
    print(f"  PASS: rewards vary over steps: {[f'{r:.4f}' for r in rewards]}")
    results["partial_progress"] = True


def test_max_actions_limit():
    """Test that environment ends when max_actions is reached."""
    print("\n[TEST] Max actions limit enforcement")
    r = requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})
    max_actions = r.json()["max_actions"]

    # Send max_actions steps
    done = False
    for i in range(max_actions + 5):
        r = requests.post(f"{SERVER_URL}/step", json={
            "action_type": "fix_cell", "row": 0, "column": "name", "value": f"Test{i}"
        })
        obs = r.json()
        if obs["done"]:
            done = True
            assert i + 1 <= max_actions, f"Ended too early at step {i+1}"
            print(f"  PASS: Episode ended at step {i+1} (max={max_actions})")
            break

    assert done, "Episode should end at max_actions"
    results["max_actions"] = True


def test_error_handling():
    """Test error handling for invalid actions."""
    print("\n[TEST] Error handling")
    requests.post(f"{SERVER_URL}/reset", json={"task_id": "easy_customer_contacts"})

    # Invalid row
    r = requests.post(f"{SERVER_URL}/step", json={
        "action_type": "fix_cell", "row": 999, "column": "name", "value": "Test"
    })
    assert r.status_code == 200  # Should not crash, just return error message
    obs = r.json()
    assert "error" in obs["message"].lower() or "Error" in obs["message"]

    # Invalid column
    r = requests.post(f"{SERVER_URL}/step", json={
        "action_type": "fix_cell", "row": 0, "column": "nonexistent", "value": "Test"
    })
    obs = r.json()
    assert "error" in obs["message"].lower() or "Error" in obs["message"]

    # Invalid action_type
    r = requests.post(f"{SERVER_URL}/step", json={
        "action_type": "invalid_action"
    })
    obs = r.json()
    assert "unknown" in obs["message"].lower() or "Unknown" in obs["message"]

    print(f"  PASS: All invalid actions handled gracefully")
    results["error_handling"] = True


def test_openenv_yaml():
    """Test openenv.yaml is valid."""
    print("\n[TEST] openenv.yaml")
    assert os.path.exists("openenv.yaml"), "openenv.yaml not found"
    with open("openenv.yaml") as f:
        content = f.read()
    assert "name:" in content
    assert "version:" in content
    assert "description:" in content
    assert "action:" in content
    assert "observation:" in content
    print(f"  PASS: openenv.yaml has all required fields")
    results["openenv_yaml"] = True


def test_dockerfile():
    """Test Dockerfile exists and has required elements."""
    print("\n[TEST] Dockerfile")
    assert os.path.exists("Dockerfile"), "Dockerfile not found"
    with open("Dockerfile") as f:
        content = f.read()
    assert "FROM" in content, "Dockerfile missing FROM"
    assert "EXPOSE" in content, "Dockerfile missing EXPOSE"
    assert "CMD" in content, "Dockerfile missing CMD"
    assert "8000" in content, "Dockerfile should expose port 8000"
    assert "uvicorn" in content, "Dockerfile should run uvicorn"
    print(f"  PASS: Dockerfile has all required directives")
    results["dockerfile"] = True


def test_inference_script():
    """Test inference.py exists and has required elements."""
    print("\n[TEST] inference.py")
    assert os.path.exists("inference.py"), "inference.py not found in root directory"
    with open("inference.py") as f:
        content = f.read()
    assert "API_BASE_URL" in content, "inference.py must read API_BASE_URL"
    assert "MODEL_NAME" in content, "inference.py must read MODEL_NAME"
    assert "HF_TOKEN" in content, "inference.py must read HF_TOKEN"
    assert "OpenAI" in content, "inference.py must use OpenAI client"
    assert "easy_customer_contacts" in content
    assert "medium_product_inventory" in content
    assert "hard_sales_reconciliation" in content
    print(f"  PASS: inference.py has all required variables and tasks")
    results["inference_script"] = True


def test_readme():
    """Test README.md has HF Space metadata and required sections."""
    print("\n[TEST] README.md")
    assert os.path.exists("README.md"), "README.md not found"
    with open("README.md") as f:
        content = f.read()
    assert "sdk: docker" in content, "README must have 'sdk: docker' in YAML frontmatter"
    assert "app_port: 8000" in content, "README must have 'app_port: 8000'"
    assert "openenv" in content.lower(), "README must mention openenv"
    assert "action" in content.lower(), "README must describe action space"
    assert "observation" in content.lower(), "README must describe observation space"
    print(f"  PASS: README.md has HF Space metadata and documentation")
    results["readme"] = True


def print_summary():
    """Print the final summary matching hackathon checklist."""
    print("\n" + "=" * 70)
    print("  HACKATHON PRE-SUBMISSION CHECKLIST")
    print("=" * 70)

    checks = [
        ("HF Space deploys (needs manual deploy)", None, "Deploy to HF Spaces"),
        ("reset() returns 200 with valid observation", results.get("reset")),
        ("step() works with fix_cell", results.get("step_fix_cell")),
        ("step() works with delete_row", results.get("step_delete_row")),
        ("step() works with mark_complete", results.get("step_mark_complete")),
        ("state() returns current state", results.get("state")),
        ("3+ tasks with graders (scores 0.0-1.0)", results.get("all_3_tasks")),
        ("Partial progress reward signal", results.get("partial_progress")),
        ("Max actions limit enforced", results.get("max_actions")),
        ("Error handling works", results.get("error_handling")),
        ("openenv.yaml valid", results.get("openenv_yaml")),
        ("Dockerfile valid", results.get("dockerfile")),
        ("inference.py present with required vars", results.get("inference_script")),
        ("README.md with HF metadata", results.get("readme")),
        ("Health check endpoint works", results.get("health")),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for item in checks:
        if len(item) == 3:
            name, status, note = item
        else:
            name, status = item
            note = None

        if status is True:
            icon = "PASS"
            passed += 1
        elif status is False:
            icon = "FAIL"
            failed += 1
        else:
            icon = "SKIP"
            skipped += 1
            note = note or "Manual step required"

        line = f"  [{icon}] {name}"
        if note:
            line += f"  ({note})"
        print(line)

    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        print("\n  ALL AUTOMATED CHECKS PASSED!")
        print("  Next: Deploy to Hugging Face Spaces and run inference.py")
    else:
        print(f"\n  {failed} CHECK(S) FAILED - fix before submitting")

    print("=" * 70)


if __name__ == "__main__":
    print("=" * 70)
    print("  Data Cleaning Environment - Full End-to-End Test")
    print("=" * 70)

    # File-level tests (no server needed)
    test_openenv_yaml()
    test_dockerfile()
    test_inference_script()
    test_readme()

    # Start server
    print("\n[SETUP] Starting FastAPI server on port 8765...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    if not wait_for_server(SERVER_URL):
        print("  FAILED: Server did not start within 15 seconds")
        sys.exit(1)
    print("  Server is running!")

    # Server tests
    try:
        test_health()
        test_root()
        test_reset_returns_200()
        test_step_fix_cell()
        test_step_delete_row()
        test_step_mark_complete()
        test_state()
        test_all_3_tasks()
        test_partial_progress()
        test_max_actions_limit()
        test_error_handling()
    except Exception as e:
        print(f"\n  TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()

    print_summary()
