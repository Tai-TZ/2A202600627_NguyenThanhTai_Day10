# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Họ và tên:** Nguyễn Thành Tài  
**MSSV:** 2A202600627  
**Vai trò:** Ingestion / Cleaning / Embed / Monitoring  
**Ngày nộp:** 10/06/2026  
**run_id chính:** `day10-final`

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách toàn bộ pipeline Day 10 trong `day10/lab/`, tập trung vào ba module chính:

- `**transform/cleaning_rules.py`** — hàm `clean_rows()`: cập nhật `ALLOWED_DOC_IDS`, thêm Rule 7–10 (phân loại `legacy_*`/`invalid_doc_*`, quarantine nguồn chưa đăng ký, loại HR stale content, enrich SLA P1 escalation), normalize `exported_at`.
- `**quality/expectations.py`** — hàm `run_expectations()`: thêm E7 `all_grading_sources_present` (halt), E8 `hr_leave_has_2026_annual_marker` (halt), E9 `access_control_sop_min_one_row` (warn).
- `**etl_pipeline.py**` — chạy end-to-end, ghi log/manifest, embed Chroma collection `day10_kb` với upsert + prune.

Ngoài code, tôi viết `docs/pipeline_architecture.md`, `data_contract.md`, `runbook.md`, `quality_report.md` và chạy artifact: `artifacts/eval/grading_run.jsonl`, `after_inject_bad.csv`, `after_fix_eval.csv`.

**Bằng chứng trong code:** comment `# Rule 7` … `# Rule 10` trong `cleaning_rules.py`; comment `# E7 (mới)` … `# E9 (mới)` trong `expectations.py`. HR cutoff đọc từ env `HR_LEAVE_MIN_EFFECTIVE_DATE` (đồng bộ `contracts/data_contract.yaml`).

---

## 2. Một quyết định kỹ thuật

Tôi chọn **halt cho lỗi dữ liệu nghiêm trọng, warn cho cảnh báo sớm**.

Cụ thể: `refund_no_stale_14d_window`, `hr_leave_no_stale_10d_annual`, `all_grading_sources_present` đặt **severity=halt** — pipeline dừng (exit 2), không embed. Lý do: nếu embed chunk refund 14 ngày hoặc thiếu `access_control_sop`, grading `gq_d10_01` và `gq_d10_10` fail ngay; chi phí xóa vector và rebuild cao hơn dừng sớm ở bước validate.

Ngược lại, `access_control_sop_min_one_row` đặt **warn** vì đã có E7 halt khi thiếu nguồn — E9 chỉ bổ sung metric `access_control_rows` để debug nhanh trên log mà không trùng lặp halt.

Về idempotency: giữ chiến lược baseline — **upsert theo `chunk_id`** rồi **prune** id không còn trong cleaned snapshot (`embed_prune_removed` trong log). Index Chroma = snapshot publish, tránh vector cũ làm `hits_forbidden=true` dù cleaned đã sạch.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:** Chạy pipeline lần đầu (`run_id=baseline-test`) bị `PIPELINE_HALT`. Log ghi:

```
expectation[hr_leave_no_stale_10d_annual] FAIL (halt) :: violations=2
cleaned_records=40
```

**Phát hiện:** Hai chunk `hr_leave_policy` có `effective_date >= 2026-01-01` nhưng `chunk_text` vẫn chứa "10 ngày phép năm (bản HR 2025)". Rule baseline chỉ quarantine theo ngày `< 2026`, chưa bắt stale **theo nội dung**.

**Fix:** Thêm Rule 9 trong `clean_rows()` — quarantine reason `stale_hr_annual_leave_content` khi text chứa "10 ngày phép năm" hoặc "bản HR 2025". Đồng thời thêm `access_control_sop` vào allowlist (8 record raw, 6 cleaned sau dedupe).

**Kết quả sau fix (`run_id=day10-final`):** `cleaned_records=44` (+4), `violations=0`, pipeline exit 0, `gq_d10_09` và `gq_d10_10` pass.

**Anomaly phụ:** `gq_d10_06` ban đầu `contains_expected=false` dù chunk escalation "10 phút" có trong cleaned — embedding rank chunk P2 cao hơn. Tôi thêm Rule 10 enrich escalation vào chunk P1 SLA; sau đó grading pass.

---

## 4. Bằng chứng trước / sau

**Inject corruption** (`run_id=inject-bad`, lệnh `--no-refund-fix --skip-validate`):

Log: `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=3`

CSV `artifacts/eval/after_inject_bad.csv`, dòng `q_refund_window`:
`hits_forbidden=yes` — top-k còn "14 ngày làm việc".

**Sau fix** (`run_id=day10-final`):

CSV `artifacts/eval/after_fix_eval.csv`, cùng câu:
`hits_forbidden=no` — chỉ còn "7 ngày làm việc".

Grading chính thức `artifacts/eval/grading_run.jsonl`: 10 dòng `gq_d10_01`…`gq_d10_10`, tất cả `contains_expected=true`, `hits_forbidden=false`, `top1_doc_matches=true`. `instructor_quick_check.py` xác nhận OK.

---

## 5. Cải tiến tiếp theo (nếu có thêm 2 giờ)

Tôi sẽ đọc `HR_LEAVE_MIN_EFFECTIVE_DATE` trực tiếp từ `contracts/data_contract.yaml` (field `policy_versioning.hr_leave_min_effective_date`) thay vì chỉ env, và thêm pydantic validate schema cleaned trước embed — đáp ứng tiêu chí Distinction mục (a) trong `SCORING.md`. Ngoài ra, tách freshness đo **2 boundary** (ingest timestamp vs publish `run_timestamp`) thay vì chỉ `latest_exported_at`, để runbook phân biệt rõ data cũ từ nguồn vs pipeline chạy muộn.