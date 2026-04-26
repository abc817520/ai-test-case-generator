import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import time
import uuid
from typing import Any, Callable, TypeVar

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = PROJECT_ROOT / "workflow"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.append(str(WORKFLOW_DIR))

from utils.document_parser.docx_parser import parse_docx
from utils.document_parser.md_parser import parse_markdown
from rag.ingest import index_document
from rag.ingest import index_testcase_knowledge_file
from workflow import create_workflow


PHASE_UPLOAD = "upload"
PHASE_REQUIREMENT = "requirement_review"
PHASE_TEST_POINTS = "test_points_review"
PHASE_OUTLINE = "outline_review"
PHASE_CASE = "case_review"
PHASE_DOWNLOAD = "download"

T = TypeVar("T")

PHASE_ORDER: list[tuple[str, str]] = [
    (PHASE_UPLOAD, "上传文档"),
    (PHASE_REQUIREMENT, "需求分析"),
    (PHASE_TEST_POINTS, "测试点提取"),
    (PHASE_OUTLINE, "测试大纲"),
    (PHASE_CASE, "测试用例"),
    (PHASE_DOWNLOAD, "下载结果"),
]


def _default_state() -> dict[str, Any]:
    return {
        "document": "",
        "structured_doc": {},
        "doc_id": "",
        "requirement_analysis": "",
        "test_points": [],
        "test_outline": [],
        "modified_outline": [],
        "test_cases": [],
        "modified_test_cases": [],
        "retrieval_logs": [],
        "excel_output_path": "",
    }


@st.cache_resource
def get_graph_and_llm() -> tuple[Any, ChatOpenAI]:
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未检测到 OPENAI_API_KEY，请先在项目根目录 .env 配置。")

    base_url = os.getenv("OPENAI_BASE_URL")
    llm = ChatOpenAI(
        model="Qwen/Qwen3.5-35B-A3B",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    return create_workflow(), llm


def _ensure_session() -> None:
    if "phase" not in st.session_state:
        st.session_state.phase = PHASE_UPLOAD
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = f"web_{uuid.uuid4().hex}"
    if "source_document" not in st.session_state:
        st.session_state.source_document = ""
    if "source_structured_doc" not in st.session_state:
        st.session_state.source_structured_doc = {}
    if "source_file_name" not in st.session_state:
        st.session_state.source_file_name = ""
    if "source_doc_id" not in st.session_state:
        st.session_state.source_doc_id = ""
    if "requirement_editor_text" not in st.session_state:
        st.session_state.requirement_editor_text = ""
    if "test_points_table" not in st.session_state:
        st.session_state.test_points_table = []
    if "outline_table" not in st.session_state:
        st.session_state.outline_table = []
    if "test_cases_table" not in st.session_state:
        st.session_state.test_cases_table = []
    if "excel_output_path" not in st.session_state:
        st.session_state.excel_output_path = ""
    if "enable_multi_query" not in st.session_state:
        st.session_state.enable_multi_query = True
    if "enable_rerank" not in st.session_state:
        st.session_state.enable_rerank = True


def _build_config(llm: ChatOpenAI) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": st.session_state.thread_id,
            "llm": llm,
            "enable_multi_query": st.session_state.enable_multi_query,
            "enable_rerank": st.session_state.enable_rerank,
        }
    }


def _parse_uploaded_document(uploaded_file: Any) -> tuple[str, dict[str, Any]]:
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".md":
        raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        structured = parse_markdown(raw_text).to_dict()
        return raw_text, structured

    if suffix == ".docx":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = Path(tmp_file.name)

        try:
            structured = parse_docx(tmp_path).to_dict()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        return f"DOCX:{uploaded_file.name}", structured

    raise ValueError("仅支持 docx 或 md 文件。")


def _get_state_values(graph: Any, config: dict[str, Any]) -> dict[str, Any]:
    snapshot = graph.get_state(config)
    values = getattr(snapshot, "values", None)
    if isinstance(values, dict):
        return values
    return {}


def _cases_to_table_rows(test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in test_cases:
        row = dict(case)
        steps = row.get("steps", [])
        if isinstance(steps, list):
            row["steps"] = "\n".join(str(item) for item in steps)
        else:
            row["steps"] = str(steps)
        rows.append(row)
    return rows


def _test_points_to_table_rows(test_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in test_points:
        rows.append(
            {
                "name": str(point.get("name", "")),
                "test_type": str(point.get("test_type", "功能")),
                "priority": str(point.get("priority", "P1")),
            }
        )
    return rows


def _normalize_test_points_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "test_type": str(row.get("test_type", "功能")).strip() or "功能",
                "priority": str(row.get("priority", "P1")).strip() or "P1",
            }
        )
    return normalized


