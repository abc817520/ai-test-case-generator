import json
import re
from typing import Any, TypeVar, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, ValidationError

try:
    from workflow.schemas import TestCase, TestOutline, TestPoint
except ModuleNotFoundError:
    from schemas import TestCase, TestOutline, TestPoint


class RequirementAnalysisOutput(BaseModel):
    """需求分析结构化输出。"""

    requirement_analysis: str = Field(
        description=(
            "需求分析报告，需覆盖核心业务逻辑、前置依赖、"
            "隐含非功能性需求（数据一致性、异常容错等）"
        )
    )


class TestPointListOutput(BaseModel):
    """测试点列表结构化输出。"""

    test_points: list[TestPoint] = Field(
        description="根据需求分析提取出的测试点列表"
    )


class TestOutlineListOutput(BaseModel):
    """测试大纲列表结构化输出。"""

    test_outline: list[TestOutline] = Field(
        description="按模块组织的测试大纲列表"
    )


class TestCaseListOutput(BaseModel):
    """测试用例列表结构化输出。"""

    test_cases: list[TestCase] = Field(
        description="结构化测试用例列表"
    )


ModelT = TypeVar("ModelT", bound=BaseModel)


def _extract_text_content(content: Any) -> str:
    """兼容不同模型返回格式，提取纯文本内容。"""
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()

    return str(content).strip()


def _extract_json_object(raw_text: str) -> str:
    """从模型输出中提取 JSON 对象文本。"""
    text = raw_text.strip()

    code_block_match = re.search(
        r"```(?:json)?\s*(\{[\s\S]*\})\s*```",
        text,
        re.IGNORECASE,
    )
    if code_block_match:
        return code_block_match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


async def _invoke_json_fallback(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    schema: type[ModelT],
    inputs: dict[str, Any],
    skill_name: str,
) -> ModelT:
    """当结构化输出不兼容时，降级为 JSON 文本输出并手动解析。"""
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    messages = prompt.format_messages(**inputs)
    messages.append(
        HumanMessage(
            content=(
                "<output_format>"
                "请仅输出一个合法 JSON 对象，不要输出额外解释，不要使用 Markdown 代码块。"
                f"输出必须满足以下 JSON Schema: {schema_text}"
                "</output_format>"
            )
        )
    )

    response = await llm.ainvoke(messages)
    raw_text = _extract_text_content(getattr(response, "content", response))
    json_text = _extract_json_object(raw_text)

    try:
        return schema.model_validate_json(json_text)
    except ValidationError:
        try:
            return schema.model_validate(json.loads(json_text))
        except Exception as exc:
            raise ValueError(
                f"{skill_name} 降级 JSON 解析失败。原始输出: {raw_text}"
            ) from exc


async def _invoke_structured_output(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    schema: type[ModelT],
    inputs: dict[str, Any],
    skill_name: str,
) -> ModelT:
    """优先走 with_structured_output，失败时自动降级。"""
    structured_llm = llm.with_structured_output(
        schema,
        method="json_mode",
        include_raw=True,
    )
    chain = prompt | structured_llm

    try:
        response = await chain.ainvoke(inputs)
    except Exception:
        return await _invoke_json_fallback(
            llm=llm,
            prompt=prompt,
            schema=schema,
            inputs=inputs,
            skill_name=skill_name,
        )

    if isinstance(response, schema):
        return response

    if not isinstance(response, dict):
        return await _invoke_json_fallback(
            llm=llm,
            prompt=prompt,
            schema=schema,
            inputs=inputs,
            skill_name=skill_name,
        )

    parsed = response.get("parsed")
    if parsed is None:
        return await _invoke_json_fallback(
            llm=llm,
            prompt=prompt,
            schema=schema,
            inputs=inputs,
            skill_name=skill_name,
        )

    return cast(ModelT, parsed)


async def analyze_requirement_skill(
    llm: BaseChatModel,
    structured_doc: dict[str, Any],
) -> str:
    """分析结构化文档，生成需求分析报告。"""
    prompt = ChatPromptTemplate.from_template(
        """
<context>
你是一名资深测试分析专家，擅长梳理需求中的显性与隐性约束。
下面是结构化需求文档：
{structured_doc}
</context>

<instruction>
请输出需求分析报告，至少覆盖：
1. 核心业务逻辑与关键流程。
2. 前置依赖（上下游系统、配置、数据准备、权限等）。
3. 隐含的非功能性需求（例如：数据一致性、异常容错、可用性）。
</instruction>

<constraints>
1. 语言使用中文。
2. 内容要可直接用于后续测试点设计。
3. 不要输出与需求无关的泛化建议。
</constraints>
""".strip()
    )

    result = await _invoke_structured_output(
        llm=llm,
        prompt=prompt,
        schema=RequirementAnalysisOutput,
        inputs={
            "structured_doc": json.dumps(
                structured_doc,
                ensure_ascii=False,
                indent=2,
            )
        },
        skill_name="analyze_requirement_skill",
    )

    requirement_analysis = result.requirement_analysis.strip()
    if not requirement_analysis:
        raise ValueError("analyze_requirement_skill 返回了空的需求分析内容。")

    return requirement_analysis


