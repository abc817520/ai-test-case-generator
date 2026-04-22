from __future__ import annotations

from typing import Any

from .parser import DocumentSection


def parse_markdown(markdown_text: str) -> DocumentSection:
    import mistune

    parser = mistune.create_markdown(renderer="ast", plugins=["table"])
    tokens = parser(markdown_text)

    root = DocumentSection(level=0, title="ROOT")
    stack: list[DocumentSection] = [root]

    for token in tokens:
        token_type = token.get("type", "")

        if token_type == "heading":
            level = int(token.get("attrs", {}).get("level", 1))
            title = _render_text_from_children(token.get("children", []))
            section = DocumentSection(level=level, title=title)

            while stack and stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(section)
            stack.append(section)
            continue

        if token_type == "table":
            stack[-1].tables.append(_extract_markdown_table(token))
            continue

        text = _token_to_text(token).strip()
        if text:
            stack[-1].content = _append_text(stack[-1].content, text)

    return root


def _append_text(existing: str, new_text: str) -> str:
    if not existing:
        return new_text
    return f"{existing}\n{new_text}"


def _render_text_from_children(children: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for child in children:
        parts.append(_token_to_text(child))
    return "".join(parts).strip()


def _token_to_text(token: dict[str, Any]) -> str:
    token_type = token.get("type", "")

    if token_type in {"text", "inline_text", "block_text", "codespan", "block_code"}:
        return token.get("raw", "") or token.get("text", "")

    children = token.get("children", [])
    if children:
        return "".join(_token_to_text(child) for child in children)

    return token.get("raw", "") or token.get("text", "")


def _extract_markdown_table(table_token: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []

    for section in table_token.get("children", []):
        section_type = section.get("type", "")
        if section_type not in {"table_head", "table_body"}:
            continue

        if section_type == "table_head":
            cells: list[str] = []
            for cell in section.get("children", []):
                cells.append(_render_text_from_children(cell.get("children", [])))
            rows.append(cells)
            continue

        for row in section.get("children", []):
            if row.get("type", "") != "table_row":
                continue

            cells: list[str] = []
            for cell in row.get("children", []):
                cells.append(_render_text_from_children(cell.get("children", [])))
            rows.append(cells)

    return rows
