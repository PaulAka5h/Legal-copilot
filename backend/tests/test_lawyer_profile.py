"""Lawyer profile details, profile photo and per-field client visibility.

All profile and case content is SAMPLE_DATA_NOT_REAL_LAW.
"""

import io
import secrets
import unicodedata

import pytest
from PIL import Image

from app.lawyer.avatar import MAX_PHOTO_BYTES, PhotoRejected, process_photo
from tests.step_c_helpers import ORIGIN, lawyer_with_case, new_client, sql_as
from tests.test_phase2_exit import create_case, register_login
from tests.test_ui_bug_fixes import _client_with_login

PHOTO_URL = "/api/v1/lawyer/profile/photo"
PROFILE_URL = "/api/v1/lawyer/profile"


def image_bytes(fmt: str, size=(800, 600), color=(40, 90, 60), exif: bool = False) -> bytes:
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    kwargs = {}
    if exif:
        data = Image.Exif()
        data[0x010F] = "SAMPLE camera make"  # Make
        data[0x0131] = "SAMPLE software"  # Software
        data[0x0112] = 6  # Orientation: rotate 90 degrees clockwise
        kwargs = {"exif": data.tobytes(), "icc_profile": b"SAMPLE icc"}
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def put_photo(client, data: bytes, filename: str = "photo.png", content_type: str = "image/png"):
    return client.put(PHOTO_URL, headers=ORIGIN, files={"file": (filename, data, content_type)})


