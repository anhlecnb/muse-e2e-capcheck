"""Integration test cho CLI ``boq`` chạy thật qua subprocess.

Mỗi test gọi ``[sys.executable, "-m", "boq", ...]`` với cwd là repo root
(tính từ ``Path(__file__).resolve().parent.parent``) và kiểm tra mã thoát,
stdout/stderr cùng file báo cáo JSON được tạo ra.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFY_BOQ = REPO_ROOT / "data" / "verify_boq.csv"
VERIFY_PRICES = REPO_ROOT / "data" / "verify_prices.csv"
DEMO_BOQ = REPO_ROOT / "data" / "demo_boq.csv"
DEMO_PRICES = REPO_ROOT / "data" / "demo_prices.csv"

#: Số kiểm chứng trên data/verify_*: material=285000, labor=75000,
#: subtotal=360000, vat(10%)=36000, total=396000 (dạng string trong JSON).
EXPECTED_VERIFY_TOTALS = {
    "material": "285000",
    "labor": "75000",
    "subtotal": "360000",
    "vat": "36000",
    "total": "396000",
}

TIMEOUT_S = 60


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Chạy CLI boq thật qua subprocess từ repo root."""
    return subprocess.run(
        [sys.executable, "-m", "boq", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
    )


def read_report(path: str | Path) -> dict:
    """Đọc báo cáo JSON vừa được CLI ghi ra."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class VerifyDataIntegrationTest(unittest.TestCase):
    """CLI trên data kiểm chứng sạch."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.out_json = str(Path(self.tmpdir.name) / "verify_report.json")

    def test_verify_cli_exit0_stdout_contains_total_and_json_created(self) -> None:
        """verify data -> exit 0, stdout chứa '396000', file JSON được tạo."""
        proc = run_cli(
            "--boq", str(VERIFY_BOQ),
            "--prices", str(VERIFY_PRICES),
            "--vat", "0.10",
            "--out", self.out_json,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("396000", proc.stdout)
        self.assertTrue(
            Path(self.out_json).is_file(),
            msg="file báo cáo JSON phải được tạo khi có --out",
        )

    def test_verify_json_totals_exact(self) -> None:
        """JSON verify phải có totals chính xác dạng string."""
        proc = run_cli(
            "--boq", str(VERIFY_BOQ),
            "--prices", str(VERIFY_PRICES),
            "--vat", "0.10",
            "--out", self.out_json,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        report = read_report(self.out_json)
        self.assertEqual(report["totals"], EXPECTED_VERIFY_TOTALS)
        self.assertEqual(report["errors"], [])

    def test_verify_strict_exit0_on_clean_data(self) -> None:
        """--strict trên data sạch -> exit 0."""
        proc = run_cli(
            "--boq", str(VERIFY_BOQ),
            "--prices", str(VERIFY_PRICES),
            "--strict",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def test_verify_vat_zero(self) -> None:
        """--vat 0 -> vat bằng 0 trong JSON, subtotal giữ nguyên."""
        proc = run_cli(
            "--boq", str(VERIFY_BOQ),
            "--prices", str(VERIFY_PRICES),
            "--vat", "0",
            "--out", self.out_json,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        report = read_report(self.out_json)
        self.assertEqual(report["totals"]["vat"], "0")
        self.assertEqual(report["totals"]["total"], report["totals"]["subtotal"])
        self.assertEqual(report["totals"]["subtotal"], "360000")


class DemoDataIntegrationTest(unittest.TestCase):
    """CLI trên data demo có lỗi có chủ đích."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.out_json = str(Path(self.tmpdir.name) / "demo_report.json")

    def test_demo_cli_exit0_with_warnings_and_errors(self) -> None:
        """demo data -> exit 0, stdout có GRAND TOTAL, stderr có WARNING,
        và errors trong JSON > 0."""
        proc = run_cli(
            "--boq", str(DEMO_BOQ),
            "--prices", str(DEMO_PRICES),
            "--out", self.out_json,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("GRAND TOTAL", proc.stdout)
        self.assertIn("WARNING", proc.stderr)
        report = read_report(self.out_json)
        self.assertGreater(
            len(report["errors"]), 0,
            msg="demo data phải có ít nhất một lỗi trong JSON",
        )

    def test_demo_strict_exit2(self) -> None:
        """--strict trên demo data có lỗi -> exit 2."""
        proc = run_cli(
            "--boq", str(DEMO_BOQ),
            "--prices", str(DEMO_PRICES),
            "--strict",
        )
        self.assertEqual(proc.returncode, 2, msg=proc.stderr)


class CliFailureIntegrationTest(unittest.TestCase):
    """Các lỗi vận hành của CLI qua subprocess."""

    def test_missing_boq_file_exit1_and_stderr_message(self) -> None:
        """File BOQ không tồn tại -> exit 1, stderr có thông báo."""
        proc = run_cli(
            "--boq", str(REPO_ROOT / "data" / "khong-ton-tai.csv"),
            "--prices", str(VERIFY_PRICES),
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertTrue(
            proc.stderr.strip(),
            msg="stderr phải có thông báo lỗi khi thiếu file",
        )
        self.assertIn("not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
