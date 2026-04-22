import asyncio
from pathlib import Path
import sys
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from state import TestCaseState

# 兼容当前脚本入口方式，确保可以导入项目根目录下的 skills 模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from skills.test_design_skills import (  # noqa: E402
    analyze_requirement_skill,
    extract_test_points_skill,
    generate_cases_skill,
    generate_outline_skill,
)


def _get_llm_from_config(config: RunnableConfig | None) -> BaseChatModel:
    """从 LangGraph 运行配置中获取 LLM 实例。"""
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
    requirement_analysis = asyncio.run(
        analyze_requirement_skill(
            llm=llm,
            structured_doc=state["structured_doc"],
        )
    )
    return {"requirement_analysis": requirement_analysis}


def extract_test_points_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """调用测试点提取 Skill，产出测试点列表。"""
    print("--- 执行测试点提取 Node ---")
    llm = _get_llm_from_config(config)
    test_points = asyncio.run(
        extract_test_points_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
        )
    )
    return {
        "test_points": [
            test_point.model_dump() for test_point in test_points
        ]
    }


def generate_outline_node(
    state: TestCaseState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """基于测试点生成测试大纲。"""
    print("--- 执行测试大纲生成 Node ---")
    llm = _get_llm_from_config(config)
    test_outline = asyncio.run(
        generate_outline_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
            test_points=state["test_points"],
        )
    )
    return {
        "test_outline": [
            outline.model_dump() for outline in test_outline
        ]
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

    test_cases = asyncio.run(
        generate_cases_skill(
            llm=llm,
            requirement_analysis=state["requirement_analysis"],
            outline_for_generation=outline_for_generation,
        )
    )
    return {
        "test_cases": [
            test_case.model_dump() for test_case in test_cases
        ]
    }
