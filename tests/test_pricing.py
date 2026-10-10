"""Unit tests cho boq.pricing (viết trước theo TDD)."""
from __future__ import annotations

import unittest
from decimal import Decimal

from boq.models import (
    MISSING_PRICE,
    UNIT_MISMATCH,
    BoqRow,
    DataError,
    PriceRow,
    ValidatedLine,
)
from boq.pricing import VND, compute_estimate


def make_line(code="C001", qty="2", mat="120000", lab="30000",
              group="G1", line_no=1, unit="m2"):
    """Dựng một ValidatedLine đúng contract boq.models."""
    row = BoqRow(line_number=line_no, code=code, description=f"desc {code}",
                 unit=unit, quantity=Decimal(qty), group=group)
    price = PriceRow(line_number=line_no, code=code,
                     material_unit_price=Decimal(mat),
                     labor_unit_price=Decimal(lab), unit=unit)
    return ValidatedLine(row=row, price=price)


class ComputeEstimateTest(unittest.TestCase):
    def test_line_totals_exact(self):
        """2x120000+2x30000 và 3x15000+3x5000 -> totals chuẩn, Decimal chính xác."""
        lines = [make_line("A", "2", "120000", "30000", "G1", 1),
                 make_line("B", "3", "15000", "5000", "G1", 2)]
        result = compute_estimate(lines, [])
        g = result.groups["G1"]
        self.assertEqual(g.material, Decimal("285000"))
        self.assertEqual(g.labor, Decimal("75000"))
        self.assertEqual(g.subtotal, Decimal("360000"))
        self.assertEqual(g.vat, Decimal("36000"))
        self.assertEqual(g.total, Decimal("396000"))
        # Grand totals nhất quán
        self.assertEqual(result.totals.material, Decimal("285000"))
        self.assertEqual(result.totals.labor, Decimal("75000"))
        self.assertEqual(result.totals.subtotal, Decimal("360000"))
        self.assertEqual(result.totals.vat, Decimal("36000"))
        self.assertEqual(result.totals.total, Decimal("396000"))

    def test_group_aggregation(self):
        """Nhiều group: gom đúng từng group, grand total = cộng dồn."""
        lines = [make_line("A", "2", "120000", "30000", "G1", 1),
                 make_line("B", "3", "15000", "5000", "G1", 2),
                 make_line("C", "1", "100000", "20000", "G2", 3)]
        result = compute_estimate(lines, [])
        self.assertEqual(result.groups["G1"].total, Decimal("396000"))
        g2 = result.groups["G2"]
        self.assertEqual(g2.material, Decimal("100000"))
        self.assertEqual(g2.labor, Decimal("20000"))
        self.assertEqual(g2.subtotal, Decimal("120000"))
        self.assertEqual(g2.vat, Decimal("12000"))
        self.assertEqual(g2.total, Decimal("132000"))
        self.assertEqual(result.totals.material, Decimal("385000"))
        self.assertEqual(result.totals.labor, Decimal("95000"))
        self.assertEqual(result.totals.subtotal, Decimal("480000"))
        self.assertEqual(result.totals.vat, Decimal("48000"))
        self.assertEqual(result.totals.total, Decimal("528000"))

    def test_rounding_half_up(self):
        """quantize HALF_UP: 10.555 -> 11; 2.5 -> 3 (không phải banker 2)."""
        line = make_line("R", "1", "10.555", "2.5", "G", 1)
        result = compute_estimate([line], [])
        g = result.groups["G"]
        self.assertEqual(g.material, Decimal("11"))
        self.assertEqual(g.labor, Decimal("3"))

    def test_rounding_half_up_fractional_quantity(self):
        """0.5 x 1 = 0.5 -> HALF_UP thành 1 (không phải 0)."""
        line = make_line("F", "0.5", "1", "1", "G", 1)
        result = compute_estimate([line], [])
        g = result.groups["G"]
        self.assertEqual(g.material, Decimal("1"))
        self.assertEqual(g.labor, Decimal("1"))

    def test_zero_quantity(self):
        """quantity 0 -> 0đ cho mọi khoản."""
        line = make_line("Z", "0", "120000", "30000", "G", 1)
        result = compute_estimate([line], [])
        g = result.groups["G"]
        self.assertEqual(g.material, Decimal("0"))
        self.assertEqual(g.labor, Decimal("0"))
        self.assertEqual(g.subtotal, Decimal("0"))
        self.assertEqual(g.vat, Decimal("0"))
        self.assertEqual(g.total, Decimal("0"))

    def test_vat_rate_zero(self):
        """vat_rate=0 -> vat 0, total = subtotal."""
        lines = [make_line("A", "2", "120000", "30000", "G1", 1)]
        result = compute_estimate(lines, [], vat_rate=Decimal("0"))
        self.assertEqual(result.groups["G1"].vat, Decimal("0"))
        self.assertEqual(result.groups["G1"].total, Decimal("300000"))
        self.assertEqual(result.totals.vat, Decimal("0"))
        self.assertEqual(result.totals.total, Decimal("300000"))

    def test_vat_rate_negative_raises(self):
        with self.assertRaises(ValueError):
            compute_estimate([make_line()], [], vat_rate=Decimal("-0.01"))

    def test_vat_rate_above_one_raises(self):
        with self.assertRaises(ValueError):
            compute_estimate([make_line()], [], vat_rate=Decimal("1.01"))

    def test_groups_sorted_by_name(self):
        """groups dict sắp xếp theo tên group."""
        lines = [make_line("A", "1", "10", "5", "Zeta", 1),
                 make_line("B", "1", "10", "5", "Alpha", 2),
                 make_line("C", "1", "10", "5", "Mid", 3)]
        result = compute_estimate(lines, [])
        self.assertEqual(list(result.groups.keys()), ["Alpha", "Mid", "Zeta"])

    def test_excluded_rows_from_errors(self):
        """excluded_rows = sorted unique (source, line_number) từ errors;
        dòng 5 của boq và dòng 3 của prices là 2 mục riêng biệt (F5)."""
        errors = [
            DataError(line_number=5, code="X1", message="no price", source="boq"),
            DataError(line_number=3, code="X2", message="bad unit", source="prices"),
            DataError(line_number=5, code="X1", message="no price", source="boq"),
        ]
        lines = [make_line("A", "2", "120000", "30000", "G1", 1)]
        result = compute_estimate(lines, errors)
        self.assertEqual(
            result.excluded_rows,
            [
                {"source": "boq", "line_number": 5},
                {"source": "prices", "line_number": 3},
            ],
        )
        self.assertEqual(result.groups["G1"].total, Decimal("330000"))
        self.assertEqual(len(result.errors), 3)

    def test_empty_lines(self):
        """Không có line hợp lệ -> groups rỗng, totals toàn 0."""
        result = compute_estimate([], [])
        self.assertEqual(result.groups, {})
        self.assertEqual(result.totals.material, Decimal("0"))
        self.assertEqual(result.totals.total, Decimal("0"))
        self.assertEqual(result.excluded_rows, [])

    def test_vnd_constant(self):
        self.assertEqual(VND, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
