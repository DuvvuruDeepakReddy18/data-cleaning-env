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

A production-ready OpenEnv environment where AI agents master the art of cleaning messy tabular datasets. Data scientists spend 60-80% of their time on data cleaning, yet it remains one of the least studied problems in ML. This environment provides a rich simulation with three difficulty levels, detailed quality feedback, and a reward structure designed for both evaluation and reinforcement learning.

## Key Features

- **Typed Actions**: Structured JSON actions (`fix_cell`, `delete_row`, `mark_complete`) with full validation
- **Cell-by-Cell Grading**: Quality scorer compares output against gold-standard clean data with intelligent row-matching
- **Partial Progress Rewards**: Every step generates signal; agents get immediate feedback on quality improvements
- **Data Profiling**: Observations include detailed issue detection showing exactly what's wrong
- **Issue Categorization**: Problems are broken down by type (formatting, missing values, logical errors, duplicates)
- **Difficulty Progression**: Easy (10 rows, 40 actions) → Medium (15 rows, 60 actions) → Hard (20 rows, 80 actions)

## Architecture

The environment operates as a multi-tier system for maximum modularity:

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent (Claude, GPT-4, Fine-tuned Model, etc.)                  │
│  Generates cleaning actions via LLM API                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │ JSON actions
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  inference.py                                                   │
│  - Parses LLM responses to structured actions                   │
│  - Manages conversation history (system prompt + recent msgs)   │
│  - Handles API retries with exponential backoff (rate limits)   │
│  - Tracks episode state and rewards                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP POST /step
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Server (data_cleaning_env/server/app.py)              │
│  - Routes: /reset, /step, /state, /health, /docs               │
│  - Request validation and error handling                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Action + State
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  DataCleanEnvironment (data_cleaning_env/server/environment.py) │
│  - Core simulation logic                                        │
│  - Action execution (fix_cell, delete_row)                      │
│  - Episode state management                                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
    ┌──────────────────┐    ┌────────────────────────────┐
    │ Dirty Dataset    │    │ Quality Scorer             │
    │ (current_data)   │    │ - Cell-by-cell comparison  │
    │                  │    │ - Best-match row alignment │
    │ 10-20 rows       │    │ - Penalty for deletions    │
    │ Multiple issues  │    │ - Produces reward signal   │
    └──────────────────┘    └────────────────────────────┘
              │                       │
              └───────────┬───────────┘
                          ▼
                  ┌──────────────────┐
                  │ Observation      │
                  │ (data_snapshot,  │
                  │  quality_score,  │
                  │  issues_detected,│
                  │  reward, etc.)   │
                  └──────────────────┘
