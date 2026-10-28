from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from prefix_api.domain.csv_import import MAX_CHARS


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    csv: Annotated[str, Field(max_length=MAX_CHARS)]
    """The whole file as text, header line first."""
    mapping: dict[str, str] = Field(default_factory=dict)
    """Header name to field name, for columns that are not named after their field."""
    dry_run: bool = True
    """Check every row and write nothing. A committed import writes only if every row is valid."""


class RowErrorOut(BaseModel):
    line: int
    column: str | None
    message: str


class ImportReportOut(BaseModel):
    kind: str
    rows: int
    valid_rows: int
    imported: int
    committed: bool
    ignored_columns: list[str]
    errors: list[RowErrorOut]