def _outline_to_table_rows(test_outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in test_outline:
        module_name = str(item.get("module_name", "")).strip()
        points = item.get("test_points", [])
        if not isinstance(points, list):
            continue

        for point in points:
            if not isinstance(point, dict):
                continue
            rows.append(
                {
                    "module_name": module_name,
                    "name": str(point.get("name", "")),
                    "test_type": str(point.get("test_type", "功能")),
                    "priority": str(point.get("priority", "P1")),
                }
            )
    return rows


def _normalize_outline_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        module_name = str(row.get("module_name", "")).strip()
        point_name = str(row.get("name", "")).strip()
        if not module_name or not point_name:
            continue

        point = {
            "name": point_name,
            "test_type": str(row.get("test_type", "功能")).strip() or "功能",
            "priority": str(row.get("priority", "P1")).strip() or "P1",
        }
        grouped.setdefault(module_name, []).append(point)

    outline: list[dict[str, Any]] = []
    for module_name, points in grouped.items():
        outline.append({"module_name": module_name, "test_points": points})
    return outline


def _editor_data_to_rows(editor_data: Any) -> list[dict[str, Any]]:
    if isinstance(editor_data, list):
        return [dict(item) for item in editor_data]

    to_dict = getattr(editor_data, "to_dict", None)
    if callable(to_dict):
        try:
            records = editor_data.to_dict(orient="records")
            return [dict(item) for item in records]
        except TypeError:
            pass

    return []


def _normalize_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        case = dict(row)
        steps_text = str(case.get("steps", ""))
        case["steps"] = [line.strip() for line in steps_text.splitlines() if line.strip()]
        normalized.append(case)
    return normalized


def _reset_flow() -> None:
    st.session_state.phase = PHASE_UPLOAD
    st.session_state.thread_id = f"web_{uuid.uuid4().hex}"
    st.session_state.source_document = ""
    st.session_state.source_structured_doc = {}
    st.session_state.source_file_name = ""
    st.session_state.source_doc_id = ""
    st.session_state.requirement_editor_text = ""
    st.session_state.test_points_table = []
    st.session_state.outline_table = []
    st.session_state.test_cases_table = []
    st.session_state.excel_output_path = ""


def _run_with_progress(task_label: str, fn: Callable[[], T]) -> T:
    """Run a blocking task with visible progress and elapsed time."""
    status = st.status(f"{task_label}中...", expanded=True)
    progress = st.progress(0, text=f"{task_label}（预估进度）")
    start = time.time()
    progress_value = 5

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            while not future.done():
                elapsed = int(time.time() - start)
                progress_value = min(progress_value + 2, 92)
                progress.progress(
                    progress_value,
                    text=f"{task_label}（预估进度） - 已等待 {elapsed}s",
                )
                time.sleep(0.2)
            result = future.result()

        total = time.time() - start
        progress.progress(100, text=f"{task_label}完成")
        status.update(
            label=f"{task_label}完成，耗时 {total:.1f}s",
            state="complete",
            expanded=False,
        )
        return result
    except Exception:
        status.update(label=f"{task_label}失败", state="error", expanded=True)
        raise


def _prime_editors_from_values(values: dict[str, Any], phase: str) -> None:
    if phase == PHASE_REQUIREMENT:
        st.session_state.requirement_editor_text = str(values.get("requirement_analysis", ""))
    if phase == PHASE_TEST_POINTS:
        st.session_state.test_points_table = _test_points_to_table_rows(values.get("test_points", []))
    if phase == PHASE_OUTLINE:
        st.session_state.outline_table = _outline_to_table_rows(values.get("test_outline", []))
    if phase == PHASE_CASE:
        st.session_state.test_cases_table = _cases_to_table_rows(values.get("test_cases", []))


def _replay_to_phase(graph: Any, llm: ChatOpenAI, target_phase: str) -> None:
    if not st.session_state.source_structured_doc:
        raise ValueError("缺少已上传文档，请先上传并开始生成。")

    invoke_count_map = {
        PHASE_REQUIREMENT: 1,
        PHASE_TEST_POINTS: 2,
        PHASE_OUTLINE: 3,
        PHASE_CASE: 4,
    }
    labels = [
        "正在生成需求分析",
        "正在提取测试点",
        "正在生成测试大纲",
        "正在生成测试用例",
    ]

    invoke_count = invoke_count_map[target_phase]
    st.session_state.thread_id = f"web_{uuid.uuid4().hex}"
    config = _build_config(llm)

    init_state = _default_state()
    init_state["document"] = st.session_state.source_document
    init_state["structured_doc"] = st.session_state.source_structured_doc
    init_state["doc_id"] = st.session_state.source_doc_id

    for index in range(invoke_count):
        payload = init_state if index == 0 else None
        _run_with_progress(labels[index], lambda p=payload: graph.invoke(p, config))

    values = _get_state_values(graph, config)
    _prime_editors_from_values(values, target_phase)
    st.session_state.phase = target_phase


def _rerun_current_phase(graph: Any, llm: ChatOpenAI, phase: str) -> None:
    """Re-run generation for current phase based on existing checkpoint state."""
    from nodes import (
        analyze_requirement_node,
        extract_test_points_node,
        generate_cases_node,
        generate_outline_node,
    )

    config = _build_config(llm)
    values = _get_state_values(graph, config)

    if phase == PHASE_REQUIREMENT:
        updates = _run_with_progress(
            "正在重新生成需求分析",
            lambda: analyze_requirement_node(values, config),
        )
    elif phase == PHASE_TEST_POINTS:
        updates = _run_with_progress(
            "正在重新提取测试点",
            lambda: extract_test_points_node(values, config),
        )
    elif phase == PHASE_OUTLINE:
        updates = _run_with_progress(
            "正在重新生成测试大纲",
            lambda: generate_outline_node(values, config),
        )
    elif phase == PHASE_CASE:
        updates = _run_with_progress(
            "正在重新生成测试用例",
            lambda: generate_cases_node(values, config),
        )
    else:
        raise ValueError(f"不支持的阶段重生成: {phase}")

    graph.update_state(config, updates)
    refreshed = _get_state_values(graph, config)
    _prime_editors_from_values(refreshed, phase)
    st.session_state.phase = phase


def _render_upload_page(graph: Any, llm: ChatOpenAI) -> None:
    st.subheader("1. 上传需求文档")
    uploaded_file = st.file_uploader("支持 docx / md", type=["docx", "md"])

    if st.button("开始生成", type="primary"):
        if uploaded_file is None:
            st.warning("请先上传文档。")
            return

        try:
            doc_id = f"web_{uuid.uuid4().hex}"
            document, structured_doc = _parse_uploaded_document(uploaded_file)
            indexed_chunks = index_document(
                doc_id=doc_id,
                source_name=uploaded_file.name,
                structured_doc=structured_doc,
            )
            st.session_state.source_document = document
            st.session_state.source_structured_doc = structured_doc
            st.session_state.source_file_name = uploaded_file.name
            st.session_state.source_doc_id = doc_id
            st.info(f"文档入库完成，chunk 数：{indexed_chunks}")
            _replay_to_phase(graph, llm, PHASE_REQUIREMENT)
            st.rerun()
        except Exception as exc:
            st.error(f"启动流程失败：{exc}")


def _render_testcase_kb_uploader() -> None:
    st.subheader("测试用例知识库入库")
    uploaded_files = st.file_uploader(
        "上传历史测试用例（md/docx，可多选）",
        type=["md", "docx"],
        accept_multiple_files=True,
        key="testcase_kb_uploader",
    )
    module = st.text_input("module（可选）", key="testcase_kb_module")
    test_type = st.selectbox(
        "test_type（可选）",
        options=["", "功能", "性能", "安全", "兼容性"],
        index=0,
        key="testcase_kb_test_type",
    )
    priority = st.selectbox(
        "priority（可选）",
        options=["", "P0", "P1", "P2", "P3"],
        index=0,
        key="testcase_kb_priority",
    )

    if st.button("入库测试用例", key="index_testcase_kb_btn"):
        if not uploaded_files:
            st.warning("请先上传至少一个测试用例文件。")
            return

        results: list[tuple[str, bool, str]] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            for uploaded in uploaded_files:
                file_name = uploaded.name
                suffix = Path(file_name).suffix.lower()
                if suffix not in {".md", ".docx"}:
                    results.append((file_name, False, "仅支持 md/docx"))
                    continue

                tmp_path = tmp_root / file_name
                tmp_path.write_bytes(uploaded.getvalue())
                try:
                    chunks = index_testcase_knowledge_file(
                        file_path=tmp_path,
                        module=module.strip(),
                        test_type=test_type.strip(),
                        priority=priority.strip(),
                    )
                    results.append((file_name, True, f"成功，chunks={chunks}"))
                except Exception as exc:
                    results.append((file_name, False, f"失败：{exc}"))

        st.markdown("**入库结果**")
        for file_name, ok, message in results:
            if ok:
                st.success(f"{file_name}: {message}")
            else:
                st.error(f"{file_name}: {message}")


def _render_retrieval_evidence(values: dict[str, Any], phase: str, title: str) -> None:
    logs = values.get("retrieval_logs", [])
    if not isinstance(logs, list) or not logs:
        return

    latest = None
    for log in reversed(logs):
        if isinstance(log, dict) and str(log.get("phase", "")) == phase:
            latest = log
            break
    if latest is None:
        return

    with st.expander(title, expanded=False):
        st.caption(f"Query: {latest.get('query', '')}")
        expanded_queries = latest.get("expanded_queries", [])
        if isinstance(expanded_queries, list) and expanded_queries:
            st.caption(f"Expanded Queries: {len(expanded_queries)}")
            for query in expanded_queries[:3]:
                st.code(str(query), language="text")
        pre_dedup_count = latest.get("pre_dedup_count")
        post_dedup_count = latest.get("post_dedup_count")
        rerank_mode = latest.get("rerank_mode", "unknown")
        rerank_enabled = latest.get("rerank_enabled")
        rerank_latency_ms = latest.get("rerank_latency_ms", 0)
        rerank_degraded = latest.get("rerank_degraded", False)
        rerank_degraded_reason = str(latest.get("rerank_degraded_reason", "")).strip()
        if pre_dedup_count is not None and post_dedup_count is not None:
            st.caption(
                f"候选数: pre_dedup={pre_dedup_count}, post_dedup={post_dedup_count}"
            )
        st.caption(
            f"Rerank: mode={rerank_mode}, enabled={rerank_enabled}, "
            f"latency={rerank_latency_ms}ms, degraded={rerank_degraded}"
        )
        if rerank_degraded_reason:
            st.caption(f"Rerank fallback reason: {rerank_degraded_reason}")

        citations = latest.get("citations", [])
        if isinstance(citations, list) and citations:
            st.markdown("**Citations**")
            for idx, citation in enumerate(citations[:3], start=1):
                if not isinstance(citation, dict):
                    continue
                st.markdown(
                    f"{idx}. `{citation.get('chunk_id', '')}` | "
                    f"`{citation.get('section_path', '')}` | "
                    f"`{citation.get('source_name', '')}` | "
                    f"score={citation.get('score', 0.0)}"
                )

        hits = latest.get("hits", [])
        if not isinstance(hits, list) or not hits:
            st.write("未检索到依据片段。")
            return
        for idx, hit in enumerate(hits[:3], start=1):
            if not isinstance(hit, dict):
                continue
            chunk_id = str(hit.get("chunk_id", ""))
            doc_type = str(hit.get("doc_type", ""))
            section_path = str(hit.get("section_path", ""))
            source_name = str(hit.get("source_name", ""))
            score = hit.get("score", 0.0)
            preview = str(hit.get("text_preview", "")).strip()
            st.markdown(
                f"{idx}. `{chunk_id}` | `{doc_type}` | `{section_path}` | `{source_name}` | score={score}"
            )
            if preview:
                st.caption(preview)
            full_text = str(hit.get("text_full", "")).strip()
            if full_text:
                with st.expander(f"查看全文 #{idx}", expanded=False):
                    st.text(full_text)


def _render_requirement_page(graph: Any, llm: ChatOpenAI) -> None:
    st.subheader("2. 审核需求分析")
    config = _build_config(llm)
    values = _get_state_values(graph, config)
    requirement_analysis = str(values.get("requirement_analysis", ""))

    if not st.session_state.requirement_editor_text:
        st.session_state.requirement_editor_text = requirement_analysis

    st.caption("AI 生成需求分析")
    st.text_area("编辑需求分析", key="requirement_editor_text", height=280)

    col1, col2 = st.columns(2)
    if col1.button("通过并提取测试点", type="primary"):
        try:
            graph.update_state(
                config,
                {"requirement_analysis": st.session_state.requirement_editor_text.strip()},
            )
            _run_with_progress("正在提取测试点", lambda: graph.invoke(None, config))
            next_values = _get_state_values(graph, config)
            st.session_state.test_points_table = _test_points_to_table_rows(
                next_values.get("test_points", [])
            )
            st.session_state.phase = PHASE_TEST_POINTS
            st.rerun()
        except Exception as exc:
            st.error(f"提取测试点失败：{exc}")

    if col2.button("重新生成需求分析"):
        try:
            _rerun_current_phase(graph, llm, PHASE_REQUIREMENT)
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    _render_retrieval_evidence(values, "analyze_requirement", "本阶段依据片段")


def _render_test_points_page(graph: Any, llm: ChatOpenAI) -> None:
    st.subheader("3. 审核测试点")
    config = _build_config(llm)
    values = _get_state_values(graph, config)

    if not st.session_state.test_points_table:
        st.session_state.test_points_table = _test_points_to_table_rows(values.get("test_points", []))

    st.caption("AI 生成测试点")
    edited_data = st.data_editor(
        st.session_state.test_points_table,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "name": st.column_config.TextColumn("测试点", required=True),
            "test_type": st.column_config.SelectboxColumn(
                "类型", options=["功能", "性能", "安全", "兼容性"], required=True
            ),
            "priority": st.column_config.SelectboxColumn(
                "优先级", options=["P0", "P1", "P2", "P3"], required=True
            ),
        },
    )

    col1, col2 = st.columns(2)
    if col1.button("通过并生成测试大纲", type="primary"):
        try:
            test_points_rows = _editor_data_to_rows(edited_data)
            test_points = _normalize_test_points_rows(test_points_rows)
            if not test_points:
                raise ValueError("至少保留一个有效测试点。")

            graph.update_state(config, {"test_points": test_points})
            _run_with_progress("正在生成测试大纲", lambda: graph.invoke(None, config))
            next_values = _get_state_values(graph, config)
            st.session_state.outline_table = _outline_to_table_rows(next_values.get("test_outline", []))
            st.session_state.phase = PHASE_OUTLINE
            st.rerun()
        except Exception as exc:
            st.error(f"生成测试大纲失败：{exc}")

    if col2.button("重新生成测试点"):
        try:
            _rerun_current_phase(graph, llm, PHASE_TEST_POINTS)
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    _render_retrieval_evidence(values, "extract_test_points", "本阶段依据片段")


