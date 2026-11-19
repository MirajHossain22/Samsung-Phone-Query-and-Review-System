import copy

import pytest

from samsung_assistant.agents import Orchestrator
from samsung_assistant.chatbot import Chatbot
from samsung_assistant.db import Database
from samsung_assistant.llm import LLM
from samsung_assistant.normalize import parse_key_specs, parse_prices
from samsung_assistant.rag import Retriever
from samsung_assistant.repository import PhoneRepository
from samsung_assistant.scraper import _model_key, next_listing_page, parse_listing, parse_phone_page
from samsung_assistant.seed import build_records

from .fixtures import LISTING_HTML, PHONE_HTML


@pytest.fixture(scope="module")
def repo():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    for rec in build_records():
        r.upsert_phone(rec)
    return r


@pytest.fixture(scope="module")
def bot(repo):
    return Chatbot(Retriever(repo), LLM("none"))


# ----------------------------------------------------------------- scraper
def test_parse_listing_and_pagination():
    items = parse_listing(LISTING_HTML)
    assert items["Galaxy S23 Ultra"].endswith("samsung_galaxy_s23_ultra-12024.php")
    assert next_listing_page(LISTING_HTML).endswith("samsung-phones-f-9-0-p2.php")
    assert _model_key("Samsung Galaxy S22 5G") == _model_key("Samsung Galaxy S22")
    assert _model_key("Samsung Galaxy S22+") == _model_key("Samsung Galaxy S22 Plus")


def test_parse_phone_page_and_normalize():
    rec = parse_phone_page(PHONE_HTML, "https://www.gsmarena.com/x.php")
    assert rec["name"] == "Samsung Galaxy S23"
    assert rec["announced"] == "2023, February 01"
    assert "512GB 8GB RAM" in rec["specs"]["Memory"]["Internal"]
    assert "UFS 4.0" in rec["specs"]["Memory"]["Internal"]          # continuation row merged
    ks = parse_key_specs(rec["specs"])
    assert ks["display_size_in"] == 6.1 and ks["refresh_rate_hz"] == 120
    assert ks["ram_gb_max"] == 8 and ks["storage_gb_max"] == 512
    assert ks["main_camera_mp"] == 50 and ks["camera_summary"] == "50 + 10 + 12 MP"
    assert ks["battery_mah"] == 3900 and ks["charging_w"] == 25


def test_parse_mobile_phone_title_markup():
    mobile_html = PHONE_HTML.replace(
        'class="specs-phone-name-title" data-spec="modelname"',
        'class="section nobor"',
    ).replace("Selfie camera", "Selfie Camera")
    rec = parse_phone_page(mobile_html)
    assert rec["name"] == "Samsung Galaxy S23"


def test_scraped_record_roundtrips_through_db():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    r.upsert_phone(parse_phone_page(PHONE_HTML))
    r.upsert_phone(parse_phone_page(PHONE_HTML))                  # idempotent upsert
    assert r.count() == 1
    p = r.get_phone("galaxy s23")
    assert p["key_specs"]["battery_mah"] == 3900
    assert {x["currency"] for x in p["prices"]} == {"USD", "EUR", "GBP"}


def test_failed_upsert_rolls_back_entire_phone():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    with pytest.raises(KeyError):
        r.upsert_phone({"name": "Samsung Galaxy Broken"})
    assert r.count() == 0


def test_parse_prices_formats():
    assert parse_prices("About 400 EUR") == [("EUR", 400.0)]
    assert parse_prices("$ 1,199.99 / € 1,299.00") == [("USD", 1199.99), ("EUR", 1299.0)]


# ----------------------------------------------------------------- database
def test_seed_has_12_phones(repo):
    assert repo.count() == 12


# ------------------------------------------------------------------ chatbot
def test_entity_detection_prefers_longest_name(bot):
    names = [p["name"] for p in bot.retriever.detect_phones("S23 Ultra vs S23+ vs S23")]
    assert names == ["Samsung Galaxy S23 Ultra", "Samsung Galaxy S23+", "Samsung Galaxy S23"]


