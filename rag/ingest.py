from __future__ import annotations

import json
from pathlib import Path
import uuid
from typing import Any

from langchain_core.documents import Document

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE
from rag.schemas import Chunk
from rag.store import get_vector_store
from utils.document_parser.docx_parser import parse_docx
from utils.document_parser.md_parser import parse_markdown


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    if chunk_size <= 0:
        return [normalized]

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(chunk_size // 5, 0)

    step = max(chunk_size - chunk_overlap, 1)
    chunks: list[str] = []
    start = 0
    text_len = len(normalized)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= text_len:
            break
        start += step
    return chunks


def _join_path(path_parts: list[str]) -> str:
    if not path_parts:
        return "ROOT"
    return "ROOT > " + " > ".join(path_parts)


def _table_to_lines(table: list[list[str]]) -> list[str]:
    rows: list[str] = []
    for row in table:
        safe_cells = [str(cell).strip() for cell in row]
        if any(safe_cells):
            rows.append(" | ".join(safe_cells))
    return rows


def _walk_sections(
    section: dict[str, Any],
    path_parts: list[str],
    source_name: str,
    doc_id: str,
    doc_type: str,
    extra_metadata: dict[str, str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    title = str(section.get("title", "")).strip()
    level = int(section.get("level", 0))

    current_parts = list(path_parts)
    if level > 0 and title:
        current_parts.append(title)
    section_path = _join_path(current_parts)

    chunks: list[Chunk] = []
    paragraph_index = 0

    content = str(section.get("content", "")).strip()
    for part in _chunk_text(content, chunk_size, chunk_overlap):
        chunks.append(
            Chunk(
                chunk_id=uuid.uuid4().hex,
                doc_id=doc_id,
                doc_type=doc_type,
                source_name=source_name,
                section_path=section_path,
                paragraph_index=paragraph_index,
                text=part,
                char_len=len(part),
                module=str(extra_metadata.get("module", "")),
                test_type=str(extra_metadata.get("test_type", "")),
                priority=str(extra_metadata.get("priority", "")),
            )
        )
        paragraph_index += 1

    tables = section.get("tables", [])
    if isinstance(tables, list):
        for table in tables:
            if not isinstance(table, list):
                continue
            table_lines = _table_to_lines(table)
            table_text = "\n".join(table_lines).strip()
            for part in _chunk_text(table_text, chunk_size, chunk_overlap):
                chunks.append(
                    Chunk(
                        chunk_id=uuid.uuid4().hex,
                        doc_id=doc_id,
                        doc_type=doc_type,
                        source_name=source_name,
                        section_path=section_path,
                        paragraph_index=paragraph_index,
                        text=part,
                        char_len=len(part),
                        module=str(extra_metadata.get("module", "")),
                        test_type=str(extra_metadata.get("test_type", "")),
                        priority=str(extra_metadata.get("priority", "")),
                    )
                )
                paragraph_index += 1

    children = section.get("children", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                chunks.extend(
                    _walk_sections(
                        section=child,
                        path_parts=current_parts,
                        source_name=source_name,
                        doc_id=doc_id,
                        doc_type=doc_type,
                        extra_metadata=extra_metadata,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )
                )
    return chunks


def _build_documents(chunks: list[Chunk]) -> tuple[list[str], list[Document]]:
    ids: list[str] = []
    docs: list[Document] = []
    for chunk in chunks:
        ids.append(chunk.chunk_id)
        docs.append(
            Document(
                page_content=chunk.text,
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "doc_type": chunk.doc_type,
                    "source_name": chunk.source_name,
                    "section_path": chunk.section_path,
                    "paragraph_index": chunk.paragraph_index,
                    "char_len": chunk.char_len,
                    "module": chunk.module,
                    "test_type": chunk.test_type,
                    "priority": chunk.priority,
                },
            )
        )
    return ids, docs


def index_document(
    doc_id: str,
    source_name: str,
    structured_doc: dict[str, Any],
    doc_type: str = "requirement",
    extra_metadata: dict[str, str] | None = None,
) -> int:
    metadata = extra_metadata or {}
    chunk_list = _walk_sections(
        section=structured_doc,
        path_parts=[],
        source_name=source_name,
        doc_id=doc_id,
        doc_type=doc_type,
        extra_metadata=metadata,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    if not chunk_list:
        return 0

    vector_store = get_vector_store()
    ids, docs = _build_documents(chunk_list)
    vector_store.add_documents(documents=docs, ids=ids)

    return len(ids)


def index_document_from_json(
    doc_id: str,
    source_name: str,
    structured_doc_json: str,
    doc_type: str = "requirement",
    extra_metadata: dict[str, str] | None = None,
) -> int:
    structured_doc = json.loads(structured_doc_json)
    if not isinstance(structured_doc, dict):
        raise ValueError("structured_doc_json 必须是 JSON 对象。")
    return index_document(
        doc_id=doc_id,
        source_name=source_name,
        structured_doc=structured_doc,
        doc_type=doc_type,
        extra_metadata=extra_metadata,
    )


def index_testcase_knowledge_file(
    file_path: str | Path,
    module: str = "",
    test_type: str = "",
    priority: str = "",
) -> int:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"未找到文件: {path}")

    suffix = path.suffix.lower()
    if suffix == ".md":
        structured_doc = parse_markdown(path.read_text(encoding="utf-8")).to_dict()
    elif suffix == ".docx":
        structured_doc = parse_docx(path).to_dict()
    else:
        raise ValueError(f"仅支持 .md/.docx，当前文件: {path}")

    doc_id = f"testcase_{path.stem}_{uuid.uuid4().hex[:8]}"
    return index_document(
        doc_id=doc_id,
        source_name=path.name,
        structured_doc=structured_doc,
        doc_type="testcase",
        extra_metadata={
            "module": module,
            "test_type": test_type,
            "priority": priority,
        },
    )
