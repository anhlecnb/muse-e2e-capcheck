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


class F4RoundingPolicyTest(unittest.TestCase):
    """F4 (business-issue): VAT tính trên từng group rồi cộng lại có thể
    lệch ±1đ/group so với VAT tính trên grand subtotal — do làm tròn
    ROUND_HALF_UP ở mỗi cấp.

    QUYẾT ĐỊNH CHÍNH SÁCH (khóa bằng test dưới đây):
    - VAT của group = round_half_up(group_subtotal × vat_rate)
    - VAT grand = round_half_up(grand_subtotal × vat_rate)  (làm tròn 1 lần
      cuối — chuẩn kế toán), KHÔNG phải tổng VAT các group.
    - Do đó Σ VAT group có thể khác VAT grand vài đồng; đây là hành vi
      đúng theo thiết kế, không phải bug. README/AUDIT_REPORT ghi rõ.
    """

    def test_group_vat_sum_may_differ_from_grand_vat_by_rounding(self):
        # 2 group, mỗi group subtotal = 5đ, VAT 10%:
        # group VAT = round(0.5) = 1 (HALF_UP) -> tổng 2
        # grand VAT = round(10 × 0.10) = round(1.0) = 1
        lines = [
            make_line("A", "5", "1", "0", "G1", 2),
            make_line("B", "5", "1", "0", "G2", 3),
        ]
        result = compute_estimate(lines, [], vat_rate=Decimal("0.10"))
        self.assertEqual(result.groups["G1"].vat, Decimal("1"))
        self.assertEqual(result.groups["G2"].vat, Decimal("1"))
        self.assertEqual(result.totals.vat, Decimal("1"))
        # nhất quán nội bộ từng cấp: total = subtotal + vat
        self.assertEqual(result.groups["G1"].total, Decimal("6"))
        self.assertEqual(result.totals.total, Decimal("11"))
        self.assertEqual(
            result.totals.total,
            result.totals.subtotal + result.totals.vat,
        )

    def test_grand_vat_is_single_rounding_of_grand_subtotal(self):
        # 3 group subtotal lẻ: VAT grand luôn = round(Σsubtotal × rate),
        # không phụ thuộc cách chia group
        lines = [
            make_line("A", "1", "3", "0", "G1", 2),  # subtotal 3
            make_line("B", "1", "3", "0", "G2", 3),  # subtotal 3
            make_line("C", "1", "3", "0", "G3", 4),  # subtotal 3
        ]
        result = compute_estimate(lines, [], vat_rate=Decimal("0.10"))
        # grand subtotal 9 -> VAT round(0.9) = 1
        self.assertEqual(result.totals.subtotal, Decimal("9"))
        self.assertEqual(result.totals.vat, Decimal("1"))
        self.assertEqual(result.totals.total, Decimal("10"))


class F5ExcludedRowsLoseSourceTest(unittest.TestCase):
    """F5 (software-bug, major): excluded_rows chỉ lưu số dòng (int) rồi
    dedupe — lỗi ở boq.csv dòng 5 và prices.csv dòng 5 bị gộp thành [5],
    không truy vết được dòng nào thuộc file nào."""

    def test_excluded_rows_keep_source(self):
        from boq.models import DataError
        errors = [
            DataError(line_number=5, code="X1", message="m1", source="boq"),
            DataError(line_number=5, code="X2", message="m2", source="prices"),
            DataError(line_number=3, code="X3", message="m3", source="boq"),
        ]
        result = compute_estimate([make_line()], errors)
        self.assertEqual(
            result.excluded_rows,
            [
                {"source": "boq", "line_number": 3},
                {"source": "boq", "line_number": 5},
                {"source": "prices", "line_number": 5},
            ],
        )

    def test_report_excluded_rows_json_has_source(self):
        from boq.models import DataError, EstimationResult, GroupSummary
        from boq.report import build_report
        g = GroupSummary()
        errors = [
            DataError(line_number=5, code="X1", message="m1", source="boq"),
            DataError(line_number=5, code="X2", message="m2", source="prices"),
        ]
        result = compute_estimate([], errors)
        report = build_report(
            EstimationResult(groups={"G": g}, totals=g, errors=errors,
                             excluded_rows=result.excluded_rows),
            {},
        )
        self.assertEqual(
            report["excluded_rows"],
            [
                {"source": "boq", "line_number": 5},
                {"source": "prices", "line_number": 5},
            ],
        )

    def test_cli_meta_excluded_row_count_key(self):
        # meta['excluded_rows'] đang là COUNT (int) trong khi report['excluded_rows']
        # là LIST — trùng tên khác kiểu. Quyết định: meta dùng 'excluded_row_count'.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bpath = os.path.join(tmp.name, "boq.csv")
        ppath = os.path.join(tmp.name, "prices.csv")
        with open(bpath, "w", encoding="utf-8") as f:
            f.write("code,description,unit,quantity,group\n"
                    "A-001,Item A,m2,2,G1\n")
        with open(ppath, "w", encoding="utf-8") as f:
            f.write("code,material_unit_price,labor_unit_price,unit\n"
                    "A-001,120000,30000,m2\n")
        out, err = io.StringIO(), io.StringIO()
        from contextlib import redirect_stderr, redirect_stdout
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli_mod.main(["--boq", bpath, "--prices", ppath,
                               "--out", os.path.join(tmp.name, "r.json")])
        self.assertEqual(rc, 0)
        with open(os.path.join(tmp.name, "r.json"), encoding="utf-8") as f:
            report = json.load(f)
        self.assertIn("excluded_row_count", report["meta"])
        self.assertNotIn("excluded_rows", report["meta"])
        self.assertEqual(report["meta"]["excluded_row_count"], 0)


class F6NegativePriceCodeTest(AuditCsvCase):
    """F6 (software-bug, minor): giá âm trong prices.csv bị gán mã
    INVALID_NUMBER chung chung (chỉ message mới nhắc 'negative').
    Mã lỗi là contract cho máy đọc -> tách thành NEGATIVE_PRICE riêng."""

    def test_negative_material_price_gets_dedicated_code(self):
        from boq.parsing import parse_prices_csv
        path = self.write(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,-5,20,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(price_map, {})
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "NEGATIVE_PRICE")
        self.assertEqual(errors[0].source, "prices")

    def test_negative_labor_price_gets_dedicated_code(self):
        from boq.parsing import parse_prices_csv
        path = self.write(
            "prices.csv",
            "code,material_unit_price,labor_unit_price,unit\n"
            "P1,100,-20,m3\n",
        )
        price_map, errors = parse_prices_csv(path)
        self.assertEqual(price_map, {})
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "NEGATIVE_PRICE")


class F7UnwritableOutPathTest(AuditCsvCase):
    """F7 (software-bug, minor): --out trỏ vào thư mục không tồn tại ->
    OSError từ write_report không được bắt -> traceback."""

    def test_cli_unwritable_out_exits_1_without_traceback(self):
        boq, prices = self.valid_pair()
        bad_out = os.path.join(
            self._tmp.name, "khong-ton-tai", "report.json")
        rc, out, err = self.run_cli(
            ["--boq", boq, "--prices", prices, "--out", bad_out])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", err)
        self.assertNotIn("Traceback", err)
