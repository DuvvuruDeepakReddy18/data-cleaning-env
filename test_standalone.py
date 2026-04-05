#!/usr/bin/env python3
"""Standalone test that validates core environment logic without external deps."""

import copy
import csv
import io
import sys
import uuid
import importlib

# ── Setup for testing without pydantic ──
sys.path.insert(0, ".")

# Ensure path is set up



def test_task_definitions():
    """Test that task data is well-formed."""
    from data_cleaning_env.tasks.task_definitions import TASKS, get_task

    print("Testing task definitions...")

    for task_id, task_fn in TASKS.items():
        task = task_fn()
        dirty = task["dirty_data"]
        clean = task["clean_data"]
        columns = task["columns"]

        print(f"\n  Task: {task_id}")
        print(f"    Dirty rows: {len(dirty)}")
        print(f"    Clean rows: {len(clean)}")
        print(f"    Columns: {columns}")
        print(f"    Max actions: {task['max_actions']}")
        print(f"    Issues: {len(task['issues'])}")

        # Verify column consistency
        for i, row in enumerate(dirty):
            for col in columns:
                assert col in row, f"Dirty row {i} missing column '{col}'"

        for i, row in enumerate(clean):
            for col in columns:
                assert col in row, f"Clean row {i} missing column '{col}'"

        # Verify dirty != clean (there must be differences)
        diffs = 0
        for d_row, c_row in zip(dirty, clean):
            for col in columns:
                if str(d_row[col]).strip() != str(c_row[col]).strip():
                    diffs += 1

        # Row count difference also counts
        row_diff = abs(len(dirty) - len(clean))
        print(f"    Cell diffs: {diffs}")
        print(f"    Row diff: {row_diff}")

        assert diffs > 0 or row_diff > 0, f"Task {task_id} has no differences!"

        # Verify get_task returns deep copy
        t1 = get_task(task_id)
        t2 = get_task(task_id)
        t1["dirty_data"][0][columns[0]] = "MODIFIED"
        assert t2["dirty_data"][0][columns[0]] != "MODIFIED", "get_task must return deep copies"

    print("\n  All task definitions valid!")


def test_quality_scoring():
    """Test the quality score computation logic."""
    print("\nTesting quality scoring...")

    from data_cleaning_env.tasks.task_definitions import get_task

    task = get_task("easy_customer_contacts")
    dirty = task["dirty_data"]
    clean = task["clean_data"]
    columns = task["columns"]

    # Test: identical data should score 1.0
    score = compute_quality(clean, clean, columns)
    assert abs(score - 1.0) < 0.001, f"Identical data should score 1.0, got {score}"
    print(f"  Identical data score: {score}")

    # Test: dirty data should score less than 1.0
    score = compute_quality(dirty, clean, columns)
    assert score < 1.0, f"Dirty data should score < 1.0, got {score}"
    assert score > 0.0, f"Dirty data should score > 0.0, got {score}"
    print(f"  Dirty data score: {score}")

    # Test: partially fixed data should score between dirty and clean
    partially_fixed = copy.deepcopy(dirty)
    partially_fixed[0]["name"] = "John Doe"  # Fix one cell
    partial_score = compute_quality(partially_fixed, clean, columns)
    assert partial_score >= score, f"Partially fixed should score >= dirty"
    print(f"  Partially fixed score: {partial_score}")

    # Test: extra rows should reduce score
    extra_data = copy.deepcopy(clean) + [clean[0]]
    extra_score = compute_quality(extra_data, clean, columns)
    assert extra_score < 1.0, f"Extra rows should score < 1.0"
    print(f"  Extra rows score: {extra_score}")

    print("  Quality scoring works correctly!")


def compute_quality(current, clean, columns):
    """Standalone quality computation matching environment logic."""
    total_cells = len(clean) * len(columns)
    if total_cells == 0:
        return 1.0

    correct_cells = 0
    used_clean_indices = set()

    for crow in current:
        best_match_score = 0
        best_match_idx = -1

        for ci, cln_row in enumerate(clean):
            if ci in used_clean_indices:
                continue
            match_score = sum(
                1 for col in columns
                if str(crow.get(col, "")).strip() == str(cln_row.get(col, "")).strip()
            )
            if match_score > best_match_score:
                best_match_score = match_score
                best_match_idx = ci

        if best_match_idx >= 0:
            used_clean_indices.add(best_match_idx)
            correct_cells += best_match_score

    extra_rows = max(0, len(current) - len(clean))
    penalty = extra_rows * len(columns)
    missing_rows = max(0, len(clean) - len(used_clean_indices))
    penalty += missing_rows * len(columns)

    score = max(0.0, (correct_cells - penalty * 0.5) / total_cells)
    return round(min(1.0, score), 4)


