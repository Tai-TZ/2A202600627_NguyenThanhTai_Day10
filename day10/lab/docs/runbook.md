# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

Agent / retrieval trả lời sai: ví dụ "14 ngày hoàn tiền", "10 ngày phép năm" (HR 2025), hoặc không tìm thấy `access_control_sop` cho câu Level 4 Admin.

---

## Detection

| Signal | Cách phát hiện |
|--------|----------------|
| Expectation halt | `python etl_pipeline.py run` exit 2; log `PIPELINE_HALT` |
| Eval keyword fail | `eval_retrieval.py` → `contains_expected=no` hoặc `hits_forbidden=yes` |
| Grading fail | `grading_run.jsonl` → `contains_expected: false` |
| Freshness | `freshness_check=FAIL` trong log hoặc lệnh `freshness --manifest` |

---

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_<run-id>.json` | Có `run_id`, `cleaned_records`, `quarantine_records` |
| 2 | Mở `artifacts/quarantine/*.csv`, group by `reason` | Xác định allowlist thiếu / stale content / duplicate |
| 3 | Chạy `python eval_retrieval.py --out artifacts/eval/debug.csv` | Xác định câu fail và `top1_doc_id` |
| 4 | Đọc `artifacts/logs/run_<run-id>.log` | Xem expectation nào FAIL (halt) |

---

## Mitigation

1. Sửa `transform/cleaning_rules.py` / `quality/expectations.py`.
2. Rerun pipeline chuẩn: `python etl_pipeline.py run --run-id <new-id>`.
3. Verify: `python grading_run.py --out artifacts/eval/grading_run.jsonl`.
4. Nếu vector cũ còn sót: pipeline tự prune; hoặc xóa `chroma_db/` và embed lại.

**Rollback inject (Sprint 3):** sau `--no-refund-fix --skip-validate`, luôn chạy lại pipeline chuẩn không flag.

---

## Prevention

1. Giữ `ALLOWED_DOC_IDS` đồng bộ với `contracts/data_contract.yaml` và `grading_questions.json`.
2. Dùng expectation **halt** cho refund 14 ngày, HR 10 ngày phép, thiếu nguồn grading.
3. Freshness SLA 24h (`FRESHNESS_SLA_HOURS`) — WARN/FAIL khi export quá cũ.
4. Before/after eval sau mỗi thay đổi rule quan trọng.
5. Owner: Data Platform — review quarantine hàng tuần.
