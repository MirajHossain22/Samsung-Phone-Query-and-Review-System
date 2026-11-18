"""RAG chatbot: routes a question (spec lookup / ranking / comparison), retrieves facts from
the database, and answers with an LLM if configured - otherwise from the facts directly.

Design choice: numbers for rankings and comparisons are computed in code from the database,
not by the LLM, so they are exact. The LLM only phrases the answer from supplied context.
"""
from __future__ import annotations

import re
from typing import Optional

from .llm import LLM
from .rag import Retriever, short_name

SYSTEM_PROMPT = (
    "You are a Samsung smartphone assistant. Answer ONLY using the CONTEXT provided, which comes from a "
    "specification database. If the context does not contain the answer, say you don't have that data. "
    "Be concise and accurate, quote units, and never invent specifications or prices."
)

# keyword -> (key_specs column, label, unit, default direction: True = higher is better)
METRICS = [
    (r"battery|mah|endurance", "battery_mah", "battery capacity", "mAh", True),
    (r"charging|charge", "charging_w", "wired charging speed", "W", True),
    (r"camera|megapixel|\bmp\b|photo", "main_camera_mp", "main camera resolution", "MP", True),
    (r"screen|display|\bsize\b|biggest screen", "display_size_in", "display size", "inches", True),
    (r"\bram\b|memory", "ram_gb_max", "maximum RAM", "GB", True),
    (r"storage", "storage_gb_max", "maximum storage", "GB", True),
    (r"weight|heavy|light", "weight_g", "weight", "g", True),
    (r"price|cost|cheap|expensive|afford", "price_usd", "GSMArena listed price", "USD", False),
]
_LOW = r"\b(cheapest|lightest|smallest|lowest|least|cheaper|lighter|smaller|affordable|best value)\b"
_SUPERLATIVE = r"\b(best|highest|largest|biggest|most|longest|greatest|top|lightest|cheapest|smallest|lowest|" \
               r"least|heaviest|fastest|better|bigger)\b"

# which comparison rows to show for which category hint
ROWS = {
    "Display": [("display_size_in", "Display size", "in"), ("display_type", "Panel", ""),
                ("resolution", "Resolution", ""), ("refresh_rate_hz", "Refresh rate", "Hz")],
    "Main Camera": [("camera_summary", "Rear cameras", "")],
    "Battery": [("battery_mah", "Battery", "mAh"), ("charging_w", "Wired charging", "W")],
    "Platform": [("chipset", "Chipset", ""), ("os", "OS at launch", "")],
    "Memory": [("ram_gb_max", "Max RAM", "GB"), ("storage_gb_max", "Max storage", "GB")],
    "Body": [("weight_g", "Weight", "g")],
    "Misc": [("price_usd", "GSMArena listed price", "USD")],
}
ORDER = ["Display", "Platform", "Memory", "Main Camera", "Battery", "Body", "Misc"]


def _price_usd(phone: dict) -> Optional[float]:
    for p in phone["prices"]:
        if p["currency"] == "USD":
            return p["amount"]
    return None


def _value(phone: dict, col: str):
    return _price_usd(phone) if col == "price_usd" else phone["key_specs"].get(col)


def _fmt(v, unit: str) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v} {unit}".strip()