```

## Action Space

All actions are JSON objects. The agent must respond with a single action per step.

| Action Type | Parameters | Required | Description |
|---|---|---|---|
| `fix_cell` | `row` (int), `column` (str), `value` (str) | Yes | Update a single cell value. Row indices are 0-based. |
| `delete_row` | `row` (int) | Yes | Remove a row from the dataset (for duplicates or unfixable rows). Subsequent rows shift down. |
| `mark_complete` | — | — | Signal that cleaning is finished. Triggers episode end and final scoring. |

Example actions:
```json
{"action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"}
{"action_type": "delete_row", "row": 5}
{"action_type": "mark_complete"}
```

## Observation Space

Observations returned after each step and on reset:

| Field | Type | Description |
|---|---|---|
| `data_snapshot` | str | CSV-formatted current dataset (with headers) |
| `columns` | List[str] | Column names in the dataset |
| `num_rows` | int | Current row count (changes when deleting) |
| `issues_detected` | List[str] | Remaining issues in human-readable form. Updated dynamically. |
| `quality_score` | float | Current quality (0.0-1.0). Cell-by-cell comparison against gold data. |
| `actions_taken` | int | Number of actions executed so far |
| `max_actions` | int | Action budget for this episode |
| `task_id` | str | Task identifier (easy_customer_contacts, medium_product_inventory, hard_sales_reconciliation) |
| `task_description` | str | Full task description and instructions |
| `message` | str | Feedback from the last action executed |
| `done` | bool | Whether episode has ended |
| `reward` | float | Cumulative reward for this step |

## Tasks

### Task 1: Easy — Customer Contact List
**10 rows, ~20 issues, 40 action budget**

Fix a customer contact list with formatting problems:
- **Whitespace**: Leading/trailing spaces in names
- **Capitalization**: Inconsistent name and city casing (should be Title Case)
- **Date formats**: Mixed formats (MM/DD/YYYY, 'Month D, YYYY', YYYY-MM-DD) — standardize to YYYY-MM-DD
- **Email validation**: Missing TLDs, double @@ symbols
- **Phone formatting**: Missing dashes, inconsistent separators
- **Geographic normalization**: City names to proper case

**Gold standard**: 10 rows, all fields properly formatted and consistent.

### Task 2: Medium — Product Inventory
**15 rows, ~17 issues, 60 action budget**

Clean a product inventory with semantic and type issues:
- **Category standardization**: Normalize to {Electronics, Stationery, Home & Office}. Handle abbreviations and case mismatches.
- **Price handling**: Remove currency symbols, convert text to numbers (e.g., "forty-five" → "45.00")
- **Stock validation**: Negative values → 0, missing values → 0
- **Weight units**: Strip unit suffixes (2500g → 2.5), ensure consistency in kg
- **Rating bounds**: Cap to 0.0-5.0 range. Handle missing ratings (→ 0.0) and out-of-range (→ 5.0 or 0.0 if negative)
- **Missing names**: Fill with "Unknown Product"

**Gold standard**: 15 rows, all fields valid and canonicalized.

### Task 3: Hard — Sales Record Reconciliation
**20 rows (with 2 duplicates), ~17+ issues, 80 action budget**

Reconcile complex sales records with logical consistency problems:
- **Duplicate detection & deletion**: Identify and delete duplicate order rows (same order_id with minor variations)
- **Arithmetic validation**: Verify total = quantity × unit_price. Fix totals if needed.
- **Date ordering**: ship_date must be ≥ order_date. Fix violations.
- **Inconsistent naming**: Standardize customer names (e.g., "ACME CORP" → "Acme Corp", trim whitespace)
- **Case standardization**: Product names should be Title Case
- **Status validation**: Standardize to {Shipped, Delivered, Pending, Cancelled}. Fix typos (Shpped → Shipped)
- **Missing order IDs**: Assign sequential IDs (ORD-011, etc.) to unassigned rows
- **Text-to-numeric**: Convert text prices (thirty → 30.00)
- **Negative values**: Take absolute value for quantities and totals

**Gold standard**: 18 rows (after deleting 2 duplicates), all records consistent and logically valid.

## Reward Function

The reward system provides immediate feedback (useful for RL) and final bonuses (useful for evaluation):

**Step Reward (0 to 0.5):**
```
progress = (current_quality - initial_quality) / (1.0 - initial_quality)
step_reward = progress × 0.5
```
Agents get immediate signal for moving in the right direction.

**Final Reward (when done=true, 0 to 1.0 cumulative):**
```
final_reward = (current_quality × 0.5) + perfect_bonus + efficiency_bonus
perfect_bonus = 0.2 if quality >= 0.99, else 0.0
efficiency_bonus = max(0, 1 - (actions_used / max_actions)) × 0.1
```

Examples:
- Task achieved 0.95 quality in 25 actions (max 60): `(0.95 × 0.5) + 0 + (1 - 0.42) × 0.1 = 0.535`
- Task achieved 0.99 quality in 30 actions (max 80): `(0.99 × 0.5) + 0.2 + (1 - 0.375) × 0.1 = 0.753`

**Streak Bonus (optional extension):**
Consecutive steps improving quality can trigger a small streak multiplier, encouraging focused, deliberate action sequences.

## Quality Scoring Algorithm

The quality scorer performs detailed cell-by-cell comparison:

1. **Row Matching**: For each row in the current dataset, find the best-matching row in clean data (maximizes matching cells)
2. **Cell Counting**: Count correct cells across all matched rows
3. **Penalization**:
   - Extra rows (current > clean): penalty = extra_row_count × num_columns × 0.5
   - Missing rows (clean > current): penalty = missing_row_count × num_columns × 0.5
4. **Score**: `quality = (correct_cells - penalty) / total_cells_in_clean_data`
5. **Clamping**: Score is clamped to [0.0, 1.0]

This approach handles deletions gracefully: if an agent deletes a duplicate, the penalty only applies for truly missing rows.

## Baseline Results

Tested with **Groq Llama 3.1 70B** (via Groq API) using the `inference.py` baseline:

| Task | Quality Score | Reward | Avg Steps | Time (s) |
|---|---|---|---|---|
| easy_customer_contacts | 0.92 | 0.71 | 18 | 8 |
| medium_product_inventory | 0.83 | 0.58 | 24 | 12 |
| hard_sales_reconciliation | 0.84 | 0.61 | 31 | 15 |
| **AVERAGE** | **0.87** | **0.63** | **24** | **12** |

Note: Scores vary with model, temperature, and LLM prompt engineering. These are reference points, not guarantees.

## Quick Start

### Local Setup

```bash
# Clone and install
git clone <repo-url>
cd data_cleaning_env_project/data_cleaning_env
pip install -r requirements.txt
pip install -e .