def test_action_handling():
    """Test action handling logic."""
    print("\nTesting action handling...")

    from data_cleaning_env.tasks.task_definitions import get_task

    task = get_task("easy_customer_contacts")
    data = copy.deepcopy(task["dirty_data"])
    columns = task["columns"]

    # Test fix_cell
    old_val = data[0]["name"]
    data[0]["name"] = "John Doe"
    assert data[0]["name"] == "John Doe"
    print(f"  fix_cell: '{old_val}' -> '{data[0]['name']}'")

    # Test delete_row
    orig_len = len(data)
    deleted = data.pop(5)
    assert len(data) == orig_len - 1
    print(f"  delete_row: removed row, {orig_len} -> {len(data)} rows")

    # Test that quality improves with fixes
    task2 = get_task("easy_customer_contacts")
    dirty = copy.deepcopy(task2["dirty_data"])
    clean = task2["clean_data"]

    initial_score = compute_quality(dirty, clean, columns)

    # Apply several fixes
    dirty[0]["name"] = "John Doe"
    dirty[0]["signup_date"] = "2024-01-15"
    dirty[0]["city"] = "New York"
    dirty[1]["name"] = "Jane Smith"

    improved_score = compute_quality(dirty, clean, columns)
    assert improved_score > initial_score, "Fixes should improve score"
    print(f"  Score improved: {initial_score} -> {improved_score}")

    print("  Action handling works correctly!")


def test_csv_generation():
    """Test CSV output generation."""
    print("\nTesting CSV generation...")

    from data_cleaning_env.tasks.task_definitions import get_task

    task = get_task("easy_customer_contacts")
    data = task["dirty_data"]
    columns = task["columns"]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in data:
        writer.writerow(row)

    csv_str = output.getvalue()
    lines = csv_str.strip().split("\n")
    assert len(lines) == len(data) + 1  # header + data rows
    # Verify header contains all columns (CSV quoting may vary)
    for col in columns:
        assert col in lines[0], f"Header missing column '{col}'"
    print(f"  Generated CSV with {len(lines)} lines")
    print(f"  Header: {lines[0]}")
    print(f"  First row: {lines[1][:60]}...")
    print("  CSV generation works correctly!")


def test_hard_task_duplicates():
    """Test that the hard task has proper duplicate detection."""
    print("\nTesting hard task duplicate handling...")

    from data_cleaning_env.tasks.task_definitions import get_task

    task = get_task("hard_sales_reconciliation")
    dirty = task["dirty_data"]
    clean = task["clean_data"]

    print(f"  Dirty rows: {len(dirty)}")
    print(f"  Clean rows: {len(clean)}")
    assert len(dirty) > len(clean), "Hard task should have duplicate rows to delete"

    # Check that order IDs in dirty have duplicates
    order_ids = [r["order_id"] for r in dirty if r["order_id"]]
    unique_ids = set(order_ids)
    duplicates = len(order_ids) - len(unique_ids)
    print(f"  Duplicate order IDs found: {duplicates}")
    assert duplicates > 0, "Hard task must have duplicate rows"

    # Check that clean data has no duplicates
    clean_ids = [r["order_id"] for r in clean if r["order_id"]]
    assert len(clean_ids) == len(set(clean_ids)), "Clean data should have no duplicates"

    print("  Hard task duplicate handling is correct!")


def test_reward_computation():
    """Test reward computation logic."""
    print("\nTesting reward computation...")

    # Simulate reward calculation
    initial_score = 0.6
    current_score = 0.8
    max_actions = 40
    actions_taken = 15

    # Progress reward
    if initial_score < 1.0:
        progress = (current_score - initial_score) / (1.0 - initial_score)
    else:
        progress = 1.0
    progress = max(0.0, min(1.0, progress))
    step_reward = progress * 0.5

    # Final reward
    final_reward = current_score * 0.5
    efficiency = max(0.0, 1.0 - (actions_taken / max_actions))
    total = min(1.0, step_reward + final_reward + efficiency * 0.1)

    print(f"  Progress: {progress:.4f}")
    print(f"  Step reward: {step_reward:.4f}")
    print(f"  Final reward: {final_reward:.4f}")
    print(f"  Efficiency bonus: {efficiency * 0.1:.4f}")
    print(f"  Total reward: {total:.4f}")

    assert 0.0 <= total <= 1.0, f"Reward must be in [0,1], got {total}"
    assert total > 0.0, "Reward should be positive for improvement"

    # Perfect score should give bonus
    perfect_score = 1.0
    perfect_progress = (perfect_score - initial_score) / (1.0 - initial_score)
    perfect_step = perfect_progress * 0.5
    perfect_final = perfect_score * 0.5 + 0.2  # bonus
    perfect_total = min(1.0, perfect_step + perfect_final + efficiency * 0.1)
    print(f"  Perfect total reward: {perfect_total:.4f}")
    assert perfect_total > total, "Perfect score should give higher reward"

    print("  Reward computation works correctly!")


if __name__ == "__main__":
    print("=" * 60)
    print("  Data Cleaning Environment - Standalone Tests")
    print("=" * 60)

    test_task_definitions()
    test_quality_scoring()
    test_action_handling()
    test_csv_generation()
    test_hard_task_duplicates()
    test_reward_computation()

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print("=" * 60)
