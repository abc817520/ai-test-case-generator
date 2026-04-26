import json
import re
from pathlib import Path
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
PROMPT_DIR = Path(__file__).resolve().parent


def _load_prompt_template(file_name: str) -> str:
    prompt_path = PROMPT_DIR / file_name
    return prompt_path.read_text(encoding="utf-8").strip()


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


def _sanitize_json_text(json_text: str) -> str:
    """对常见脏输出做轻量清洗，尽量不改动合法 JSON。"""
    sanitized = json_text.strip()
    if not sanitized:
        return sanitized

    sanitized = sanitized.replace("\u201c", '"').replace("\u201d", '"')
    sanitized = sanitized.replace("\u2018", "'").replace("\u2019", "'")
    sanitized = sanitized.replace("\ufeff", "")

    lines = sanitized.splitlines()
    cleaned_lines: list[str] = []
    for line in lines:
        if '"' not in line or ":" not in line:
            cleaned_lines.append(line)
            continue

        colon_index = line.find(":")
        first_quote_after_colon = line.find('"', colon_index)
        last_quote = line.rfind('"')
        if first_quote_after_colon == -1 or last_quote <= first_quote_after_colon:
            cleaned_lines.append(line)
            continue

        value = line[first_quote_after_colon + 1 : last_quote]
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
        cleaned_lines.append(
            f"{line[:first_quote_after_colon + 1]}{escaped_value}{line[last_quote:]}"
        )

    return "\n".join(cleaned_lines)


async def _repair_json_with_llm(
    llm: BaseChatModel,
    schema: type[ModelT],
    broken_json_text: str,
) -> str:
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    repair_prompt = (
        "你是 JSON 修复器。"
        "请将下面的内容修复为一个严格合法的 JSON 对象。"
        "不要输出任何解释、不要使用 Markdown 代码块。"
        "必须满足给定 JSON Schema。"
        f"\nJSON Schema:\n{schema_text}"
        f"\n待修复内容:\n{broken_json_text}"
    )
    response = await llm.ainvoke([HumanMessage(content=repair_prompt)])
    repaired_raw = _extract_text_content(getattr(response, "content", response))
    return _extract_json_object(repaired_raw)


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
    sanitized_json_text = _sanitize_json_text(json_text)

    try:
        return schema.model_validate_json(sanitized_json_text)
    except ValidationError:
        try:
            return schema.model_validate(json.loads(sanitized_json_text))
        except Exception as exc:
            try:
                repaired_json_text = await _repair_json_with_llm(
                    llm=llm,
                    schema=schema,
                    broken_json_text=sanitized_json_text,
                )
                try:
                    return schema.model_validate_json(repaired_json_text)
                except ValidationError:
                    return schema.model_validate(json.loads(repaired_json_text))
            except Exception as repair_exc:
                raise ValueError(
                    f"{skill_name} 降级 JSON 解析失败。原始输出: {raw_text}"
                ) from repair_exc


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
    retrieved_context: str = "",
) -> str:
    """分析结构化文档，生成需求分析报告。"""
    prompt = ChatPromptTemplate.from_template(
        _load_prompt_template("analyze_requirement_skill.md")
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
            ),
            "retrieved_context": retrieved_context,
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
    retrieved_context: str = "",
) -> list[TestPoint]:
    """基于需求分析提取测试点列表。"""
    prompt = ChatPromptTemplate.from_template(
        _load_prompt_template("extract_test_points_skill.md")
    )

    result = await _invoke_structured_output(
        llm=llm,
        prompt=prompt,
        schema=TestPointListOutput,
        inputs={
            "requirement_analysis": requirement_analysis,
            "retrieved_context": retrieved_context,
        },
        skill_name="extract_test_points_skill",
    )
    return result.test_points


async def generate_outline_skill(
    llm: BaseChatModel,
    requirement_analysis: str,
    test_points: list[dict[str, Any]],
    retrieved_context: str = "",
) -> list[TestOutline]:
    """基于测试点生成分模块测试大纲。"""
    prompt = ChatPromptTemplate.from_template(
        _load_prompt_template("generate_outline_skill.md")
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
            "retrieved_context": retrieved_context,
        },
        skill_name="generate_outline_skill",
    )
    return result.test_outline


async def generate_cases_skill(
    llm: BaseChatModel,
    requirement_analysis: str,
    outline_for_generation: list[dict[str, Any]],
    retrieved_context: str = "",
) -> list[TestCase]:
    """基于测试大纲生成结构化测试用例。"""
    prompt = ChatPromptTemplate.from_template(
        _load_prompt_template("generate_cases_skill.md")
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
            "retrieved_context": retrieved_context,
        },
        skill_name="generate_cases_skill",
    )
    return result.test_cases
