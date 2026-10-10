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

Chi tiết: `decimal.InvalidOperation` tại `boq/pricing.py` dòng 44
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
