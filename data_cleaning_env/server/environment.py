"""
Core environment logic for the Data Cleaning Environment.

Implements reset(), step(), and state property following the OpenEnv spec.
"""

import copy
import csv
import io
import uuid
from typing import Any

from data_cleaning_env.models import (
    DataCleanAction,
    DataCleanObservation,
    DataCleanState,
)
from data_cleaning_env.tasks import TASKS, get_task


class DataCleanEnvironment:
    """Environment where an agent cleans messy tabular data.

    The agent inspects a dirty dataset and takes cleaning actions (fix_cell,
    delete_row) to transform it toward a gold-standard clean version.
    Grading compares the agent's final state cell-by-cell against the gold data.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True
    DEFAULT_TASK = "easy_customer_contacts"

    def __init__(self):
        self._state = DataCleanState()
        self._current_data: list[dict[str, str]] = []
        self._clean_data: list[dict[str, str]] = []
        self._columns: list[str] = []
        self._task_config: dict[str, Any] = {}
        self._max_actions: int = 40
        self._actions_taken: int = 0
        self._initial_dirty_data: list[dict[str, str]] = []

    def reset(self, seed=None, episode_id=None, **kwargs) -> DataCleanObservation:
        """Reset the environment with a task.

        Pass task_id in kwargs to select a task:
        - "easy_customer_contacts"
        - "medium_product_inventory"
        - "hard_sales_reconciliation"
        """
        task_id = kwargs.get("task_id", self.DEFAULT_TASK)

        task = get_task(task_id)
        self._task_config = task
        self._current_data = copy.deepcopy(task["dirty_data"])
        self._initial_dirty_data = copy.deepcopy(task["dirty_data"])
        self._clean_data = task["clean_data"]
        self._columns = task["columns"]
        self._max_actions = task["max_actions"]
        self._actions_taken = 0

        initial_score = self._compute_quality_score()
        total_issues = self._count_total_issues()

        self._state = DataCleanState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_id=task_id,
            total_issues=total_issues,
            issues_fixed=0,
            issues_introduced=0,
            quality_score=initial_score,
        )

        return DataCleanObservation(
            done=False,
            reward=None,
            data_snapshot=self._data_to_csv(),
            columns=self._columns,
            num_rows=len(self._current_data),
            issues_detected=task.get("issues", []),
            quality_score=initial_score,
            actions_taken=0,
            max_actions=self._max_actions,
            task_id=task_id,
            task_description=task["description"],
            message=f"Dataset loaded with {len(self._current_data)} rows. Begin cleaning!",
        )

    def step(self, action: DataCleanAction, timeout_s=None, **kwargs) -> DataCleanObservation:
        """Execute a cleaning action on the dataset."""
        self._actions_taken += 1
        self._state.step_count += 1
        message = ""

        action_type = action.action_type.lower().strip()

        if action_type == "fix_cell":
            message = self._handle_fix_cell(action)
        elif action_type == "delete_row":
            message = self._handle_delete_row(action)
        elif action_type == "mark_complete":
            message = "Cleaning marked as complete."
        else:
            message = (
                f"Unknown action_type '{action.action_type}'. "
                "Valid types: fix_cell, delete_row, mark_complete"
            )

        # Compute current quality
        quality_score = self._compute_quality_score()
        self._state.quality_score = quality_score

        # Check if episode is done
        done = (
            action_type == "mark_complete"
            or self._actions_taken >= self._max_actions
        )

        if self._actions_taken >= self._max_actions and action_type != "mark_complete":
            message += " Max actions reached. Episode ending."

        # Compute reward
        reward = self._compute_reward(done)

        return DataCleanObservation(
            done=done,
            reward=reward,
            data_snapshot=self._data_to_csv(),
            columns=self._columns,
            num_rows=len(self._current_data),
            issues_detected=self._detect_remaining_issues(),
            quality_score=quality_score,
            actions_taken=self._actions_taken,
            max_actions=self._max_actions,
            task_id=self._state.task_id,
            task_description=self._task_config.get("description", ""),
            message=message,
        )

    @property
    def state(self) -> DataCleanState:
        """Return the current environment state."""
        return self._state

    # ── Reward computation ──

    def _compute_reward(self, done: bool) -> float:
        """Compute reward based on data quality improvement.

        Provides partial progress signal at every step plus a final bonus.
        Penalizes introducing new errors.
        """
        current_score = self._state.quality_score
        initial_score = self._compute_initial_quality_score()

        # Progress reward: how much quality improved from initial
        if initial_score < 1.0:
            progress = (current_score - initial_score) / (1.0 - initial_score)
        else:
            progress = 1.0

        progress = max(0.0, min(1.0, progress))

        # Step-level reward: proportional to quality improvement
        step_reward = progress * 0.5

        if done:
            # Final reward: heavily weighted on final quality
            final_reward = current_score * 0.5
            # Bonus for perfect cleaning
            if current_score >= 0.99:
                final_reward += 0.2
            # Efficiency bonus: fewer actions = better
            efficiency = max(0.0, 1.0 - (self._actions_taken / self._max_actions))
            final_reward += efficiency * 0.1
            return min(1.0, step_reward + final_reward)

        return round(step_reward, 4)

    def _compute_quality_score(self) -> float:
        """Compare current data to clean data cell-by-cell.

        Returns a score from 0.0 to 1.0 representing data quality.
        Handles both value correctness and row structure (deletions).
        """
        if not self._clean_data:
            return 1.0

        clean = self._clean_data
        current = self._current_data

        total_cells = len(clean) * len(self._columns)
        if total_cells == 0:
            return 1.0

        correct_cells = 0

        # Check for matching rows
        # Build a mapping from current rows to clean rows based on best match
        used_clean_indices = set()

        for crow in current:
            best_match_score = 0
            best_match_idx = -1

            for ci, cln_row in enumerate(clean):
                if ci in used_clean_indices:
                    continue
                match_score = sum(
                    1 for col in self._columns
                    if str(crow.get(col, "")).strip() == str(cln_row.get(col, "")).strip()
                )
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_idx = ci

            if best_match_idx >= 0:
                used_clean_indices.add(best_match_idx)
                correct_cells += best_match_score

        # Penalize for extra rows (rows in current but not matched to clean)
        extra_rows = max(0, len(current) - len(clean))
        penalty = extra_rows * len(self._columns)

        # Penalize for missing rows (clean rows not matched)
        missing_rows = max(0, len(clean) - len(used_clean_indices))
        penalty += missing_rows * len(self._columns)

        score = max(0.0, (correct_cells - penalty * 0.5) / total_cells)
        return round(min(1.0, score), 4)

    def _compute_initial_quality_score(self) -> float:
        """Compute quality score of the original dirty data."""
        # Save current data, compute with dirty data, restore
        saved = self._current_data
        self._current_data = self._initial_dirty_data
        score = self._compute_quality_score()
        self._current_data = saved
        return score

    def _count_total_issues(self) -> int:
        """Count total issues in the dirty data compared to clean data."""
        dirty = self._initial_dirty_data
        clean = self._clean_data

        issues = 0
        # Count cell-level differences
        for i, (d_row, c_row) in enumerate(zip(dirty, clean)):
            for col in self._columns:
                if str(d_row.get(col, "")).strip() != str(c_row.get(col, "")).strip():
                    issues += 1

        # Count extra rows that need deletion
        if len(dirty) > len(clean):
            issues += len(dirty) - len(clean)

        return issues

    # ── Action handlers ──

    def _handle_fix_cell(self, action: DataCleanAction) -> str:
        """Fix a cell value in the dataset."""
        if action.row is None:
            return "Error: fix_cell requires 'row' parameter."
        if action.column is None:
            return "Error: fix_cell requires 'column' parameter."
        if action.value is None:
            return "Error: fix_cell requires 'value' parameter."

        row_idx = action.row
        col = action.column

        if row_idx < 0 or row_idx >= len(self._current_data):
            return f"Error: row {row_idx} out of range (0 to {len(self._current_data) - 1})."

        if col not in self._columns:
            return f"Error: column '{col}' not found. Available: {', '.join(self._columns)}"

        old_value = self._current_data[row_idx][col]
        self._current_data[row_idx][col] = action.value

        return f"Fixed row {row_idx}, column '{col}': '{old_value}' -> '{action.value}'"

    def _handle_delete_row(self, action: DataCleanAction) -> str:
        """Delete a row from the dataset."""
        if action.row is None:
            return "Error: delete_row requires 'row' parameter."

        row_idx = action.row

        if row_idx < 0 or row_idx >= len(self._current_data):
            return f"Error: row {row_idx} out of range (0 to {len(self._current_data) - 1})."

        deleted_row = self._current_data.pop(row_idx)
        preview = ", ".join(f"{k}={v}" for k, v in list(deleted_row.items())[:3])
        return f"Deleted row {row_idx}: {preview}..."

    # ── Helpers ──

    def _data_to_csv(self) -> str:
        """Convert current data to CSV string for observation."""
        if not self._current_data:
            return ""

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self._columns)
        writer.writeheader()
        for row in self._current_data:
            writer.writerow(row)
        return output.getvalue()

    def _detect_remaining_issues(self) -> list[str]:
        """Detect remaining issues by comparing to clean data.

        Returns human-readable descriptions of remaining problems.
        """
        issues = []
        current = self._current_data
        clean = self._clean_data

        # Check for row count mismatch
        if len(current) > len(clean):
            issues.append(
                f"Dataset has {len(current)} rows but should have {len(clean)} "
                f"({len(current) - len(clean)} rows should be deleted)"
            )

        # Check cell-level issues (compare rows by best match)
        used_clean = set()
        for ri, crow in enumerate(current):
            best_idx = -1
            best_score = -1
            for ci, cln in enumerate(clean):
                if ci in used_clean:
                    continue
                score = sum(
                    1 for col in self._columns
                    if str(crow.get(col, "")).strip() == str(cln.get(col, "")).strip()
                )
                if score > best_score:
                    best_score = score
                    best_idx = ci

            if best_idx >= 0:
                used_clean.add(best_idx)
                cln = clean[best_idx]
                for col in self._columns:
                    cv = str(crow.get(col, "")).strip()
                    gv = str(cln.get(col, "")).strip()
                    if cv != gv:
                        issues.append(f"Row {ri}, column '{col}': current='{cv}' needs fixing")

        return issues[:30]  # Cap to avoid huge observations
