"""Strong ETags for cases (TRD §3.1 concurrency).

The tag is the case's ``updated_at`` in whole microseconds since the Unix epoch,
computed with exact integer arithmetic so it round-trips to the same timestamp
that PostgreSQL stored. ``If-Match`` must carry exactly one such tag.
"""

import re
from datetime import UTC, datetime, timedelta

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)
_TAG = re.compile(r'^"(\d{1,20})"$')


def case_etag(updated_at: datetime) -> str:
    return f'"{(updated_at - _EPOCH) // _MICROSECOND}"'


def parse_case_etag(if_match: str) -> datetime | None:
    """Return the timestamp an If-Match value names, or None if it is not our tag."""
    match = _TAG.match(if_match.strip())
    if match is None:
        return None
    try:
        return _EPOCH + int(match.group(1)) * _MICROSECOND
    except OverflowError:
        return None
