from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from prefix_api.db.base import Base, TenantScoped, Timestamps, UUIDPrimaryKey


class Organization(UUIDPrimaryKey, Timestamps, Base):
    """A tenant: one hospital or hospital group."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    country_code: Mapped[str] = mapped_column(String(2))
    default_timezone: Mapped[str] = mapped_column(String(64))


class Facility(UUIDPrimaryKey, Timestamps, TenantScoped, Base):
    __tablename__ = "facility"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(500))
    maps_url: Mapped[str | None] = mapped_column(String(1000))
    phone: Mapped[str | None] = mapped_column(String(32))
