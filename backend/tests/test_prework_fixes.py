"""Pre-Step-D fixes: quote minimum, case permissions, Gemini provider and fallback. SAMPLE_DATA_NOT_REAL_LAW."""

import json
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.ai.llm import GeminiLLM, _gemini_schema, resolve_provider, strict_json_schema
from app.cases.dependencies import require_case_permission
from app.cases.schemas import CaseAccess
from app.config import Settings
from app.facts.extractor import FallbackFactExtractor, LLMFactExtractor, MockFactExtractor, PageInput
from app.facts.schemas import ExtractionOutput
from app.facts.service import check_sources, substantive_quote

PAGE_TEXT = "SAMPLE_DATA_NOT_REAL_LAW the buyer paid the seller on 12 March 2024 at the shop."


def test_trivial_quotes_fail_the_source_check():
    assert not substantive_quote("the")
    assert not substantive_quote("paid the seller")  # 3 words
    assert not substantive_quote("SAMPLE_DATA_NOT_REAL")  # 20 chars, 1 word
    assert substantive_quote("the buyer paid the seller")
    page = PageInput(uuid4(), uuid4(), 1, 1, PAGE_TEXT)
    pages = {(page.document_id, 1): page}
    trivial = [{"document_id": page.document_id, "page_no": 1, "quote": "the"}]
    real = [{"document_id": page.document_id, "page_no": 1, "quote": "the buyer paid the seller on 12 March 2024"}]
    assert check_sources("document_says", trivial, pages)[0] == "failed"
    assert check_sources("document_says", real, pages)[0] == "passed"


def test_case_permissions():
    case_id = uuid4()
    require_case_permission(CaseAccess(case_id=case_id, role="lead_lawyer", permissions={}), "can_upload")
    require_case_permission(CaseAccess(case_id=case_id, role="team_lawyer", permissions={"can_run_ai": True}),
                            "can_run_ai")
    for role, permissions, needed in (("team_lawyer", {}, "can_upload"), ("assistant", {"can_upload": True}, "can_run_ai")):
        with pytest.raises(HTTPException) as denied:
            require_case_permission(CaseAccess(case_id=case_id, role=role, permissions=permissions), needed)
        assert denied.value.status_code == 403


def test_gemini_request_shape_and_schema_simplification():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"facts": []}'}]}}]})

    llm = resolve_provider(Settings(llm_provider="gemini", llm_approved_providers="mock,gemini",
                                    gemini_api_key="test-key", gemini_model="sample-model"),
                           transport=httpx.MockTransport(handler))
    assert isinstance(llm, GeminiLLM)
    out = LLMFactExtractor(llm).extract_batch([PageInput(UUID(int=1), UUID(int=2), 1, 1, PAGE_TEXT)])
    assert json.loads(out) == {"facts": []}
    assert seen["url"].endswith("/models/sample-model:generateContent")
    assert "test-key" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "test-key"
    config = seen["body"]["generationConfig"]
    assert config["temperature"] == 0 and config["responseMimeType"] == "application/json"
    dumped = json.dumps(config["responseJsonSchema"])
    for keyword in ("maxLength", "pattern", "additionalProperties", "$ref", "minimum"):
        assert keyword not in dumped
    assert "maxLength" in json.dumps(strict_json_schema(ExtractionOutput.model_json_schema()))  # Pydantic keeps it
    assert _gemini_schema({"type": "string", "maxLength": 5, "description": "d"}) == {"type": "string", "description": "d"}


def test_fallback_chain_gemini_to_mock():
    assert resolve_provider(Settings(llm_provider="gemini", llm_approved_providers="mock,gemini",
                                     gemini_api_key=None)) is None  # no key -> mock

    def failing(request):
        return httpx.Response(503, json={"error": {"message": "overloaded"}})

    gemini = resolve_provider(Settings(llm_provider="gemini", llm_approved_providers="mock,gemini",
                                       gemini_api_key="k", gemini_model="m"), transport=httpx.MockTransport(failing))
    extractor = FallbackFactExtractor(LLMFactExtractor(gemini), MockFactExtractor())
    raw = extractor.extract_batch([PageInput(UUID(int=1), UUID(int=2), 1, 1, PAGE_TEXT)])
    assert extractor.last_origin == "ai_mock" and extractor.fallbacks == 1  # labelled as mock, not as Gemini
    assert ExtractionOutput.model_validate_json(raw).facts


def test_secrets_never_appear_in_reprs():
    settings = Settings(gemini_api_key="SECRET-GEMINI-KEY", minio_secret_key="SECRET-MINIO-KEY",
                        llm_provider="gemini", llm_approved_providers="gemini", gemini_model="m")
    assert "SECRET-GEMINI-KEY" not in repr(settings) and "SECRET-MINIO-KEY" not in repr(settings)
    assert "SECRET-GEMINI-KEY" not in repr(resolve_provider(settings))