class Chatbot:
    def __init__(self, retriever: Retriever, llm: Optional[LLM] = None):
        self.retriever = retriever
        self.llm = llm or LLM()

    # ------------------------------------------------------------------ API
    def answer(self, query: str) -> dict:
        query = query.strip()
        if not self.retriever.phones:
            return self._result(query, "none", [], "The database is empty. Run the scraper (or the seed script) first.", [])
        phones = self.retriever.detect_phones(query)
        q = query.lower()
        unknown = self.retriever.unknown_model_mentions(query, phones)
        if unknown:
            shown = ", ".join(x.upper().replace(" PLUS", "+") for x in unknown)
            answer = f"I don't have scraped data for: {shown}. Use /phones to see the available models."
            return self._result(query, "unknown_model", phones, answer, [])

        if re.search(r"\b(list|which|what)\b.*\b(phones|models)\b.*\b(have|available|know|database)\b", q) \
                and not phones and not self._metric(q):
            names = [p["name"] for p in self.retriever.phones]
            return self._result(query, "list", [], "I have data for: " + ", ".join(names) + ".", [])

        if len(phones) >= 2 or (re.search(r"\b(compare|versus|vs\.?|difference|better than)\b", q) and phones):
            if len(phones) >= 2:
                return self._compare(query, phones)
        metric = self._metric(q)
        if metric and re.search(_SUPERLATIVE, q) and not phones:
            return self._rank(query, metric)
        return self._lookup(query, phones)

    # ------------------------------------------------------------- handlers
    def _overview(self, query: str, phones: list[dict]) -> dict:
        lines = []
        for p in phones:
            lines.append(f"{p['name']} ({p.get('announced') or 'n/a'}):")
            for cat in ORDER:
                for col, label, unit in ROWS[cat]:
                    v = _value(p, col)
                    if v is not None:
                        lines.append(f"- {label}: {_fmt(v, unit)}")
        context = "\n".join(lines)
        return self._finish(query, "overview", phones, context, context, [])

    def _lookup(self, query: str, phones: list[dict]) -> dict:
        if phones and not self.retriever.categories_for(query):
            return self._overview(query, phones[:2])
        chunks = self.retriever.retrieve(query, phones, k=4 if phones else 5)
        if not chunks:
            return self._result(query, "lookup", phones, "I couldn't find anything relevant in the database. "
                                "Try naming a model, e.g. \"Galaxy S23 Ultra\".", [])
        context = "\n".join(c.text for c in chunks)
        fallback = "\n".join(f"- {c.text.replace(' - ', ': ', 1).replace(' - ', ' - ')}" for c in chunks)
        return self._finish(query, "lookup", phones, context, fallback, chunks)

    def _rank(self, query: str, metric: tuple) -> dict:
        _, col, label, unit, _default_high = metric
        want_low = bool(re.search(_LOW, query.lower())) or col == "price_usd"
        want_low = want_low and not re.search(r"\b(most expensive|priciest|highest price)\b", query.lower())
        if col == "weight_g":
            want_low = bool(re.search(r"light|lightest|least", query.lower())) and not re.search(r"heav", query.lower())
        rows = [(p, _value(p, col)) for p in self.retriever.phones]
        rows = [(p, v) for p, v in rows if v is not None]
        if not rows:
            return self._result(query, "rank", [], f"I have no {label} data yet.", [])
        rows.sort(key=lambda t: t[1], reverse=not want_low)
        best = rows[0][1]
        winners = [p for p, v in rows if v == best]
        later = []
        for p, v in rows:
            if v != best and len(later) < 3:
                later.append(f"{short_name(p['name'])} ({_fmt(v, unit)})")
        direction = "lowest" if want_low else "highest"
        text = (f"By {label}, the {direction} is {_fmt(best, unit)}: "
                + ", ".join(short_name(p["name"]) for p in winners)
                + (" (tie)" if len(winners) > 1 else "") + ".")
        if later:
            text += " Next: " + ", ".join(later) + "."
        if col == "battery_mah":
            text += " (Capacity in mAh; real-world battery life also depends on chipset and display.)"
        if col == "main_camera_mp":
            text += " (Megapixels are not the whole story - lenses, zoom and processing matter too.)"
        context = f"Ranking by {label} ({direction} first):\n" + "\n".join(
            f"{p['name']}: {_fmt(v, unit)}" for p, v in rows)
        return self._finish(query, "rank", winners, context, text, [])

    def _compare(self, query: str, phones: list[dict]) -> dict:
        phones = phones[:3]
        cats = [c for c in self.retriever.categories_for(query) if c in ROWS] or ORDER
        if "performance" in query.lower():
            cats = ["Platform", "Memory"]
        lines = []
        for cat in [c for c in ORDER if c in cats]:
            for col, label, unit in ROWS[cat]:
                vals = [_value(p, col) for p in phones]
                if all(v is None for v in vals):
                    continue
                cells = " | ".join(f"{short_name(p['name'])}: {_fmt(v, unit)}" for p, v in zip(phones, vals))
                note = ""
                nums = [v for v in vals if isinstance(v, (int, float))]
                if len(nums) == len(vals) and len(set(nums)) > 1 and col not in ("price_usd", "weight_g"):
                    top = max(range(len(vals)), key=lambda i: vals[i])
                    note = f"  -> higher: {short_name(phones[top]['name'])}"
                lines.append(f"{label}: {cells}{note}")
        context = f"Comparison of {', '.join(p['name'] for p in phones)}:\n" + "\n".join(lines)
        fallback = f"Comparison of {', '.join(short_name(p['name']) for p in phones)}\n" + "\n".join(f"- {l}" for l in lines)
        return self._finish(query, "compare", phones, context, fallback, [])

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _metric(q: str):
        for m in METRICS:
            if re.search(m[0], q):
                return m
        return None

    def _finish(self, query, intent, phones, context, fallback, chunks) -> dict:
        generated = self.llm.generate(SYSTEM_PROMPT, f"CONTEXT:\n{context}\n\nQUESTION: {query}\n\nANSWER:")
        return self._result(query, intent, phones, generated or fallback, context.splitlines(),
                            llm_used=generated is not None)

    @staticmethod
    def _result(query, intent, phones, answer, context, llm_used=False) -> dict:
        return {
            "question": query, "intent": intent, "answer": answer,
            "phones": [p["name"] for p in phones], "context": context, "llm_used": llm_used,
        }
