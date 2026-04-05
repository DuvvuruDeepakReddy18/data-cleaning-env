"""Typed models for the Data Cleaning Environment.

Uses Pydantic BaseModel directly for self-contained operation.
Compatible with the OpenEnv spec (Action, Observation, State).
"""

from typing import Dict, List, Optional

try:
    from pydantic import BaseModel
except ImportError:
    # Fallback for environments without pydantic (testing only)
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            # Set defaults for missing fields
            for k, v in getattr(self.__class__, '__annotations__', {}).items():
                if not hasattr(self, k):
                    if hasattr(self.__class__, k):
                        setattr(self, k, getattr(self.__class__, k))

        def model_dump(self):
            return {k: getattr(self, k) for k in self.__class__.__annotations__}


class DataCleanAction(BaseModel):
    """An action to clean a dataset.

    action_type options:
        - "fix_cell": Update a cell value. Requires row, column, value.
        - "delete_row": Remove a row. Requires row.
        - "mark_complete": Signal that cleaning is done.
    """

    action_type: str
    row: Optional[int] = None
    column: Optional[str] = None
    value: Optional[str] = None
    reason: Optional[str] = None


class DataCleanObservation(BaseModel):
    """Observation returned after each step with richer feedback."""

    done: bool = False
    reward: Optional[float] = None
    data_snapshot: str = ""
    columns: List[str] = []
    num_rows: int = 0
    issues_detected: List[str] = []
    quality_score: float = 0.0
    actions_taken: int = 0
    max_actions: int = 0
    task_id: str = ""
    task_description: str = ""
    message: str = ""
    data_profile: Dict = {}
    cleaning_history: List[str] = []
    issue_categories: Dict = {}
    difficulty: str = ""
    progress_pct: float = 0.0


class DataCleanState(BaseModel):
    """Internal state of the environment with enhanced tracking."""

    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = ""
    total_issues: int = 0
    issues_fixed: int = 0
    issues_introduced: int = 0
    quality_score: float = 0.0
    quality_history: List[float] = []
    actions_log: List[str] = []
    reward_total: float = 0.0
