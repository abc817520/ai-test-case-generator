from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from nodes import (
    analyze_requirement_node,
    extract_test_points_node,
    generate_cases_node,
    generate_outline_node,
)
from state import TestCaseState


workflow = StateGraph(TestCaseState)

workflow.add_node("analyze_requirement_node", analyze_requirement_node)
workflow.add_node("extract_test_points_node", extract_test_points_node)
workflow.add_node("generate_outline_node", generate_outline_node)
workflow.add_node("generate_cases_node", generate_cases_node)

workflow.add_edge(START, "analyze_requirement_node")
workflow.add_edge("analyze_requirement_node", "extract_test_points_node")
workflow.add_edge("extract_test_points_node", "generate_outline_node")
workflow.add_edge("generate_outline_node", "generate_cases_node")
workflow.add_edge("generate_cases_node", END)


def create_workflow() -> Any:
    """创建并返回编译后的 LangGraph 工作流。"""
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["generate_cases_node"],
    )