# Start the environment server (Terminal 1)
uvicorn data_cleaning_env.server.app:app --host 0.0.0.0 --port 8000

# Run the baseline (Terminal 2)
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="sk-..."
python inference.py

# Or run a specific task
python inference.py --task easy_customer_contacts
```

### Docker Setup

```bash
# Build image
docker build -t data-cleaning-env .

# Run environment server
docker run -p 8000:8000 data-cleaning-env

# From host, run inference
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="sk-..."
python inference.py --env-url http://localhost:8000
```

## API Reference

All requests/responses are JSON. The environment runs as a REST API server (FastAPI).

### Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{"status": "ok", "version": "1.0"}
```

### Reset Episode

```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy_customer_contacts"}'
```

**Request body:**
```json
{
  "task_id": "easy_customer_contacts"  // or medium_product_inventory, hard_sales_reconciliation
}
```

**Response:** Full observation object (see Observation Space)

### Execute Action

```bash
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "fix_cell", "row": 0, "column": "name", "value": "John Doe"}'
```

**Response:** Updated observation object

### Get Current State

```bash
curl http://localhost:8000/state
```

**Response:** Current observation (same as last /step or /reset response)

### Interactive Docs

```
http://localhost:8000/docs
```

Swagger UI with test interface for all endpoints.

## Environment Variables

Configure the agent via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_BASE_URL` | Yes | — | LLM API base URL (e.g., https://api.openai.com/v1) |
| `MODEL_NAME` | Yes | — | Model identifier (gpt-4o-mini, gpt-4, llama-3.1-70b, etc.) |
| `HF_TOKEN` | Yes | — | API key for the LLM service (also accepts OPENAI_API_KEY) |
| `ENV_URL` | No | http://localhost:8000 | Environment server URL |

## Project Structure

```
data_cleaning_env/
├── Dockerfile                         # Docker container definition
├── README.md                          # This file
├── inference.py                       # Baseline agent script (OpenAI client)
├── openenv.yaml                       # OpenEnv manifest
├── pyproject.toml                     # Python package metadata
├── requirements.txt                   # Dependencies
├── results.json                       # Output from baseline runs
└── data_cleaning_env/
    ├── __init__.py
    ├── models.py                      # Pydantic models (Action, Observation, State)
    ├── client.py                      # WebSocket/HTTP client utilities
    ├── tasks/
    │   ├── __init__.py
    │   └── task_definitions.py        # Task data (dirty/clean datasets, issues)
    └── server/
        ├── __init__.py
        ├── app.py                     # FastAPI server & routes
        ├── environment.py             # Core env logic (reset, step, scoring)
        └── __init__.py
```

## Design Decisions

### Why Three Difficulty Levels?
Progressive difficulty allows agents to demonstrate learning and enables curriculum-based training. Easy provides a sanity check; hard requires sophisticated multi-step reasoning.

### Why Cell-by-Cell Grading?
Unlike row-level accuracy, cell-level comparison encourages partial fixes and rewards incremental progress. An agent fixing 5 cells in a row gets credit even if other cells remain broken.

### Why Best-Match Row Alignment?
Real data may be reordered by agents (though this task doesn't require it). Best-match aligns rows semantically, avoiding penalizing correct data that's been rearranged.

### Why Immediate Step Rewards?
RL algorithms benefit from dense rewards. Step rewards let agents learn which actions help even mid-episode, improving training efficiency.

### Why Typed Actions?
JSON structure forces agents to think about action components separately: row, column, value. This reduces hallucination compared to free-form text actions.

### Why These Three Tasks?
Easy: Common formatting issues (whitespace, case, dates). Medium: Semantic consistency (categories, ranges, units). Hard: Logical coherence (arithmetic, temporal ordering, referential integrity). Together they span the data quality spectrum.

## Contributing

To add new tasks:
1. Create a new function `_task_custom()` in `data_cleaning_env/tasks/task_definitions.py`
2. Define `dirty_data`, `clean_data`, `columns`, `description`, `max_actions`, `issues`
3. Register in the `TASKS` dictionary
4. Update this README with task details

To improve agents:
1. Modify the `SYSTEM_PROMPT` in `inference.py` with better cleaning strategies
2. Experiment with message history length and conversation management
3. Try different models or fine-tune an existing one

## License

MIT License. See LICENSE file for details.

---

**Questions?** Open an issue or reach out. This environment is designed for research, education, and evaluation of LLM agents on a realistic, high-impact task.
