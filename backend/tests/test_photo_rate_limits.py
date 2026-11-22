"""Per-user rate limits on the profile photo endpoints (migration 0027).

All profile and case content is SAMPLE_DATA_NOT_REAL_LAW.
"""

import asyncio
import time
from uuid import UUID

import pytest

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.client_portal import extras
from app.database import create_database_engine
from app.lawyer import photo
from app.rate_limit import RateLimit, consume_user_quota
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_lawyer_profile import PHOTO_URL, image_bytes, put_photo
from tests.test_phase2_exit import register_login
from tests.test_ui_bug_fixes import _client_with_login


def test_photo_uploads_are_limited_per_user(api_client) -> None:
    register_login(api_client, "photo-rate-write")
    assert put_photo(api_client, b"%PDF-1.7 SAMPLE", "fake.jpg", "image/jpeg").status_code == 415  # counts too
    for _ in range(photo.PHOTO_WRITE_LIMIT.limit - 2):
        assert put_photo(api_client, image_bytes("PNG", size=(64, 64))).status_code == 200
    assert api_client.delete(PHOTO_URL, headers=ORIGIN).status_code == 200  # removals share the bucket
    blocked = put_photo(api_client, image_bytes("PNG", size=(64, 64)))
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == str(photo.PHOTO_WRITE_LIMIT.window_seconds)
    assert blocked.headers["content-type"].startswith("application/problem+json")
    assert api_client.delete(PHOTO_URL, headers=ORIGIN).status_code == 429

    other = new_client(api_client, 0)
    with other:  # the limit is per user
        register_login(other, "photo-rate-other")
        assert put_photo(other, image_bytes("PNG", size=(64, 64))).status_code == 200


def test_photo_serving_is_limited_per_user(api_client, monkeypatch) -> None:
    small = RateLimit("profile_photo_read", limit=3, window_seconds=3600)
    monkeypatch.setattr(photo, "PHOTO_READ_LIMIT", small)
    monkeypatch.setattr(extras, "PHOTO_READ_LIMIT", small)
    _, case_id = lawyer_with_case(api_client, "photo-rate-read")
    assert put_photo(api_client, image_bytes("PNG", size=(64, 64))).status_code == 200
    for _ in range(3):
        assert api_client.get(PHOTO_URL).status_code == 200
    blocked = api_client.get(PHOTO_URL)
    assert blocked.status_code == 429 and blocked.headers["retry-after"] == "3600"

    client = new_client(api_client, 0)
    with client:  # the client has their own count
        _client_with_login(api_client, client, case_id)
        url = f"/api/v1/client/cases/{case_id}/lawyer/photo"
        assert [client.get(url).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_rate_limit_window_resets_and_table_is_private(api_client, local_app_user_database_url) -> None:
    user_id = UUID(register_login(api_client, "photo-rate-window"))

    async def consume_three(rule: RateLimit) -> list[bool]:
        engine = create_database_engine(local_app_user_database_url)
        try:
            factory = async_sessionmaker(engine)
            return [await consume_user_quota(factory, user_id, rule) for _ in range(3)]
        finally:
            await engine.dispose()

    rule = RateLimit("test_window", limit=2, window_seconds=1)
    assert asyncio.run(consume_three(rule)) == [True, True, False]
    time.sleep(1.1)
    assert asyncio.run(consume_three(rule))[0] is True  # a new window
    # app_user cannot read the counters directly (RLS forced, no grants): only through the function.
    with pytest.raises(Exception, match="permission denied"):
        sql_as(local_app_user_database_url, user_id, "SELECT count(*) FROM public.user_rate_limits")
