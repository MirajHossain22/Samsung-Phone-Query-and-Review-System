"""OPTIONAL: the same two-agent workflow expressed with CrewAI (pip install crewai).

NOTE: written against the CrewAI Agent/Task/Crew API; it was not executed in the environment
where this project was prepared (no network to install crewai) - verify with your installed
CrewAI version. The default API path uses agents.Orchestrator, which has no extra dependencies.

    python -m samsung_assistant.crew_adapter "Samsung Galaxy S23 Ultra"

LLM: CrewAI uses its own LLM config - e.g. set OPENAI_API_KEY, or point it at Ollama
(see CrewAI docs: LLM(model="ollama/llama3.1", base_url="http://localhost:11434")).
"""
from __future__ import annotations

import json
import os
import sys

from .db import Database
from .repository import PhoneRepository


def build_crew(phone_name: str):
    from crewai import Agent, Crew, LLM, Process, Task
    from crewai.tools import tool

    repo = PhoneRepository(Database())
    model = os.getenv("CREWAI_MODEL", f"ollama/{os.getenv('LLM_MODEL', 'qwen2.5:1.5b')}")
    base_url = os.getenv("CREWAI_BASE_URL", "http://localhost:11434").rstrip("/")
    crew_llm = LLM(model=model, base_url=base_url, temperature=0.2, timeout=120)

    @tool("get_phone_specs")
    def get_phone_specs(name: str) -> str:
        """Return the full specification sheet of a Samsung phone from the database as JSON."""
        phone = repo.get_phone(name)
        return json.dumps(phone, default=str) if phone else "Phone not found"

    retriever = Agent(
        role="Specification Retrieval Specialist",
        goal="Fetch complete and accurate phone specifications from the database",
        backstory="You only report facts that exist in the database and never guess.",
        tools=[get_phone_specs], llm=crew_llm, allow_delegation=False, verbose=True,
    )
    writer = Agent(
        role="Smartphone Reviewer",
        goal="Write a detailed, balanced review using only the retrieved specifications",
        backstory="A tech journalist who backs every claim with a concrete spec.",
        llm=crew_llm, allow_delegation=False, verbose=True,
    )
    t1 = Task(description=f"Retrieve the full specifications of '{phone_name}' using the tool.",
              expected_output="All specs grouped by category (display, platform, camera, battery, body, price).",
              agent=retriever)
    t2 = Task(description="Write a detailed review with Overview, Display, Performance, Camera, Battery, "
                          "Pros, Cons and Verdict sections using only the retrieved specs.",
              expected_output="A well-structured review in Markdown.", agent=writer, context=[t1])
    return Crew(agents=[retriever, writer], tasks=[t1, t2], process=Process.sequential)


if __name__ == "__main__":
    print(build_crew(sys.argv[1] if len(sys.argv) > 1 else "Samsung Galaxy S23").kickoff())
