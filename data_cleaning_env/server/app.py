"""
FastAPI application for the Data Cleaning Environment.

Self-contained server implementing the OpenEnv HTTP API spec:
- POST /reset   -> Reset environment, returns initial observation
- POST /step    -> Execute action, returns observation
- GET  /state   -> Returns current state
- GET  /health  -> Health check
- GET  /info    -> Rich environment information
- GET  /tasks   -> List all available tasks with metadata
- GET  /metrics -> Usage statistics and performance metrics

Compatible with openenv validate and OpenEnv clients.

Meta PyTorch OpenEnv Hackathon submission.
"""

import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from data_cleaning_env.models import DataCleanAction, DataCleanObservation, DataCleanState
from data_cleaning_env.server.environment import DataCleanEnvironment
from data_cleaning_env.tasks import TASKS, get_task

# Application version
APP_VERSION = "1.0.0"

app = FastAPI(
    title="Data Cleaning Environment",
    description="A real-world OpenEnv environment for cleaning messy tabular data with reinforcement learning. Meta PyTorch OpenEnv Hackathon submission.",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS for HF Spaces and browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global environment instance (per-worker)
env = DataCleanEnvironment()

# Metrics tracking
class MetricsTracker:
    """Track HTTP metrics across the server lifetime."""
    def __init__(self):
        self.total_requests = 0
        self.total_response_time_ms = 0.0
        self.total_episodes = 0
        self.total_steps = 0
        self.episode_quality_scores = []
        self.request_counts_by_endpoint = {}

    def record_request(self, endpoint: str, response_time_ms: float):
        """Record a request to metrics."""
        self.total_requests += 1
        self.total_response_time_ms += response_time_ms
        if endpoint not in self.request_counts_by_endpoint:
            self.request_counts_by_endpoint[endpoint] = 0
        self.request_counts_by_endpoint[endpoint] += 1

    def record_episode_start(self):
        """Record a new episode."""
        self.total_episodes += 1

    def record_step(self):
        """Record a step taken."""
        self.total_steps += 1

    def record_episode_end(self, quality_score: float):
        """Record episode completion with quality score."""
        self.episode_quality_scores.append(quality_score)

    def get_average_response_time_ms(self) -> float:
        """Get average response time in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return round(self.total_response_time_ms / self.total_requests, 2)

    def get_average_quality_score(self) -> float:
        """Get average quality score across episodes."""
        if not self.episode_quality_scores:
            return 0.0
        return round(sum(self.episode_quality_scores) / len(self.episode_quality_scores), 4)

metrics = MetricsTracker()


# Middleware to track response times
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record metrics for each request."""
    start_time = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start_time) * 1000
    metrics.record_request(request.url.path, elapsed_ms)
    return response


@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint.

    Returns:
        dict: Status and environment information
    """
    return {
        "status": "healthy",
        "environment": "data_cleaning_env",
        "version": APP_VERSION,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with comprehensive environment information.

    Returns:
        dict: Overview of the environment, available tasks, and endpoints
    """
    return {
        "name": "data_cleaning_env",
        "version": APP_VERSION,
        "description": "A real-world data cleaning environment for OpenEnv. Designed for Meta PyTorch OpenEnv Hackathon.",
        "author": "Data Cleaning Environment Team",
        "tasks": list(TASKS.keys()),
        "task_count": len(TASKS),
        "endpoints": {
            "System": ["/health", "/docs", "/openapi.json"],
            "Core": ["/reset", "/step", "/state"],
            "Information": ["/info", "/tasks"],
            "Metrics": ["/metrics"],
        },
        "documentation": "/docs",
    }


@app.get("/info", tags=["Information"])
async def info():
    """Get rich environment information.

    Returns comprehensive details about the environment, reward structure,
    observation fields, and supported actions.

    Returns:
        dict: Environment metadata and specifications
    """
    return {
        "name": "Data Cleaning Environment",
        "version": APP_VERSION,
        "description": "An RL environment where agents learn to clean messy tabular data by fixing cell values and removing erroneous rows.",
        "environment_type": "Tabular Data Cleaning",
        "action_space": {
            "description": "Discrete action space with three action types",
            "actions": [
                {
                    "type": "fix_cell",
                    "description": "Update a cell value in the dataset",
                    "required_fields": ["row", "column", "value"],
                    "optional_fields": ["reason"],
                },
                {
                    "type": "delete_row",
                    "description": "Remove a row from the dataset",
                    "required_fields": ["row"],
                    "optional_fields": ["reason"],
                },
                {
                    "type": "mark_complete",
                    "description": "Signal that cleaning is complete and episode should end",
                    "required_fields": [],
                    "optional_fields": ["reason"],
                },
            ],
        },
        "observation_space": {
            "description": "Rich observation with tabular data and metadata",
            "fields": {
                "done": "Whether the episode has ended (boolean)",
                "reward": "Reward for the last action (float)",
                "data_snapshot": "Current data as CSV string",
                "columns": "List of column names",
                "num_rows": "Current number of rows",
                "issues_detected": "List of remaining data quality issues",
                "quality_score": "Data quality score from 0.0 to 1.0",
                "actions_taken": "Number of actions taken so far",
                "max_actions": "Maximum allowed actions per episode",
                "task_id": "Identifier of the current task",
                "task_description": "Human-readable description of the task",
                "message": "Detailed message about the last action",
                "data_profile": "Per-column statistics (nulls, uniques, types)",
                "cleaning_history": "List of recent successful actions",
                "issue_categories": "Count of issues by category",
                "difficulty": "Task difficulty level (easy/medium/hard)",
                "progress_pct": "Percentage of issues fixed (0-100)",
            },
        },
        "reward_structure": {
            "description": "Dense rewards for every action plus sparse final bonus",
            "components": [
                "Progress reward: proportional to quality improvement from initial state",
                "Step-level reward: quality improvement scaled by 0.5",
                "Failure penalty: diminishing penalty for repeated failed actions",
                "Streak bonus: bonus for consecutive quality improvements",
                "Final reward: weighted heavily on final quality at episode end",
                "Perfection bonus: +0.2 for achieving quality >= 0.99",
                "Efficiency bonus: reward for using fewer actions",
            ],
            "range": "[-0.2, 1.0] approximate (varies by efficiency)",
        },
        "task_count": len(TASKS),
        "available_tasks": list(TASKS.keys()),
        "features": [
            "Rich tabular observations with data profiling",
            "Issue categorization (formatting, missing values, duplicates, etc)",
            "Dense reward signal with progress tracking",
            "Multiple difficulty levels (easy, medium, hard)",
            "Per-column data statistics in observations",
            "Action history and cleaning progress tracking",
        ],
    }


