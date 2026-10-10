"""Xây dựng báo cáo dự toán dạng JSON và text tóm tắt cho stdout."""
from __future__ import annotations

import json
from typing import Any

from .models import EstimationResult, GroupSummary


def _summary_to_dict(summary: GroupSummary) -> dict[str, str]:
    """Chuyển GroupSummary thành dict JSON-serializable (Decimal -> str)."""
    return {
        "material": str(summary.material),
        "labor": str(summary.labor),
        "subtotal": str(summary.subtotal),
        "vat": str(summary.vat),
        "total": str(summary.total),
    }


def build_report(result: EstimationResult, meta: dict[str, Any]) -> dict[str, Any]:
    """Xây dựng dict báo cáo JSON-serializable từ kết quả dự toán.

    Mọi Decimal được chuyển thành str(decimal) giữ nguyên precision
    (ví dụ "360000"); vat_rate trong meta cũng là str.

    Args:
        result: Kết quả từ compute_estimate.
        meta: Metadata của lần chạy (boq_file, prices_file, vat_rate,
            generated_at, valid_rows, excluded_rows, ...).

    Returns:
        Dict với các key: meta, groups, totals, errors, excluded_rows.
    """
    return {
        "meta": dict(meta),
        "groups": {
            name: _summary_to_dict(summary)
            for name, summary in result.groups.items()
        },
        "totals": _summary_to_dict(result.totals),
        "errors": [
            {
                "line_number": e.line_number,
                "code": e.code,
                "message": e.message,
                "source": e.source,
            }
            for e in result.errors
        ],
        "excluded_rows": list(result.excluded_rows),
    }


def write_report(report: dict[str, Any], path: str) -> None:
    """Ghi báo cáo ra file JSON (indent=2, ensure_ascii=False).

    Args:
        report: Dict báo cáo từ build_report.
        path: Đường dẫn file đích.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def format_summary(result: EstimationResult, meta: dict[str, Any]) -> str:
    """Tạo text tóm tắt cho stdout: mỗi group một dòng, grand total,
    và dòng thống kê lỗi.

    Số tiền in dạng nguyên (str của Decimal đã quantize).

    Args:
        result: Kết quả từ compute_estimate.
        meta: Metadata của lần chạy (không bắt buộc dùng hết).

    Returns:
        Chuỗi nhiều dòng, sẵn sàng in ra stdout.
    """
    lines: list[str] = []
    for name, summary in result.groups.items():
        lines.append(
            f"GROUP {name}: material={summary.material} "
            f"labor={summary.labor} subtotal={summary.subtotal} "
            f"vat={summary.vat} total={summary.total}"
        )
    t = result.totals
    lines.append(
        f"GRAND TOTAL: material={t.material} labor={t.labor} "
        f"subtotal={t.subtotal} vat={t.vat} total={t.total}"
    )
    excluded = ", ".join(
        f"{entry['source']}:{entry['line_number']}"
        for entry in result.excluded_rows
    )
    lines.append(
        f"Errors: {len(result.errors)} (excluded rows: [{excluded}])"
    )
    return "\n".join(lines)
