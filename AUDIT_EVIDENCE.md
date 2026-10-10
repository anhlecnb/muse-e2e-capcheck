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