@app.get("/tasks", tags=["Information"])
async def list_tasks():
    """Get all available tasks with metadata.

    Returns:
        dict: Comprehensive information about each available task including
              difficulty, description, number of rows, and cleaning objectives
    """
    tasks_info = {}
    for task_id, task_data in TASKS.items():
        tasks_info[task_id] = {
            "id": task_id,
            "description": task_data.get("description", ""),
            "difficulty": "easy" if "easy" in task_id else "medium" if "medium" in task_id else "hard",
            "num_rows": len(task_data.get("dirty_data", [])),
            "num_columns": len(task_data.get("columns", [])),
            "columns": task_data.get("columns", []),
            "max_actions": task_data.get("max_actions", 40),
            "issues": task_data.get("issues", []),
            "issue_count": len(task_data.get("issues", [])),
            "objectives": [
                "Fix data quality issues",
                "Maximize quality score",
                "Complete within action budget",
            ],
        }
    return {
        "total_tasks": len(tasks_info),
        "tasks": tasks_info,
    }


@app.get("/metrics", tags=["Metrics"])
async def get_metrics():
    """Get server metrics and usage statistics.

    Returns:
        dict: Aggregated metrics including request counts, response times,
              episode statistics, and quality scores
    """
    return {
        "server_metrics": {
            "total_requests": metrics.total_requests,
            "average_response_time_ms": metrics.get_average_response_time_ms(),
            "requests_by_endpoint": metrics.request_counts_by_endpoint,
        },
        "episode_metrics": {
            "total_episodes": metrics.total_episodes,
            "total_steps": metrics.total_steps,
            "average_steps_per_episode": (
                round(metrics.total_steps / metrics.total_episodes, 2)
                if metrics.total_episodes > 0
                else 0
            ),
        },
        "quality_metrics": {
            "average_quality_score": metrics.get_average_quality_score(),
            "episodes_completed": len(metrics.episode_quality_scores),
        },
        "version": APP_VERSION,
    }


@app.post("/reset", tags=["Core"])
async def reset(request: Request):
    """Reset the environment with optional task_id.

    Request body (optional JSON):
        {"task_id": "easy_customer_contacts"}

    Available tasks:
        - easy_customer_contacts (default) - Basic contact data cleaning
        - medium_product_inventory - More complex product inventory data
        - hard_sales_reconciliation - Advanced multi-table reconciliation

    Returns:
        DataCleanObservation: Initial observation with data snapshot and task details
    """
    # Parse body - handle both empty body and JSON
    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        body = {}

    task_id = body.get("task_id", "easy_customer_contacts")

    # Validate task_id
    if task_id not in TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{task_id}'. Available tasks: {list(TASKS.keys())}",
        )

    try:
        metrics.record_episode_start()
        obs = env.reset(task_id=task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Failed to reset environment: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    return obs.model_dump()


@app.post("/step", tags=["Core"])
async def step(action: DataCleanAction):
    """Execute an action on the environment.

    Request body examples:
        {"action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"}
        {"action_type": "delete_row", "row": 5}
        {"action_type": "mark_complete"}

    Valid action_type values:
        - fix_cell: Requires row, column, value
        - delete_row: Requires row
        - mark_complete: No additional parameters required

    Returns:
        DataCleanObservation: Updated observation with reward and new state

    Raises:
        HTTPException: 400 if action is invalid, 500 for server errors
    """
    try:
        # Validate action
        action_type = action.action_type.lower().strip()
        if action_type not in ["fix_cell", "delete_row", "mark_complete"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type '{action.action_type}'. Valid types: fix_cell, delete_row, mark_complete",
            )

        metrics.record_step()
        obs = env.step(action)

        # Track episode completion
        if obs.done:
            metrics.record_episode_end(obs.quality_score)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to execute action: {str(e)}",
        )

    return obs.model_dump()


@app.get("/state", tags=["Core"])
async def state():
    """Get the current environment state.

    Returns:
        DataCleanState: Current internal state including step count, quality history,
                       actions log, reward tracking, and issue counts
    """
    return env.state.model_dump()


def main():
    """Main entry point for running the server.

    Starts a production-ready uvicorn server serving the Data Cleaning
    Environment OpenEnv API with full documentation at /docs.
    """
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
