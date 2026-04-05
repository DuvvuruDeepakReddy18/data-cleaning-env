"""
Core environment logic for the Data Cleaning Environment.

Implements reset(), step(), and state property following the OpenEnv spec.
"""

import copy
import csv
import io
import uuid
from typing import Any, Dict, List

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
        self._cleaning_history: List[str] = []
        self._failed_action_count: int = 0
        self._last_quality_score: float = 0.0

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
        self._cleaning_history = []
        self._failed_action_count = 0

        initial_score = self._compute_quality_score()
        total_issues = self._count_total_issues()
        self._last_quality_score = initial_score

        self._state = DataCleanState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_id=task_id,
            total_issues=total_issues,
            issues_fixed=0,
            issues_introduced=0,
            quality_score=initial_score,
            quality_history=[initial_score],
            actions_log=[],
            reward_total=0.0,
        )

        # Determine difficulty
        difficulty = "unknown"
        if task_id == "easy_customer_contacts":
            difficulty = "easy"
        elif task_id == "medium_product_inventory":
            difficulty = "medium"
        elif task_id == "hard_sales_reconciliation":
            difficulty = "hard"

        data_profile = self._compute_data_profile()
        issue_categories = self._categorize_issues(self._detect_remaining_issues())
        progress_pct = self._compute_progress_percentage(total_issues, 0)

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
            data_profile=data_profile,
            cleaning_history=[],
            issue_categories=issue_categories,
            difficulty=difficulty,
            progress_pct=progress_pct,
        )

    def step(self, action: DataCleanAction, timeout_s=None, **kwargs) -> DataCleanObservation:
        """Execute a cleaning action on the dataset."""
        self._actions_taken += 1
        self._state.step_count += 1
        message = ""
        action_log_entry = ""

        action_type = action.action_type.lower().strip()

        if action_type == "fix_cell":
            message = self._handle_fix_cell(action)
            reason_str = f" (reason: {action.reason})" if action.reason else ""
            action_log_entry = f"fix_cell at row {action.row}, col {action.column}{reason_str}"
        elif action_type == "delete_row":
            message = self._handle_delete_row(action)
            reason_str = f" (reason: {action.reason})" if action.reason else ""
            action_log_entry = f"delete_row at row {action.row}{reason_str}"
        elif action_type == "mark_complete":
            message = "Cleaning marked as complete."
            action_log_entry = "mark_complete"
        else:
            message = (
                f"Unknown action_type '{action.action_type}'. "
                "Valid types: fix_cell, delete_row, mark_complete"
            )
            action_log_entry = f"unknown action: {action.action_type}"

        # Log the action
        if action_log_entry:
            self._state.actions_log.append(action_log_entry)

        # Compute current quality
        quality_score = self._compute_quality_score()
        self._state.quality_score = quality_score
        self._state.quality_history.append(quality_score)

        # Track successful actions for cleaning history
        if action_type in ["fix_cell", "delete_row"] and "Error:" not in message:
            self._cleaning_history.append(message)
            self._cleaning_history = self._cleaning_history[-10:]  # Keep last 10
        else:
            self._failed_action_count += 1

        # Check if episode is done
        done = (
            action_type == "mark_complete"
            or self._actions_taken >= self._max_actions
        )

        if self._actions_taken >= self._max_actions and action_type != "mark_complete":
            message += " Max actions reached. Episode ending."

        # Compute reward with enhancements
        reward = self._compute_reward(done, quality_score)
        self._state.reward_total += reward

        # Compute new statistics
        data_profile = self._compute_data_profile()
        raw_issues = self._detect_remaining_issues()
        issue_categories = self._categorize_issues(raw_issues)
        issues_fixed = self._state.total_issues - len(raw_issues)
        self._state.issues_fixed = issues_fixed
        progress_pct = self._compute_progress_percentage(
            self._state.total_issues, issues_fixed
        )

        return DataCleanObservation(
            done=done,
            reward=reward,
            data_snapshot=self._data_to_csv(),
            columns=self._columns,
            num_rows=len(self._current_data),
            issues_detected=raw_issues,
            quality_score=quality_score,
            actions_taken=self._actions_taken,
            max_actions=self._max_actions,
            task_id=self._state.task_id,
            task_description=self._task_config.get("description", ""),
            message=message,
            data_profile=data_profile,
            cleaning_history=self._cleaning_history.copy(),
            issue_categories=issue_categories,
            difficulty=self._get_task_difficulty(),
            progress_pct=progress_pct,
        )

    @property
    def state(self) -> DataCleanState:
        """Return the current environment state."""
        return self._state

    # ── Reward computation ──

    def _compute_reward(self, done: bool, current_score: float = None) -> float:
        """Compute reward based on data quality improvement.

        Provides partial progress signal at every step plus a final bonus.
        Penalizes introducing new errors.
        Includes diminishing returns penalty and streak bonus.
        """
        if current_score is None:
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

        # Diminishing returns penalty for repeated failed actions
        fail_penalty = min(0.1, self._failed_action_count * 0.02)

        # Streak bonus for consecutive quality improvements
        streak_bonus = 0.0
        if len(self._state.quality_history) >= 2:
            recent_scores = self._state.quality_history[-3:]
            if all(
                recent_scores[i] <= recent_scores[i + 1]
                for i in range(len(recent_scores) - 1)
            ):
                streak_bonus = 0.05

        if done:
            # Final reward: heavily weighted on final quality
            final_reward = current_score * 0.5
            # Bonus for perfect cleaning
            if current_score >= 0.99:
                final_reward += 0.2
            # Efficiency bonus: fewer actions = better
            efficiency = max(0.0, 1.0 - (self._actions_taken / self._max_actions))
            final_reward += efficiency * 0.1
            return min(1.0, step_reward + final_reward - fail_penalty)

        return round(step_reward - fail_penalty + streak_bonus, 4)

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
        Issues are categorized but raw list is returned here.
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

    def _categorize_issues(self, issues: List[str]) -> Dict[str, int]:
        """Categorize detected issues into types.

        Categories:
        - "formatting": case, whitespace, date format issues
        - "missing_values": empty, null, N/A values
        - "duplicates": duplicate rows
        - "logical_errors": math wrong, dates out of order, values out of range
        - "type_errors": text instead of number, type mismatches
        """
        categories = {
            "formatting": 0,
            "missing_values": 0,
            "duplicates": 0,
            "logical_errors": 0,
            "type_errors": 0,
        }

        for issue in issues:
            issue_lower = issue.lower()

            # Classify the issue
            if "empty" in issue_lower or "null" in issue_lower or "n/a" in issue_lower:
                categories["missing_values"] += 1
            elif "whitespace" in issue_lower or "case" in issue_lower or "format" in issue_lower:
                categories["formatting"] += 1
            elif "duplicate" in issue_lower:
                categories["duplicates"] += 1
            elif (
                "out of range" in issue_lower
                or "out of order" in issue_lower
                or "mismatch" in issue_lower
            ):
                categories["logical_errors"] += 1
            elif "type" in issue_lower or "number" in issue_lower or "text" in issue_lower:
                categories["type_errors"] += 1
            else:
                # Default to formatting for unknown issues
                categories["formatting"] += 1

        return categories

    def _compute_data_profile(self) -> Dict[str, Dict[str, Any]]:
        """Compute per-column statistics for data profiling.

        Returns dict mapping column names to stats:
        - null_count: number of null/empty values
        - unique_count: number of unique values
        - sample_values: first 3 sample values
        - inferred_type: likely type (string, number, date, etc.)
        """
        profile = {}

        for col in self._columns:
            values = [row.get(col, "") for row in self._current_data]
            non_empty = [v for v in values if str(v).strip()]

            null_count = len(values) - len(non_empty)
            unique_count = len(set(non_empty))
            sample_values = non_empty[:3]

            # Infer type
            inferred_type = "string"
            if non_empty:
                try:
                    for v in non_empty[:3]:
                        float(v)
                    inferred_type = "number"
                except (ValueError, TypeError):
                    # Check for date-like patterns
                    if any(
                        "/" in str(v) or "-" in str(v)
                        for v in non_empty[:3]
                    ):
                        inferred_type = "date"
                    else:
                        inferred_type = "string"

            profile[col] = {
                "null_count": null_count,
                "unique_count": unique_count,
                "sample_values": sample_values,
                "inferred_type": inferred_type,
            }

        return profile

    def _compute_progress_percentage(self, total_issues: int, issues_fixed: int) -> float:
        """Calculate percentage of issues fixed (0-100)."""
        if total_issues == 0:
            return 100.0
        return round((issues_fixed / total_issues) * 100.0, 2)

    def _get_task_difficulty(self) -> str:
        """Get the difficulty level based on task_id."""
        task_id = self._state.task_id
        if task_id == "easy_customer_contacts":
            return "easy"
        elif task_id == "medium_product_inventory":
            return "medium"
        elif task_id == "hard_sales_reconciliation":
            return "hard"
        return "unknown"
