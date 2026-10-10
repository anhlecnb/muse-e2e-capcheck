# RED-GREEN Log — BOQ Estimation Engine

Nhật ký trung thực các chu trình red-green của dự án, trích từ log thật
trong `/tmp` (`rg_core_*`, `rg_calc_*`, `rg_int_*`). Mỗi chu trình ghi:
test/case, kỳ vọng, trích output FAIL thật, thay đổi code, trích output PASS.

---

## Phần 1 — Core: models / parsing / validation (subagent 1)

### Chu trình 1.1 — Viết test trước khi có implementation

- **Test:** `test_parsing`, `test_validation` (viết trước toàn bộ).
- **Kỳ vọng:** parse/validate CSV BOQ đúng spec.
- **FAIL thật** (`/tmp/rg_core_fail_1.txt`):
  ```text
  ERROR: test_parsing (unittest.loader._FailedTest.test_parsing)
  ModuleNotFoundError: No module named 'boq.models'
  ...
  Ran 2 tests in 0.001s
  FAILED (errors=2)
  ```
- **Thay đổi:** implement `boq/models.py` (dataclasses `BoqRow`, `PriceRow`,
  `DataError`, `ValidatedLine`, `GroupSummary`, `EstimationResult` + 6 hằng
  mã lỗi).
- **Kết quả:** vẫn FAIL — chuyển sang chu trình 1.2.

### Chu trình 1.2 — Implement models, thiếu parsing/validation

- **FAIL thật** (`/tmp/rg_core_fail_2.txt`):
  ```text
  File ".../tests/test_parsing.py", line 18, in <module>
      from boq.parsing import parse_boq_csv, parse_prices_csv
  ModuleNotFoundError: No module named 'boq.parsing'
  ...
  File ".../tests/test_validation.py", line 14, in <module>
      from boq.validation import validate
  ModuleNotFoundError: No module named 'boq.validation'
  ```
- **Thay đổi:** implement `boq/parsing.py` (`parse_boq_csv`,
  `parse_prices_csv`).
- **Kết quả:** 16/17 test parsing pass, 1 ERROR — chuyển sang chu trình 1.3.

### Chu trình 1.3 — Bug nằm trong chính file test

- **Test:** `test_parse_boq_csv_missing_code`.
- **Kỳ vọng:** dòng thiếu `code` bị loại với lỗi phù hợp.
- **FAIL thật** (`/tmp/rg_core_fail_3.txt`):
  ```text
  ERROR: test_parse_boq_csv_missing_code (test_parsing.ParseBoqCsvTest.test_parse_boq_csv_missing_code)
  Traceback (most recent call last):
    File ".../tests/test_parsing.py", line 115, in test_parse_boq_csv_missing_code
      path = self.write_csv(
  TypeError: CsvTestCase.write_csv() takes 3 positional arguments but 4 were given
  ```
  Nguyên nhân: dấu phẩy thừa trong lời gọi `write_csv` ở file test khiến
  helper nhận 4 arg thay vì 3 — bug của test, không phải của implementation.
- **Thay đổi:** sửa lời gọi `write_csv` trong `tests/test_parsing.py`;
  đồng thời implement `boq/validation.py` (`validate`).
- **PASS thật** (`/tmp/rg_core_pass_2.txt`):
  ```text
  Ran 25 tests in 0.015s
  OK
  ```
  (Log `/tmp/rg_core_pass_1.txt` ghi lại trạng thái trung gian: 25 pass +
  1 ERROR `test_pricing` vì `boq.pricing` chưa tồn tại — điểm bàn giao sang
  subagent pricing/CLI.)

### Chu trình 1.4 — Tự thêm test NaN/Infinity, FAIL thật

- **Test mới:** `test_parse_boq_csv_non_finite_quantity_rejected`
  (subtests `NaN`, `Infinity`, `-Infinity`).
