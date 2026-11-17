from app.auth.security import (
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)


def test_password_hash_is_argon2id_and_verifies_only_matching_password() -> None:
    password_hash = hash_password("a sufficiently long password")

    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "a sufficiently long password")
    assert not verify_password(password_hash, "a different password")


def test_session_tokens_are_opaque_and_stored_as_hashes() -> None:
    token = new_session_token()

    assert len(token) >= 43
    assert hash_token(token) != token.encode()
    assert hash_token(token) == hash_token(token)
