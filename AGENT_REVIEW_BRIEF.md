# Review brief for the VS Code agent

You are reviewing a finished-but-partly-unverified submission for the GTR "Python Software Intern" assignment
(Samsung Phone Query and Review System). Read this file first, then audit the code against the assignment.
**Do not rewrite the project; verify, run, and fix what is broken, and report findings.**
Deadline for the real submission: 19 Nov 2026, 12:00 PM (Dhaka time).

## 1. The assignment (summary of the PDF)

1. **Scrape** 10–15 Samsung phones from GSMArena (BeautifulSoup/Scrapy/Selenium): display, camera, battery, processor, etc. **Store in PostgreSQL/MySQL** (tables for phones, specifications, prices).
2. **Chatbot** using an open-source LLM or OpenAI with **RAG** over the DB. Must handle: "What are the camera specs of the Galaxy S23?", "Which Samsung phone has the best battery life?", "How does the S23 compare to the S22 in terms of performance?", "What is the screen size of the Galaxy S22?". Also pricing and comparisons.
3. **Multi-agent system** (CrewAI/AutoGen/LangChain): one agent retrieves specs from the DB, another writes a detailed review.
4. **API** (FastAPI/Flask) to ask questions and get accurate answers, handling multiple queries.
5. Submission: GitHub repo + 5–10 min Google Drive video + email to sd14@gtrbd.com.
Assessment: scraping accuracy/completeness/structure, chatbot relevance/accuracy, agent collaboration, API behaviour.

## 2. Project layout

```
samsung_assistant/
  schema.sql        PostgreSQL DDL (SQLite DDL derived at runtime)
  db.py             Database wrapper: PostgreSQL (psycopg2) if DATABASE_URL set, else SQLite; "?" placeholders
  normalize.py      raw spec strings -> numeric key specs + price parsing
  repository.py     upsert_phone / get_phone / list_phones / all_phones
  scraper.py        GSMArena scraper (requests + bs4 + lxml)
  seed.py           12-phone OFFLINE SAMPLE dataset (not scraped)
  rag.py            Retriever: phone-name detection + TF-IDF over per-category spec chunks
  llm.py            LLM client: none | openai-compatible (OpenAI/Ollama) | hf (transformers)
  chatbot.py        Intent routing: overview / lookup / rank / compare / list; deterministic fallback
  agents.py         SpecRetrievalAgent -> ReviewWriterAgent via Orchestrator (+ trace)
  crew_adapter.py   Same two agents in CrewAI (optional)
  api.py            FastAPI app
tests/              test_core.py, fixtures.py (mock GSMArena HTML)
README.md, requirements.txt, docker-compose.yml, .env.example, VIDEO_SCRIPT.md, SUBMISSION_EMAIL.md
```

## 3. Requirement checklist and status

Legend: ✅ implemented and tested in the authoring sandbox · ⚠️ implemented but NOT executed · ❌ not done

| # | Requirement | Where | Status |
|---|---|---|---|
| 1a | Scrape 10–15 Samsung phones from GSMArena | `scraper.py` | ⚠️ Parser tested only on a **mock** page (`tests/fixtures.py`). Never run against live GSMArena (no network in sandbox). CSS selectors come from memory of GSMArena markup. |
| 1b | Capture display, camera, battery, processor, other | `scraper.py`, `normalize.py` | ✅ on mock; ⚠️ on live pages |
| 1c | Structured DB (phones/specs/prices) | `schema.sql`, `repository.py` | ✅ on SQLite; ⚠️ PostgreSQL path (psycopg2, `RETURNING id`, `ON CONFLICT`) never run |
| 2a | RAG chatbot, answers the 4 sample questions | `rag.py`, `chatbot.py` | ✅ against the **seed** data, with no LLM (deterministic answers) |
| 2b | Open-source LLM / OpenAI integration | `llm.py` | ⚠️ Code path never executed (no LLM available); only the "none" fallback is tested |
| 3 | Multi-agent: retrieval agent + review agent | `agents.py` | ✅ custom 2-agent pipeline tested (no LLM). |
| 3b | Uses CrewAI/AutoGen/LangChain | `crew_adapter.py` | ⚠️ Not executed; `crewai` not installed. Note: the default path (`agents.py`) is a hand-rolled framework, so the CrewAI adapter is what satisfies the "use a framework" wording. |
| 4 | FastAPI endpoints | `api.py` | ⚠️ Compiles (`py_compile`); the TestClient test is **skipped** in the sandbox (fastapi/httpx missing). Never served. |
| 5 | GitHub repo, video, email | — | ❌ Left to the user (video script and email draft provided) |

