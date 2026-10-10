# AUDIT_EVIDENCE — Bằng chứng red/green từng finding (Assessment #3)

Mỗi finding: output FAIL thật trước fix (red), rồi output PASS sau fix (green).
Trích nguyên văn từ lần chạy `python3 -m unittest`.

---

## F1 — `--vat NaN` crash bằng `InvalidOperation` không được bắt

**RED** (`python3 -m unittest tests.test_audit`, trước fix):

```text
ERROR: test_cli_vat_nan_exits_2_without_traceback (tests.test_audit.F1NanVatRateTest.test_cli_vat_nan_exits_2_without_traceback)
ERROR: test_compute_estimate_rejects_nan_vat_rate (tests.test_audit.F1NanVatRateTest.test_compute_estimate_rejects_nan_vat_rate)
----------------------------------------------------------------------
Ran 2 tests in 0.003s
FAILED (errors=2)
```

Chi tiết: `decimal.InvalidOperation` tại `boq/pricing.py`
(`if vat_rate < 0 or vat_rate > 1:`) — so sánh thứ tự với `Decimal("NaN")`
raise `InvalidOperation` thay vì trả về False. CLI không bắt
`InvalidOperation` nên in traceback và thoát mã 1.

**GREEN** (sau fix — kiểm tra `is_finite()` trước khi so sánh):

```text
test_compute_estimate_rejects_nan_vat_rate (tests.test_audit.F1NanVatRateTest.test_compute_estimate_rejects_nan_vat_rate) ... ok
test_cli_vat_nan_exits_2_without_traceback (tests.test_audit.F1NanVatRateTest.test_cli_vat_nan_exits_2_without_traceback) ... ok
----------------------------------------------------------------------
Ran 2 tests in 0.003s
OK
```

---

## F2 — Header CSV sai / file rỗng -> `ValueError` không được bắt -> traceback

**RED** (`python3 -m unittest tests.test_audit.F2BadHeaderTracebackTest`, trước fix):

```text
ERROR: test_cli_bad_prices_header_exits_1_without_traceback (...)
FAIL: test_cli_bad_boq_header_exits_1_without_traceback (...)
FAIL: test_cli_empty_boq_file_exits_1_without_traceback (...)
----------------------------------------------------------------------
Ran 3 tests in 0.007s
FAILED (failures=2, errors=1)
```

Kiểm chứng thủ công: `cli.main()` với boq.csv thiếu cột header ->
`UNCAUGHT: ValueError` (không có thông báo ERROR gọn, chạy thật qua
`python -m boq` sẽ in traceback và thoát mã 1).

**GREEN** (sau fix — `CsvFormatError(ValueError)` riêng, CLI bắt và in
`ERROR: Invalid header in ...`, thoát mã 1):

```text
test_cli_bad_boq_header_exits_1_without_traceback ... ok
test_cli_bad_prices_header_exits_1_without_traceback ... ok
test_cli_empty_boq_file_exits_1_without_traceback ... ok
----------------------------------------------------------------------
Ran 3 tests in 0.007s
OK
```
Lưu ý: 2 test ban đầu tôi viết sai thứ tự ghi file tạm (valid_pair ghi đè
file lỗi) nên fail giả sau khi fix; đã sửa test, không liên quan logic fix.

---

## F3 — File CSV có BOM (UTF-8-BOM từ Excel) bị từ chối

**RED** (`python3 -m unittest tests.test_audit.F3BomFileTest`, trước fix):

```text
ERROR: test_parse_boq_csv_with_bom (...)
ERROR: test_parse_prices_csv_with_bom (...)
FAIL: test_cli_end_to_end_with_bom_files (...)
----------------------------------------------------------------------
Ran 3 tests in 0.004s
FAILED (failures=1, errors=2)
```

Ký tự `\ufeff` dính vào tên cột đầu (`'\ufeffcode'`) -> header check fail ->
`CsvFormatError`. File Excel xuất ra rất hay có BOM nên đây là lỗi thực tế.

**GREEN** (sau fix — đọc bằng `encoding="utf-8-sig"` ở cả hai hàm parse,
tự loại BOM nếu có, không ảnh hưởng file không BOM):

```text
Ran 3 tests in 0.006s
OK
```

---

## F4 — Chính sách làm tròn: Σ VAT group vs VAT grand (business-issue)

**Không có red phase** — đây không phải bug mà là điểm nghiệp vụ cần quyết
định. Hành vi hiện tại đã đúng đắn, test dưới đây KHÓA chính sách:

```text
test_group_vat_sum_may_differ_from_grand_vat_by_rounding ... ok
test_grand_vat_is_single_rounding_of_grand_subtotal ... ok
----------------------------------------------------------------------
Ran 2 tests in 0.004s
OK
```

Ví dụ khóa lại: 2 group subtotal=5đ, VAT 10% -> VAT mỗi group =
round_half_up(0.5) = 1 (tổng 2), nhưng VAT grand = round_half_up(10×0.10)
= 1. **Quyết định:** VAT grand làm tròn một lần trên grand subtotal
(chuẩn kế toán); Σ VAT group có thể lệch vài đồng — là hành vi đúng theo
thiết kế, đã ghi vào docstring `compute_estimate`, README và AUDIT_REPORT.

---

## F5 — `excluded_rows` mất thông tin file nguồn (dòng 5 boq.csv vs dòng 5 prices.csv bị gộp)

**RED** (`python3 -m unittest tests.test_audit.F5ExcludedRowsLoseSourceTest`, trước fix):

```text
FAIL: test_cli_meta_excluded_row_count_key (...)
FAIL: test_excluded_rows_keep_source (...)
FAIL: test_report_excluded_rows_json_has_source (...)
----------------------------------------------------------------------
Ran 3 tests in 0.005s
FAILED (failures=3)
```

Nguyên nhân: `excluded_rows=sorted({e.line_number for e in errors})` —
set int dedupe xuyên file. Thêm phát hiện phụ: `meta["excluded_rows"]` là
COUNT (int) trong khi `report["excluded_rows"]` là LIST — trùng tên khác kiểu.

**GREEN** (sau fix — `excluded_rows` là list `{"source","line_number"}`
sorted theo (source, line_number); meta đổi thành `excluded_row_count`;
`format_summary` in `excluded rows: [boq:5, prices:3]`):

```text
Ran 78 tests in 0.699s
OK
```
Các test hiện có được cập nhật sang contract mới (chặt hơn, có kiểm tra
source — không nới lỏng assertion nào): `test_excluded_rows_from_errors`,
`test_errors_serialize`, `test_errors_line`, `test_main_warnings_to_stderr`,
`test_main_writes_out_report`.
