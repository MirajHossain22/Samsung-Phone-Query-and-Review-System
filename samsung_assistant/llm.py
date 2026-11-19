"""Pluggable LLM client. Configure with environment variables:

LLM_BACKEND = none (default) | openai | gemini | hf
  gemini : Google Gemini API (free tier). Set GEMINI_API_KEY or GOOGLE_API_KEY.
             LLM_MODEL (default gemini-3.1-flash-lite)
  openai : any OpenAI-compatible /chat/completions endpoint - OpenAI itself, or an
           open-source model served locally by Ollama / vLLM / LM Studio.
             OPENAI_BASE_URL (default https://api.openai.com/v1; Ollama: http://localhost:11434/v1)
             OPENAI_API_KEY  (any string for Ollama)
             LLM_MODEL       (e.g. gpt-4o-mini, or llama3.1:8b for Ollama)
  hf     : local Hugging Face transformers pipeline (open-source model, needs `pip install transformers torch`)
             HF_MODEL        (default Qwen/Qwen2.5-1.5B-Instruct)

With `none`, the system still works: answers are composed deterministically from the
retrieved database facts (no hallucination), which is also the fallback if an LLM call fails.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

log = logging.getLogger("llm")


class LLM:
    def __init__(self, backend: Optional[str] = None):
        self.backend = (backend or os.getenv("LLM_BACKEND", "none")).lower()
        self._hf_pipe = None

    @property
    def enabled(self) -> bool:
        return self.backend in ("openai", "hf", "gemini", "google")

    @property
    def model(self) -> str:
        if self.backend in ("gemini", "google"):
            return os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
        if self.backend == "openai":
            return os.getenv("LLM_MODEL", "gpt-4o-mini")
        if self.backend == "hf":
            return os.getenv("HF_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
        return "deterministic"

    def generate(self, system: str, user: str, max_tokens: int = 500) -> Optional[str]:
        """Return generated text, or None if disabled / failed (caller falls back)."""
        if not self.enabled:
            return None
        try:
            if self.backend in ("gemini", "google"):
                return self._gemini(system, user, max_tokens)
            if self.backend == "openai":
                return self._openai(system, user, max_tokens)
            return self._hf(system, user, max_tokens)
        except Exception as exc:
            log.warning("LLM call failed (%s); using deterministic fallback", exc)
            return None

    def _gemini(self, system: str, user: str, max_tokens: int) -> str:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _openai(self, system: str, user: str, max_tokens: int) -> str:
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', 'none')}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _hf(self, system: str, user: str, max_tokens: int) -> str:
        if self._hf_pipe is None:
            from transformers import pipeline  # heavy import, only when requested

            self._hf_pipe = pipeline("text-generation", model=os.getenv("HF_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"))
        out = self._hf_pipe(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_new_tokens=max_tokens, do_sample=False,
        )
        return out[0]["generated_text"][-1]["content"].strip()
