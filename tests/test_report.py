"""Unit tests cho boq.report (viết trước theo TDD)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from decimal import Decimal

from boq.models import (
    MISSING_PRICE,
    DataError,
    EstimationResult,
    GroupSummary,
)
from boq.report import build_report, format_summary, write_report


def make_result() -> EstimationResult:
    """Dựng EstimationResult với số liệu chuẩn: total 396000."""
    g1 = GroupSummary(material=Decimal("285000"), labor=Decimal("75000"),
                      subtotal=Decimal("360000"), vat=Decimal("36000"),
                      total=Decimal("396000"))
    errors = [DataError(line_number=5, code="X1", message="no price", source="boq")]
    return EstimationResult(groups={"G1": g1}, totals=g1,
                            errors=errors,
                            excluded_rows=[{"source": "boq", "line_number": 5}])


class BuildReportTest(unittest.TestCase):
    def test_report_keys(self):
        report = build_report(make_result(), {"vat_rate": "0.10"})
        self.assertEqual(set(report.keys()),
                         {"meta", "groups", "totals", "errors", "excluded_rows"})

    def test_decimals_serialized_as_str(self):
        """Mọi Decimal -> str giữ nguyên precision, vd '360000'."""
        report = build_report(make_result(), {"vat_rate": "0.10"})
        totals = report["totals"]
        self.assertEqual(totals["material"], "285000")
        self.assertEqual(totals["labor"], "75000")
        self.assertEqual(totals["subtotal"], "360000")
        self.assertEqual(totals["vat"], "36000")
        self.assertEqual(totals["total"], "396000")
        self.assertEqual(report["groups"]["G1"]["total"], "396000")

    def test_meta_passthrough(self):
        meta = {"boq_file": "b.csv", "prices_file": "p.csv",
                "vat_rate": "0.10", "generated_at": "2026-10-10T00:00:00+00:00",
                "valid_rows": 2, "excluded_rows": 1}
        report = build_report(make_result(), meta)
        self.assertEqual(report["meta"], meta)

    def test_errors_serialize(self):
        report = build_report(make_result(), {})
        self.assertEqual(report["errors"],
                         [{"line_number": 5, "code": "X1",
                           "message": "no price", "source": "boq"}])
        self.assertEqual(report["excluded_rows"],
                         [{"source": "boq", "line_number": 5}])

    def test_report_is_json_serializable(self):
        """json.dumps phải thành công trên toàn bộ report."""
        report = build_report(make_result(), {"vat_rate": "0.10"})
        json.dumps(report, ensure_ascii=False)


class WriteReportTest(unittest.TestCase):
    def test_write_and_read_back(self):
        report = build_report(make_result(), {"vat_rate": "0.10"})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.json")
            write_report(report, path)
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
        self.assertEqual(loaded, report)
        self.assertEqual(loaded["totals"]["total"], "396000")


class FormatSummaryTest(unittest.TestCase):
    def test_contains_grand_total_and_amount(self):
        summary = format_summary(make_result(), {"vat_rate": "0.10"})
        self.assertIn("GRAND TOTAL", summary)
        self.assertIn("396000", summary)

    def test_group_line_format(self):
        summary = format_summary(make_result(), {})
        self.assertIn("GROUP G1:", summary)
        self.assertIn("material=285000", summary)
        self.assertIn("labor=75000", summary)
        self.assertIn("subtotal=360000", summary)
        self.assertIn("vat=36000", summary)
        self.assertIn("total=396000", summary)

    def test_errors_line(self):
        summary = format_summary(make_result(), {})
        self.assertIn("Errors: 1 (excluded rows: [boq:5])", summary)

    def test_no_raw_decimal_objects(self):
        """Không in object thô kiểu Decimal('...')."""
        summary = format_summary(make_result(), {})
        self.assertNotIn("Decimal(", summary)


if __name__ == "__main__":
    unittest.main()
