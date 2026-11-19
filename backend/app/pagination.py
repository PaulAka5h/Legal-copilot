"""Cursor pagination (TRD §3.1: ``?cursor=...&limit=...``).

Cursors are opaque keyset positions ``(timestamp, id)`` encoded as base64url
JSON. They carry no authorization meaning: every page query still runs under
RLS and the endpoint's own SQL filters, so a forged cursor can only reposition
within rows the caller may already see. Malformed cursors return 400.
"""

import base64
import binascii
import json
from datetime import datetime
from collections.abc import Callable
from typing import Annotated, Generic, TypeVar

from fastapi import HTTPException, Query, status
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

CursorQuery = Annotated[
    str | None,
    Query(
        max_length=512,
        description="Opaque cursor from the previous page's `next_cursor`; omit for the first page.",
    ),
]
LimitQuery = Annotated[
    int,
    Query(ge=1, le=MAX_PAGE_SIZE, description=f"Page size, 1 to {MAX_PAGE_SIZE}."),
]


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = Field(
        description="Pass as `cursor` to fetch the next page; null on the last page."
    )


class Keyset(BaseModel):
    at: datetime
    id: str


def encode_cursor(at: datetime, row_id: object) -> str:
    raw = json.dumps({"at": at.isoformat(), "id": str(row_id)}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None, id_parser: Callable[[str], object]) -> tuple[datetime, object] | None:
    """Return ``(timestamp, parsed_id)`` or None; any malformed cursor is a 400."""
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        keyset = Keyset.model_validate_json(base64.urlsafe_b64decode(padded.encode("ascii")))
        return keyset.at, id_parser(keyset.id)
    except (ValueError, binascii.Error, UnicodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The pagination cursor is invalid.",
        ) from exc


def build_page(rows: list[T], limit: int, key: Callable[[T], tuple[datetime, object]]) -> CursorPage[T]:
    """``rows`` was fetched with ``LIMIT limit + 1``; ``key(row)`` -> (timestamp, id)."""
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(*key(items[-1])) if has_more and items else None
    return CursorPage[T](items=items, next_cursor=next_cursor)
