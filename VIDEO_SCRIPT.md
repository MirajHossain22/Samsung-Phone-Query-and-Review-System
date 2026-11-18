# 5–10 minute video outline (screen recording + voice)

**0:00 – Intro (30 s)** Problem: one place to query and review Samsung phones. Show the architecture diagram from the README.

**0:30 – Scraping (1.5 min)** Open `scraper.py`: listing page → phone page → spec tables (`th` = category, `td.ttl`/`td.nfo` = key/value, empty key = continuation row). Mention polite delay + retry on HTTP 429. Run the scraper live (or show the log of a finished run).

**2:00 – Database (1 min)** Show `schema.sql`; in psql run `SELECT name, battery_mah, chipset FROM phones JOIN key_specs ON id = phone_id;`. Explain raw `specifications` vs normalised `key_specs`.

**3:00 – Chatbot / RAG (2 min)** `rag.py`: name detection (`S23 Ultra` vs `S23`), spec chunks, TF-IDF. `chatbot.py`: intents (lookup, ranking, comparison). Demo the 3 sample questions. Point out: ranking is computed from the DB, ties are reported, unknown questions are refused rather than invented. Mention the pluggable LLM (Ollama/HF/OpenAI) and the `llm_used` flag.

**5:00 – Multi-agent (1.5 min)** `agents.py`: SpecRetrievalAgent → ReviewWriterAgent, data-driven pros/cons, the `trace` in the response. Mention `crew_adapter.py` for CrewAI.

**6:30 – API (1.5 min)** Open `/docs`; call `/chat`, `/compare`, `/review`; show a 404 for an unknown phone.

**8:00 – Tests, limitations, next steps (1 min)** `pytest`; limitations (battery = capacity in mAh, prices are GSMArena page values at scrape time, scraper depends on GSMArena markup); next steps (embeddings, conversation memory, price tracking).