async def extract_test_points_skill(
    llm: BaseChatModel,
    requirement_analysis: str,
) -> list[TestPoint]:
    """基于需求分析提取测试点列表。"""
    prompt = ChatPromptTemplate.from_template(
        """
<context>
你是一名资深测试设计专家，擅长等价类划分、边界值分析和错误推测法。
下面是需求分析报告：
{requirement_analysis}
</context>

<instruction>
请基于需求分析提取测试点，必须覆盖以下维度：
1. 正常场景。
2. 边界值场景（例如：空值、极大值、非法字符）。
3. 异常场景（例如：网络中断、权限不足）。
</instruction>

<constraints>
1. 必须输出结构化测试点列表。
2. 每个测试点都必须填写：name、test_type（功能/性能/安全）、priority（P0-P3）。
3. 优先级要与业务风险匹配，避免全部给高优先级。
4. 不要输出多余解释文本。
</constraints>
""".strip()
    )

    result = await _invoke_structured_output(
        llm=llm,
        prompt=prompt,
        schema=TestPointListOutput,
        inputs={"requirement_analysis": requirement_analysis},
        skill_name="extract_test_points_skill",
    )
    return result.test_points


async def generate_outline_skill(
    llm: BaseChatModel,
    requirement_analysis: str,
    test_points: list[dict[str, Any]],
) -> list[TestOutline]:
    """基于测试点生成分模块测试大纲。"""
    prompt = ChatPromptTemplate.from_template(
        """
<context>
你是一名资深测试架构师。
下面是需求分析：
{requirement_analysis}

下面是已提取的测试点列表：
{test_points}
</context>

<instruction>
请基于测试点生成测试大纲，并按模块聚合。
每个模块下必须放入对应测试点，不能丢失原始高优先级测试点。
</instruction>

<constraints>
1. 输出必须是 TestOutline 列表（字段：module_name, test_points）。
2. test_points 中每项必须是完整 TestPoint（name、test_type、priority）。
3. 模块划分要清晰，避免“其他”这类无意义模块名。
4. 不要输出解释文字。
</constraints>
""".strip()
    )

    result = await _invoke_structured_output(
        llm=llm,
        prompt=prompt,
        schema=TestOutlineListOutput,
        inputs={
            "requirement_analysis": requirement_analysis,
            "test_points": json.dumps(
                test_points,
                ensure_ascii=False,
                indent=2,
            ),
        },
        skill_name="generate_outline_skill",
    )
    return result.test_outline


async def generate_cases_skill(
    llm: BaseChatModel,
    requirement_analysis: str,
    outline_for_generation: list[dict[str, Any]],
) -> list[TestCase]:
    """基于测试大纲生成结构化测试用例。"""
    prompt = ChatPromptTemplate.from_template(
        """
<context>
你是一名资深测试设计专家。
下面是需求分析：
{requirement_analysis}

下面是用于生成用例的测试大纲：
{outline}
</context>

<instruction>
请根据测试大纲生成可执行测试用例。
每条用例都要填写：case_id、directory、case_level、test_point、precondition、steps、expected_result。
</instruction>

<constraints>
1. 输出必须是 TestCase 列表。
2. case_id 唯一，建议使用 TC-001 递增格式。
3. directory 体现模块路径，例如：登录/鉴权、下单/支付。
4. steps 至少 2 步，描述清晰可执行。
5. case_level 仅可为 P0/P1/P2/P3。
6. 不要输出解释文字。
</constraints>
""".strip()
    )

    result = await _invoke_structured_output(
        llm=llm,
        prompt=prompt,
        schema=TestCaseListOutput,
        inputs={
            "requirement_analysis": requirement_analysis,
            "outline": json.dumps(
                outline_for_generation,
                ensure_ascii=False,
                indent=2,
            ),
        },
        skill_name="generate_cases_skill",
    )
    return result.test_cases
