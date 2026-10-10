"""Tính toán dự toán (estimation) từ các dòng BOQ đã validate.

Mọi số tiền được làm tròn về đồng VND (số nguyên) bằng ROUND_HALF_UP.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from .models import DataError, EstimationResult, GroupSummary, ValidatedLine

#: Đơn vị tiền tệ nhỏ nhất: 1 VND. Mọi số tiền được quantize về bội số này.
VND = Decimal("1")


def money(value: Decimal) -> Decimal:
    """Làm tròn một số tiền về VND (số nguyên) theo ROUND_HALF_UP."""
    return value.quantize(VND, rounding=ROUND_HALF_UP)


def compute_estimate(
    valid_lines: Iterable[ValidatedLine],
    errors: list[DataError],
    vat_rate: Decimal = Decimal("0.10"),
) -> EstimationResult:
    """Tính dự toán từ các dòng đã validate.

    Mỗi dòng: material = quantize(quantity x material_unit_price),
    labor = quantize(quantity x labor_unit_price). Gom theo group,
    cộng dồn rồi tính subtotal/vat/total cho từng group và grand total.

    Args:
        valid_lines: Các dòng hợp lệ (đã khớp giá).
        errors: Lỗi dữ liệu từ parsing + validation (điền vào result).
        vat_rate: Thuế suất VAT, phải nằm trong [0, 1].

    Returns:
        EstimationResult với groups sắp xếp theo tên, errors và
        excluded_rows (sorted, unique).

        Chính sách làm tròn (khóa bởi tests/test_audit.py::F4):
        material/labor/subtotal của grand total là cộng dồn các group;
        nhưng VAT grand = round_half_up(grand_subtotal × vat_rate) — làm
        tròn MỘT lần ở cấp cuối (chuẩn kế toán), không phải tổng VAT các
        group. Do đó Σ VAT group có thể lệch vài đồng so với VAT grand;
        total = subtotal + vat luôn đúng ở mọi cấp.

    Raises:
        ValueError: Nếu vat_rate không phải số hữu hạn, âm, hoặc lớn hơn 1.
            (Kiểm tra `is_finite()` trước vì so sánh thứ tự với NaN
            raise `InvalidOperation` thay vì trả về False.)
    """
    if not vat_rate.is_finite() or vat_rate < 0 or vat_rate > 1:
        raise ValueError(
            f"vat_rate must be a finite number within [0, 1], got {vat_rate!r}"
        )

    groups: dict[str, GroupSummary] = {}
    for line in valid_lines:
        material = money(line.row.quantity * line.price.material_unit_price)
        labor = money(line.row.quantity * line.price.labor_unit_price)
        summary = groups.setdefault(line.row.group, GroupSummary())
        summary.material += material
        summary.labor += labor

    for summary in groups.values():
        summary.subtotal = summary.material + summary.labor
        summary.vat = money(summary.subtotal * vat_rate)
        summary.total = summary.subtotal + summary.vat

    totals = GroupSummary()
    for summary in groups.values():
        totals.material += summary.material
        totals.labor += summary.labor
    totals.subtotal = totals.material + totals.labor
    totals.vat = money(totals.subtotal * vat_rate)
    totals.total = totals.subtotal + totals.vat

    return EstimationResult(
        groups=dict(sorted(groups.items())),
        totals=totals,
        errors=list(errors),
        excluded_rows=sorted({e.line_number for e in errors}),
    )
