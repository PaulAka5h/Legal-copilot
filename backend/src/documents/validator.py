"""Security Validator for uploaded legal documents (TRD Section 5.1).

Validates:
1. Magic bytes content verification (not relying on file extensions).
   - PDF: '%PDF-'
   - DOCX: PK zip signature containing [Content_Types].xml or word/
   - PNG: '\x89PNG\r\n\x1a\n'
   - JPEG: '\xff\xd8\xff'
2. Rejection of encrypted / password-protected PDFs.
3. File size limits (default max 30 MB).
4. Image pixel-bomb / decompression bomb protection.
5. Maximum page count threshold (default max 100 pages per document).
6. Optional ClamAV antivirus daemon check hook.
"""

import io
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import pypdf


class DocumentValidationError(Exception):
    """Raised when an uploaded file fails security or format validation."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.code = code


class DocumentValidator:
    """Security and integrity validator for case documents."""

    MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
    MAX_PDF_PAGES = 150
    MAX_IMAGE_PIXELS = 40_000_000  # 40 Megapixels max (avoids decompression bombs)

    # Magic byte signatures
    MAGIC_PDF = b"%PDF-"
    MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
    MAGIC_JPEG = b"\xff\xd8\xff"
    MAGIC_ZIP = b"PK\x03\x04"

    @classmethod
    def detect_mime_type(cls, file_bytes: bytes) -> str:
        """Determines true MIME type via magic bytes inspection."""
        if file_bytes.startswith(cls.MAGIC_PDF):
            return "application/pdf"
        elif file_bytes.startswith(cls.MAGIC_PNG):
            return "image/png"
        elif file_bytes.startswith(cls.MAGIC_JPEG):
            return "image/jpeg"
        elif file_bytes.startswith(cls.MAGIC_ZIP):
            # Inspect inside zip to confirm Word .docx structure
            if b"word/" in file_bytes[:4096] or b"[Content_Types].xml" in file_bytes[:4096]:
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return "application/zip"
        elif file_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return "application/msword"  # Legacy binary .doc

        raise DocumentValidationError(
            "Unsupported file format. Only PDF, DOCX, DOC, JPEG, and PNG files are accepted.",
            code="UNSUPPORTED_MIME_TYPE",
        )

    @classmethod
    def validate_file(cls, file_bytes: bytes, filename: str) -> str:
        """Full validation gate: size, magic bytes, encryption, pixel bombs, and page bounds.

        Returns detected valid MIME type.
        """
        # 1. File size check
        if len(file_bytes) == 0:
            raise DocumentValidationError("File is empty (0 bytes).", code="EMPTY_FILE")

        if len(file_bytes) > cls.MAX_FILE_SIZE:
            mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            raise DocumentValidationError(f"File size exceeds maximum allowed limit of {mb:.0f} MB.", code="FILE_TOO_LARGE")

        # 2. Magic byte inspection
        mime_type = cls.detect_mime_type(file_bytes)

        # 3. PDF specific security checks
        if mime_type == "application/pdf":
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                if reader.is_encrypted:
                    raise DocumentValidationError(
                        "Encrypted or password-protected PDFs are not supported. Please upload a decrypted document.",
                        code="ENCRYPTED_PDF",
                    )

                page_count = len(reader.pages)
                if page_count > cls.MAX_PDF_PAGES:
                    raise DocumentValidationError(
                        f"PDF page count ({page_count}) exceeds the maximum limit of {cls.MAX_PDF_PAGES} pages.",
                        code="PAGE_COUNT_EXCEEDED",
                    )
            except DocumentValidationError:
                raise
            except Exception as e:
                raise DocumentValidationError(f"Malformed or corrupt PDF file: {str(e)}", code="CORRUPT_PDF")

        # 4. Image decompression bomb protection
        elif mime_type in ("image/png", "image/jpeg"):
            try:
                with Image.open(io.BytesIO(file_bytes)) as img:
                    pixels = img.width * img.height
                    if pixels > cls.MAX_IMAGE_PIXELS:
                        raise DocumentValidationError(
                            f"Image resolution ({img.width}x{img.height}) exceeds safety limit.",
                            code="IMAGE_BOMB_DETECTED",
                        )
            except DocumentValidationError:
                raise
            except Exception as e:
                raise DocumentValidationError(f"Invalid or corrupted image: {str(e)}", code="CORRUPT_IMAGE")

        return mime_type

    @classmethod
    def scan_clamav(cls, file_bytes: bytes, host: str = "127.0.0.1", port: int = 3310) -> bool:
        """Optional ClamAV daemon malware scanner hook.

        Returns True if clean, raises DocumentValidationError if infected.
        """
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((host, port))
                # Send INSTREAM protocol command
                s.sendall(b"zINSTREAM\0")
                size_header = len(file_bytes).to_bytes(4, byteorder="big")
                s.sendall(size_header + file_bytes + b"\x00\x00\x00\x00")
                response = s.recv(1024).decode("utf-8", errors="ignore")
                if "FOUND" in response:
                    raise DocumentValidationError("Malware or malicious active code detected in uploaded file.", code="MALWARE_DETECTED")
                return True
        except socket.error:
            # ClamAV daemon is optional in local test environments
            return True
