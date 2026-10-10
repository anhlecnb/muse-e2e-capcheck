"""Unit tests cho boq.cli (viết trước theo TDD).

parse_boq_csv / parse_prices_csv / validate được mock để test không phụ
thuộc vào format CSV của module parsing (do subagent khác implement).
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from boq import cli as cli_mod
from boq.models import (
    MISSING_PRICE,
    BoqRow,
    DataError,
    PriceRow,
    ValidatedLine,
)


def make_valid_lines() -> list[ValidatedLine]:
    """2 dòng chuẩn: 2x120000+2x30000 và 3x15000+3x5000 -> total 396000."""
    def line(code, qty, mat, lab, no):
        row = BoqRow(line_number=no, code=code, description=f"desc {code}",
                     unit="m2", quantity=Decimal(qty), group="G1")
        price = PriceRow(line_number=no, code=code,
                         material_unit_price=Decimal(mat),
                         labor_unit_price=Decimal(lab), unit="m2")
        return ValidatedLine(row=row, price=price)

    return [line("A", "2", "120000", "30000", 1),
            line("B", "3", "15000", "5000", 2)]


def run_main(argv, valid_lines=None, errors=()):
    """Chạy cli.main với parse/validate đã mock; trả về (rc, stdout, stderr)."""
    if valid_lines is None:
        valid_lines = make_valid_lines()
    out, err = io.StringIO(), io.StringIO()
    with patch.object(cli_mod, "parse_boq_csv", return_value=([], [])), \
         patch.object(cli_mod, "parse_prices_csv", return_value=({}, [])), \
         patch.object(cli_mod, "validate",
                      return_value=(valid_lines, list(errors))), \
         redirect_stdout(out), redirect_stderr(err):
        rc = cli_mod.main(argv)
    return rc, out.getvalue(), err.getvalue()


class BuildParserTest(unittest.TestCase):
    def test_required_args(self):
        parser = cli_mod.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])

    def test_defaults(self):
        args = cli_mod.build_parser().parse_args(
            ["--boq", "b.csv", "--prices", "p.csv"])
        self.assertEqual(args.vat, "0.10")
        self.assertIsNone(args.out)
        self.assertFalse(args.strict)


class MainTest(unittest.TestCase):
    def test_main_ok_prints_summary(self):
        rc, out, err = run_main(["--boq", "b.csv", "--prices", "p.csv"])
        self.assertEqual(rc, 0)
        self.assertIn("GRAND TOTAL", out)
        self.assertIn("396000", out)
        self.assertIn("GROUP G1:", out)
        self.assertNotIn("Decimal(", out)

    def test_main_writes_out_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.json")
            rc, out, err = run_main(
                ["--boq", "b.csv", "--prices", "p.csv", "--out", path])
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as f:
                report = json.load(f)
        self.assertEqual(report["totals"]["total"], "396000")
        self.assertEqual(report["meta"]["vat_rate"], "0.10")
        self.assertEqual(report["meta"]["boq_file"], "b.csv")
        self.assertEqual(report["meta"]["prices_file"], "p.csv")
        self.assertEqual(report["meta"]["valid_rows"], 2)
        self.assertEqual(report["meta"]["excluded_row_count"], 0)
        self.assertIn("generated_at", report["meta"])

    def test_main_warnings_to_stderr(self):
        errors = [DataError(line_number=5, code=MISSING_PRICE,
                            message="no price for X1", source="boq")]
        rc, out, err = run_main(["--boq", "b.csv", "--prices", "p.csv"],
                                errors=errors)
        self.assertEqual(rc, 0)  # không strict -> vẫn 0
        self.assertIn("WARNING", err)
        self.assertIn("Errors: 1 (excluded rows: [boq:5])", out)

    def test_main_strict_returns_2_on_errors(self):
        errors = [DataError(line_number=5, code=MISSING_PRICE,
                            message="no price for X1", source="boq")]
        rc, out, err = run_main(
            ["--boq", "b.csv", "--prices", "p.csv", "--strict"], errors=errors)
        self.assertEqual(rc, 2)

    def test_main_missing_boq_file(self):
        with patch.object(cli_mod, "parse_boq_csv",
                          side_effect=FileNotFoundError("nope")):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = cli_mod.main(["--boq", "missing.csv",
                                   "--prices", "p.csv"])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err.getvalue())

    def test_main_missing_prices_file(self):
        with patch.object(cli_mod, "parse_prices_csv",
                          side_effect=FileNotFoundError("nope")):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = cli_mod.main(["--boq", "b.csv",
                                   "--prices", "missing.csv"])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err.getvalue())

    def test_main_invalid_vat(self):
        rc, out, err = run_main(["--boq", "b.csv", "--prices", "p.csv",
                                 "--vat", "abc"])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", err)

    def test_main_vat_out_of_range(self):
        rc, out, err = run_main(["--boq", "b.csv", "--prices", "p.csv",
                                 "--vat", "1.5"])
        self.assertEqual(rc, 2)
        self.assertIn("ERROR", err)


if __name__ == "__main__":
    unittest.main()
