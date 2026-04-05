"""
HTTP Client for the Data Cleaning Environment.

Provides a simple sync client for interacting with the environment server.
"""

import requests

from data_cleaning_env.models import (
    DataCleanAction,
    DataCleanObservation,
    DataCleanState,
)


class DataCleanEnvClient:
    """HTTP client for the Data Cleaning Environment.

    Usage:
        client = DataCleanEnvClient("http://localhost:8000")
        obs = client.reset(task_id="easy_customer_contacts")
        obs = client.step(DataCleanAction(
            action_type="fix_cell", row=0, column="name", value="John Doe"
        ))
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict:
        """Check environment health."""
        resp = requests.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def reset(self, task_id: str = "easy_customer_contacts") -> DataCleanObservation:
        """Reset the environment with a task."""
        resp = requests.post(
            f"{self.base_url}/reset",
            json={"task_id": task_id},
            timeout=30,
        )
        resp.raise_for_status()
        return DataCleanObservation(**resp.json())

    def step(self, action: DataCleanAction) -> DataCleanObservation:
        """Execute a cleaning action."""
        resp = requests.post(
            f"{self.base_url}/step",
            json=action.model_dump(),
            timeout=30,
        )
        resp.raise_for_status()
        return DataCleanObservation(**resp.json())

    def state(self) -> DataCleanState:
        """Get current environment state."""
        resp = requests.get(f"{self.base_url}/state", timeout=10)
        resp.raise_for_status()
        return DataCleanState(**resp.json())
