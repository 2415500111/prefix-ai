import pytest
from api_testkit import TEST_KEY_ACTIVE, TEST_KEY_OLD

from prefix_api.core.crypto import BlindIndexer, CryptoError, FieldCipher, generate_key

CONTEXT = "patient.first_name"


@pytest.fixture
def cipher() -> FieldCipher:
    return FieldCipher.from_entries([TEST_KEY_ACTIVE, TEST_KEY_OLD])


def test_round_trip(cipher: FieldCipher) -> None:
    token = cipher.encrypt("Asha Verma", CONTEXT)

    assert token.startswith("enc:v1:test2:")
    assert "Asha" not in token
    assert cipher.decrypt(token, CONTEXT) == "Asha Verma"


def test_unicode_round_trip(cipher: FieldCipher) -> None:
    assert cipher.decrypt(cipher.encrypt("आशा वर्मा", CONTEXT), CONTEXT) == "आशा वर्मा"


def test_same_plaintext_encrypts_differently_each_time(cipher: FieldCipher) -> None:
    assert cipher.encrypt("same", CONTEXT) != cipher.encrypt("same", CONTEXT)


def test_tampered_ciphertext_is_rejected(cipher: FieldCipher) -> None:
    token = cipher.encrypt("Asha", CONTEXT)
    tampered = token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]

    with pytest.raises(CryptoError, match="authentication"):
        cipher.decrypt(tampered, CONTEXT)


def test_ciphertext_cannot_be_moved_to_another_column(cipher: FieldCipher) -> None:
    token = cipher.encrypt("+919876543210", "patient.phone")

    with pytest.raises(CryptoError):
        cipher.decrypt(token, "patient.email")


def test_old_key_still_decrypts_after_rotation() -> None:
    old_only = FieldCipher.from_entries([TEST_KEY_OLD])
    rotated = FieldCipher.from_entries([TEST_KEY_ACTIVE, TEST_KEY_OLD])
    legacy_token = old_only.encrypt("legacy value", CONTEXT)

    assert rotated.decrypt(legacy_token, CONTEXT) == "legacy value"
    assert rotated.needs_rotation(legacy_token)
    assert not rotated.needs_rotation(rotated.encrypt("new value", CONTEXT))


def test_retired_key_cannot_decrypt() -> None:
    old_only = FieldCipher.from_entries([TEST_KEY_OLD])
    new_only = FieldCipher.from_entries([TEST_KEY_ACTIVE])

    with pytest.raises(CryptoError, match="Unknown encryption key"):
        new_only.decrypt(old_only.encrypt("x", CONTEXT), CONTEXT)


@pytest.mark.parametrize(
    "entries",
    [
        [],
        ["no-separator"],
        ["bad id!:" + generate_key()],
        ["k1:" + generate_key()[:-4]],
        ["k1:" + generate_key(), "k1:" + generate_key()],
    ],
)
def test_misconfigured_keys_are_rejected(entries: list[str]) -> None:
    with pytest.raises(CryptoError):
        FieldCipher.from_entries(entries)


def test_plaintext_is_not_accepted_as_ciphertext(cipher: FieldCipher) -> None:
    with pytest.raises(CryptoError):
        cipher.decrypt("Asha", CONTEXT)


def test_blind_index_is_deterministic_and_context_separated() -> None:
    indexer = BlindIndexer(key=b"k" * 32)

    assert indexer.index("+919876543210", "phone") == indexer.index("+919876543210", "phone")
    assert indexer.index("x", "phone") != indexer.index("x", "email")
    assert BlindIndexer(key=b"z" * 32).index("x", "phone") != indexer.index("x", "phone")
