"""Core data models for the BOQ estimation engine.

This module defines the contract shared by the parsing, validation, pricing
and reporting layers. Every other subagent depends on these names and
signatures, so they must not be renamed or changed without coordination.
"""

from dataclasses import dataclass, field
from decimal import Decimal

# Error code constants -------------------------------------------------------
DUPLICATE_CODE = "DUPLICATE_CODE"
MISSING_PRICE = "MISSING_PRICE"
UNIT_MISMATCH = "UNIT_MISMATCH"
NEGATIVE_QUANTITY = "NEGATIVE_QUANTITY"
INVALID_NUMBER = "INVALID_NUMBER"
INVALID_ROW = "INVALID_ROW"


@dataclass(frozen=True)
class BoqRow:
    """One validated data row from the BOQ CSV file."""

    line_number: int  # 1-based; the header is line 1
    code: str
    description: str
    unit: str
    quantity: Decimal
    group: str


@dataclass(frozen=True)
class PriceRow:
    """One validated data row from the prices CSV file."""

    line_number: int  # 1-based; the header is line 1
    code: str
    material_unit_price: Decimal
    labor_unit_price: Decimal
    unit: str


@dataclass(frozen=True)
class DataError:
    """A single data problem found while parsing or validating."""

    line_number: int
    code: str  # one of the DUPLICATE_CODE / ... constants above
    message: str  # English, descriptive, mentions the related code/line
    source: str  # "boq" or "prices"


@dataclass(frozen=True)
class ValidatedLine:
    """A BOQ row successfully matched to its price row."""

    row: BoqRow
    price: PriceRow


@dataclass
class GroupSummary:
    """Aggregated money amounts for one group (or for the whole estimate)."""

    material: Decimal = field(default_factory=lambda: Decimal("0"))
    labor: Decimal = field(default_factory=lambda: Decimal("0"))
    subtotal: Decimal = field(default_factory=lambda: Decimal("0"))
    vat: Decimal = field(default_factory=lambda: Decimal("0"))
    total: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class EstimationResult:
    """Final output of the estimation pipeline."""

    groups: dict  # group name -> GroupSummary, sorted by group name
    totals: GroupSummary
    errors: list  # list[DataError], in line order
    excluded_rows: list  # list[int] of excluded line numbers, sorted
