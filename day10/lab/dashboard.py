#!/usr/bin/env python3
"""
Day 10 — Dashboard trực quan (pipeline + retrieval + grading).

Không phải chatbot LLM — chỉ visualize data layer sau ETL/embed.
Chạy: streamlit run dashboard.py

Yêu cầu: đã chạy `python etl_pipeline.py run` ít nhất một lần.
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from monitoring.freshness_check import check_manifest_freshness

load_dotenv()

ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts"


@st.cache_resource
def get_chroma_collection():
    import chromadb
    from chromadb.utils import embedding_functions

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    collection_name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    return client.get_collection(name=collection_name, embedding_function=emb)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def latest_manifest() -> Optional[Path]:
    manifests = sorted((ART / "manifests").glob("manifest_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return manifests[0] if manifests else None


def latest_quarantine_for_run(run_id: str) -> Optional[Path]:
    safe = run_id.replace(":", "-")
    p = ART / "quarantine" / f"quarantine_{safe}.csv"
    return p if p.is_file() else None


def query_retrieval(question: str, top_k: int = 5) -> Dict[str, Any]:
    col = get_chroma_collection()
    res = col.query(query_texts=[question], n_results=top_k)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]
    hits = []
    for i, (chunk_id, meta, doc) in enumerate(zip(ids, metas, docs), start=1):
        hits.append(
            {
                "rank": i,
                "chunk_id": chunk_id,
                "doc_id": (meta or {}).get("doc_id", ""),
                "effective_date": (meta or {}).get("effective_date", ""),
                "text": doc or "",
            }
        )
    return {"hits": hits, "top1_doc_id": hits[0]["doc_id"] if hits else ""}


def status_badge(ok: bool, label_ok: str = "PASS", label_bad: str = "FAIL") -> str:
    return label_ok if ok else label_bad


def main() -> None:
    st.set_page_config(
        page_title="Day 10 — Data Pipeline Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("Day 10 — Data Pipeline & Observability")
    st.caption(
        "Dashboard trực quan cho ETL / clean / validate / embed. "
        "**Không** phải chatbot LLM — Day 10 tập trung tầng dữ liệu."
    )

    manifest_path = latest_manifest()
    manifest: Dict[str, Any] = {}
    if manifest_path:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    run_id = manifest.get("run_id", "—")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("run_id", run_id)
    col2.metric("raw_records", manifest.get("raw_records", "—"))
    col3.metric("cleaned_records", manifest.get("cleaned_records", "—"))
    col4.metric("quarantine_records", manifest.get("quarantine_records", "—"))

    tab_overview, tab_grading, tab_retrieval, tab_quarantine, tab_compare = st.tabs(
        ["Tổng quan", "Grading 10 câu", "Retrieval Explorer", "Quarantine", "Before / After"]
    )

    with tab_overview:
        st.subheader("Manifest & Freshness")
        if manifest_path:
            st.json(manifest)
            sla = float(os.environ.get("FRESHNESS_SLA_HOURS", "24"))
            status, detail = check_manifest_freshness(manifest_path, sla_hours=sla)
            color = {"PASS": "green", "WARN": "orange", "FAIL": "red"}.get(status, "gray")
            st.markdown(f"**Freshness:** :{color}[{status}]")
            st.json(detail)
        else:
            st.warning("Chưa có manifest. Chạy: `python etl_pipeline.py run --run-id day10-final`")

        st.subheader("Pipeline flow")
        st.code(
            "raw CSV → clean → expectations → embed (Chroma day10_kb) → manifest + log",
            language="text",
        )
        st.info(
            "Day 10 **không yêu cầu** UI chatbot để chấm điểm. "
            "Dashboard này chỉ để demo trực quan sau khi pipeline chạy xong."
        )

    with tab_grading:
        st.subheader("Grading chính thức (10 câu)")
        grading_path = ART / "eval" / "grading_run.jsonl"
        rows = load_jsonl(grading_path)
        if not rows:
            st.warning("Chưa có grading. Chạy: `python grading_run.py --out artifacts/eval/grading_run.jsonl`")
        else:
            pass_count = sum(
                1
                for r in rows
                if r.get("contains_expected") and not r.get("hits_forbidden")
            )
            st.metric("Pass", f"{pass_count}/{len(rows)}")
            for r in rows:
                ok = bool(r.get("contains_expected")) and not bool(r.get("hits_forbidden"))
                top1_ok = r.get("top1_doc_matches")
                title = f"{r.get('id')} — {status_badge(ok)}"
                with st.expander(title, expanded=not ok):
                    st.write(r.get("question"))
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**top1_doc_id:** `{r.get('top1_doc_id')}`")
                    c2.write(f"**contains_expected:** `{r.get('contains_expected')}`")
                    c3.write(f"**hits_forbidden:** `{r.get('hits_forbidden')}`")
                    if top1_ok is not None:
                        st.write(f"**top1_doc_matches:** `{top1_ok}`")

    with tab_retrieval:
        st.subheader("Retrieval Explorer")
        st.caption("Gõ câu hỏi → xem top-k chunk từ vector store (không gọi LLM).")

        grading_qs = json.loads((ROOT / "data" / "grading_questions.json").read_text(encoding="utf-8"))
        preset_labels = [f"{q['id']}: {q['question'][:60]}…" for q in grading_qs]
        preset = st.selectbox("Câu mẫu (grading)", ["— Tự nhập —"] + preset_labels)
        default_q = ""
        if preset != "— Tự nhập —":
            idx = preset_labels.index(preset)
            default_q = grading_qs[idx]["question"]

        question = st.text_area("Câu hỏi", value=default_q, height=80)
        top_k = st.slider("top-k", 1, 10, 5)

        if st.button("Tìm kiếm", type="primary"):
            if not question.strip():
                st.error("Nhập câu hỏi.")
            else:
                try:
                    result = query_retrieval(question.strip(), top_k=top_k)
                    st.success(f"Top-1 doc_id: `{result['top1_doc_id']}`")
                    for hit in result["hits"]:
                        with st.container(border=True):
                            st.markdown(f"**#{hit['rank']}** `{hit['doc_id']}` · `{hit['effective_date']}`")
                            st.write(hit["text"][:500])
                            if len(hit["text"]) > 500:
                                st.caption("… (truncated)")
                except Exception as e:
                    st.error(f"Chưa có collection Chroma. Chạy pipeline trước. ({e})")

    with tab_quarantine:
        st.subheader("Phân loại quarantine")
        q_path = latest_quarantine_for_run(run_id) if run_id != "—" else None
        if not q_path or not q_path.is_file():
            st.warning("Không tìm thấy quarantine CSV cho run hiện tại.")
        else:
            qrows = load_csv(q_path)
            reasons = Counter(r.get("reason", "unknown") for r in qrows)
            st.bar_chart(dict(sorted(reasons.items(), key=lambda x: -x[1])))
            st.dataframe(
                [{"reason": k, "count": v} for k, v in reasons.most_common()],
                use_container_width=True,
            )
            show_reason = st.selectbox("Xem chi tiết reason", ["—"] + [k for k, _ in reasons.most_common()])
            if show_reason != "—":
                sample = [r for r in qrows if r.get("reason") == show_reason][:20]
                st.dataframe(sample, use_container_width=True)

    with tab_compare:
        st.subheader("Before / After (Sprint 3)")
        bad_path = ART / "eval" / "after_inject_bad.csv"
        good_path = ART / "eval" / "after_fix_eval.csv"
        bad_rows = load_csv(bad_path)
        good_rows = load_csv(good_path)

        if not bad_rows and not good_rows:
            st.warning(
                "Chưa có eval CSV. Chạy inject + fix theo README Sprint 3."
            )
        else:
            key_ids = ["q_refund_window", "q_leave_version"]
            for qid in key_ids:
                bad = next((r for r in bad_rows if r.get("question_id") == qid), None)
                good = next((r for r in good_rows if r.get("question_id") == qid), None)
                if bad or good:
                    st.markdown(f"### `{qid}`")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Inject bad**")
                        if bad:
                            st.write(f"hits_forbidden: `{bad.get('hits_forbidden')}`")
                            st.write(f"contains_expected: `{bad.get('contains_expected')}`")
                            st.caption(bad.get("top1_preview", ""))
                        else:
                            st.write("—")
                    with c2:
                        st.markdown("**Sau fix**")
                        if good:
                            st.write(f"hits_forbidden: `{good.get('hits_forbidden')}`")
                            st.write(f"contains_expected: `{good.get('contains_expected')}`")
                            st.caption(good.get("top1_preview", ""))
                        else:
                            st.write("—")

            if bad_rows and good_rows:
                st.subheader("Toàn bộ eval")
                c1, c2 = st.columns(2)
                c1.markdown("**after_inject_bad.csv**")
                c1.dataframe(bad_rows, use_container_width=True)
                c2.markdown("**after_fix_eval.csv**")
                c2.dataframe(good_rows, use_container_width=True)

    st.sidebar.header("Lệnh nhanh")
    st.sidebar.code(
        "python etl_pipeline.py run --run-id day10-final\n"
        "python grading_run.py --out artifacts/eval/grading_run.jsonl\n"
        "streamlit run dashboard.py",
        language="bash",
    )
    st.sidebar.markdown("**Phạm vi:** chỉ `day10/lab` — không đụng Day 08/09.")


if __name__ == "__main__":
    main()
