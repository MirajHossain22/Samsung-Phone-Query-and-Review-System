"""Multi-agent review pipeline.

  SpecRetrievalAgent  -- fetches the full spec sheet + peer context from the database
          |  (structured hand-off: SpecReport)
  ReviewWriterAgent   -- turns the specs into a detailed review (LLM if configured,
                         otherwise a data-driven template)
  Orchestrator        -- runs them in order and records a trace of what each agent did

Pros/cons are computed from the data by ranking the phone against the others in the
database, so the review is grounded even when no LLM is available. `crew_adapter.py`
exposes the same two agents through CrewAI.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .llm import LLM
from .rag import Retriever, short_name
from .repository import PhoneRepository

# (column, human label, unit, higher_is_better)
RANKED = [
    ("battery_mah", "battery capacity", "mAh", True),
    ("display_size_in", "display size", "in", True),
    ("main_camera_mp", "main camera resolution", "MP", True),
    ("ram_gb_max", "maximum RAM", "GB", True),
    ("storage_gb_max", "maximum storage", "GB", True),
    ("charging_w", "wired charging speed", "W", True),
    ("weight_g", "weight", "g", False),
]


@dataclass
class SpecReport:
    phone: dict
    peers: list[dict]
    notes: list[str] = field(default_factory=list)


class SpecRetrievalAgent:
    name = "SpecRetrievalAgent"
    role = "Fetch the complete, verified specification sheet for a phone from the database."

    def __init__(self, repo: PhoneRepository, retriever: Retriever):
        self.repo, self.retriever = repo, retriever

    def run(self, query: str) -> Optional[SpecReport]:
        matches = self.retriever.detect_phones(query) or []
        phone = matches[0] if matches else self.repo.get_phone(query)
        if phone is None:
            return None
        peers = [p for p in self.retriever.phones if p["id"] != phone["id"]]
        return SpecReport(phone=phone, peers=peers,
                          notes=[f"{len(phone['specs'])} spec categories, {len(peers)} peer phones for context"])


class ReviewWriterAgent:
    name = "ReviewWriterAgent"
    role = "Write a detailed, balanced product review from the retrieved specifications."

    SYSTEM = ("You are a smartphone reviewer. Write a detailed, balanced review using ONLY the facts supplied. "
              "Use sections: Overview, Display, Performance, Camera, Battery & Charging, Pros, Cons, Verdict. "
              "Do not invent benchmarks, prices or features that are not in the facts.")

    def __init__(self, llm: Optional[LLM] = None):
        self.llm = llm or LLM()

    # -- data-driven strengths / weaknesses ---------------------------------
    @staticmethod
    def strengths_weaknesses(report: SpecReport) -> tuple[list[str], list[str]]:
        pros, cons = [], []
        ks = report.phone["key_specs"]
        for col, label, unit, high_good in RANKED:
            v = ks.get(col)
            vals = [p["key_specs"].get(col) for p in report.peers if p["key_specs"].get(col) is not None]
            if v is None or not vals:
                continue
            beaten_by = sum(1 for x in vals if (x > v if high_good else x < v))   # peers strictly better
            beats = sum(1 for x in vals if (x < v if high_good else x > v))      # peers strictly worse
            n = len(vals)
            shown = f"{int(v) if float(v).is_integer() else v} {unit}"
            # ties count as top-tier / bottom-tier (several Ultras share 5000 mAh, for example)
            if beaten_by / n <= 0.1 and beats / n >= 0.5:
                pros.append(f"Top-tier {label} ({shown}) - beats {beats} of {n} other Galaxy models in the database")
            elif beats / n <= 0.1 and beaten_by / n >= 0.5:
                cons.append(f"Modest {label} ({shown}) - trails {beaten_by} of {n} other Galaxy models in the database")
        return pros, cons

    def run(self, report: SpecReport) -> dict:
        p, ks = report.phone, report.phone["key_specs"]
        pros, cons = self.strengths_weaknesses(report)
        price = next((x for x in p["prices"] if x["currency"] == "USD"), None)
        facts = "\n".join(
            f"[{cat}] " + "; ".join(f"{k}: {v}" for k, v in items.items()) for cat, items in p["specs"].items())
        facts += "\nData-driven strengths: " + (" | ".join(pros) or "none notable")
        facts += "\nData-driven weaknesses: " + (" | ".join(cons) or "none notable")

        generated = self.llm.generate(self.SYSTEM, f"PHONE: {p['name']}\nFACTS:\n{facts}\n\nWrite the review.", 900)
        if generated:
            return {"review": generated, "pros": pros, "cons": cons, "llm_used": True}

        def line(label, val, unit=""):
            return f"{label}: {val} {unit}".strip() if val is not None else None

        sections = [
            f"# {p['name']} - Review",
            "## Overview",
            f"Announced {p.get('announced') or 'n/a'}"
            + (f"; GSMArena listed price: ${price['amount']:.2f}." if price else "."),
            "## Display",
            f"A {ks.get('display_size_in')}-inch {ks.get('display_type')} panel at {ks.get('resolution')} "
            f"with a {ks.get('refresh_rate_hz')} Hz refresh rate.",
            "## Performance",
            f"Powered by {ks.get('chipset')}, with up to {ks.get('ram_gb_max')} GB RAM and up to "
            f"{ks.get('storage_gb_max')} GB storage. Ships with {ks.get('os')}.",
            "## Camera",
            f"Rear setup: {ks.get('camera_summary')}. "
            + (p["specs"].get("Selfie camera") and "Selfie: " + "; ".join(p["specs"]["Selfie camera"].values()) + "." or ""),
            "## Battery & Charging",
            f"{ks.get('battery_mah') or 'Unknown'} mAh battery with "
            f"{ks.get('charging_w') or 'unknown'} W wired charging; "
            + (f"weighs {ks['weight_g']:g} g." if ks.get("weight_g") is not None else "weight is not listed."),
            "## Pros", *[f"- {x}" for x in (pros or ["Balanced spec sheet with no standout extremes in this lineup"])],
            "## Cons", *[f"- {x}" for x in (cons or ["No clear weaknesses relative to the other models in the database"])],
            "## Verdict",
            f"The {short_name(p['name'])} " + (
                "excels in " + ", ".join(x.split(" (")[0].replace("Top-tier ", "") for x in pros[:3]) + ". "
                if pros else "is a well-rounded option. ")
            + ("Trade-offs: " + ", ".join(x.split(" (")[0].replace("Modest ", "") for x in cons[:3]) + "." if cons else ""),
        ]
        return {"review": "\n".join(s for s in sections if s), "pros": pros, "cons": cons, "llm_used": False}


class Orchestrator:
    """Sequential crew: retrieval agent -> writer agent, with an execution trace."""

    def __init__(self, repo: PhoneRepository, retriever: Retriever, llm: Optional[LLM] = None):
        self.retrieval = SpecRetrievalAgent(repo, retriever)
        self.writer = ReviewWriterAgent(llm)

    def review(self, phone_query: str) -> dict:
        trace = []
        t0 = time.perf_counter()
        report = self.retrieval.run(phone_query)
        trace.append({"agent": self.retrieval.name, "task": f"fetch specs for '{phone_query}'",
                      "result": "not found" if report is None else "; ".join(report.notes),
                      "ms": round((time.perf_counter() - t0) * 1000, 1)})
        if report is None:
            return {"found": False, "phone": None, "review": None, "trace": trace}
        t1 = time.perf_counter()
        out = self.writer.run(report)
        trace.append({"agent": self.writer.name, "task": "write review from specs",
                      "result": f"{len(out['pros'])} pros, {len(out['cons'])} cons, llm_used={out['llm_used']}",
                      "ms": round((time.perf_counter() - t1) * 1000, 1)})
        return {"found": True, "phone": report.phone["name"], **out, "trace": trace}
