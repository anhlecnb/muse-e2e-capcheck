# AUDIT REPORT — Adversarial Quality Audit (Assessment #3)

**Đối tượng:** PR #2 — BOQ Estimation Engine (`feature/boq-engine`)
**Branch audit:** `feature/boq-audit` (tách từ `feature/boq-engine`, không merge)
**Phương pháp:** đọc toàn bộ source + test trước, viết test tái hiện đỏ
trước khi sửa (red-green), commit riêng từng bước `test(audit)` / `fix(audit)`.
Bằng chứng chi tiết: `AUDIT_EVIDENCE.md`. Test mới: `tests/test_audit.py`.

**Kết quả tổng:** 9 findings (5 software-bug, 3 business-issue, 1 missing-feature
được nâng thành fix). 23 test audit mới, tổng suite **88/88 pass**.

---

## Findings

### F1 — `--vat NaN` crash bằng `InvalidOperation` không được bắt
- **Mức độ:** critical · **Phân loại:** software-bug
- **Mô tả:** `compute_estimate` kiểm tra `vat_rate < 0 or vat_rate > 1`, nhưng
  so sánh thứ tự của `Decimal("NaN")` **raise `InvalidOperation`** chứ không
  trả về False. CLI chỉ bắt `ValueError` → traceback, exit code 1.
- **Bằng chứng FAIL:** `decimal.InvalidOperation` tại `boq/pricing.py`
  (xem `AUDIT_EVIDENCE.md`).
- **Fix:** kiểm tra `vat_rate.is_finite()` trước khi so sánh khoảng →
  `ValueError` rõ ràng → CLI thoát mã 2 gọn gàng, không traceback.
- **Bằng chứng PASS:** 2/2 test F1 xanh; full suite xanh.

### F2 — Header CSV sai / file rỗng → `ValueError` không được bắt → traceback
- **Mức độ:** major · **Phân loại:** software-bug
- **Mô tả:** `_check_header` raise `ValueError`; CLI chỉ bắt `FileNotFoundError`
  → chạy thật in traceback.
- **Fix:** thêm `CsvFormatError(ValueError)` trong `boq/parsing.py`; CLI bắt
  riêng và in `ERROR: Invalid header in ...`, thoát mã 1. Dùng subclass nên
  các test cũ `assertRaises(ValueError)` vẫn đúng.
- **Bằng chứng:** red 3 fail → green 3 pass (xem `AUDIT_EVIDENCE.md`).

### F3 — File CSV có BOM (UTF-8-BOM từ Excel) bị từ chối
- **Mức độ:** major · **Phân loại:** software-bug
- **Mô tả:** ký tự `\ufeff` dính vào tên cột đầu → header check fail.
  File Excel xuất ra rất hay có BOM — lỗi thực tế, không phải lý thuyết.
- **Fix:** đọc cả hai file bằng `encoding="utf-8-sig"` (tự loại BOM nếu có,
  không ảnh hưởng file không BOM).
- **Bằng chứng:** red 3 fail → green 3 pass.

### F4 — Chính sách làm tròn: Σ VAT group vs VAT grand có thể lệch
- **Mức độ:** major · **Phân loại:** business-issue
- **Mô tả:** VAT group = `round_half_up(group_subtotal × rate)`; nếu cộng các
  VAT group lại có thể lệch ±1đ/group so với VAT tính trên grand subtotal.
  Ví dụ: 2 group subtotal=5đ, VAT 10% → VAT mỗi group = round(0.5) = 1
  (tổng 2), nhưng VAT grand = round(10×0.10) = 1.
- **Quyết định thiết kế:** VAT grand làm tròn **một lần** trên grand subtotal
  (chuẩn kế toán), không phải tổng VAT các group. Σ VAT group lệch vài đồng
  là **hành vi đúng theo thiết kế**. `total = subtotal + vat` luôn đúng ở
  mọi cấp. Đã ghi vào docstring `compute_estimate`, README và test khóa F4.
- Không có red phase (không phải bug) — test khóa chính sách, pass ngay và
  xác nhận đúng hành vi hiện tại.

### F5 — `excluded_rows` mất thông tin file nguồn
- **Mức độ:** major · **Phân loại:** software-bug
- **Mô tả:** `excluded_rows = sorted({e.line_number for e in errors})` —
  set int dedupe xuyên file: lỗi ở boq.csv dòng 5 và prices.csv dòng 5 bị gộp
  thành `[5]`, không truy vết được. Phát hiện phụ: `meta["excluded_rows"]`
  là COUNT (int) trong khi `report["excluded_rows"]` là LIST — trùng tên khác kiểu.
- **Fix:** `excluded_rows` thành list `{"source", "line_number"}` sorted theo
  `(source, line_number)`; meta đổi thành `excluded_row_count`;
  `format_summary` in `excluded rows: [boq:5, prices:3]`.
- Các test hiện có được cập nhật sang contract mới **chặt hơn** (có kiểm tra
  source), không nới lỏng assertion nào.
- **Bằng chứng:** red 3 fail → green; full suite 78/78 lúc đó.

### F6 — Giá âm dùng chung mã `INVALID_NUMBER`
- **Mức độ:** minor · **Phân loại:** software-bug
- **Mô tả:** giá âm trong prices.csv bị gán `INVALID_NUMBER` — chỉ message mới
  nhắc "negative". Mã lỗi là contract cho máy đọc/lọc.
