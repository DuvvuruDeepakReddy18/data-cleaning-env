---
title: Data Cleaning Environment
emoji: 🧹
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
tags:
  - openenv
---

# Data Cleaning Environment

A real-world OpenEnv environment where AI agents learn to clean messy tabular datasets. Data cleaning is one of the most time-consuming tasks in data science — this environment lets agents practice fixing formatting errors, handling missing values, resolving duplicates, and reconciling logical inconsistencies.

## Why Data Cleaning?

Data scientists spend 60-80% of their time cleaning data. This environment simulates that real-world task with progressively harder challenges, providing rich partial-credit reward signals that make it suitable for both evaluation and reinforcement learning training.

## Action Space

Actions are JSON objects with the following structure:

| Action Type | Parameters | Description |
|---|---|---|
| `fix_cell` | `row` (int), `column` (str), `value` (str) | Update a single cell value |
| `delete_row` | `row` (int) | Remove a row (for duplicates) |
| `mark_complete` | — | Signal that cleaning is done |

Example:
```json
{"action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"}
```

## Observation Space

Each observation includes:

| Field | Type | Description |
|---|---|---|
| `data_snapshot` | str | CSV-formatted current dataset |
| `columns` | List[str] | Column names |
| `num_rows` | int | Row count |
| `issues_detected` | List[str] | Remaining issues description |
| `quality_score` | float | Current quality (0.0-1.0) |
| `actions_taken` | int | Actions used so far |
| `max_actions` | int | Action budget |
| `task_id` | str | Current task name |
| `task_description` | str | Full task instructions |
| `message` | str | Feedback from last action |
| `done` | bool | Whether episode ended |
| `reward` | float | Current reward signal |

## Tasks

### Task 1: Easy — Customer Contact List
**10 rows, ~20 issues, 40 action budget**

Fix a customer contact list with formatting problems: inconsistent name capitalization, extra whitespace, non-standard date formats (standardize to YYYY-MM-DD), malformed emails, and city name casing.

### Task 2: Medium — Product Inventory
**15 rows, ~17 issues, 60 action budget**

Clean a product inventory with: inconsistent category names, prices as text or with currency symbols, negative/missing stock values, weight values with unit suffixes, ratings outside valid range, and missing product names.

### Task 3: Hard — Sales Record Reconciliation
**20 rows, ~17 issues + duplicates, 80 action budget**

Reconcile sales records with complex problems: duplicate orders to delete, arithmetic inconsistencies (total ≠ quantity × price), date ordering violations (ship before order), inconsistent customer/product names, missing order IDs, misspelled status values, and cross-field validation failures.

## Reward Function

The reward provides meaningful signal throughout the episode:

- **Step reward (0-0.5)**: Proportional to quality improvement from initial state
- **Final reward (0-0.5)**: Based on final data quality score
- **Perfect bonus (+0.2)**: For achieving ≥99% quality
- **Efficiency bonus (0-0.1)**: For using fewer actions

Quality score is computed by cell-by-cell comparison against the gold-standard clean dataset, with penalties for extra/missing rows.

## Setup & Usage

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e .

# Start the environment server
uvicorn data_cleaning_env.server.app:app --host 0.0.0.0 --port 8000

# In another terminal, run the baseline
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="your-api-key"
python inference.py
```

### Run with Docker

```bash
docker build -t data-cleaning-env .
docker run -p 8000:8000 data-cleaning-env

# Then run inference
python inference.py --env-url http://localhost:8000
```

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/reset` | POST | Reset environment (pass `{"task_id": "..."}`) |
| `/step` | POST | Execute an action |
| `/state` | GET | Get current state |
| `/docs` | GET | Interactive API docs |

## Baseline Scores

Tested with `gpt-4o-mini`:

| Task | Quality Score | Reward | Steps |
|---|---|---|---|
| easy_customer_contacts | ~0.85 | ~0.70 | ~18 |
| medium_product_inventory | ~0.75 | ~0.55 | ~25 |
| hard_sales_reconciliation | ~0.60 | ~0.40 | ~35 |

## Environment Variables

| Variable | Description |
|---|---|
| `API_BASE_URL` | LLM API endpoint |
| `MODEL_NAME` | Model identifier |
| `HF_TOKEN` | API key (also accepts `OPENAI_API_KEY`) |

## Project Structure

```
├── Dockerfile              # Container definition
├── README.md               # This file
├── inference.py            # Baseline inference script
├── openenv.yaml            # OpenEnv manifest
├── pyproject.toml          # Package metadata
├── requirements.txt        # Dependencies
└── data_cleaning_env/
    ├── __init__.py
    ├── models.py           # Action, Observation, State types
    ├── client.py           # WebSocket/HTTP client
    ├── tasks/
    │   ├── __init__.py
    │   └── task_definitions.py  # Task data & graders
    └── server/
        ├── __init__.py
        ├── environment.py  # Core environment logic
        └── app.py          # FastAPI server
```
