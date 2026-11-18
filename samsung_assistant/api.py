"""FastAPI service.   uvicorn samsung_assistant.api:app --reload   ->   http://localhost:8000/docs"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from .agents import Orchestrator
from .chatbot import Chatbot
from .db import Database
from .llm import LLM
from .rag import Retriever
from .repository import PhoneRepository


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, examples=["What are the camera specs of the Samsung Galaxy S23?"])


class ReviewRequest(BaseModel):
    phone: str = Field(..., min_length=2, examples=["Samsung Galaxy S23 Ultra"])


def build_state(db: Database | None = None) -> dict:
    db = db or Database()
    db.init_schema()
    repo = PhoneRepository(db)
    retriever = Retriever(repo)
    llm = LLM()
    return {"db": db, "repo": repo, "retriever": retriever, "chatbot": Chatbot(retriever, llm),
            "crew": Orchestrator(repo, retriever, llm), "llm": llm}


def create_app(db: Database | None = None) -> FastAPI:
    state: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.update(build_state(db))
        try:
            yield
        finally:
            state["db"].close()

    app = FastAPI(title="Samsung Phone Query & Review System", version="1.0.0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def index():
        static_index = Path(__file__).parent / "static" / "index.html"
        if static_index.exists():
            html = static_index.read_text(encoding="utf-8")
            try:
                phones = state["repo"].list_phones()
                html = html.replace("__SERVER_PHONES_JSON__", json.dumps(phones))
            except Exception:
                html = html.replace("__SERVER_PHONES_JSON__", "[]")
            return HTMLResponse(content=html)
        return HTMLResponse(content="<h1>Samsung Phone Assistant API</h1><p>Visit <a href='/docs'>/docs</a></p>")

    @app.get("/bg.jpg")
    def background_image():
        bg_path = Path(__file__).parent / "static" / "bg.jpg"
        if bg_path.exists():
            return FileResponse(bg_path, media_type="image/jpeg")
        raise HTTPException(404, "Background not found")

    @app.get("/health")
    def health():
        return {"status": "ok", "phones_in_db": state["repo"].count(),
                "llm_backend": state["llm"].backend}

    @app.get("/phones")
    def phones():
        return state["repo"].list_phones()

    @app.get("/phones/{name}")
    def phone(name: str):
        p = state["repo"].get_phone(name)
        if not p:
            raise HTTPException(404, f"No phone matching '{name}'")
        return p

    @app.post("/chat")
    def chat(req: ChatRequest):
        """Ask anything: specs, 'which phone has the best battery', comparisons ..."""
        return state["chatbot"].answer(req.question)

    @app.get("/compare")
    def compare(a: str = Query(..., description="e.g. Galaxy S23"), b: str = Query(..., description="e.g. Galaxy S22"),
                aspect: str = Query("", description="optional: performance, camera, battery, display ...")):
        return state["chatbot"].answer(f"Compare {a} vs {b} {aspect}".strip())

    @app.post("/review")
    def review(req: ReviewRequest):
        """Multi-agent pipeline: retrieval agent -> review-writer agent (with execution trace)."""
        out = state["crew"].review(req.phone)
        if not out["found"]:
            raise HTTPException(404, f"No phone matching '{req.phone}'")
        return out

    @app.post("/admin/reload")
    def reload():
        """Rebuild the retrieval index after re-scraping."""
        state["retriever"].refresh()
        return {"phones_indexed": len(state["retriever"].phones)}

    return app


app = create_app()