def _render_outline_page(graph: Any, llm: ChatOpenAI) -> None:
    st.subheader("4. 审核测试大纲")
    config = _build_config(llm)
    values = _get_state_values(graph, config)

    if not st.session_state.outline_table:
        st.session_state.outline_table = _outline_to_table_rows(values.get("test_outline", []))

    st.caption("AI 生成测试大纲")
    edited_data = st.data_editor(
        st.session_state.outline_table,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "module_name": st.column_config.TextColumn("模块", required=True),
            "name": st.column_config.TextColumn("测试点", required=True),
            "test_type": st.column_config.SelectboxColumn(
                "类型", options=["功能", "性能", "安全", "兼容性"], required=True
            ),
            "priority": st.column_config.SelectboxColumn(
                "优先级", options=["P0", "P1", "P2", "P3"], required=True
            ),
        },
    )

    col1, col2 = st.columns(2)
    if col1.button("通过并生成测试用例", type="primary"):
        try:
            outline_rows = _editor_data_to_rows(edited_data)
            modified_outline = _normalize_outline_rows(outline_rows)
            if not modified_outline:
                raise ValueError("至少保留一个有效模块与测试点。")

            graph.update_state(config, {"modified_outline": modified_outline})
            _run_with_progress("正在生成测试用例", lambda: graph.invoke(None, config))
            next_values = _get_state_values(graph, config)
            st.session_state.test_cases_table = _cases_to_table_rows(
                next_values.get("test_cases", [])
            )
            st.session_state.phase = PHASE_CASE
            st.rerun()
        except Exception as exc:
            st.error(f"生成测试用例失败：{exc}")

    if col2.button("重新生成测试大纲"):
        try:
            _rerun_current_phase(graph, llm, PHASE_OUTLINE)
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    _render_retrieval_evidence(values, "generate_outline", "本阶段依据片段")


