import hashlib
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Body, File, Form, HTTPException, Path, Request, UploadFile, status

from app.auth.dependencies import require_same_origin, LawyerDep, SessionFactoryDep, UserSessionDep, request_ip
from app.auth.repository import write_audit_event
import asyncio

from app.cases.dependencies import CaseAccessDep, CaseAccessShortDep, require_case_permission
from app.database import user_transaction
from app.documents import repository as repo
from app.documents.processing import ScannerNotConfigured, process_document, scan_status_for
from app.documents.schemas import (
    DocumentResponse,
    PageCorrectionRequest,
    PageResponse,
    PageVersion,
    UploadResponse,
)
from app.documents.storage import StorageNotConfigured, document_key, get_store
from app.documents.validation import MAX_UPLOAD_BYTES, DocumentRejected, validate_upload
from app.errors import problem_responses
from app.rag.text import nfc

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}/documents", tags=["case-documents"])

NOT_CONFIGURED = status.HTTP_503_SERVICE_UNAVAILABLE


async def _writable_case(session, case_id: UUID) -> UUID:
    found = await repo.case_status(session, case_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if found[0] == "closed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Closed cases are read-only.")
    return found[1]


@router.post(
    "",
    summary="Upload and process a case document",
    description=(
        "Accepts a PDF, PNG, JPEG, or TIFF of at most 20 MB. The type is checked by magic bytes; "
        "password-protected PDFs and oversized images are refused. The original is stored in object "
        "storage under cases/{case_id}/documents/{document_id}, then processed synchronously: the PDF "
        "text layer is used where present and scanned pages are OCRed with Tesseract (ben+eng), with "
        "per-page confidence. Without a malware scanner, development processes the file with "
        "scan_status 'not_configured' and a warning; production refuses with NOT_CONFIGURED. "
        "Duplicate files in the same case are refused. Requires an active lawyer membership in an "
        "open case."
    ),
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 413, 415, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def upload_document(
    request: Request,
    access: CaseAccessShortDep,
    user: LawyerDep,
    session_factory: SessionFactoryDep,
    file: Annotated[UploadFile, File(description="The document file")],
    title: Annotated[str | None, Form(max_length=300, description="Display title; defaults to the filename")] = None,
) -> UploadResponse:
    require_case_permission(access, "can_upload")
    settings = request.app.state.settings
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        upload = await asyncio.to_thread(validate_upload, data, settings.max_pdf_pages)
        scan_status = scan_status_for(settings)
        store = get_store(settings)
    except DocumentRejected as error:
        raise HTTPException(status_code=error.status_code, detail=f"{error.code}: {error}") from error
    except (ScannerNotConfigured, StorageNotConfigured) as error:
        raise HTTPException(status_code=NOT_CONFIGURED, detail=f"NOT_CONFIGURED: {error}") from error

    filename = (file.filename or "document").strip()[:255] or "document"
    sha256 = hashlib.sha256(data).digest()
    document_id = uuid4()
    key = document_key(access.case_id, document_id)

    async with user_transaction(session_factory, user.id) as session:
        organization_id = await _writable_case(session, access.case_id)
        if await repo.find_by_sha(session, access.case_id, sha256):
            raise HTTPException(status_code=409, detail="This file is already in the case.")
        await repo.insert_document(session, {
            "id": document_id, "case_id": access.case_id, "organization_id": organization_id,
            "title": nfc((title or filename).strip()) or filename, "original_filename": filename,
            "mime_type": upload.mime_type, "size_bytes": len(data), "sha256": sha256, "storage_key": key,
            "page_count": upload.page_count, "scan_status": scan_status, "uploaded_by": user.id,
        })
        await write_audit_event(
            session, action="document.uploaded", actor_user_id=user.id, actor_role="lawyer",
            object_type="document", object_id=document_id, case_id=access.case_id,
            ip_address=request_ip(request), user_agent=request.headers.get("user-agent", "")[:512] or None,
            request_id=getattr(request.state, "request_id", None),
            details={"mime_type": upload.mime_type, "size_bytes": len(data), "scan_status": scan_status},
        )

    try:
        await asyncio.to_thread(store.put, key, data, upload.mime_type)
    except Exception as error:
        async with user_transaction(session_factory, user.id) as session:
            await repo.set_processing_state(session, document_id, processing_status="failed",
                                            processing_error="storage_error")
        raise HTTPException(status_code=NOT_CONFIGURED, detail="Document storage is unavailable.") from error

    result = await process_document(
        session_factory, document_id=document_id, case_id=access.case_id,
        acting_user_id=user.id, store=store, settings=settings,
    )
    async with user_transaction(session_factory, user.id) as session:
        document = await repo.get_document(session, access.case_id, document_id)
    return UploadResponse(document=DocumentResponse(**document), warnings=result.warnings)


@router.get(
    "",
    summary="List case documents",
    description="Lists the case's documents with processing status. Lawyer case members only.",
    response_model=list[DocumentResponse],
    responses=problem_responses(401, 403, 404),
)
async def list_case_documents(access: CaseAccessDep, session: UserSessionDep) -> list[DocumentResponse]:
    return [DocumentResponse(**d) for d in await repo.list_documents(session, access.case_id)]


@router.get(
    "/{document_id}",
    summary="Get a case document",
    description="Returns one document's metadata and processing status.",
    response_model=DocumentResponse,
    responses=problem_responses(401, 403, 404),
)
async def get_case_document(
    access: CaseAccessDep,
    session: UserSessionDep,
    document_id: Annotated[UUID, Path(description="Document ID")],
) -> DocumentResponse:
    document = await repo.get_document(session, access.case_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document was not found.")
    return DocumentResponse(**document)


@router.get(
    "/{document_id}/pages/{page_no}",
    summary="Get a page with its version history",
    description="Returns the current text of a page and every earlier version (newest first).",
    response_model=PageResponse,
    responses=problem_responses(401, 403, 404),
)
async def get_page(
    access: CaseAccessDep,
    session: UserSessionDep,
    document_id: Annotated[UUID, Path(description="Document ID")],
    page_no: Annotated[int, Path(ge=1, description="1-based page number")],
) -> PageResponse:
    versions = await repo.page_versions(session, access.case_id, document_id, page_no)
    current = next((v for v in versions if v["is_current"]), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Page was not found.")
    return PageResponse(document_id=document_id, page_no=page_no, current=PageVersion(**current),
                        history=[PageVersion(**v) for v in versions])


@router.post(
    "/{document_id}/pages/{page_no}/versions",
    summary="Correct a page's text",
    description=(
        "Stores a lawyer correction as a new page version (source_method 'lawyer_edit'); the earlier "
        "version is kept. Facts keep pointing at the page version they were extracted from."
    ),
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def correct_page(
    request: Request,
    access: CaseAccessDep,
    user: LawyerDep,
    session: UserSessionDep,
    document_id: Annotated[UUID, Path(description="Document ID")],
    page_no: Annotated[int, Path(ge=1, description="1-based page number")],
    payload: Annotated[PageCorrectionRequest, Body(description="Corrected text")],
) -> PageResponse:
    require_case_permission(access, "can_upload")
    organization_id = await _writable_case(session, access.case_id)
    versions = await repo.page_versions(session, access.case_id, document_id, page_no)
    current = next((v for v in versions if v["is_current"]), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Page was not found.")
    from app.documents.extraction import detect_language

    corrected = nfc(payload.text).strip()
    await repo.retire_page(session, current["id"])
    new_id = await repo.insert_page(session, {
        "document_id": document_id, "case_id": access.case_id, "organization_id": organization_id,
        "page_no": page_no, "version": current["version"] + 1, "text": corrected,
        "source_method": "lawyer_edit", "ocr_engine": None, "ocr_confidence": None,
        "quality_flag": "ok", "language": detect_language(corrected), "edited_by": user.id,
        "supersedes_id": current["id"],
    })
    await write_audit_event(
        session, action="document.page_corrected", actor_user_id=user.id, actor_role="lawyer",
        object_type="extracted_page", object_id=new_id, case_id=access.case_id,
        ip_address=request_ip(request), user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        details={"document_id": str(document_id), "page_no": page_no, "version": current["version"] + 1},
    )
    versions = await repo.page_versions(session, access.case_id, document_id, page_no)
    return PageResponse(document_id=document_id, page_no=page_no,
                        current=PageVersion(**next(v for v in versions if v["is_current"])),
                        history=[PageVersion(**v) for v in versions])
