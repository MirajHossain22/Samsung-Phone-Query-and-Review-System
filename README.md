# Samsung Phone Query & Review System

Scrape Samsung specs from GSMArena → store them in PostgreSQL → answer questions with a RAG chatbot →
generate reviews with a two-agent pipeline → expose everything through a FastAPI service.

```
GSMArena ──scraper──▶ PostgreSQL ──▶ Retriever (entity detection + TF-IDF over spec chunks)
                                        │                     │
                                        ▼                     ▼
                                    Chatbot (RAG)      Multi-agent crew
                                        │            SpecRetrievalAgent → ReviewWriterAgent
                                        └──────────┬──────────┘
                                                FastAPI
```

## Quick start

### Windows PowerShell

Run these commands from the project directory. Python 3.11 and Docker Desktop
with its Linux engine running are required for this setup.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q

docker compose up -d
$env:DATABASE_URL = "postgresql://samsung:samsung@localhost:5433/samsung"
.\.venv\Scripts\python.exe -m samsung_assistant.scraper --limit 12 --delay 6
.\.venv\Scripts\python.exe -m uvicorn samsung_assistant.api:app --reload
```

Open http://localhost:8000/docs to exercise the API. Environment variables apply
only to the current terminal; set `DATABASE_URL` again in each new terminal.
The application does not automatically load `.env`. The default LLM backend is
`none`; configure a real model as described below for the assignment demonstration.

### Bash

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Database (PostgreSQL via Docker; skip to use SQLite automatically)
docker compose up -d
cp .env.example .env && export $(grep -v '^#' .env | xargs)

# 2) Data: scrape 12 Galaxy S21–S24 models from GSMArena (be polite: ~5 s between requests)
python -m samsung_assistant.scraper --limit 12 --delay 5
#    ...or, offline demo data (sample values, NOT scraped):  python -m samsung_assistant.seed

# 3) API  →  http://localhost:8000/docs
uvicorn samsung_assistant.api:app --reload

# 4) Tests
pytest -q
```

## Components

| Task | Where | Notes |
|---|---|---|
| Scraping | `scraper.py` | `requests` + BeautifulSoup. Walks the Samsung brand listing, parses every spec table, retries on HTTP 429 with back-off. |
| Database | `schema.sql`, `db.py`, `repository.py` | `phones`, `specifications` (raw sheet, one row per category/key), `key_specs` (parsed numbers for ranking), `prices`. PostgreSQL, SQLite fallback. |
| Chatbot (RAG) | `rag.py`, `chatbot.py`, `llm.py` | Detects phone names (`S23 Ultra` ≠ `S23`), retrieves the relevant spec chunks, then answers. Rankings/comparisons are computed in code from the DB; the LLM only phrases the answer. Open-source LLM via Ollama/HF, or OpenAI; works without any LLM. |
| Multi-agent | `agents.py` (default), `crew_adapter.py` (CrewAI) | Retrieval agent → review-writer agent; the API returns an execution trace. Pros/cons come from ranking the phone against the others in the DB. |
| API | `api.py` | `POST /chat`, `POST /review`, `GET /compare`, `GET /phones`, `GET /phones/{name}`, `GET /health`, `POST /admin/reload` |

## Example calls

```bash
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "Which Samsung phone has the best battery life?"}'
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "How does the Galaxy S23 compare to the S22 in terms of performance?"}'
curl -s localhost:8000/review -H 'content-type: application/json' -d '{"phone": "Galaxy S23 Ultra"}'
curl -s 'localhost:8000/compare?a=S23&b=S22&aspect=camera'
```

## Using a local open-source LLM

Install [Ollama](https://ollama.com/), then download and run a small instruct model:

```powershell
ollama pull qwen2.5:1.5b
$env:LLM_BACKEND = "openai"
$env:OPENAI_BASE_URL = "http://localhost:11434/v1"
$env:OPENAI_API_KEY = "ollama"
$env:LLM_MODEL = "qwen2.5:1.5b"
.\.venv\Scripts\python.exe -m uvicorn samsung_assistant.api:app --reload
```

Successful generated responses return `"llm_used": true`. If the model service is
unavailable, the chatbot returns its deterministic database-grounded answer and
sets `llm_used` to `false`.

## CrewAI workflow

The API's default review route uses the lightweight two-agent orchestrator in
`agents.py`. The same retrieval-agent → review-agent handoff can be demonstrated
with CrewAI and Ollama:

```powershell
.\.venv\Scripts\python.exe -m pip install "crewai[litellm]>=1.15,<2"
$env:DATABASE_URL = "postgresql://samsung:samsung@localhost:5433/samsung"
$env:CREWAI_MODEL = "ollama/qwen2.5:1.5b"
$env:CREWAI_BASE_URL = "http://localhost:11434"
.\.venv\Scripts\python.exe -m samsung_assistant.crew_adapter "Galaxy S23 Ultra"
```

## Design notes & limitations

- **Grounding over fluency:** the model is told to answer only from retrieved context; numeric answers
  (best battery, lightest, cheapest) are computed from the DB, and ties are reported (several Ultras share 5000 mAh).
- "Best battery life" is based on battery capacity (mAh); "best camera" on main-sensor megapixels. Both caveats are stated in the answer.
- Prices are values from each page's current `Misc → Price` row at scrape time; they may differ from launch and local retail prices.
- Retrieval is TF-IDF (no embeddings download needed); swapping in `sentence-transformers` would only change `rag.py`.
- GSMArena changes its markup and blocks heavy scraping; scrape once, keep the DB.
