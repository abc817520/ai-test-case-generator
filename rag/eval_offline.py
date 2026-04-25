from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from rag.ingest import index_document
from rag.retriever import retrieve_context_with_meta, retrieve_testcase_context_with_meta
from utils.document_parser.docx_parser import parse_docx
from utils.document_parser.md_parser import parse_markdown


def _load_structured_doc(input_path: Path) -> dict:
    suffix = input_path.suffix.lower()
    if suffix == ".md":
        raw = input_path.read_text(encoding="utf-8")
        return parse_markdown(raw).to_dict()
    if suffix == ".docx":
        return parse_docx(input_path).to_dict()
    raise ValueError("仅支持 md 或 docx")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG Day1 离线评测")
    parser.add_argument("--input", required=True, help="md/docx 文件路径")
    parser.add_argument("--query", required=True, help="检索 query")
    parser.add_argument(
        "--doc-type",
        default="requirement",
        choices=["requirement", "testcase"],
        help="检索评测类型",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    if args.doc_type == "requirement":
        structured_doc = _load_structured_doc(input_path)
        doc_id = f"offline_{uuid.uuid4().hex}"
        index_start = time.time()
        indexed_chunks = index_document(
            doc_id=doc_id,
            source_name=input_path.name,
            structured_doc=structured_doc,
            doc_type="requirement",
        )
        index_latency_ms = int((time.time() - index_start) * 1000)
        print(f"indexed_chunks={indexed_chunks}")
        print(f"index_latency_ms={index_latency_ms}")
        retrieve_start = time.time()
        chunks, meta = retrieve_context_with_meta(
            query=args.query,
            doc_id=doc_id,
            doc_type="requirement",
            top_k=8,
        )
    else:
        print("doc_type=testcase 模式：仅检索已有测试用例知识库，不执行临时入库。")
        retrieve_start = time.time()
        chunks, meta = retrieve_testcase_context_with_meta(
            query=args.query,
            top_k=8,
        )
    retrieve_latency_ms = int((time.time() - retrieve_start) * 1000)
    unique_section_paths = len({chunk.section_path for chunk in chunks})

    print(f"retrieved_count={len(chunks)}")
    print(f"unique_section_paths={unique_section_paths}")
    print(f"retrieve_latency_ms={retrieve_latency_ms}")
    print(f"expanded_queries={len(meta.expanded_queries)}")
    print(f"pre_dedup_count={meta.pre_dedup_count}")
    print(f"post_dedup_count={meta.post_dedup_count}")
    print(f"rerank_enabled={meta.rerank_enabled}")
    print(f"rerank_latency_ms={meta.rerank_latency_ms}")

    for idx, chunk in enumerate(chunks, start=1):
        text = chunk.text.replace("\n", " ").strip()
        short_text = text[:120]
        payload = {
            "idx": idx,
            "chunk_id": chunk.chunk_id,
            "section_path": chunk.section_path,
            "source_name": chunk.source_name,
            "score": chunk.score,
            "text_preview": short_text,
        }
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