def opened(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    assert image.format == "WEBP"
    return image


# --- processing (no database) ---------------------------------------------------------------

def test_photo_is_resized_center_cropped_and_stripped_of_metadata() -> None:
    source = image_bytes("JPEG", size=(1200, 600), exif=True)
    assert Image.open(io.BytesIO(source)).getexif()  # the fixture really carries EXIF
    photo = process_photo(source)
    for data, size in ((photo.large, 512), (photo.thumb, 96)):
        image = opened(data)
        assert image.size == (size, size)
        assert not image.getexif()
        assert not {"exif", "icc_profile", "xmp"} & set(image.info)
        assert b"SAMPLE" not in data


def test_photo_accepts_png_and_webp_by_content() -> None:
    for fmt in ("PNG", "WEBP"):
        assert opened(process_photo(image_bytes(fmt)).thumb).size == (96, 96)


@pytest.mark.parametrize(("data", "code"), [
    (b"", "empty_file"),
    (b"%PDF-1.7 SAMPLE", "unsupported_type"),
    (b"GIF89a" + b"\x00" * 64, "unsupported_type"),
    (b"\xff\xd8\xff" + b"\x00" * (MAX_PHOTO_BYTES - 2), "file_too_large"),
    (b"\x89PNG\r\n\x1a\nnot really a png", "invalid_image"),
])
def test_photo_rejections(data: bytes, code: str) -> None:
    with pytest.raises(PhotoRejected) as caught:
        process_photo(data)
    assert caught.value.code == code


def test_pixel_limit_is_checked_before_decoding() -> None:
    out = io.BytesIO()
    Image.new("1", (8000, 8000)).save(out, format="PNG")  # 64 MP, a few KB on disk
    assert len(out.getvalue()) < MAX_PHOTO_BYTES
    with pytest.raises(PhotoRejected) as caught:
        process_photo(out.getvalue())
    assert caught.value.code == "image_too_large"


# --- API ------------------------------------------------------------------------------------

def test_photo_upload_validation(api_client) -> None:
    register_login(api_client, "photo-upload")
    too_large = put_photo(api_client, b"\xff\xd8\xff" + b"\x00" * MAX_PHOTO_BYTES, "big.jpg", "image/jpeg")
    assert too_large.status_code == 413
    pdf = b"%PDF-1.7\n% SAMPLE_DATA_NOT_REAL_LAW\n"
    assert put_photo(api_client, pdf, "doc.pdf", "application/pdf").status_code == 415
    # A fake extension and Content-Type do not help: the bytes decide.
    assert put_photo(api_client, pdf, "photo.jpg", "image/jpeg").status_code == 415
    renamed_png = put_photo(api_client, image_bytes("PNG"), "photo.pdf", "application/pdf")
    assert renamed_png.status_code == 200, renamed_png.text
    assert put_photo(api_client, image_bytes("PNG")).status_code == 200
    assert api_client.put(PHOTO_URL, files={"file": ("p.png", image_bytes("PNG"), "image/png")}).status_code == 403


def test_photo_upload_serve_replace_and_remove(api_client, local_app_user_database_url) -> None:
    user_id = register_login(api_client, "photo-cycle")
    assert api_client.get(PHOTO_URL).status_code == 404  # no photo yet: the UI shows initials
    assert api_client.get(PROFILE_URL).json()["photo_id"] is None

    first = put_photo(api_client, image_bytes("JPEG", exif=True), "me.jpg", "image/jpeg")
    assert first.status_code == 200, first.text
    first_id = first.json()["photo_id"]
    assert api_client.get(PROFILE_URL).json()["photo_id"] == first_id
    thumb = api_client.get(PHOTO_URL)
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    assert thumb.headers["cache-control"].startswith("private")
    assert opened(thumb.content).size == (96, 96) and not opened(thumb.content).getexif()
    assert opened(api_client.get(PHOTO_URL, params={"size": 512}).content).size == (512, 512)
    assert api_client.get(PHOTO_URL, params={"size": 300}).status_code == 422

    second = put_photo(api_client, image_bytes("WEBP", color=(200, 30, 30)), "me.webp", "image/webp")
    assert second.status_code == 200 and second.json()["photo_id"] != first_id
    assert api_client.get(PROFILE_URL).json()["photo_id"] == second.json()["photo_id"]

    assert api_client.delete(PHOTO_URL).status_code == 403  # CSRF
    removed = api_client.delete(PHOTO_URL, headers=ORIGIN)
    assert removed.status_code == 200 and removed.json()["photo_id"] is None
    assert api_client.get(PHOTO_URL).status_code == 404

    actions = [row[0] for row in sql_as(
        local_app_user_database_url, user_id,
        "SELECT action FROM public.audit_logs WHERE actor_user_id = :u AND action LIKE 'lawyer.photo_%' "
        "ORDER BY id", u=user_id)]
    assert actions == ["lawyer.photo_updated", "lawyer.photo_updated", "lawyer.photo_removed"]


def test_profile_details_validation_and_nfc(api_client) -> None:
    register_login(api_client, "profile-details")
    decomposed_bio = unicodedata.normalize("NFD", "SAMPLE_DATA_NOT_REAL_LAW দেওয়ানি ও ফৌজদারি মামলা।")
    saved = api_client.patch(PROFILE_URL, headers=ORIGIN, json={
        "bar_enrollment_no": " SAMPLE-1234 ",
        "courts": ["Supreme Court – High Court Division", "District Court", "District Court", ""],
        "practice_areas": ["criminal", "cheque_ni_act", "criminal"],
        "years_experience": 12,
        "office_address": "SAMPLE Chamber, Dhaka",
        "languages": ["bn", "en"],
        "bio": decomposed_bio,
        "public_phone": "017 1234-5678",
        "public_email": "chamber@example.com",
    })
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["bar_enrollment_no"] == "SAMPLE-1234"
    assert body["courts"] == ["Supreme Court – High Court Division", "District Court"]
    assert body["practice_areas"] == ["criminal", "cheque_ni_act"]
    assert body["public_phone"] == "+8801712345678"
    assert body["bio"] == unicodedata.normalize("NFC", decomposed_bio) != decomposed_bio
    assert body["client_visible_fields"] == ["photo", "firm", "phone"]  # default

    for bad in ({"public_phone": "+8801212345678"}, {"public_phone": "12345"}, {"public_email": "not-an-email"},
                {"bio": "x" * 501}, {"years_experience": 81}, {"practice_areas": ["tax"]},
                {"languages": ["fr"]}, {"courts": ["x" * 151]}, {"client_visible_fields": ["login_email"]},
                {"client_visible_fields": None}):
        assert api_client.patch(PROFILE_URL, headers=ORIGIN, json=bad).status_code == 422, bad
    assert api_client.patch(PROFILE_URL, headers=ORIGIN, json={"bio": "ব" * 500}).status_code == 200
    cleared = api_client.patch(PROFILE_URL, headers=ORIGIN, json={"public_phone": None, "courts": []}).json()
    assert cleared["public_phone"] is None and cleared["courts"] == []


def test_client_sees_only_the_fields_the_lawyer_allows(api_client) -> None:
    _, case_id = lawyer_with_case(api_client, "visibility")
    assert api_client.patch(PROFILE_URL, headers=ORIGIN, json={
        "chamber_name": "SAMPLE Chamber", "public_phone": "+8801812345678", "public_email": "pub@example.com",
        "bar_enrollment_no": "SAMPLE-77", "courts": ["District Court"], "practice_areas": ["land"],
        "years_experience": 5, "office_address": "SAMPLE address", "languages": ["bn"], "bio": "SAMPLE bio",
    }).status_code == 200
    photo_id = put_photo(api_client, image_bytes("PNG")).json()["photo_id"]
    client = new_client(api_client, 0)
    with client:
        _client_with_login(api_client, client, case_id)
        card_url = f"/api/v1/client/cases/{case_id}/lawyer"
        card = client.get(card_url).json()
        assert card["photo_id"] == photo_id and card["firm"] == "SAMPLE Chamber"
        assert card["phone"] == "+8801812345678"
        hidden = ("email", "bar_enrollment_no", "courts", "practice_areas", "years_experience", "office_address",
                  "languages", "bio")
        assert all(card[field] is None for field in hidden)
        assert "lawyer_user_id" not in card and "avatar_id" not in card
        photo = client.get(f"{card_url}/photo", params={"size": 512})
        assert photo.status_code == 200 and opened(photo.content).size == (512, 512)

        assert api_client.patch(PROFILE_URL, headers=ORIGIN,
                                json={"client_visible_fields": ["email", "bio", "courts"]}).status_code == 200
        card = client.get(card_url).json()
        assert (card["email"], card["bio"], card["courts"]) == ("pub@example.com", "SAMPLE bio", ["District Court"])
        assert (card["photo_id"], card["firm"], card["phone"], card["practice_areas"]) == (None, None, None, None)
        assert client.get(f"{card_url}/photo").status_code == 404  # photo hidden


def test_another_lawyers_photo_is_not_accessible(api_client) -> None:
    _, case_id = lawyer_with_case(api_client, "photo-owner")
    assert put_photo(api_client, image_bytes("PNG")).status_code == 200
    other_lawyer, other_client = new_client(api_client, 0), new_client(api_client, 0)
    with other_lawyer, other_client:
        register_login(other_lawyer, "photo-other")
        assert other_lawyer.get(PHOTO_URL).status_code == 404  # their own (none), never someone else's
        assert other_lawyer.get(f"/api/v1/client/cases/{case_id}/lawyer/photo").status_code == 403  # client API
        other_case = create_case(other_lawyer, f"SAMPLE-photo-{secrets.token_hex(3)}")
        _client_with_login(other_lawyer, other_client, other_case)
        assert other_client.get(f"/api/v1/client/cases/{case_id}/lawyer/photo").status_code == 404
        assert other_client.get(f"/api/v1/client/cases/{case_id}/lawyer").status_code == 404