- **Kỳ vọng:** mọi quantity không hữu hạn đều bị loại với `INVALID_NUMBER`.
- **FAIL thật** (`/tmp/rg_core_fail_4.txt`) — 3 kiểu hỏng khác nhau:
  ```text
  (value='NaN') ... ERROR
  decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]
  # -> dòng `if quantity < 0:` ở parsing.py:131 nổ khi quantity là NaN

  (value='Infinity') ... FAIL
  AssertionError: Lists differ: [BoqRow(..., quantity=Decimal('Infinity'), ...)] != []
  # -> Infinity lọt qua, row vẫn được giữ

  (value='-Infinity') ... FAIL
  AssertionError: 'NEGATIVE_QUANTITY' != 'INVALID_NUMBER'
  # -> -Infinity bị gắn nhãn sai (NEGATIVE_QUANTITY thay vì INVALID_NUMBER)
  ```
- **Thay đổi:** thêm guard `quantity.is_finite()` trong `boq/parsing.py`
  trước khi kiểm tra âm — mọi giá trị không hữu hạn đều thành
  `INVALID_NUMBER`.
- **PASS thật** (`/tmp/rg_core_pass_3.txt`):
  ```text
  Ran 26 tests in 0.014s
  OK
  ```

---

## Phần 2 — Pricing / report / CLI (subagent 2)

### Chu trình 2.1 — test_pricing viết trước, dùng stub tạm

- **Test:** `tests/test_pricing.py` (12 test, viết trước).
- **Kỳ vọng:** `compute_estimate` tính đúng, làm tròn về VND (`ROUND_HALF_UP`).
- **FAIL thật** (`/tmp/rg_calc_fail_1.txt`):
  ```text
  File ".../tests/test_pricing.py", line 15, in <module>
      from boq.pricing import VND, compute_estimate
  ModuleNotFoundError: No module named 'boq.pricing'
  ```
  (Khi viết test đã dùng stub tạm trong `/tmp/stubs` để định hình API.)
- **Thay đổi:** implement `boq/pricing.py` (`VND`, `money()`,
  `compute_estimate`), bỏ stub.
- **PASS thật** (`/tmp/rg_calc_pass_1.txt`): `Ran 12 tests ... OK`, gồm case
  chuẩn với số kiểm chứng:
  `test_...` material=285000, labor=75000, subtotal=360000, vat=36000,
  total=396000.

### Chu trình 2.2 — test_report viết trước

- **Test:** `tests/test_report.py` (10 test, viết trước).
- **Kỳ vọng:** `build_report`/`format_summary`/`write_report` cho JSON
  JSON-serializable (Decimal → str), không in object thô.
- **FAIL thật** (`/tmp/rg_calc_fail_2.txt`):
  ```text
  File ".../tests/test_report.py", line 16, in <module>
      from boq.report import build_report, format_summary, write_report
  ModuleNotFoundError: No module named 'boq.report'
  ```
- **Thay đổi:** implement `boq/report.py`.
- **PASS thật** (`/tmp/rg_calc_pass_2.txt`): `Ran 10 tests ... OK`, gồm
  `test_no_raw_decimal_objects` ("Không in object thô kiểu Decimal('...')")
  và `test_write_and_read_back`.

### Chu trình 2.3 — test_cli viết trước, ImportError khi chuyển module thật

- **Test:** `tests/test_cli.py` (viết trước).
- **Kỳ vọng:** `main()` trả mã thoát 0/1/2, warnings ra stderr, ghi file
  `--out`, `--strict` trả 2 khi có lỗi.
- **FAIL thật** (`/tmp/rg_calc_fail_3.txt`):
  ```text
  File ".../tests/test_cli.py", line 17, in <module>
      from boq import cli as cli_mod
  ImportError: cannot import name 'cli' from 'boq' (.../boq/__init__.py)
  ```
  (Test ban đầu import stub; khi chuyển sang module thật thì `boq/__init__.py`
  chưa expose `cli`.)
