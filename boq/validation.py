"""Validation layer for the BOQ estimation engine.

:func:`validate` matches parsed :class:`~boq.models.BoqRow` records against
the price map built by :func:`boq.parsing.parse_prices_csv`, producing the
list of valid (row, price) pairs plus one :class:`~boq.models.DataError`
per rejected row.
"""

from typing import Dict, List, Tuple

from boq.models import (
    DUPLICATE_CODE,
    MISSING_PRICE,
    UNIT_MISMATCH,
    BoqRow,
    DataError,
    PriceRow,
    ValidatedLine,
)


def validate(
    boq_rows: List[BoqRow], price_map: Dict[str, PriceRow]
) -> Tuple[List[ValidatedLine], List[DataError]]:
    """Validate BOQ rows against the price map.

    For each row, in order, the checks run in this priority and at most one
    error is reported per row (the first one encountered):

    1. The code was already seen in an earlier row -> ``DUPLICATE_CODE``
       (the first occurrence is kept, later duplicates are rejected).
    2. The code has no entry in ``price_map`` -> ``MISSING_PRICE``.
    3. The row's unit differs from the price row's unit (compared after
       stripping, case-sensitive) -> ``UNIT_MISMATCH``.

    Args:
        boq_rows: Parsed BOQ rows in file order.
        price_map: Mapping of price code -> :class:`~boq.models.PriceRow`.

    Returns:
        A ``(valid_lines, errors)`` tuple. ``valid_lines`` holds
        :class:`~boq.models.ValidatedLine` pairs in row order; ``errors``
        holds the :class:`~boq.models.DataError` records (source ``"boq"``),
        also in row order.
    """
    valid_lines: List[ValidatedLine] = []
    errors: List[DataError] = []
    seen_codes = set()

    for row in boq_rows:
        if row.code in seen_codes:
            errors.append(
                DataError(
                    line_number=row.line_number,
                    code=DUPLICATE_CODE,
                    message=(
                        f"Duplicate code '{row.code}' at line "
                        f"{row.line_number}: first occurrence kept"
                    ),
                    source="boq",
                )
            )
            continue
        seen_codes.add(row.code)

        price = price_map.get(row.code)
        if price is None:
            errors.append(
                DataError(
                    line_number=row.line_number,
                    code=MISSING_PRICE,
                    message=(
                        f"Missing price at line {row.line_number}: "
                        f"no price entry for code '{row.code}'"
                    ),
                    source="boq",
                )
            )
            continue

        if row.unit.strip() != price.unit.strip():
            errors.append(
                DataError(
                    line_number=row.line_number,
                    code=UNIT_MISMATCH,
                    message=(
                        f"Unit mismatch at line {row.line_number} for code "
                        f"'{row.code}': BOQ unit '{row.unit}' does not match "
                        f"price unit '{price.unit}'"
                    ),
                    source="boq",
                )
            )
            continue

        valid_lines.append(ValidatedLine(row=row, price=price))

    return valid_lines, errors
