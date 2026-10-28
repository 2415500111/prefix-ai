"""CSV parsing for imports: headers, column mapping and row shape. No database access here.

Error messages name columns and rules, never cell values, so patient data cannot leak into
an error report or a log line.
"""

import csv
import io
from dataclasses import dataclass

MAX_ROWS = 500
MAX_CHARS = 1_000_000

_TRUE_WORDS = frozenset({"yes", "y", "true", "1"})
_FALSE_WORDS = frozenset({"", "no", "n", "false", "0"})


class CsvFormatError(ValueError):
    """The file as a whole cannot be imported. The message says why, never what the data is."""


@dataclass(frozen=True, slots=True)
class CsvRow:
    line: int
    """The line in the file the row starts on (the header is line 1)."""
    values: dict[str, str]
    """Field name to trimmed cell text. Blank cells are left out."""


@dataclass(frozen=True, slots=True)
class CsvTable:
    rows: list[CsvRow]
    ignored_columns: list[str]


def normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def parse_flag(text: str) -> bool | None:
    """Yes or no, as a clinic would write it. None when the word is not recognised."""
    word = text.strip().lower()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    return None


def read_table(
    text: str,
    *,
    fields: frozenset[str],
    required: frozenset[str],
    mapping: dict[str, str],
) -> CsvTable:
    """Read a CSV whose first line is a header.

    A header matches a field when its normalised name equals the field name, or when
    ``mapping`` says so (``{"DOB": "date_of_birth"}``). Unknown columns are ignored and listed.
    """
    if len(text) > MAX_CHARS:
        raise CsvFormatError("The file is larger than 1 MB")
    targets = {normalize_header(header): field for header, field in mapping.items()}
    for field in targets.values():
        if field not in fields:
            raise CsvFormatError(f"The mapping points at an unknown field: {field}")

    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header_row = next(reader, None)
    if header_row is None or not any(cell.strip() for cell in header_row):
        raise CsvFormatError("The file is empty")

    columns: dict[int, str] = {}
    ignored: list[str] = []
    for index, header in enumerate(header_row):
        name = normalize_header(header)
        if not name:
            continue
        field = targets.get(name, name)
        if field not in fields:
            ignored.append(header.strip())
            continue
        if field in columns.values():
            raise CsvFormatError(f"Two columns map to {field}")
        columns[index] = field
    missing = sorted(required - set(columns.values()))
    if missing:
        raise CsvFormatError(f"Missing required column: {', '.join(missing)}")

    rows: list[CsvRow] = []
    for cells in reader:
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) == MAX_ROWS:
            raise CsvFormatError(f"The file has more than {MAX_ROWS} rows; split it")
        values: dict[str, str] = {}
        for index, field in columns.items():
            cell = cells[index].strip() if index < len(cells) else ""
            if cell:
                values[field] = cell
        rows.append(CsvRow(line=reader.line_num, values=values))
    return CsvTable(rows=rows, ignored_columns=ignored)
