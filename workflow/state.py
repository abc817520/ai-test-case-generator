from typing import TypedDict


class TestCaseState(TypedDict):
    """LangGraph 全局状态：用于在多 Agent 协作流程中共享测试生成上下文。"""

    # 原始文档内容（例如 PRD、需求说明、接口文档等未结构化文本）
    document: str

    # 结构化文档（由前期解析模块输出，通常为分层字典结构）
    structured_doc: dict

    # 当前上传文档 ID（用于 RAG 过滤）
    doc_id: str

    # 需求分析报告（对业务目标、范围、约束、风险点的分析结论）
    requirement_analysis: str

    # 测试点列表（从需求中提取出的可验证要点，每一项为一个字典）
    test_points: list[dict]

    # 测试大纲（按模块/场景组织的测试设计框架，每一项为一个字典）
    test_outline: list[dict]

    # 人工修改后的测试大纲（人工评审与调整后的大纲结果）
    modified_outline: list[dict]

    # 生成的测试用例（模型根据大纲产出的测试用例集合，每一项为一个字典）
    test_cases: list[dict]

    # 人工修改后的测试用例（人工补充、修订、确认后的最终用例集合）
    modified_test_cases: list[dict]

    # 各节点检索日志（用于可观测性与前端展示）
    retrieval_logs: list[dict]

    # 导出的 Excel 文件路径
    excel_output_path: str
