"""Retrieval layer for RAG: turns database rows into text chunks and retrieves the best ones.

Two retrieval signals are combined:
  1. Entity detection - which phone(s) does the question mention? (exact, structured)
  2. TF-IDF similarity between the question and per-category spec chunks (semantic-ish).
Everything is read live from the database, so re-scraping updates the chatbot immediately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .repository import PhoneRepository

# Words in a question -> spec categories most likely to hold the answer.
CATEGORY_HINTS = {
    "Display": ["screen", "display", "size", "inch", "resolution", "refresh", "amoled", "brightness", "hz"],
    "Main Camera": ["camera", "photo", "megapixel", "mp", "zoom", "lens", "video", "rear"],
    "Selfie camera": ["camera", "selfie", "front camera", "front-facing"],
    "Battery": ["battery", "mah", "charging", "charge", "wireless", "endurance"],
    "Platform": ["processor", "chipset", "cpu", "gpu", "performance", "speed", "snapdragon", "exynos", "os",
                 "android", "software", "update", "one ui"],
    "Memory": ["ram", "memory", "storage", "gb", "performance"],
    "Body": ["weight", "heavy", "light", "dimension", "build", "thick"],
    "Misc": ["price", "cost", "cheap", "expensive", "colors", "model", "much"],
    "Launch": ["release", "announced", "launch", "date", "year"],
}


@dataclass
class Chunk:
    phone: str
    category: str
    text: str


def short_name(full: str) -> str:
    return re.sub(r"^samsung\s+galaxy\s+", "", full, flags=re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("+", " plus ")).strip()


def phone_aliases(full: str) -> list[str]:
    """Names users may type for a stored GSMArena model."""
    short = short_name(full)
    without_5g = re.sub(r"\s+5g$", "", short, flags=re.I)
    return list(dict.fromkeys([_norm(short), _norm(without_5g)]))


class Retriever:
    def __init__(self, repo: PhoneRepository):
        self.repo = repo
        self.refresh()

    def refresh(self) -> None:
        self.phones = self.repo.all_phones()
        self.by_name = {p["name"]: p for p in self.phones}
        self.chunks: list[Chunk] = []
        for p in self.phones:
            for cat, items in p["specs"].items():
                body = "; ".join(f"{k}: {v}" for k, v in items.items())
                self.chunks.append(Chunk(p["name"], cat, f"{p['name']} - {cat} - {body}"))
        self._vec = None
        if self.chunks:
            self._vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
            self._matrix = self._vec.fit_transform([c.text for c in self.chunks])

    # ------------------------------------------------------------ entities
    def detect_phones(self, query: str) -> list[dict]:
        """Find phones named in the query. 'S23 Ultra' must not also match 'S23'."""
        q = f" {_norm(query)} "
        names = sorted(self.phones, key=lambda p: -max(map(len, phone_aliases(p["name"]))))
        found: list[tuple[int, dict]] = []
        for p in names:
            matches = [
                match for alias in phone_aliases(p["name"])
                if (match := re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", q))
            ]
            m = min(matches, key=lambda match: match.start()) if matches else None
            if m:
                found.append((m.start(), p))
                q = q[: m.start()] + " " * (m.end() - m.start()) + q[m.end():]  # consume the span
        return [p for _, p in sorted(found, key=lambda t: t[0])]

    @staticmethod
    def model_mentions(query: str) -> list[str]:
        """Return explicit Galaxy S-series model tokens, preserving query order."""
        pattern = r"(?<![\w])(?:samsung\s+)?(?:galaxy\s+)?(s\d{1,2}(?:\s*(?:\+|plus|ultra|fe))?(?:\s*5g)?)(?![\w])"
        return [_norm(match.group(1)) for match in re.finditer(pattern, query, re.I)]

    def unknown_model_mentions(self, query: str, phones: list[dict]) -> list[str]:
        known = {alias for phone in phones for alias in phone_aliases(phone["name"])}
        return [mention for mention in self.model_mentions(query) if mention not in known]

    # ------------------------------------------------------------ retrieval
    def categories_for(self, query: str) -> list[str]:
        q = _norm(query)
        words = set(re.findall(r"[\w-]+", q))
        hits = [c for c, kws in CATEGORY_HINTS.items()
                if any((kw in words) or (" " in kw and kw in q) for kw in kws)]
        return hits

    def retrieve(self, query: str, phones: list[dict] | None = None, k: int = 6) -> list[Chunk]:
        if not self.chunks:
            return []
        phones = phones if phones is not None else self.detect_phones(query)
        wanted_names = {p["name"] for p in phones}
        cats = self.categories_for(query)
        scores = cosine_similarity(self._vec.transform([query]), self._matrix)[0]
        ranked = []
        for i, c in enumerate(self.chunks):
            if wanted_names and c.phone not in wanted_names:
                continue
            if wanted_names and cats and c.category not in cats:
                continue  # a specific phone + a specific topic: only return that topic's chunks
            boost = 0.5 if c.category in cats else 0.0
            ranked.append((scores[i] + boost, i))
        ranked.sort(reverse=True)
        top = [self.chunks[i] for s, i in ranked[:k] if s > 0]
        if wanted_names and cats:  # stable, readable order: by phone, then spec category
            order = list(CATEGORY_HINTS)
            top.sort(key=lambda c: (c.phone, order.index(c.category) if c.category in order else 99))
        return top
