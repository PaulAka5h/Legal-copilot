"""Page text extraction: PDF text layer first, Tesseract OCR (ben+eng) for scanned pages.

All page text is NFC. OCR confidence is the mean word confidence (0-1) per page.
Pages are OCR'd in greyscale (Tesseract binarizes anyway; a third of the memory of
RGB) at OCR_DPI at most; photos are scaled to the same pixel budget as an A4 page at
that DPI, which bounds memory (Render free: 512 MB, OCR_DPI=200).
If Tesseract or the requested languages are missing, scanned pages are stored
with empty text, ocr_engine 'not_configured', and quality 'needs_review', and an
`ocr_not_configured` warning is returned. Page text is never logged.
"""

import io
from dataclasses import dataclass
from functools import lru_cache

from app.rag.text import nfc

MIN_TEXT_LAYER_CHARS = 25
OCR_DPI = 300  # default; Settings.ocr_dpi (env OCR_DPI) overrides
A4_AREA_IN2 = 8.27 * 11.69
OCR_NOT_CONFIGURED = "not_configured"
OCR_TIMEOUT_SECONDS = 60  # per call; a timeout fails processing instead of hanging


@dataclass(frozen=True)
class PageText:
    page_no: int
    text: str
    source_method: str  # text_layer | ocr
    ocr_engine: str | None
    ocr_confidence: float | None
    quality_flag: str
    language: str


@lru_cache(maxsize=4)
def ocr_engine_for(languages: str) -> str | None:
    """'tesseract-<version>' if the binary and all requested languages exist, else None."""
    try:
        import pytesseract

        available = set(pytesseract.get_languages(config=""))
        if not set(languages.split("+")) <= available:
            return None
        return f"tesseract-{pytesseract.get_tesseract_version()}"
    except Exception:
        return None


def detect_language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    bengali = sum(1 for c in letters if "ঀ" <= c <= "৿") / len(letters)
    if bengali >= 0.9:
        return "bn"
    if bengali <= 0.1:
        return "en"
    return "mixed"  # both scripts carry more than 10% of the letters


def render_dpi(width_pt: float, height_pt: float, max_dpi: int = OCR_DPI) -> int:
    """max_dpi, lowered so the rendered page never exceeds MAX_IMAGE_PIXELS (memory bound)."""
    from app.documents.validation import MAX_IMAGE_PIXELS

    area_in2 = max(width_pt / 72 * height_pt / 72, 1e-6)
    return max(36, min(max_dpi, int((MAX_IMAGE_PIXELS / area_in2) ** 0.5)))


def ocr_size(width: int, height: int, dpi: int = OCR_DPI) -> tuple[int, int]:
    """(width, height) scaled down to at most an A4 page's pixels at `dpi`."""
    budget = A4_AREA_IN2 * dpi * dpi
    scale = min(1.0, (budget / max(width * height, 1)) ** 0.5)
    return max(1, int(width * scale)), max(1, int(height * scale))


def _quality(confidence: float | None, text: str) -> str:
    if not text.strip():
        return "needs_review"
    if confidence is None or confidence >= 0.75:
        return "ok"
    return "needs_review" if confidence >= 0.5 else "poor"


def _ocr(image, languages: str, engine: str | None) -> tuple[str, float | None, str]:
    if engine is None:
        return "", None, OCR_NOT_CONFIGURED
    import pytesseract

    data = pytesseract.image_to_data(image, lang=languages, output_type=pytesseract.Output.DICT,
                                     timeout=OCR_TIMEOUT_SECONDS)
    confidences = [float(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and float(c) >= 0]
    text = pytesseract.image_to_string(image, lang=languages, timeout=OCR_TIMEOUT_SECONDS)
    confidence = round(sum(confidences) / len(confidences) / 100, 3) if confidences else 0.0
    return text, confidence, engine


def _ocr_page(page_no: int, image, languages: str, engine: str | None) -> PageText:
    text, confidence, used = _ocr(image, languages, engine)
    text = nfc(text).strip()
    return PageText(page_no, text, "ocr", used, confidence, _quality(confidence, text), detect_language(text))


def _ocr_image(frame, dpi: int):
    """Greyscale frame within the OCR pixel budget."""
    from PIL import Image

    size = ocr_size(frame.width, frame.height, dpi)
    frame = frame.convert("L")
    return frame if size == frame.size else frame.resize(size, Image.Resampling.LANCZOS)


def extract_pages(data: bytes, mime_type: str, languages: str,
                  dpi: int = OCR_DPI) -> tuple[list[PageText], list[str]]:
    engine = ocr_engine_for(languages)
    pages: list[PageText] = []
    if mime_type == "application/pdf":
        import pymupdf
        from PIL import Image

        with pymupdf.open(stream=data, filetype="pdf") as document:
            for index, page in enumerate(document, start=1):
                text = nfc(page.get_text("text")).strip()
                if len("".join(text.split())) >= MIN_TEXT_LAYER_CHARS:
                    pages.append(PageText(index, text, "text_layer", None, None, "ok", detect_language(text)))
                    continue
                pixmap = page.get_pixmap(dpi=render_dpi(page.rect.width, page.rect.height, dpi),
                                         colorspace=pymupdf.csGRAY, alpha=False)
                image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
                del pixmap
                pages.append(_ocr_page(index, image, languages, engine))
    else:
        from PIL import Image, ImageSequence

        with Image.open(io.BytesIO(data)) as image:
            if image.format == "JPEG":  # decode straight to reduced-size greyscale
                image.draft("L", ocr_size(image.width, image.height, dpi))
            for index, frame in enumerate(ImageSequence.Iterator(image), start=1):
                pages.append(_ocr_page(index, _ocr_image(frame, dpi), languages, engine))

    warnings = []
    if any(p.ocr_engine == OCR_NOT_CONFIGURED for p in pages):
        warnings.append("ocr_not_configured: scanned pages have no text until Tesseract ben+eng is installed")
    return pages, warnings


def document_language(pages: list[PageText]) -> str:
    languages = {p.language for p in pages if p.language != "unknown"}
    if not languages:
        return "unknown"
    return languages.pop() if len(languages) == 1 else "mixed"
