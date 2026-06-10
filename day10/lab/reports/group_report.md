# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nguyen Thanh Tai (solo)  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyen Thanh Tai | Ingestion / Cleaning / Embed / Docs | 2A202600627 |

**Ngày nộp:** 2026-06-10  
**Repo:** `day10/lab/`  
**run_id chính:** `day10-final`

---

## 1. Pipeline tổng quan

Nguồn raw là `data/raw/policy_export_dirty.csv` — export mô phỏng từ 5 hệ thống (Policy, ITSM, FAQ, HR, IAM) cộng export lỗi (`invalid_doc_*`, `legacy_*`, nguồn chưa đăng ký). Pipeline: ingest → clean (`cleaning_rules.py`) → validate (`expectations.py`) → embed Chroma (`day10_kb`) → ghi manifest + log.

`run_id` xuất hiện ở dòng đầu log `artifacts/logs/run_day10-final.log` và `artifacts/manifests/manifest_day10-final.json`.

**Lệnh chạy một dòng:**

```bash
python etl_pipeline.py run --run-id day10-final && python grading_run.py --out artifacts/eval/grading_run.jsonl
```

---

## 2. Cleaning & expectation

Baseline halt vì 2 chunk `hr_leave_policy` có `effective_date >= 2026` nhưng vẫn chứa "10 ngày phép năm (bản HR 2025)". Thêm `access_control_sop` vào allowlist (8 record raw → 6 cleaned).

### 2a. Bảng metric_impact

| Rule / Expectation mới | Trước | Sau / inject | Chứng cứ |
|------------------------|-------|--------------|----------|
| `legacy_catalog_export` / `invalid_export_doc_id` | reason=`unknown_doc_id` (117) | legacy=31, invalid=28, unknown=58 | `quarantine_day10-final.csv` |
| `unregistered_catalog_source` | gộp unknown | +47 rows (29+18) | quarantine reason breakdown |
| `stale_hr_annual_leave_content` | cleaned=40, E6 FAIL (2) | cleaned=44, E6 OK (0) | log `baseline-test` vs `day10-final` |
| `sla_p1_escalation_enrich` | gq_d10_06 `contains_expected=false` | true | `grading_run.jsonl` |
| `all_grading_sources_present` (E7) | thiếu access_control | missing=[] | log expectation |
| `hr_leave_has_2026_annual_marker` (E8) | N/A | rows_with_12d=2 | log expectation |
| inject `--no-refund-fix` | refund violations=0 | violations=3, eval `hits_forbidden=yes` | `after_inject_bad.csv` |

**Expectation halt:** `min_one_row`, `no_empty_doc_id`, `refund_no_stale_14d_window`, `effective_date_iso`, `hr_leave_no_stale_10d_annual`, `all_grading_sources_present`, `hr_leave_has_2026_annual_marker`.

**Ví dụ fail:** run `baseline-test` → `hr_leave_no_stale_10d_annual FAIL (violations=2)` → thêm rule 9 quarantine stale HR content → pass.

---

## 3. Before / after retrieval

**Inject:** `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`

- `artifacts/eval/after_inject_bad.csv`: `q_refund_window` → `hits_forbidden=yes` (top-k còn "14 ngày")
- `artifacts/eval/after_fix_eval.csv`: `hits_forbidden=no` (chỉ "7 ngày")

Grading: 10/10 pass trong `artifacts/eval/grading_run.jsonl`.

---

## 4. Freshness & monitoring

SLA 24h. Sau normalize `exported_at`, timestamp parse được; `freshness_check=FAIL` vì `latest_exported_at=2026-04-11` cách thời điểm run ~60 ngày (> 24h SLA) — đúng kịch bản dữ liệu mẫu cũ. WARN xảy ra khi timestamp không parse (đã fix slash → dash).

---

## 5. Liên hệ Day 09

Day 10 làm sạch export trước khi embed; Day 09 agent có thể dùng collection `day10_kb` thay vì đọc raw. Tách collection để không ảnh hưởng vector store Day 09 trong cùng repo.

---

## 6. Rủi ro còn lại

- Embedding ranking phụ thuộc model — rule enrich SLA là mitigation tạm.
- Chưa có alert tự động Slack/email khi expectation halt.

---

## Peer review (3 câu hỏi)

1. Rule mới của bạn có thay đổi số liệu quarantine/cleaned không? Chứng minh bằng file nào?
2. Khi inject `--skip-validate`, rủi ro gì nếu quên chạy lại pipeline chuẩn?
3. Vì sao cần prune vector sau mỗi publish thay vì chỉ upsert?
