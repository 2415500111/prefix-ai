import datetime as dt
from enum import StrEnum

from sqlalchemy import Dialect, Enum, Text
from sqlalchemy.types import TypeDecorator

from prefix_api.core.crypto import get_field_cipher


class EncryptedString(TypeDecorator[str]):
    """Text column encrypted with AES-GCM; ``context`` binds ciphertexts to this column."""

    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_field_cipher().encrypt(value, self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_field_cipher().decrypt(value, self.context)


class EncryptedDate(TypeDecorator[dt.date]):
    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: dt.date | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_field_cipher().encrypt(value.isoformat(), self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> dt.date | None:
        if value is None:
            return None
        return dt.date.fromisoformat(get_field_cipher().decrypt(value, self.context))


def str_enum[E: StrEnum](enum_cls: type[E], name: str) -> Enum:
    """Store enum *values* as VARCHAR with a CHECK constraint (easy to extend later)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=40,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
