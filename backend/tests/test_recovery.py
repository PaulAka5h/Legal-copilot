"""Crash recovery for document processing (migration 0015). SAMPLE_DATA_NOT_REAL_LAW."""

import asyncio
import hashlib
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import create_database_engine, user_transaction
from app.documents import repository as repo
from app.documents.processing import process_document
from app.documents.recovery import sweep_stuck_documents
from app.documents.storage import MinioStore, document_key
from app.main import create_app
from tests.step_c_helpers import lawyer_with_case, sample_pdf, sql_as

EN = ["SAMPLE_DATA_NOT_REAL_LAW recovery test page dated 2024."]


class Crash(BaseException):
    """Stands in for a killed process: not an Exception, so process_document cannot catch it."""


class CrashingStore:
    def __init__(self, inner):
        self.inner = inner

    def put(self, key, data, content_type):
        self.inner.put(key, data, content_type)

    def get(self, key):
        raise Crash()


def stuck_document(settings, user_id: UUID, case_id: str) -> UUID:
    """Create a document and crash during processing, leaving it 'processing' with no pages."""
    data = sample_pdf(EN)
    document_id = uuid4()
    store = MinioStore(settings)
    store.put(document_key(UUID(case_id), document_id), data, "application/pdf")

    async def run():
        engine = create_database_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with user_transaction(factory, user_id) as session:
                organization_id = (await repo.case_status(session, UUID(case_id)))[1]
                await repo.insert_document(session, {
                    "id": document_id, "case_id": UUID(case_id), "organization_id": organization_id,
                    "title": "SAMPLE_DATA_NOT_REAL_LAW", "original_filename": "stuck.pdf",
                    "mime_type": "application/pdf", "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).digest(),
                    "storage_key": document_key(UUID(case_id), document_id), "page_count": 1,
                    "scan_status": "not_configured", "uploaded_by": user_id,
                })
            with pytest.raises(Crash):
                await process_document(factory, document_id=document_id, case_id=UUID(case_id),
                                       acting_user_id=user_id, store=CrashingStore(store), settings=settings)
        finally:
            await engine.dispose()

    asyncio.run(run())
    return document_id


def state(settings, user_id, document_id):
    return sql_as(settings.database_url, user_id,
                  "SELECT processing_status, processing_error, processing_started_at IS NOT NULL, "
                  "(SELECT count(*) FROM public.extracted_pages p WHERE p.document_id = d.id) "
                  "FROM public.documents d WHERE id = :d", d=document_id)[0]


def backdate(settings, user_id, document_id, minutes: int):
    sql_as(settings.database_url, user_id,
           "UPDATE public.documents SET processing_started_at = now() - make_interval(mins => :m) "
           "WHERE id = :d RETURNING id", m=minutes, d=document_id)


def sweep(settings, minutes):
    async def run():
        engine = create_database_engine(settings.database_url)
        try:
            return await sweep_stuck_documents(engine, minutes)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_sweep_marks_stuck_documents_failed_and_they_can_be_retried(api_client):
    settings = api_client.app.state.settings
    user_id, case_id = lawyer_with_case(api_client, "recovery")
    old = stuck_document(settings, user_id, case_id)
    recent = stuck_document(settings, user_id, case_id)
    assert state(settings, user_id, old) == ("processing", None, True, 0)
    backdate(settings, user_id, old, 120)

    assert sweep(settings, 30) >= 1
    assert state(settings, user_id, old)[:2] == ("failed", "processing_timeout")
    assert state(settings, user_id, recent)[0] == "processing"  # in-flight work is left alone

    async def retry():
        engine = create_database_engine(settings.database_url)
        try:
            return await process_document(async_sessionmaker(engine, expire_on_commit=False),
                                          document_id=old, case_id=UUID(case_id), acting_user_id=user_id,
                                          store=MinioStore(settings), settings=settings)
        finally:
            await engine.dispose()

    result = asyncio.run(retry())
    assert (result.processing_status, result.page_count) == ("ready", 1)
    assert state(settings, user_id, old)[0] == "ready"

    with pytest.raises(ValueError):
        sweep(settings, 1)
    with pytest.raises(Exception, match="at least 5 minutes"):
        sql_as(settings.database_url, user_id, "SELECT app.fail_stuck_documents(interval '1 minute')")


def test_startup_sweep_recovers_documents(api_client):
    settings = api_client.app.state.settings
    user_id, case_id = lawyer_with_case(api_client, "recovery-startup")
    stuck = stuck_document(settings, user_id, case_id)
    backdate(settings, user_id, stuck, settings.stuck_processing_minutes + 5)

    with TestClient(create_app(settings), base_url="https://testserver"):
        pass  # lifespan runs the sweep
    assert state(settings, user_id, stuck)[:2] == ("failed", "processing_timeout")