def test_entity_detection_accepts_plus_and_omitted_5g_suffix():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    records = build_records()
    s22 = copy.deepcopy(next(x for x in records if x["name"] == "Samsung Galaxy S22"))
    s22["name"] += " 5G"
    s22_plus = copy.deepcopy(next(x for x in records if x["name"] == "Samsung Galaxy S22+"))
    s22_plus["name"] += " 5G"
    r.upsert_phone(s22)
    r.upsert_phone(s22_plus)
    retriever = Retriever(r)
    assert retriever.detect_phones("screen size of Galaxy S22?")[0]["name"].endswith("S22 5G")
    assert retriever.detect_phones("compare S22 Plus and S22")[0]["name"].endswith("S22+ 5G")


def test_camera_spec_question(bot):
    r = bot.answer("What are the camera specs of the Samsung Galaxy S23?")
    assert r["phones"] == ["Samsung Galaxy S23"]
    assert "50 MP" in r["answer"] and "12 MP" in r["answer"]


def test_screen_size_question(bot):
    assert "6.1 inches" in bot.answer("What is the screen size of the Galaxy S22?")["answer"]


def test_best_battery_reports_ties(bot):
    r = bot.answer("Which Samsung phone has the best battery life?")
    assert r["intent"] == "rank" and "5000 mAh" in r["answer"] and "tie" in r["answer"]
    assert "S24 Ultra" in r["answer"]


def test_lightest_and_cheapest(bot):
    assert "167 g" in bot.answer("Which phone is the lightest?")["answer"]
    assert "799.99" in bot.answer("cheapest samsung phone")["answer"]


def test_compare_performance(bot):
    r = bot.answer("How does the Galaxy S23 compare to the S22 in terms of performance?")
    assert r["intent"] == "compare" and "Snapdragon 8 Gen 2" in r["answer"] and "Exynos 2200" in r["answer"]


def test_unknown_question_does_not_hallucinate(bot):
    assert "couldn't find" in bot.answer("what is the weather today")["answer"]


def test_unknown_model_and_partial_comparison_are_reported(bot):
    unknown = bot.answer("What are the camera specs of the Galaxy S25?")
    assert unknown["intent"] == "unknown_model" and "S25" in unknown["answer"]
    partial = bot.answer("Compare Galaxy S23 with Galaxy S25")
    assert partial["intent"] == "unknown_model" and "S25" in partial["answer"]


def test_llm_gemini_backend(monkeypatch):
    llm = LLM("gemini")
    assert llm.enabled is True

    class MockResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "6.1 inches"}]}}]}

    monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")
    monkeypatch.setattr("requests.post", lambda *a, **kw: MockResp())
    assert llm.generate("system prompt", "user prompt") == "6.1 inches"


# -------------------------------------------------------------- multi-agent
def test_review_pipeline(repo):
    crew = Orchestrator(repo, Retriever(repo), LLM("none"))
    out = crew.review("Samsung Galaxy S23 Ultra")
    assert out["found"] and [t["agent"] for t in out["trace"]] == ["SpecRetrievalAgent", "ReviewWriterAgent"]
    assert "200 + 12 + 10 + 10 MP" in out["review"] and "## Verdict" in out["review"]
    assert any("battery" in p for p in out["pros"])


def test_review_unknown_phone(repo):
    assert Orchestrator(repo, Retriever(repo), LLM("none")).review("Nokia 3310")["found"] is False


def test_review_handles_missing_weight():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    record = copy.deepcopy(build_records()[0])
    record["specs"]["Body"].pop("Weight")
    r.upsert_phone(record)
    out = Orchestrator(r, Retriever(r), LLM("none")).review("Galaxy S21")
    assert out["found"] and "weight is not listed" in out["review"]


# ---------------------------------------------------------------------- API
def test_api_endpoints(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "none")
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from samsung_assistant.api import create_app

    db = Database("sqlite:///:memory:")
    db.init_schema()
    r = PhoneRepository(db)
    for rec in build_records():
        r.upsert_phone(rec)
    with TestClient(create_app(db)) as c:
        assert c.get("/").status_code == 200
        assert c.get("/input.js").headers["content-type"].startswith("text/javascript")
        health = c.get("/health").json()
        assert health["phones_in_db"] == 12 and health["llm_model"] == "deterministic"
        assert "6.1 inches" in c.post("/chat", json={"question": "screen size of the Galaxy S22?"}).json()["answer"]
        assert c.post("/review", json={"phone": "S23 Ultra"}).json()["found"] is True
        assert c.post("/review", json={"phone": "Nokia 3310"}).status_code == 404
        assert c.get("/compare", params={"a": "S23", "b": "S22", "aspect": "performance"}).json()["intent"] == "compare"
