"""Profile photo processing: sniff the real type, cap pixels before decoding,
drop all metadata, center-crop to 512x512 plus a 96x96 thumbnail, WebP out.

Uploads are untrusted input. The type comes from the file's bytes, never its
name or the client's Content-Type. Memory stays low on a 512 MB server: the
header is read first and anything over MAX_PIXELS is refused before any pixel
is decoded, JPEGs decode at a reduced scale (draft mode), and at most
MAX_CONCURRENT photos are processed at once.
"""

import io
import threading
from dataclasses import dataclass
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000  # e.g. 4900 x 3265; at most ~64 MB decoded (RGBA), once
SIZES = (512, 96)
MAX_CONCURRENT = 1  # photo uploads are rare; one decode at a time bounds peak memory

_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "PNG"),
)
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)


class PhotoRejected(Exception):
    """Upload refused; `code` and the message are safe to return and log."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ProcessedPhoto:
    large: bytes  # 512x512 WebP
    thumb: bytes  # 96x96 WebP


def detect_photo_type(data: bytes) -> tuple[str, str] | None:
    """(mime, Pillow format) from magic bytes, or None for anything else."""
    for signature, mime, fmt in _SIGNATURES:
        if data.startswith(signature):
            return mime, fmt
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "WEBP"
    return None


def avatar_key(user_id: UUID, avatar_id: UUID, size: int) -> str:
    return f"users/{user_id}/avatar/{avatar_id}-{size}.webp"


def _encode(image: Image.Image, size: int) -> bytes:
    resized = ImageOps.fit(image, (size, size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    # A fresh image from raw pixels carries no EXIF, XMP, ICC or text chunks.
    clean = Image.frombytes(resized.mode, resized.size, resized.tobytes())
    out = io.BytesIO()
    clean.save(out, format="WEBP", quality=85, method=4)
    return out.getvalue()


def process_photo(data: bytes) -> ProcessedPhoto:
    if not data:
        raise PhotoRejected("empty_file", "The file is empty.")
    if len(data) > MAX_PHOTO_BYTES:
        raise PhotoRejected("file_too_large", "Photos may be at most 5 MB.", status_code=413)
    detected = detect_photo_type(data)
    if detected is None:
        raise PhotoRejected("unsupported_type", "Only JPEG, PNG and WebP photos are accepted.", status_code=415)
    _, expected_format = detected
    with _slots:
        try:
            with Image.open(io.BytesIO(data), formats=[expected_format]) as image:
                width, height = image.size  # header only; nothing decoded yet
                if width < 1 or height < 1 or width * height > MAX_PIXELS:
                    raise PhotoRejected("image_too_large", "The photo's pixel dimensions are too large.")
                if image.format == "JPEG":
                    image.draft("RGB", (SIZES[0] * 2, SIZES[0] * 2))
                image.seek(0)  # first frame of an animated PNG/WebP
                image.thumbnail((SIZES[0] * 2, SIZES[0] * 2))  # shrink right after decoding; later copies are small
                image = ImageOps.exif_transpose(image)  # apply rotation, then the EXIF is dropped
                image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                return ProcessedPhoto(large=_encode(image, SIZES[0]), thumb=_encode(image, SIZES[1]))
        except PhotoRejected:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise PhotoRejected("invalid_image", "The photo could not be read.") from error
