"""Red phase: tests for boq.validation written BEFORE any implementation exists."""

import unittest
from decimal import Decimal

from boq.models import (
    BoqRow,
    PriceRow,
    ValidatedLine,
    DUPLICATE_CODE,
    MISSING_PRICE,
    UNIT_MISMATCH,
)
from boq.validation import validate


def make_boq_row(line_number, code, unit="m3", quantity="10", group="Structure"):
    return BoqRow(
        line_number=line_number,
        code=code,
        description=f"desc-{code}",
        unit=unit,
        quantity=Decimal(quantity),
        group=group,
    )


def make_price_row(line_number, code, unit="m3"):
    return PriceRow(
        line_number=line_number,
        code=code,
        material_unit_price=Decimal("100"),
        labor_unit_price=Decimal("20"),
        unit=unit,
    )


class ValidateTest(unittest.TestCase):
    def test_validate_all_valid(self):
        rows = [make_boq_row(2, "B1"), make_boq_row(3, "B2")]
        price_map = {"B1": make_price_row(2, "B1"), "B2": make_price_row(3, "B2")}
        valid, errors = validate(rows, price_map)
        self.assertEqual(errors, [])
        self.assertEqual(len(valid), 2)
        self.assertIsInstance(valid[0], ValidatedLine)
        self.assertIs(valid[0].row, rows[0])
        self.assertIs(valid[0].price, price_map["B1"])
        self.assertIs(valid[1].row, rows[1])

    def test_validate_missing_price(self):
        rows = [make_boq_row(2, "B1"), make_boq_row(3, "NOPE")]
        price_map = {"B1": make_price_row(2, "B1")}
        valid, errors = validate(rows, price_map)
        self.assertEqual(len(valid), 1)
        self.assertIs(valid[0].row, rows[0])
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.code, MISSING_PRICE)
        self.assertEqual(e.source, "boq")
        self.assertEqual(e.line_number, 3)
        self.assertIn("NOPE", e.message)

    def test_validate_unit_mismatch(self):
        rows = [make_boq_row(2, "B1", unit="m3")]
        price_map = {"B1": make_price_row(2, "B1", unit="m2")}
        valid, errors = validate(rows, price_map)
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.code, UNIT_MISMATCH)
        self.assertEqual(e.source, "boq")
        self.assertEqual(e.line_number, 2)
        self.assertIn("B1", e.message)

    def test_validate_unit_comparison_is_case_sensitive(self):
        rows = [make_boq_row(2, "B1", unit="M2")]
        price_map = {"B1": make_price_row(2, "B1", unit="m2")}
        valid, errors = validate(rows, price_map)
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, UNIT_MISMATCH)

    def test_validate_duplicate_code_keeps_first(self):
        rows = [make_boq_row(2, "B1"), make_boq_row(3, "B1")]
        price_map = {"B1": make_price_row(2, "B1")}
        valid, errors = validate(rows, price_map)
        # first occurrence stays valid, the later duplicate gets the error
        self.assertEqual(len(valid), 1)
        self.assertIs(valid[0].row, rows[0])
        self.assertEqual(len(errors), 1)
        e = errors[0]
        self.assertEqual(e.code, DUPLICATE_CODE)
        self.assertEqual(e.source, "boq")
        self.assertEqual(e.line_number, 3)
        self.assertIn("B1", e.message)

    def test_validate_duplicate_takes_priority_over_missing_price(self):
        rows = [make_boq_row(2, "B1"), make_boq_row(3, "B1")]
        price_map = {}  # B1 has no price at all
        valid, errors = validate(rows, price_map)
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0].code, MISSING_PRICE)
        self.assertEqual(errors[1].code, DUPLICATE_CODE)
        self.assertEqual(errors[1].line_number, 3)

    def test_validate_at_most_one_error_per_row(self):
        # row 3 is BOTH a duplicate of row 2 and has a unit mismatch ->
        # only the first error (duplicate) is reported
        rows = [
            make_boq_row(2, "B1", unit="m3"),
            make_boq_row(3, "B1", unit="m2"),  # duplicate + unit mismatch
        ]
        price_map = {"B1": make_price_row(2, "B1", unit="m3")}
        valid, errors = validate(rows, price_map)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, DUPLICATE_CODE)

    def test_validate_empty_inputs(self):
        valid, errors = validate([], {})
        self.assertEqual(valid, [])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