def _render_case_page(graph: Any, llm: ChatOpenAI) -> None:
    st.subheader("5. 审核测试用例")
    config = _build_config(llm)
    values = _get_state_values(graph, config)

    edited_data = st.data_editor(
        st.session_state.test_cases_table,
        width="stretch",
        num_rows="dynamic",
    )

    col1, col2 = st.columns(2)
    if col1.button("通过并导出 Excel", type="primary"):
        try:
            config = _build_config(llm)
            case_rows = _editor_data_to_rows(edited_data)
            modified_cases = _normalize_cases(case_rows)
            graph.update_state(config, {"modified_test_cases": modified_cases})

            final_state = _run_with_progress("正在导出 Excel", lambda: graph.invoke(None, config))

            excel_path = ""
            if isinstance(final_state, dict):
                excel_path = str(final_state.get("excel_output_path", ""))
            if not excel_path:
                values = _get_state_values(graph, config)
                excel_path = str(values.get("excel_output_path", ""))

            st.session_state.excel_output_path = excel_path
            st.session_state.phase = PHASE_DOWNLOAD
            st.rerun()
        except Exception as exc:
            st.error(f"导出失败：{exc}")

    if col2.button("重新生成测试用例"):
        try:
            _rerun_current_phase(graph, llm, PHASE_CASE)
            st.rerun()
        except Exception as exc:
            st.error(f"重新生成失败：{exc}")

    _render_retrieval_evidence(values, "generate_cases_requirement", "需求依据片段")
    _render_retrieval_evidence(values, "generate_cases_testcase", "历史用例参考片段")


