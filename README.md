# Autonomous Insurance Claims Processing Agent

A lightweight API that processes **FNOL (First Notice of Loss)** documents: it extracts key fields, detects missing or inconsistent data, and recommends a claim route (e.g. Fast-track, Manual review) with a short explanation.

Built for the Synapx assessment and aligned with **ACORD Automobile Loss Notice** structure.

---

## What it does

- **Accepts** PDF or TXT FNOL documents (upload or raw text).
- **Extracts** policy info, incident date/location/description, claimant, asset (e.g. vehicle, VIN, estimate).
- **Validates** mandatory fields and reports what’s missing.
- **Routes** the claim using fixed rules and returns a human-readable reason.

### Routing rules

| Condition | Route |
|-----------|--------|
| Any mandatory field missing | **Manual review** |
| Description contains "fraud", "inconsistent", or "staged" | **Investigation Flag** |
| Claim type = injury | **Specialist Queue** |
| Estimated damage < 25,000 | **Fast-track** |
| Otherwise | **Standard** |

### Response format (JSON)

```json
{
  "extractedFields": { ... },
  "missingFields": [ "policy_number", ... ],
  "recommendedRoute": "Fast-track",
  "reasoning": "Estimated damage (5000.0) is below threshold (25000.0); eligible for fast-track."
}
```

---

## How to run

**Prerequisites:** Python 3.10+

```bash
# Clone the repo and go into the project folder
cd autonomous-insurance-claims-agent

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser (you’ll be redirected to **http://localhost:8000/docs** for the API docs).

---

## How to use the API

- **Swagger UI:** http://localhost:8000/docs  
- **Health check:** `GET http://localhost:8000/health`  
- **Process a file (PDF or TXT):** `POST http://localhost:8000/api/v1/process` with form field `file`  
- **Process raw text:** `POST http://localhost:8000/api/v1/process/text` with JSON body `{"content": "your FNOL text here"}`  

**Example (curl):**

```bash
# Health
curl http://localhost:8000/health

# Process a sample file
curl -X POST http://localhost:8000/api/v1/process -F "file=@samples/fnol_sample_complete.txt"
```

---

## Run tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Project structure

```
autonomous-insurance-claims-agent/
├── src/
│   ├── main.py              # FastAPI app: /health, /api/v1/process, /api/v1/process/text
│   ├── config.py            # Settings (env)
│   ├── schemas.py            # Pydantic models and response shape
│   ├── extraction/
│   │   └── parser.py        # PDF/text → structured fields
│   └── routing/
│       └── engine.py        # Routing rules and reasoning
├── tests/                    # pytest: extraction, routing, API
├── samples/                  # Sample FNOL documents (TXT)
├── requirements.txt
├── pyproject.toml            # Project config, pytest options
├── .env.example              # Optional env vars (copy to .env)
└── README.md
```

---

## Configuration (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `FAST_TRACK_DAMAGE_THRESHOLD` | `25000` | Damage below this → Fast-track |
| `LOG_LEVEL` | `INFO` | Logging level |

Copy `.env.example` to `.env` and edit as needed.

---

