"""
Root-level server entry point for OpenEnv validation.

Re-exports the FastAPI app from the data_cleaning_env package.
This file exists at server/app.py as required by the OpenEnv spec.
"""

from data_cleaning_env.server.app import app


def main():
    """Main entry point for running the server."""
    import uvicorn
    uvicorn.run(
        "data_cleaning_env.server.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