Sandbox test result: `pytest -q` → 14 passed, 1 skipped (the API test).

## 4. Known limitations / design decisions (verify these are acceptable)

- "Best battery life" = battery capacity (mAh); "best camera" = main-sensor MP. The answer text states this caveat. Ties are reported.
- Prices are GSMArena launch prices from the `Misc → Price` row, not live retail prices. Some GSMArena pages show "About 400 EUR"-style text; `normalize.parse_prices` handles `$ € £ ₹` and `NNN EUR/USD/GBP/INR`.
- Retrieval is TF-IDF, not embeddings (no model download needed). The assignment says "RAG"; this satisfies retrieval-augmented answering but a reviewer may prefer embeddings. Possible upgrade: `sentence-transformers` in `rag.py` only.
- `chatbot.answer()` is stateless (no conversation memory).
- Rankings/comparisons are computed in code and the LLM only phrases them; this is deliberate to avoid hallucinated numbers.
- `seed.py` values were compiled from memory of public launch specs. **They must not be presented as scraped data.**

## 5. Tasks for you (in order)

1. **Environment:** create a venv, `pip install -r requirements.txt`, then `pytest -q`. Expect 15 passed (the API test should now run). Fix anything that fails.
2. **Static review:** read every file in `samsung_assistant/`. Look for bugs, edge cases (empty DB, unknown phone, queries naming 3+ phones, query with "+" or "plus"), SQL differences between SQLite and PostgreSQL, and thread-safety in `db.py`.
3. **PostgreSQL path:** `docker compose up -d`, set `DATABASE_URL` from `.env.example`, run `python -m samsung_assistant.seed`, then query with `psql` to confirm all four tables are populated. Fix any dialect error (especially `insert_returning_id` and the `ON CONFLICT` clauses).
4. **Live scraper (most important):** run `python -m samsung_assistant.scraper --limit 12 --delay 6`. Check: the brand listing is found, each of the 12 target names is matched (`DEFAULT_TARGETS`), spec categories are parsed, `key_specs` columns are non-NULL for display/chipset/RAM/camera/battery/weight, and prices parse. If GSMArena returns 429/403, increase `--delay` or use `--urls` with specific phone pages. If selectors are wrong, fix `parse_listing`, `parse_phone_page`, `next_listing_page` and update `tests/fixtures.py` to match the real markup. Then spot-check 3 phones' stored values against the actual GSMArena pages.
5. **Chatbot on real data:** re-ask the 4 sample questions plus extras (price, "compare S24 Ultra and S23 Ultra camera", "which phone has the most RAM", "tell me about the S22+") and confirm answers match the scraped values. Check that name detection still works with the real `phones.name` strings (e.g. GSMArena may name phones "Galaxy S23 FE", "Galaxy S23 5G" etc.).
6. **API:** `uvicorn samsung_assistant.api:app`, open `/docs`, exercise `/chat`, `/compare`, `/review`, `/phones`, `/phones/{name}`, `/health`; fire ~20 concurrent requests (e.g. a small `httpx`/`asyncio` script) to confirm "handling multiple queries" works without DB/thread errors.
7. **LLM path:** if Ollama is available (`LLM_BACKEND=openai`, `OPENAI_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=<model>`), confirm `llm_used: true` in `/chat` and `/review` and that answers stay grounded. Otherwise just confirm the fallback works when the endpoint is unreachable.
8. **CrewAI:** `pip install crewai`, run `python -m samsung_assistant.crew_adapter "Samsung Galaxy S23"`. Fix API mismatches with the installed version (the `@tool` import path and `LLM` configuration changed between versions). If it can't run, report clearly.
9. **Requirements audit:** go through section 1 line by line and mark each as met / partially met / not met with evidence (file and line, or command output).
10. **Docs:** make sure `README.md` commands actually work as written; correct anything that doesn't.

## 6. Output I want from you

A short report with: (a) test results, (b) a requirements table with evidence, (c) list of bugs found and fixed (file + what changed), (d) anything still unverified, (e) any risk a hiring reviewer would notice. Do not commit secrets. Keep changes minimal and re-run `pytest -q` after each fix.
