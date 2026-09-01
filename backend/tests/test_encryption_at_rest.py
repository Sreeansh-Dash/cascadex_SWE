"""
tests/test_encryption_at_rest.py — Phase 09

Verifies that the field-level encryption helpers work correctly:

1. When FIELD_ENCRYPTION_KEY is set, encrypt_field produces ciphertext (not plaintext).
2. decrypt_field on the ciphertext recovers the original plaintext.
3. When FIELD_ENCRYPTION_KEY is empty (passthrough mode), encrypt_field returns
   the original string unchanged — dev/test mode is safe.
4. Round-trip fidelity: encrypt then decrypt always returns the original string.

Note: These unit tests do NOT require Neo4j — they test the crypto helpers
directly.  The integration path (ScanRecord written → raw Neo4j property is
ciphertext) is covered separately in conftest-backed test fixtures if a real
FIELD_ENCRYPTION_KEY is provided; otherwise, the passthrough path is validated.
"""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_key() -> str:
    """Generate a valid Fernet key as a decoded string."""
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Unit tests — crypto helpers
# ---------------------------------------------------------------------------


class TestEncryptFieldWithKey:
    """Tests when a valid FIELD_ENCRYPTION_KEY is configured."""

    def setup_method(self) -> None:
        """Set a valid Fernet key before each test."""
        self._key = _generate_key()
        os.environ["FIELD_ENCRYPTION_KEY"] = self._key
        # Force settings reload — pydantic_settings caches on import
        import importlib

        from app.core import config
        importlib.reload(config)
        # Re-import security to pick up reloaded settings
        from app.core import security
        importlib.reload(security)

    def teardown_method(self) -> None:
        """Remove key override after each test."""
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        import importlib

        from app.core import config, security
        importlib.reload(config)
        importlib.reload(security)

    def test_encrypt_produces_ciphertext(self) -> None:
        """encrypt_field returns a Fernet token, not the original plaintext."""
        from app.core.security import encrypt_field
        plaintext = "warfarin 5mg daily"
        ciphertext = encrypt_field(plaintext)
        assert ciphertext != plaintext, "Expected ciphertext, got plaintext back"
        # Fernet tokens start with gAAAAA (URL-safe base64 token header)
        assert len(ciphertext) > len(plaintext)

    def test_decrypt_recovers_plaintext(self) -> None:
        """decrypt_field reverses encrypt_field exactly."""
        from app.core.security import decrypt_field, encrypt_field
        plaintext = "metformin 500mg twice daily"
        ciphertext = encrypt_field(plaintext)
        recovered = decrypt_field(ciphertext)
        assert recovered == plaintext

    def test_round_trip_fidelity(self) -> None:
        """Multiple encrypt/decrypt cycles always return the original string."""
        from app.core.security import decrypt_field, encrypt_field
        for text in [
            "warfarin",
            "Patient OCR text with spaces and 5mg dosage",
            "Atorvastatin 10 mg tablet — take at bedtime",
            "",  # edge case: empty string
        ]:
            result = decrypt_field(encrypt_field(text))
            assert result == text, f"Round-trip failed for: {text!r}"

    def test_ciphertext_differs_per_call(self) -> None:
        """Fernet uses random IVs — same plaintext produces different tokens."""
        from app.core.security import encrypt_field
        plaintext = "aspirin"
        c1 = encrypt_field(plaintext)
        c2 = encrypt_field(plaintext)
        # With random IV, ciphertexts should not be identical
        assert c1 != c2, "Expected different ciphertext per call (random IV)"


class TestEncryptFieldPassthrough:
    """Tests when FIELD_ENCRYPTION_KEY is empty (dev/test passthrough mode)."""

    def setup_method(self) -> None:
        """Ensure empty key before each test."""
        os.environ["FIELD_ENCRYPTION_KEY"] = ""
        import importlib

        from app.core import config, security
        importlib.reload(config)
        importlib.reload(security)

    def teardown_method(self) -> None:
        """Clean up after each test."""
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        import importlib

        from app.core import config, security
        importlib.reload(config)
        importlib.reload(security)

    def test_passthrough_returns_plaintext(self) -> None:
        """Without a key, encrypt_field returns the original string unchanged."""
        from app.core.security import encrypt_field
        plaintext = "warfarin"
        result = encrypt_field(plaintext)
        assert result == plaintext

    def test_passthrough_decrypt_is_identity(self) -> None:
        """Without a key, decrypt_field is a no-op."""
        from app.core.security import decrypt_field
        text = "aspirin 100mg"
        assert decrypt_field(text) == text


class TestInvalidKey:
    """Tests for bad/malformed key detection."""

    def test_invalid_key_raises_value_error(self) -> None:
        """A non-Fernet key string must raise ValueError on first use."""
        os.environ["FIELD_ENCRYPTION_KEY"] = "this_is_not_a_valid_fernet_key"
        import importlib

        from app.core import config, security
        importlib.reload(config)
        importlib.reload(security)
        try:
            from app.core.security import encrypt_field
            with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEY"):
                encrypt_field("test")
        finally:
            os.environ.pop("FIELD_ENCRYPTION_KEY", None)
            importlib.reload(config)
            importlib.reload(security)
