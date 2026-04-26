import asyncio
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import Any, cast

# Ensure project root is importable before importing project packages.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from rag.retriever import (
    build_citations,
    format_retrieved_context,
    retrieve_testcase_context_with_meta,
    retrieve_context_with_meta,
)
from state import TestCaseState
from utils.excel_exporter.excel_exporter import export_test_cases_to_excel

from skills.test_design_skills import (  # noqa: E402
    analyze_requirement_skill,
    extract_test_points_skill,
    generate_cases_skill,
    generate_outline_skill,
)


def _append_retrieval_log(
    state: TestCaseState,
    phase: str,
    query: str,
    expanded_queries: list[str],
    pre_dedup_count: int,
    post_dedup_count: int,
    chunks: list[Any],
    citations: list[dict[str, Any]],
    latency_ms: int,
    rerank_mode: str,
    rerank_enabled: bool,
    rerank_latency_ms: int,
    rerank_degraded: bool,
    rerank_degraded_reason: str,
) -> list[dict[str, Any]]:
    logs = list(state.get("retrieval_logs", []))
    logs.append(
        {
            "phase": phase,
            "query": query,
            "expanded_queries": expanded_queries,
            "top_k": len(chunks),
            "pre_dedup_count": pre_dedup_count,
            "post_dedup_count": post_dedup_count,
            "hits": [
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_type": getattr(chunk, "doc_type", ""),
                    "section_path": chunk.section_path,
                    "source_name": chunk.source_name,
                    "score": chunk.score,
                    "text_preview": chunk.text[:300],
                    "text_full": chunk.text,
                }
                for chunk in chunks
            ],
            "citations": citations,
            "latency_ms": latency_ms,
            "rerank_mode": rerank_mode,
            "rerank_enabled": rerank_enabled,
            "rerank_latency_ms": rerank_latency_ms,
            "rerank_degraded": rerank_degraded,
            "rerank_degraded_reason": rerank_degraded_reason,
        }
    )
    return logs


def _truncate_for_query(text: str, limit: int = 600) -> str:
    plain = str(text).strip()
    if len(plain) <= limit:
        return plain
    return plain[:limit]


def _build_retrieval_for_phase(
    state: TestCaseState,
    config: RunnableConfig | None,
    phase: str,
    query: str,
    doc_type: str = "requirement",
) -> tuple[str, list[dict[str, Any]], int]:
    doc_id = str(state.get("doc_id", "")).strip()
    if not doc_id:
        return "", list(state.get("retrieval_logs", [])), 0

    configurable = {}
    if config is not None:
        configurable = config.get("configurable", {})
    enable_multi_query = configurable.get("enable_multi_query", None)
    enable_rerank = configurable.get("enable_rerank", None)

    start = time.time()
    chunks, meta = retrieve_context_with_meta(
        query=query,
        doc_id=doc_id,
        doc_type=doc_type,
        multi_query=enable_multi_query,
        enable_rerank=enable_rerank,
    )
    elapsed_ms = int((time.time() - start) * 1000)
    citations = build_citations(chunks, limit=5)
    logs = _append_retrieval_log(
        state=state,
        phase=phase,
        query=query,
        expanded_queries=meta.expanded_queries,
        pre_dedup_count=meta.pre_dedup_count,
        post_dedup_count=meta.post_dedup_count,
        chunks=chunks,
        citations=citations,
        latency_ms=elapsed_ms,
        rerank_mode=meta.rerank_mode,
        rerank_enabled=meta.rerank_enabled,
        rerank_latency_ms=meta.rerank_latency_ms,
        rerank_degraded=meta.rerank_degraded,
        rerank_degraded_reason=meta.rerank_degraded_reason,
    )
    return format_retrieved_context(chunks), logs, elapsed_ms


def _get_llm_from_config(config: RunnableConfig | None) -> BaseChatModel:
    """Get LLM instance from LangGraph runtime config."""
    if config is None:
        raise ValueError("缺少 config，无法获取 LLM 实例。")

    configurable = config.get("configurable", {})
    llm = configurable.get("llm")
    if llm is None:
        raise ValueError(
            "请在 config['configurable']['llm'] 中传入可用的 ChatModel 实例。"
        )

    return cast(BaseChatModel, llm)


def analyze_requirement_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """调用需求分析 Skill，产出需求分析文本。"""
    print("--- 执行需求分析 Node ---")
    llm = _get_llm_from_config(config)
    query = "请提取核心业务流程、前置依赖、关键约束、异常处理和隐含非功能需求"
    retrieved_context, retrieval_logs, _ = _build_retrieval_for_phase(
        state=state,
        config=config,
        phase="analyze_requirement",
        query=query,
    )
    requirement_analysis = asyncio.run(
        analyze_requirement_skill(
            llm=llm,
            structured_doc=state["structured_doc"],
            retrieved_context=retrieved_context,
        )
    )
    return {
        "requirement_analysis": requirement_analysis,
        "retrieval_logs": retrieval_logs,
    }