def _render_download_page() -> None:
    st.subheader("6. 下载测试用例")
    excel_output_path = st.session_state.excel_output_path

    if excel_output_path and Path(excel_output_path).exists():
        output_path = Path(excel_output_path)
        st.success(f"已生成文件：{output_path}")
        st.download_button(
            label="下载 Excel 文件",
            data=output_path.read_bytes(),
            file_name=output_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.warning("未找到导出的 Excel 文件，请返回上一步重新导出。")

    if st.button("生成新的测试用例"):
        _reset_flow()
        st.rerun()


def _render_phase_nav(phase: str) -> None:
    labels = [label for _, label in PHASE_ORDER]
    phase_index_map = {phase_name: idx for idx, (phase_name, _) in enumerate(PHASE_ORDER)}
    current_index = phase_index_map.get(phase, 0)

    cols = st.columns(len(labels))
    for idx, col in enumerate(cols):
        if idx < current_index:
            col.success(f"已完成\n{idx + 1}. {labels[idx]}")
        elif idx == current_index:
            col.info(f"当前\n{idx + 1}. {labels[idx]}")
        else:
            col.caption(f"待执行\n{idx + 1}. {labels[idx]}")


def main() -> None:
    st.set_page_config(page_title="AI 测试用例生成器", layout="wide")
    st.title("AI 测试用例生成器")

    _ensure_session()
    with st.sidebar:
        st.subheader("RAG 设置")
        st.session_state.enable_multi_query = st.toggle(
            "启用 Multi-Query",
            value=st.session_state.enable_multi_query,
        )
        st.session_state.enable_rerank = st.toggle(
            "启用 Rerank",
            value=st.session_state.enable_rerank,
        )
        st.divider()
        _render_testcase_kb_uploader()

    try:
        graph, llm = get_graph_and_llm()
    except Exception as exc:
        st.error(f"初始化失败：{exc}")
        st.stop()

    phase = st.session_state.phase
    _render_phase_nav(phase)
    st.divider()

    if phase == PHASE_UPLOAD:
        _render_upload_page(graph, llm)
    elif phase == PHASE_REQUIREMENT:
        _render_requirement_page(graph, llm)
    elif phase == PHASE_TEST_POINTS:
        _render_test_points_page(graph, llm)
    elif phase == PHASE_OUTLINE:
        _render_outline_page(graph, llm)
    elif phase == PHASE_CASE:
        _render_case_page(graph, llm)
    elif phase == PHASE_DOWNLOAD:
        _render_download_page()
    else:
        _reset_flow()
        st.rerun()


if __name__ == "__main__":
    main()