- **Thay đổi:** implement `boq/cli.py` + `boq/__main__.py` (argparse:
  `--boq`, `--prices`, `--vat`, `--out`, `--strict`; exit 0/1/2).
- **PASS thật** (`/tmp/rg_calc_pass_3.txt`): `Ran 32 tests in 0.016s ... OK`
  (gồm `test_main_vat_out_of_range`, `test_main_warnings_to_stderr`,
  `test_main_writes_out_report`, ...). Ngoài ra đã e2e thật bằng CSV có
  1 dòng lỗi: stdout đúng, `--strict` trả `rc=2`.

---

## Phần 3 — Integration: subprocess CLI + data (subagent 3, 2026-10-10)

### Chu trình 3.1 — Viết `tests/test_integration.py` trước (7 test)

Bảy test chạy CLI thật qua
`[sys.executable, "-m", "boq", ...]` với `cwd` = repo root:

1. verify data → exit 0, stdout chứa `"396000"`, file JSON được tạo;
2. đọc JSON verify → totals đúng string
   `285000`/`75000`/`360000`/`36000`/`396000`;
3. demo data → exit 0, stdout có `GRAND TOTAL`, stderr có `WARNING`,
   `errors` trong JSON > 0;
4. `--strict` trên demo → exit 2;
5. `--strict` trên verify (sạch) → exit 0;
6. file BOQ không tồn tại → exit 1, stderr có thông báo;
7. `--vat 0` → `vat == "0"` trong JSON.

Để tái hiện trung thực tình huống "test viết trước khi fixture/implementation
sẵn sàng", lần chạy RED được thực hiện với thư mục `data/` tạm thời di chuyển
đi nơi khác (sau đó khôi phục nguyên vẹn).

- **FAIL thật** (`/tmp/rg_int_fail.txt`) — 6/7 FAIL:
  ```text
  test_demo_cli_exit0_with_warnings_and_errors ... FAIL
  test_demo_strict_exit2 ... FAIL
  test_verify_cli_exit0_stdout_contains_total_and_json_created ... FAIL
  test_verify_json_totals_exact ... FAIL
  test_verify_strict_exit0_on_clean_data ... FAIL
  test_verify_vat_zero ... FAIL
  ...
  FAIL: test_demo_cli_exit0_with_warnings_and_errors (...)
  AssertionError: 1 != 0 : ERROR: boq file not found: /home/hatch/workspace/boq-e2e/data/demo_boq.csv
  ```
  (Test "file BOQ không tồn tại" pass ngay cả ở RED vì nó vốn dùng path giả —
  hành vi đúng, không phải test yếu.)
- **Thay đổi (fix):** tạo đầy đủ fixture `data/` theo spec —
  `verify_boq.csv`/`verify_prices.csv` (đúng số kiểm chứng 285000/75000/
  360000/36000/396000) và `demo_boq.csv`/`demo_prices.csv` (12 dòng dữ liệu,
  3 nhóm, 6 lỗi có chủ đích: `DUPLICATE_CODE`, `MISSING_PRICE`,
  `UNIT_MISMATCH`, `NEGATIVE_QUANTITY`, `INVALID_NUMBER`, `INVALID_ROW`).
  Không sửa test, không làm yếu assertion nào.
- **PASS thật** (`/tmp/rg_int_pass.txt`):
  ```text
  Ran 7 tests in 0.701s
  OK
  ```

---

## Ghi chú kiểm chứng

- **CI GitHub Actions (`.github/workflows/ci.yml`) chưa được chạy thật** —
  chỉ tạo file theo spec, chưa kiểm chứng trên GitHub Actions.
- Toàn bộ log trích dẫn ở trên đọc trực tiếp từ các file
  `/tmp/rg_core_fail_*.txt`, `/tmp/rg_core_pass_*.txt`,
  `/tmp/rg_calc_fail_*.txt`, `/tmp/rg_calc_pass_*.txt`,
  `/tmp/rg_int_fail.txt`, `/tmp/rg_int_pass.txt`; không bịa thêm case nào.
