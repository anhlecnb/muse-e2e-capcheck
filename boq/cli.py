"""Command-line interface cho công cụ dự toán BOQ.

Luồng chạy: parse tham số -> đọc 2 file CSV -> validate -> tính dự toán ->
xây dựng báo cáo -> (ghi file JSON) -> in tóm tắt ra stdout, cảnh báo lỗi
ra stderr.

Mã thoát: 0 = thành công; 1 = lỗi file; 2 = tham số/vat không hợp lệ hoặc
--strict gặp lỗi dữ liệu.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .parsing import parse_boq_csv, parse_prices_csv
from .pricing import compute_estimate
from .report import build_report, format_summary, write_report
from .validation import validate

DEFAULT_VAT = "0.10"


def build_parser() -> argparse.ArgumentParser:
    """Tạo argument parser cho CLI dự toán BOQ."""
    parser = argparse.ArgumentParser(
        prog="boq",
        description="Tính dự toán từ file BOQ CSV và file đơn giá CSV.",
    )
    parser.add_argument("--boq", required=True,
                        help="Đường dẫn file BOQ CSV.")
    parser.add_argument("--prices", required=True,
                        help="Đường dẫn file đơn giá CSV.")
    parser.add_argument("--vat", default=DEFAULT_VAT,
                        help=f"Thuế suất VAT dạng thập phân, trong [0, 1] "
                             f"(mặc định: {DEFAULT_VAT}).")
    parser.add_argument("--out", default=None,
                        help="Ghi báo cáo JSON ra file này (mặc định: không ghi).")
    parser.add_argument("--strict", action="store_true",
                        help="Trả mã thoát 2 nếu có bất kỳ lỗi dữ liệu nào.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Điểm vào CLI. Trả về mã thoát (0/1/2), không raise SystemExit."""
    args = build_parser().parse_args(argv)

    try:
        vat_rate = Decimal(args.vat)
    except InvalidOperation:
        print(f"ERROR: invalid vat rate: {args.vat!r}", file=sys.stderr)
        return 2

    try:
        boq_rows, boq_errors = parse_boq_csv(args.boq)
    except FileNotFoundError:
        print(f"ERROR: boq file not found: {args.boq}", file=sys.stderr)
        return 1
    try:
        price_map, price_errors = parse_prices_csv(args.prices)
    except FileNotFoundError:
        print(f"ERROR: prices file not found: {args.prices}", file=sys.stderr)
        return 1

    valid_lines, validation_errors = validate(boq_rows, price_map)
    errors = boq_errors + price_errors + validation_errors

    try:
        result = compute_estimate(valid_lines, errors, vat_rate=vat_rate)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    meta = {
        "boq_file": args.boq,
        "prices_file": args.prices,
        "vat_rate": str(vat_rate),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid_rows": len(valid_lines),
        "excluded_rows": len(result.excluded_rows),
    }
    report = build_report(result, meta)

    if args.out:
        write_report(report, args.out)

    print(format_summary(result, meta))

    for error in result.errors:
        print(
            f"WARNING: [line {error.line_number}] {error.code}: "
            f"{error.message} (source={error.source})",
            file=sys.stderr,
        )

    if args.strict and result.errors:
        return 2
    return 0
