# Data contract — Lab Day 10

> Đồng bộ với `contracts/data_contract.yaml`

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` | CSV export từ Policy DB | Stale chunk "14 ngày" thay vì 7 ngày | `refund_no_stale_14d_window` halt; eval `hits_forbidden` |
| `sla_p1_2026` | CSV export từ ITSM | Chunk P1 thiếu dòng escalation 10 phút trong top-k | eval `contains_expected` false cho gq_d10_06 |
| `hr_leave_policy` | CSV export từ HRIS | Version conflict 2025 (10 ngày) vs 2026 (12 ngày) | `quarantine_records` tăng; `hr_leave_no_stale_10d_annual` halt |
| `it_helpdesk_faq` | CSV export FAQ portal | Duplicate chunk_text | `duplicate_chunk_text` trong quarantine CSV |
| `access_control_sop` | CSV export IAM (ban đầu thiếu allowlist) | Bị quarantine `unknown_doc_id` → grading gq_d10_10 fail | `all_grading_sources_present` halt |
| `invalid_doc_*` / `legacy_*` | Export catalog lỗi | doc_id không đăng ký | `invalid_export_doc_id`, `legacy_catalog_export` counts |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | SHA256-based stable id |
| doc_id | string | Có | Một trong 5 allowlist canonical |
| chunk_text | string | Có | min 8 ký tự; có thể có marker `[cleaned: …]` |
| effective_date | date | Có | ISO `YYYY-MM-DD` sau normalize |
| exported_at | datetime | Có | Slash `/` được chuẩn hóa thành `-` |

---

## 3. Quy tắc quarantine vs drop

- Record lỗi → `artifacts/quarantine/quarantine_<run-id>.csv` với cột `reason`.
- Không drop im lặng: mọi reject đều có reason (`unknown_doc_id`, `stale_hr_annual_leave_content`, …).
- Merge lại: cần owner Data Platform review quarantine CSV, sửa nguồn upstream, rerun pipeline.

---

## 4. Phiên bản & canonical

| doc_id | Source of truth | Version rule |
|--------|-----------------|--------------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | Cửa sổ hoàn tiền = 7 ngày làm việc |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | `effective_date >= HR_LEAVE_MIN_EFFECTIVE_DATE` (env: `2026-01-01`); loại nội dung "bản HR 2025" |
| `access_control_sop` | `data/docs/access_control_sop.txt` | Level 4 = IT Manager + CISO |