def extract_test_points_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """调用测试点提取 Skill，产出测试点列表。"""
    print("--- 执行测试点提取 Node ---")
    llm = _get_llm_from_config(config)
    query = (
        f"{_truncate_for_query(state['requirement_analysis'])}\n"
        "请围绕正常流程、边界值、异常场景、权限控制和数据校验提取可测试点"
    )
    retrieved_context, retrieval_logs, _ = _build_retrieval_for_phase(
        state=state,
        config=config,
        phase="extract_test_points",
        query=query,
    )
    test_points = asyncio.run(
        extract_test_points_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
            retrieved_context=retrieved_context,
        )
    )
    return {
        "test_points": [test_point.model_dump() for test_point in test_points],
        "retrieval_logs": retrieval_logs,
    }


def generate_outline_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """基于测试点生成测试大纲。"""
    print("--- 执行测试大纲生成 Node ---")
    llm = _get_llm_from_config(config)
    query = (
        f"{_truncate_for_query(state['requirement_analysis'])}\n"
        "请根据业务模块、用户路径、状态流转和异常分支整理测试结构\n"
        f"测试点摘要:\n{_truncate_for_query(str(state['test_points']))}"
    )
    retrieved_context, retrieval_logs, _ = _build_retrieval_for_phase(
        state=state,
        config=config,
        phase="generate_outline",
        query=query,
    )
    test_outline = asyncio.run(
        generate_outline_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
            test_points=state["test_points"],
            retrieved_context=retrieved_context,
        )
    )
    return {
        "test_outline": [outline.model_dump() for outline in test_outline],
        "retrieval_logs": retrieval_logs,
    }


def generate_cases_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """基于测试大纲生成符合 TestCase 契约的测试用例。"""
    print("--- 执行测试用例生成 Node ---")
    llm = _get_llm_from_config(config)

    outline_for_generation = state["modified_outline"]
    if not outline_for_generation:
        outline_for_generation = state["test_outline"]

    requirement_query = (
        f"{_truncate_for_query(state['requirement_analysis'])}\n"
        "请检索与该功能点相关的主流程、前置条件、状态变化、校验规则和异常约束\n"
        f"测试大纲摘要:\n{_truncate_for_query(str(outline_for_generation))}"
    )
    testcase_query = (
        f"{_truncate_for_query(state['requirement_analysis'])}\n"
        "请检索相似功能的测试步骤写法、前置条件表达、预期结果描述和异常场景覆盖方式\n"
        f"测试大纲摘要:\n{_truncate_for_query(str(outline_for_generation))}"
    )
    requirement_context, retrieval_logs, requirement_latency_ms = _build_retrieval_for_phase(
        state=state,
        config=config,
        phase="generate_cases_requirement",
        query=requirement_query,
        doc_type="requirement",
    )
    testcase_start = time.time()
    testcase_chunks, testcase_meta = retrieve_testcase_context_with_meta(
        query=testcase_query,
        multi_query=(
            config.get("configurable", {}).get("enable_multi_query", None)
            if config is not None
            else None
        ),
        enable_rerank=(
            config.get("configurable", {}).get("enable_rerank", None)
            if config is not None
            else None
        ),
    )
    testcase_elapsed_ms = int((time.time() - testcase_start) * 1000)
    testcase_context = format_retrieved_context(testcase_chunks)
    testcase_citations = build_citations(testcase_chunks, limit=5)
    retrieval_logs = _append_retrieval_log(
        state={**state, "retrieval_logs": retrieval_logs},
        phase="generate_cases_testcase",
        query=testcase_query,
        expanded_queries=testcase_meta.expanded_queries,
        pre_dedup_count=testcase_meta.pre_dedup_count,
        post_dedup_count=testcase_meta.post_dedup_count,
        chunks=testcase_chunks,
        citations=testcase_citations,
        latency_ms=testcase_elapsed_ms,
        rerank_mode=testcase_meta.rerank_mode,
        rerank_enabled=testcase_meta.rerank_enabled,
        rerank_latency_ms=testcase_meta.rerank_latency_ms,
        rerank_degraded=testcase_meta.rerank_degraded,
        rerank_degraded_reason=testcase_meta.rerank_degraded_reason,
    )
    combined_context = requirement_context
    if testcase_context:
        combined_context = (
            f"{requirement_context}\n\n"
            "<testcase_reference>\n"
            "以下为历史测试用例写法参考，仅用于覆盖与表达方式参考，严禁逐句照抄。\n"
            f"{testcase_context}\n"
            "</testcase_reference>"
        ).strip()

    test_cases = asyncio.run(
        generate_cases_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
            outline_for_generation=outline_for_generation,
            retrieved_context=combined_context,
        )
    )
    return {
        "test_cases": [test_case.model_dump() for test_case in test_cases],
        "retrieval_logs": retrieval_logs,
    }


def export_excel_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """导出测试用例为 Excel 文件并返回输出路径。"""
    print("--- 执行 Excel 导出 Node ---")
    _ = config

    cases_for_export = state["modified_test_cases"] or state["test_cases"]
    output_dir = PROJECT_ROOT / "output"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"test_cases_{timestamp}.xlsx"

    excel_output_path = export_test_cases_to_excel(
        test_cases=cases_for_export,
        output_file_path=output_file,
    )
    return {"excel_output_path": excel_output_path}
