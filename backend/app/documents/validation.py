"""Upload validation: type by magic bytes, size, encrypted PDFs, page and pixel limits.

Documents are untrusted input (Rule 9). Nothing here logs file content.
"""

import io
from dataclasses import dataclass

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_PDF_PAGE_POINTS = 5_000  # ~69 inches per side; A0 is ~3,370 pt

_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)


class DocumentRejected(Exception):
    """Upload refused; `code` is safe to return and log, `status_code` is the HTTP status."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    mime_type: str
    page_count: int


def detect_mime(data: bytes) -> str | None:
    for signature, mime in _SIGNATURES:
        if data.startswith(signature):
            return mime
    return None


def validate_upload(data: bytes, max_pdf_pages: int) -> ValidatedUpload:
    if not data:
        raise DocumentRejected("empty_file", "The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentRejected("file_too_large", "Files may be at most 20 MB.", status_code=413)
    mime = detect_mime(data)
    if mime is None:
        raise DocumentRejected(
            "unsupported_type", "Only PDF, PNG, JPEG, and TIFF files are accepted.", status_code=415
        )
    if mime == "application/pdf":
        return ValidatedUpload(mime, _check_pdf(data, max_pdf_pages))
    return ValidatedUpload(mime, _check_image(data, max_pdf_pages))


def _check_pdf(data: bytes, max_pages: int) -> int:
    import pymupdf

    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:
        raise DocumentRejected("unreadable_pdf", "The PDF could not be read.") from error
    with document:
        if document.needs_pass or document.is_encrypted:
            raise DocumentRejected("encrypted_pdf", "Password-protected PDFs are not accepted.")
        if document.page_count == 0:
            raise DocumentRejected("empty_pdf", "The PDF has no pages.")
        if document.page_count > max_pages:
            raise DocumentRejected("too_many_pages", f"PDFs may have at most {max_pages} pages.")
        for page in document:
            if max(page.rect.width, page.rect.height) > MAX_PDF_PAGE_POINTS:
                raise DocumentRejected("page_too_large", "A PDF page is larger than the allowed size.")
        return document.page_count


def _check_image(data: bytes, max_frames: int) -> int:
    from PIL import Image, ImageSequence

    try:
        with Image.open(io.BytesIO(data)) as image:
            frames = 0
            for frame in ImageSequence.Iterator(image):
                frames += 1
                if frame.width * frame.height > MAX_IMAGE_PIXELS:
                    raise DocumentRejected("image_too_large", "Image dimensions are too large.")
                if frames > max_frames:
                    raise DocumentRejected("too_many_pages", f"Images may have at most {max_frames} pages.")
    except DocumentRejected:
        raise
    except Exception as error:
        raise DocumentRejected("unreadable_image", "The image could not be read.") from error
    return frames
