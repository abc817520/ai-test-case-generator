from __future__ import annotations

import re


_SYNONYM_BUCKETS: list[list[str]] = [
    ["异常", "错误", "失败"],
    ["流程", "路径", "步骤"],
    ["约束", "限制", "规则"],
    ["边界", "边界值", "极值"],
    ["兼容性", "适配", "兼容"],
]


def _replace_first(text: str, source: str, target: str) -> str:
    return text.replace(source, target, 1)


def _synonym_rewrite(query: str) -> str:
    rewritten = query
    for bucket in _SYNONYM_BUCKETS:
        for token in bucket:
            if token in rewritten:
                replacement = next((x for x in bucket if x != token), token)
                rewritten = _replace_first(rewritten, token, replacement)
                return rewritten
    return f"{query}\n请重点关注异常、错误、失败等场景。"


def _intent_rewrite(query: str) -> str:
    plain = re.sub(r"\s+", " ", query).strip()
    return (
        f"{plain}\n"
        "请从流程、约束、边界、兼容性四个视角补充检索上下文。"
    )


def expand_query(query: str, max_queries: int = 3) -> list[str]:
    base = str(query).strip()
    if not base:
        return []

    variants: list[str] = [base, _synonym_rewrite(base), _intent_rewrite(base)]
    unique: list[str] = []
    for item in variants:
        normalized = item.strip()
        if normalized and normalized not in unique:
            unique.append(normalized)

    return unique[: max(max_queries, 1)]
