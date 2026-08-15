"""Unit tests for JWT and password verification primitives."""

import bcrypt
import pytest

from boun_scrape.api.auth import (
    create_jwt_token,
    verify_jwt_token,
    verify_password,
)


class TestVerifyPassword:
    def test_correct_bcrypt_password_verifies(self) -> None:
        pwd_hash = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt()).decode()
        assert verify_password("correcthorse", pwd_hash) is True

    def test_incorrect_password_rejected(self) -> None:
        pwd_hash = bcrypt.hashpw(b"correcthorse", bcrypt.gensalt()).decode()
        assert verify_password("wrongpassword", pwd_hash) is False

    def test_literal_admin_hash_is_not_a_backdoor(self) -> None:
        """Regression: stored hash literally 'admin' must never authenticate 'admin'."""
        assert verify_password("admin", "admin") is False

    def test_default_admin_hash_sentinel_is_not_a_backdoor(self) -> None:
        """Regression: a hash containing 'default_admin_hash' must never bypass verification."""
        assert verify_password("admin", "default_admin_hash_marker") is False

    def test_plaintext_equal_to_hash_is_rejected(self) -> None:
        """Regression: a misconfigured plaintext-stored password must not authenticate."""
        assert verify_password("mypassword", "mypassword") is False

    def test_sha256_hash_no_longer_accepted(self) -> None:
        import hashlib

        sha256_hash = hashlib.sha256(b"secret").hexdigest()
        assert verify_password("secret", sha256_hash) is False

    def test_empty_inputs_rejected(self) -> None:
        assert verify_password("", "somehash") is False
        assert verify_password("password", "") is False


class TestJwt:
    def test_round_trip(self) -> None:
        token = create_jwt_token({"sub": "admin"}, secret_key="test-secret")
        payload = verify_jwt_token(token, secret_key="test-secret")
        assert payload is not None
        assert payload["sub"] == "admin"

    def test_wrong_secret_rejected(self) -> None:
        token = create_jwt_token({"sub": "admin"}, secret_key="test-secret")
        assert verify_jwt_token(token, secret_key="wrong-secret") is None

    def test_tampered_alg_header_rejected(self) -> None:
        import base64
        import json

        token = create_jwt_token({"sub": "admin"}, secret_key="test-secret")
        header_b64, payload_b64, sig_b64 = token.split(".")

        forged_header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        forged_token = f"{forged_header}.{payload_b64}.{sig_b64}"
        assert verify_jwt_token(forged_token, secret_key="test-secret") is None

    def test_malformed_token_rejected(self) -> None:
        assert verify_jwt_token("not-a-jwt", secret_key="test-secret") is None
        assert verify_jwt_token("a.b", secret_key="test-secret") is None
