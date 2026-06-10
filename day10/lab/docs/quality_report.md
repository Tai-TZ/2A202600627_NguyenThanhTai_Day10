# Quality report — Lab Day 10

**run_id:** `day10-final`  
**Ngày:** 2026-06-10

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (baseline chưa sửa) | Sau (`day10-final`) | Ghi chú |
|--------|---------------------------|---------------------|---------|
| raw_records | 247 | 247 | Không đổi |
| cleaned_records | 40 | 44 | +4 nhờ thêm `access_control_sop` |
| quarantine_records | 207 | 203 | Phân loại reason rõ hơn (legacy/invalid/unregistered) |
| Expectation halt? | Có (`hr_leave_no_stale_10d_annual`) | Không — exit 0 | 2 chunk HR stale content đã quarantine |

---

## 2. Before / after retrieval

**File:** `artifacts/eval/after_inject_bad.csv` (trước) vs `artifacts/eval/after_fix_eval.csv` (sau)

### Câu then chốt: `q_refund_window`

| | inject-bad | day10-final |
|---|------------|-------------|
| top1_preview | "...14 ngày làm việc..." | "...7 ngày làm việc..." |
| contains_expected | yes | yes |
| hits_forbidden | **yes** | **no** |

### HR versioning: `gq_d10_09` (grading)

| | inject-bad (nếu bỏ HR rules) | day10-final |
|---|------------------------------|-------------|
| contains_expected | có thể false | true |
| hits_forbidden | có thể true (10 ngày) | false |

---

## 3. Freshness & monitor

```bash
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_day10-final.json
```

- SLA: 24 giờ (`FRESHNESS_SLA_HOURS=24`)
- Sau normalize `exported_at`: timestamp parse được (`2026-04-11T00:00:00`)
- Kết quả: **FAIL** — `age_hours≈1447` (> 24h) vì dữ liệu mẫu export từ tháng 4, run pipeline tháng 6 → đúng hành vi SLA
- WARN trước đó do format `2026/04/07` (slash) không parse — đã fix trong cleaning

---

## 4. Corruption inject (Sprint 3)

**Lệnh:**
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Cố ý làm hỏng:**
- Tắt rule fix refund 14→7 (`--no-refund-fix`)
- Bỏ qua expectation halt (`--skip-validate`) → embed dữ liệu xấu

**Phát hiện:**
- Expectation `refund_no_stale_14d_window` FAIL (3 violations)
- Eval `q_refund_window`: `hits_forbidden=yes`

**Khôi phục:** chạy lại pipeline chuẩn → tất cả 10 câu grading pass.

---

## 5. Hạn chế & việc chưa làm

- Chưa tích hợp Great Expectations / pydantic schema validate trên cleaned CSV.
- Freshness chỉ đo 1 boundary (publish/manifest), chưa tách ingest vs publish riêng.
- Rule enrich SLA P1 escalation là workaround retrieval — lý tưởng nên cải thiện chunking upstream.
