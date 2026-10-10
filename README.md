# muse-e2e-capcheck

Disposable repo for Muse capability e2e test.

---

# BOQ Estimation Engine

Công cụ dự toán chi phí từ **BOQ** (Bill of Quantities) viết bằng Python thuần:
đọc 2 file CSV (khối lượng + đơn giá), kiểm tra dữ liệu, tính tiền vật liệu /
nhân công theo từng nhóm, cộng VAT và xuất báo cáo JSON.

## Yêu cầu

- Python **3.12**
- **Chỉ dùng thư viện chuẩn** (stdlib): `argparse`, `csv`, `json`, `decimal`,
  `dataclasses`, `unittest`, `subprocess`... Không có dependency bên ngoài,
  không cần cài đặt gì thêm.

## Định dạng 2 file CSV

### 1. File BOQ — khối lượng (`--boq`)

Header bắt buộc, đúng thứ tự: `code,description,unit,quantity,group`

| Cột | Ý nghĩa | Ràng buộc |
|---|---|---|
| `code` | Mã vật tư / hạng mục | Không rỗng, duy nhất |
| `description` | Diễn giải | Chuỗi tự do |
| `unit` | Đơn vị tính | Phải **khớp** đơn vị trong file đơn giá (so sánh phân biệt hoa/thường) |
| `quantity` | Khối lượng | Số thập phân **>= 0**, hữu hạn (không nhận `NaN`/`Infinity`) |
| `group` | Nhóm hạng mục | Chuỗi tự do, dùng để gom nhóm báo cáo |

Ví dụ (`data/verify_boq.csv`):

```csv
code,description,unit,quantity,group
V-001,Vat tu 1,bo,2,Nhom A
V-002,Vat tu 2,cai,3,Nhom A
```

### 2. File đơn giá (`--prices`)

Header bắt buộc, đúng thứ tự: `code,material_unit_price,labor_unit_price,unit`

| Cột | Ý nghĩa | Ràng buộc |
|---|---|---|
| `code` | Mã vật tư / hạng mục | Khớp với `code` trong file BOQ |
| `material_unit_price` | Đơn giá vật liệu | Số thập phân >= 0 |
| `labor_unit_price` | Đơn giá nhân công | Số thập phân >= 0 |
| `unit` | Đơn vị tính | Phải khớp `unit` của dòng BOQ tương ứng |

Ví dụ (`data/verify_prices.csv`):

```csv
code,material_unit_price,labor_unit_price,unit
V-001,120000,30000,bo
V-002,15000,5000,cai
```

## Lệnh CLI

```bash
python -m boq --boq <file-boq.csv> --prices <file-gia.csv> [tùy chọn]
```

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--boq` | *(bắt buộc)* | Đường dẫn file BOQ CSV |
| `--prices` | *(bắt buộc)* | Đường dẫn file đơn giá CSV |
| `--vat` | `0.10` | Thuế suất VAT dạng thập phân, trong khoảng `[0, 1]` |
| `--out` | *(không ghi)* | Ghi báo cáo JSON ra file này |
| `--strict` | tắt | Trả mã thoát `2` nếu có bất kỳ lỗi dữ liệu nào |

Mã thoát: `0` = thành công · `1` = lỗi đọc file · `2` = VAT không hợp lệ
hoặc `--strict` gặp lỗi dữ liệu.

### Ví dụ chạy

```bash
python -m boq --boq data/verify_boq.csv --prices data/verify_prices.csv \
    --vat 0.10 --out /tmp/verify_report.json
```

Output (stdout):

```text
GROUP Nhom A: material=285000 labor=75000 subtotal=360000 vat=36000 total=396000
GRAND TOTAL: material=285000 labor=75000 subtotal=360000 vat=36000 total=396000
Errors: 0 (excluded rows: [])
```

Các cảnh báo dữ liệu (nếu có) được in ra **stderr** dạng:

```text
WARNING: [line 9] MISSING_PRICE: Missing price at line 9: no price entry for code 'D-007' (source=boq)
```

## 6 loại lỗi dữ liệu

| Mã lỗi | Nguồn | Ý nghĩa |
|---|---|---|
| `INVALID_ROW` | parsing | Dòng sai số cột so với header (thiếu/thừa cột) |
| `INVALID_NUMBER` | parsing | Giá trị số không parse được (`abc`, `NaN`, `Infinity`,...) |
| `NEGATIVE_QUANTITY` | parsing | `quantity` âm trong file BOQ (giá âm cũng bị loại ở file prices) |
| `DUPLICATE_CODE` | validation | `code` lặp lại — giữ dòng xuất hiện đầu tiên, loại các dòng sau |
| `MISSING_PRICE` | validation | `code` trong BOQ không có dòng đơn giá tương ứng |
| `UNIT_MISMATCH` | validation | Đơn vị trong BOQ khác đơn vị trong file giá (so sánh phân biệt hoa/thường) |

Mỗi dòng lỗi chỉ nhận **tối đa 1 lỗi** (ưu tiên: parse trước, rồi
`DUPLICATE_CODE` > `MISSING_PRICE` > `UNIT_MISMATCH`); các dòng lỗi bị loại
khỏi tính toán và liệt kê trong `excluded_rows`.

## Chạy test

```bash
python -m unittest discover -s tests -v
```

- `tests/test_parsing.py`, `test_validation.py`, `test_pricing.py`,
  `test_report.py`, `test_cli.py` — unit test cho từng module.
- `tests/test_integration.py` — integration test chạy CLI thật qua
  `subprocess` (`python -m boq ...`) trên dữ liệu trong `data/`.

CI: `.github/workflows/ci.yml` chạy `python -m unittest discover -s tests -v`
trên Python 3.12 cho mỗi push / pull request.

## Cấu trúc báo cáo JSON (`--out`)

```json
{
  "meta": {
    "boq_file": "data/verify_boq.csv",
    "prices_file": "data/verify_prices.csv",
    "vat_rate": "0.10",
    "generated_at": "2026-10-10T09:46:59.123456+00:00",
    "valid_rows": 2,
    "excluded_rows": 0
  },
  "groups": {
    "Nhom A": {
      "material": "285000",
      "labor": "75000",
      "subtotal": "360000",
      "vat": "36000",
      "total": "396000"
    }
  },
  "totals": {
    "material": "285000",
    "labor": "75000",
    "subtotal": "360000",
    "vat": "36000",
    "total": "396000"
  },
  "errors": [],
  "excluded_rows": []
}
```

Lưu ý: mọi số tiền trong JSON là **string** (không phải number) để giữ
nguyên precision của `Decimal`; `vat_rate` trong `meta` cũng là string.

## Lưu ý về VAT

- `--vat` nhận thuế suất dạng thập phân: `0.10` = 10%, `0` = không thuế.
  Giá trị ngoài khoảng `[0, 1]` → mã thoát `2`.
- Mọi số tiền được làm tròn về **đồng VND** (số nguyên) theo `ROUND_HALF_UP`.
- VAT được tính **riêng cho từng group** (`vat = round(subtotal_group × rate)`)
  rồi mới cộng dồn thành grand total; grand total VAT là
  `round(subtotal_grand × rate)`. Với số liệu kiểm chứng:
  material = 2×120000 + 3×15000 = **285000**,
  labor = 2×30000 + 3×5000 = **75000**,
  subtotal = **360000**, VAT 10% = **36000**, total = **396000**.
