"""CSV parsing for the BOQ estimation engine.

Two entry points:

- :func:`parse_boq_csv` parses the bill-of-quantities file into
  :class:`~boq.models.BoqRow` records.
- :func:`parse_prices_csv` parses the unit-price file into a
  ``code -> PriceRow`` mapping.

Both return a ``(records, errors)`` tuple where ``errors`` is a list of
:class:`~boq.models.DataError` in line order. Rows with any data problem
are skipped (not returned as records) and reported through ``errors``.
"""

import csv
import os
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Union

from boq.models import (
    DUPLICATE_CODE,
    INVALID_NUMBER,
    INVALID_ROW,
    NEGATIVE_QUANTITY,
    BoqRow,
    DataError,
    PriceRow,
)

PathLike = Union[str, os.PathLike]

BOQ_HEADER = ["code", "description", "unit", "quantity", "group"]
PRICES_HEADER = ["code", "material_unit_price", "labor_unit_price", "unit"]


def _is_blank_row(raw: List[str]) -> bool:
    """Return True if every field of the raw row is empty or whitespace."""
    return all(cell.strip() == "" for cell in raw)


def _check_header(actual: List[str], expected: List[str], path: PathLike) -> None:
    """Raise ValueError if the CSV header does not match ``expected`` exactly."""
    if actual is None or [cell.strip() for cell in actual] != expected:
        raise ValueError(
            f"Invalid header in {path}: expected {expected}, got {actual!r}"
        )


def _parse_decimal(text: str) -> Decimal:
    """Parse a stripped string into Decimal; raise InvalidOperation on failure."""
    return Decimal(text)


def parse_boq_csv(path: PathLike) -> Tuple[List[BoqRow], List[DataError]]:
    """Parse a BOQ CSV file into BoqRow records.

    Args:
        path: Path to the CSV file. The header must be exactly
            ``code,description,unit,quantity,group`` (in that order).

    Returns:
        A ``(rows, errors)`` tuple. ``rows`` holds the successfully parsed
        :class:`~boq.models.BoqRow` records; ``errors`` holds one
        :class:`~boq.models.DataError` per rejected row, in line order.
        Blank lines are skipped silently. Line numbers are 1-based and
        follow the physical file lines (the header is line 1).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the header is wrong or misordered.
    """
    rows: List[BoqRow] = []
    errors: List[DataError] = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        _check_header(next(reader, None), BOQ_HEADER, path)

        for raw in reader:
            line_number = reader.line_num
            if _is_blank_row(raw):
                continue
            if len(raw) != len(BOQ_HEADER):
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_ROW,
                        message=(
                            f"Invalid row at line {line_number}: expected "
                            f"{len(BOQ_HEADER)} columns, got {len(raw)}"
                        ),
                        source="boq",
                    )
                )
                continue

            code, description, unit, quantity_text, group = (
                cell.strip() for cell in raw
            )
            if not code:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_ROW,
                        message=(
                            f"Invalid row at line {line_number}: "
                            "code is required but empty"
                        ),
                        source="boq",
                    )
                )
                continue

            try:
                quantity = _parse_decimal(quantity_text)
            except InvalidOperation:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid number at line {line_number} for code "
                            f"'{code}': quantity '{quantity_text}' is not a "
                            "valid decimal"
                        ),
                        source="boq",
                    )
                )
                continue

            if not quantity.is_finite():
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid number at line {line_number} for code "
                            f"'{code}': quantity '{quantity_text}' is not a "
                            "finite number"
                        ),
                        source="boq",
                    )
                )
                continue

            if quantity < 0:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=NEGATIVE_QUANTITY,
                        message=(
                            f"Negative quantity at line {line_number} for code "
                            f"'{code}': {quantity}"
                        ),
                        source="boq",
                    )
                )
                continue

            rows.append(
                BoqRow(
                    line_number=line_number,
                    code=code,
                    description=description,
                    unit=unit,
                    quantity=quantity,
                    group=group if group else "UNGROUPED",
                )
            )

    return rows, errors


def parse_prices_csv(
    path: PathLike,
) -> Tuple[Dict[str, PriceRow], List[DataError]]:
    """Parse a prices CSV file into a ``code -> PriceRow`` mapping.

    Args:
        path: Path to the CSV file. The header must be exactly
            ``code,material_unit_price,labor_unit_price,unit`` (in that order).

    Returns:
        A ``(price_map, errors)`` tuple. ``price_map`` maps each unique code
        to its first :class:`~boq.models.PriceRow`; duplicate codes produce
        a ``DUPLICATE_CODE`` error and keep the first occurrence. ``errors``
        is in line order. Blank lines are skipped silently. Line numbers are
        1-based and follow the physical file lines (the header is line 1).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the header is wrong or misordered.
    """
    price_map: Dict[str, PriceRow] = {}
    errors: List[DataError] = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        _check_header(next(reader, None), PRICES_HEADER, path)

        for raw in reader:
            line_number = reader.line_num
            if _is_blank_row(raw):
                continue
            if len(raw) != len(PRICES_HEADER):
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_ROW,
                        message=(
                            f"Invalid row at line {line_number}: expected "
                            f"{len(PRICES_HEADER)} columns, got {len(raw)}"
                        ),
                        source="prices",
                    )
                )
                continue

            code, material_text, labor_text, unit = (
                cell.strip() for cell in raw
            )
            if not code:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_ROW,
                        message=(
                            f"Invalid row at line {line_number}: "
                            "code is required but empty"
                        ),
                        source="prices",
                    )
                )
                continue

            try:
                material_unit_price = _parse_decimal(material_text)
            except InvalidOperation:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid number at line {line_number} for code "
                            f"'{code}': material_unit_price "
                            f"'{material_text}' is not a valid decimal"
                        ),
                        source="prices",
                    )
                )
                continue

            try:
                labor_unit_price = _parse_decimal(labor_text)
            except InvalidOperation:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid number at line {line_number} for code "
                            f"'{code}': labor_unit_price '{labor_text}' is "
                            "not a valid decimal"
                        ),
                        source="prices",
                    )
                )
                continue

            if not material_unit_price.is_finite() or not labor_unit_price.is_finite():
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid number at line {line_number} for code "
                            f"'{code}': prices must be finite numbers"
                        ),
                        source="prices",
                    )
                )
                continue

            if material_unit_price < 0 or labor_unit_price < 0:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=INVALID_NUMBER,
                        message=(
                            f"Invalid negative price at line {line_number} "
                            f"for code '{code}': material_unit_price="
                            f"{material_unit_price}, labor_unit_price="
                            f"{labor_unit_price}"
                        ),
                        source="prices",
                    )
                )
                continue

            if code in price_map:
                errors.append(
                    DataError(
                        line_number=line_number,
                        code=DUPLICATE_CODE,
                        message=(
                            f"Duplicate code '{code}' at line {line_number}: "
                            "first occurrence kept"
                        ),
                        source="prices",
                    )
                )
                continue

            price_map[code] = PriceRow(
                line_number=line_number,
                code=code,
                material_unit_price=material_unit_price,
                labor_unit_price=labor_unit_price,
                unit=unit,
            )

    return price_map, errors
