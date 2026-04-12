"""
FastAPI application for the Data Cleaning Environment.

Self-contained server implementing the OpenEnv HTTP API spec:
- POST /reset   -> Reset environment, returns initial observation
- POST /step    -> Execute action, returns observation
- GET  /state   -> Returns current state
- GET  /health  -> Health check

Compatible with openenv validate and OpenEnv clients.
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from data_cleaning_env.models import DataCleanAction, DataCleanObservation, DataCleanState
from data_cleaning_env.server.environment import DataCleanEnvironment

app = FastAPI(
    title="Data Cleaning Environment",
    description="A real-world OpenEnv environment for cleaning messy tabular data",
    version="0.1.0",
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


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "environment": "data_cleaning_env"}


@app.get("/")
async def root():
    """Root endpoint with environment info."""
    return {
        "name": "data_cleaning_env",
        "version": "0.1.0",
        "description": "A real-world data cleaning environment for OpenEnv",
        "tasks": [
            "easy_customer_contacts",
            "medium_product_inventory",
            "hard_sales_reconciliation",
        ],
        "endpoints": ["/health", "/reset", "/step", "/state", "/docs"],
    }


@app.post("/reset")
async def reset(request: Request):
    """Reset the environment with optional task_id.

    Request body (optional JSON):
        {"task_id": "easy_customer_contacts"}

    Available tasks:
        - easy_customer_contacts (default)
        - medium_product_inventory
        - hard_sales_reconciliation
    """
    # Parse body - handle both empty body and JSON
    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        body = {}

    task_id = body.get("task_id", "easy_customer_contacts")

    try:
        obs = env.reset(task_id=task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return obs.model_dump()


@app.post("/step")
async def step(action: DataCleanAction):
    """Execute an action on the environment.

    Request body:
        {"action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"}
        {"action_type": "delete_row", "row": 5}
        {"action_type": "mark_complete"}
    """
    try:
        obs = env.step(action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return obs.model_dump()


@app.get("/state")
async def state():
    """Get the current environment state."""
    return env.state.model_dump()


def main():
    """Main entry point for running the server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