- **Fix:** thêm hằng `NEGATIVE_PRICE` trong `boq/models.py`, dùng cho nhánh
  giá âm. Test hiện có được cập nhật sang mã chính xác hơn.
- **Bằng chứng:** red 2 fail → green; full suite 80/80 lúc đó.

### F7 — `--out` vào đường dẫn không ghi được → `OSError` traceback
- **Mức độ:** minor · **Phân loại:** software-bug
- **Fix:** bắt `OSError` quanh `write_report` → `ERROR: cannot write report
  to ...`, thoát mã 1.
- **Bằng chứng:** red 1 error → green; full suite 81/81 lúc đó.

### F8 — Các biên của `--vat` chưa được khóa (Infinity, khoảng trắng, 1=100%, "10")
- **Mức độ:** minor · **Phân loại:** business-issue
- **Quyết định thiết kế:** `--vat` là phân số thập phân trong `[0, 1]`;
  `1` = 100%; nhập `10` (ý 10%) bị từ chối kèm gợi ý khoảng `[0, 1]` thay vì
  âm thầm tính 1000%; `Infinity`/`NaN` bị từ chối; khoảng trắng quanh số được chấp nhận.
- 5 locking test, pass ngay (khóa hành vi đúng hiện tại + fix F1).

### F9 — Chính sách case-sensitivity và phân tách hàng nghìn
- **Mức độ:** minor · **Phân loại:** business-issue
- **Quyết định thiết kế:** mã và đơn vị so sánh **phân biệt hoa/thường**
  (`"A-001"` ≠ `"a-001"` → `MISSING_PRICE`) — mismatch explicit tốt hơn
  silent merge. Chuỗi `"1,000"` mơ hồ (1000 hay 1.000?) → từ chối
  `INVALID_NUMBER`, không đoán mò.
- 2 locking test, pass ngay; đã ghi README.

---

## Quyết định thiết kế đã chốt (tổng hợp)

1. **Làm tròn tiền:** `ROUND_HALF_UP` về đồng nguyên (đúng nghiệp vụ VND,
   không dùng banker's rounding). Làm tròn từng dòng trước khi cộng dồn.
2. **VAT:** phân số thập phân trong `[0, 1]`, hữu hạn; VAT grand làm tròn một
   lần trên grand subtotal (F4).
3. **Trùng mã** (cả 2 file): giữ dòng đầu + báo `DUPLICATE_CODE`.
4. **So sánh mã/đơn vị:** case-sensitive, explicit (F9).
5. **Số mơ hồ** (`"1,000"`, `NaN`, `Infinity`): từ chối, không đoán (F9, F1).
6. **BOM:** đọc trong suốt bằng `utf-8-sig` (F3).
7. **Triết lý lỗi:** thu thập hết lỗi, loại dòng lỗi khỏi tính toán, mặc định
   lenient (exit 0 + WARNING stderr); `--strict` để gating CI (exit 2).
8. **Mã thoát:** 0 ok · 1 lỗi file (không thấy / sai format / không ghi được
   report) · 2 tham số sai hoặc `--strict` gặp lỗi dữ liệu. Không bao giờ
   in traceback ra người dùng cuối.
9. **JSON:** tiền dạng string giữ precision; `excluded_rows` mang source;
   `meta.excluded_row_count` là số lượng (F5).

---

## Đánh giá enterprise-readiness (trung thực)

**Đã đủ tốt:**
- Thuần stdlib → không rủi ro supply-chain, cài đặt zero-dependency.
- Tiền tệ `Decimal` + chính sách làm tròn rõ ràng, có test khóa.
- 88 test (65 gốc + 23 audit), CI xanh; CLI không bao giờ traceback.
- Báo cáo JSON máy đọc được, lỗi truy vết được đến file + dòng.

**Chưa đủ cho nghiệp vụ doanh nghiệp có tính pháp lý / kiểm toán:**
1. **Thiếu audit trail:** report có `generated_at` nhưng không có hash của
   file đầu vào → không chứng minh được "báo cáo này tính từ đúng 2 file này".
   Cần thêm `sha256` của input vào `meta`. (missing-feature)
2. **Thiếu schema version** trong JSON report → đổi schema sau này làm consumer
   gãy âm thầm. Cần `"schema_version": "1.0"`. (missing-feature)
3. **Chưa có chữ ký / phê duyệt:** không có khái niệm người lập / người duyệt /
   khóa số liệu (lock) sau khi chốt. (missing-feature)
4. **i18n nửa vời:** message lỗi tiếng Anh, README tiếng Việt — cần thống nhất
   theo đối tượng dùng.
5. **Hiệu năng:** đọc toàn bộ vào RAM — ổn với BOQ thông thường (vài nghìn dòng),
   nhưng file >100k dòng nên chuyển streaming. (ghi nhận, chưa phải vấn đề)

**Kết luận:** đủ dùng cho **dự toán nội bộ** của team nhỏ ngay hôm nay; muốn
dùng cho **chốt số liệu có tính hợp đồng / kiểm toán** thì cần thêm mục
1–3 ở trên. Không tô hồng: đây là công cụ tính toán đúng, chưa phải hệ thống
kế toán.
