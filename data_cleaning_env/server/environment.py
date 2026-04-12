"""
Core environment logic for the Data Cleaning Environment.

Implements reset(), step(), and state property following the OpenEnv spec.
Supports both atomic operations (fix_cell, delete_row) and batch operations
(fill_missing, standardize_column, deduplicate) for realistic data cleaning.
"""

import copy
import csv
import io
import re
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

    The agent inspects a dirty dataset and takes cleaning actions to transform
    it toward a gold-standard clean version. Supports both fine-grained atomic
    actions (fix_cell, delete_row) and efficient batch operations (fill_missing,
    standardize_column, deduplicate) that mirror real-world data cleaning tools.

    Grading compares the agent's final state cell-by-cell against the gold data.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True
    DEFAULT_TASK = "easy_customer_contacts"

    VALID_ACTIONS = {
        "fix_cell", "delete_row", "mark_complete",
        "fill_missing", "standardize_column", "deduplicate",
    }

    STANDARDIZE_RULES = {
        "title_case", "upper_case", "lower_case",
        "strip_whitespace", "date_iso", "numeric_clean",
    }

    def __init__(self):
        self._state = DataCleanState()
        self._current