"""Adversarial audit tests (Assessment #3).

Mỗi class tương ứng một finding F1..Fx trong AUDIT_REPORT.md.
Quy tắc: test tái hiện viết TRƯỚC, phải FAIL trước khi fix (red),
sau đó fix code và test phải PASS (green). Không làm yếu assertion.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal

from boq import cli as cli_mod
from boq.models import (
    BoqRow,
    PriceRow,
    ValidatedLine,
)
from boq.pricing import compute_estimate


def make_line(code="A", qty="2", mat="120000", lab="30000",
              group="G1", line_no=2, unit="m2"):
    row = BoqRow(line_number=line_no, code=code, description=f"desc {code}",
                 unit=unit, quantity=Decimal(qty), group=group)
    price = PriceRow(line_number=line_no, code=code,
                     material_unit_price=Decimal(mat),
                     labor_unit_price=Decimal(lab), unit=unit)
    return ValidatedLine(row=row, price=price)


class AuditCsvCase(unittest.TestCase):
    """Helper: ghi CSV thật vào thư mục tạm để chạy cli.main end-to-end."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def write(self, name, content, encoding="utf-8"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", newline="", encoding=encoding) as f:
            f.write(content)
        return path

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli_mod.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def valid_pair(self):
        boq = self.write(
            "boq.csv",
            "code,description,unit,quantity,group\n"
            "A-001,Item A,m2,2,G1\n",
        )
        prices = self.write(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "A-001,120000,30000,m2\n",
        )
        return boq, prices


class F1NanVatRateTest(AuditCsvCase):
    """F1 (software-bug, critical): --vat NaN lọt qua validate rồi crash
    bằng InvalidOperation không được bắt -> traceback, exit code 1."""

    def test_compute_estimate_rejects_nan_vat_rate(self):
        with self.assertRaises(ValueError):
            compute_estimate([make_line()], [], vat_rate=Decimal("NaN"))

    def test_cli_vat_nan_exits_2_without_traceback(self):
        boq, prices = self.valid_pair()
        rc, out, err = self.run_cli(
            ["--boq", boq, "--prices", prices, "--vat", "NaN"])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", err)
        self.assertNotIn("Traceback", err)


class F2BadHeaderTracebackTest(AuditCsvCase):
    """F2 (software-bug, major): header CSV sai / file rỗng -> ValueError
    từ _check_header không được CLI bắt -> traceback thay vì lỗi gọn."""

    def test_cli_bad_boq_header_exits_1_without_traceback(self):
        _, prices = self.valid_pair()
        boq = self.write(
            "boq.csv",
            "code,description,unit,quantity\n"  # thiếu cột group
            "A-001,Item A,m2,2\n",
        )
        rc, out, err = self.run_cli(["--boq", boq, "--prices", prices])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err)
        self.assertNotIn("Traceback", err)

    def test_cli_bad_prices_header_exits_1_without_traceback(self):
        boq, _ = self.valid_pair()
        prices = self.write(
            "prices.csv",
            "code,material_unit_price,labor_unit_price\n"  # thiếu cột unit
            "A-001,120000,30000\n",
        )
        rc, out, err = self.run_cli(["--boq", boq, "--prices", prices])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err)
        self.assertNotIn("Traceback", err)

    def test_cli_empty_boq_file_exits_1_without_traceback(self):
        _, prices = self.valid_pair()
        boq = self.write("boq.csv", "")
        rc, out, err = self.run_cli(["--boq", boq, "--prices", prices])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err)
        self.assertNotIn("Traceback", err)


class F3BomFileTest(AuditCsvCase):
    """F3 (software-bug, major): file CSV có BOM (Excel hay xuất UTF-8-BOM)
    -> ký tự \\ufeff dính vào header -> CsvFormatError. Kỳ vọng: parse
    trong suốt, không bắt user phải xử lý BOM."""

    def test_parse_boq_csv_with_bom(self):
        from boq.parsing import parse_boq_csv
        path = self.write(
            "boq.csv",
            "\ufeffcode,description,unit,quantity,group\n"
            "B1,Concrete,m3,10,G1\n",
        )
        rows, errors = parse_boq_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].code, "B1")

    def test_parse_prices_csv_with_bom(self):
        from boq.parsing import parse_prices_csv
        path = self.write(
            "prices.csv",
            "\ufeffcode,material_unit_price,labor_unit_price,unit\n"
            "B1,100,20,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(errors, [])
        self.assertEqual(price_map["B1"].material_unit_price, Decimal("100"))

    def test_cli_end_to_end_with_bom_files(self):
        boq = self.write(
            "boq.csv",
            "\ufeffcode,description,unit,quantity,group\n"
            "A-001,Item A,m2,2,G1\n",
        )
        prices = self.write(
            "prices.csv",
            "\ufeffcode,material_unit_price,labor_unit_price,unit\n"
            "A-001,120000,30000,m2\n",
        )
        rc, out, err = self.run_cli(["--boq", boq, "--prices", prices])
        self.assertEqual(rc, 0, msg=err)
        self.assertIn("330000", out)  # (2*120000+2*30000)*1.1
