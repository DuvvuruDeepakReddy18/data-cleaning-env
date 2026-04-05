"""
Root-level server entry point for OpenEnv validation.

Re-exports the FastAPI app from the data_cleaning_env package.
This file exists at server/app.py as required by the OpenEnv spec.
"""

from data_cleaning_env.server.app import app, main

if __name__ == "__main__":
    main()
