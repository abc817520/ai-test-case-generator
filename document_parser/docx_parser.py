from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .parser import DocumentSection


def parse_docx(docx_file: str | Path) -> DocumentSection:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(docx_file))

    root = DocumentSection(level=0, title="ROOT")
    stack: list[DocumentSection] = [root]

    for block in _iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue

            heading_level = _heading_level_from_style(block.style.name if block.style else "")
            if heading_level is not None:
                section = DocumentSection(level=heading_level, title=text)
                while stack and stack[-1].level >= heading_level:
                    stack.pop()
                stack[-1].children.append(section)
                stack.append(section)
            else:
                stack[-1].content = _append_text(stack[-1].content, text)
            continue

        if isinstance(block, Table):
            table_rows: list[list[str]] = []
            for row in block.rows:
                table_rows.append([cell.text.strip() for cell in row.cells])
            stack[-1].tables.append(table_rows)

    return root


def _append_text(existing: str, new_text: str) -> str:
    if not existing:
        return new_text
    return f"{existing}\n{new_text}"


def _heading_level_from_style(style_name: str) -> int | None:
    if not style_name:
        return None

    match = re.search(r"(?:heading|\u6807\u9898)\s*(\d+)", style_name, flags=re.IGNORECASE)
    if not match:
        return None

    return int(match.group(1))


def _iter_docx_blocks(doc: Any):
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = doc.element.body

    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)
