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

    def test_missing_exp_rejected(self) -> None:
        import base64
        import hashlib
        import hmac
        import json

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "admin"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        signing_input = f"{header_b64}.{payload_b64}".encode()
        sig = hmac.new("test-secret".encode(), signing_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        token = f"{header_b64}.{payload_b64}.{sig_b64}"

        assert verify_jwt_token(token, secret_key="test-secret") is None

    def test_invalid_exp_type_rejected(self) -> None:
        import base64
        import hashlib
        import hmac
        import json

        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()

        for invalid_exp in (True, False, "9999999999", [12345], {"exp": 1}):
            payload = {"sub": "admin", "exp": invalid_exp}
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
            signing_input = f"{header_b64}.{payload_b64}".encode()
            sig = hmac.new("test-secret".encode(), signing_input, hashlib.sha256).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
            token = f"{header_b64}.{payload_b64}.{sig_b64}"

            assert verify_jwt_token(token, secret_key="test-secret") is None


class TestClientIp:
    def test_x_forwarded_for_header(self) -> None:
        from fastapi import Request
        from boun_scrape.api.rate_limit import _get_client_ip

        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 127.0.0.1")],
            "client": ("127.0.0.1", 12345),
        }
        request = Request(scope)
        assert _get_client_ip(request) == "203.0.113.195"

    def test_untrusted_proxy_ignores_forwarded_for(self) -> None:
        from fastapi import Request
        from boun_scrape.api.rate_limit import _get_client_ip

        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
            "client": ("198.51.100.25", 12345),
        }
        request = Request(scope)
        assert _get_client_ip(request) == "198.51.100.25"

    def test_fallback_to_client_host(self) -> None:
        from fastapi import Request
        from boun_scrape.api.rate_limit import _get_client_ip

        scope = {
            "type": "http",
            "headers": [],
            "client": ("192.168.1.10", 12345),
        }
        request = Request(scope)
        assert _get_client_ip(request) == "192.168.1.10"

    def test_no_client_unknown(self) -> None:
        from fastapi import Request
        from boun_scrape.api.rate_limit import _get_client_ip

        scope = {
            "type": "http",
            "headers": [],
            "client": None,
        }
        request = Request(scope)
        assert _get_client_ip(request) == "unknown"


class TestRateLimiter:
    def test_cleanup_empty_hits(self) -> None:
        import time
        from boun_scrape.api.rate_limit import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=0.01)
        limiter.check("1.2.3.4")
        assert "1.2.3.4" in limiter._hits
        time.sleep(0.02)
        # Next check should clear expired timestamps and record new hit
        limiter.check("1.2.3.4")
        assert len(limiter._hits["1.2.3.4"]) == 1
