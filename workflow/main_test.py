import os
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from state import TestCaseState
from workflow import create_workflow


def build_initial_state() -> TestCaseState:
    """构造用于首次运行的初始状态。"""
    return {
        "document": "这是用于演示的原始文档内容。",
        "structured_doc": {
            "title": "Mock需求文档",
            "modules": ["登录", "下单"],
            "version": "0.1",
        },
        "requirement_analysis": "",
        "test_points": [],
        "test_outline": [],
        "modified_outline": [],
        "test_cases": [],
        "modified_test_cases": [],
        "excel_output_path": "",
    }


def build_llm_from_env() -> ChatOpenAI:
    """从 .env 加载并初始化 LLM。"""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "未检测到 OPENAI_API_KEY，请在项目根目录 .env 中配置。"
            f"当前读取路径: {env_path}"
        )

    base_url = os.getenv("OPENAI_BASE_URL")

    return ChatOpenAI(
        model="Qwen/Qwen3.5-35B-A3B",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )


def main() -> None:
    """验证工作流中断、人工干预和恢复执行流程。"""
    graph = create_workflow()
    llm = build_llm_from_env()

    config = {
        "configurable": {
            "thread_id": "test_thread_001",
            "llm": llm,
        }
    }
    initial_state = build_initial_state()

    print("=== 第一次执行：预期在 generate_cases_node 前挂起 ===")
    first_result = graph.invoke(initial_state, config)
    print("第一次 invoke 返回：")
    pprint(first_result)

    snapshot = graph.get_state(config)
    print("第一次执行后的检查点状态（graph.get_state）：")
    pprint(snapshot)
    if hasattr(snapshot, "next"):
        print(f"下一步待执行节点: {snapshot.next}")
    if hasattr(snapshot, "values"):
        print("挂起时保存的 state values：")
        pprint(snapshot.values)

    print("=== 模拟人工干预：更新 modified_outline ===")
    graph.update_state(
        config,
        {"modified_outline": [{"point": "这是人工修改后的大纲"}]},
    )

    updated_snapshot = graph.get_state(config)
    print("人工干预后的检查点状态（graph.get_state）：")
    if hasattr(updated_snapshot, "values"):
        pprint(updated_snapshot.values)
    else:
        pprint(updated_snapshot)

    print("=== 第二次执行：从挂起点恢复并运行到 END ===")
    final_state = graph.invoke(None, config)
    print("最终完整 State：")
    pprint(final_state)

    if isinstance(final_state, dict):
        print("关键字段验证：")
        pprint(
            {
                "modified_outline": final_state.get("modified_outline"),
                "test_cases": final_state.get("test_cases"),
                "excel_output_path": final_state.get("excel_output_path"),
            }
        )


if __name__ == "__main__":
    main()
