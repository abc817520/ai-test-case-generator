from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from rag.ingest import index_testcase_knowledge_file


def _load_mapping(mapping_path: Path) -> dict[str, dict[str, str]]:
    if not mapping_path.exists():
        return {}
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("mapping 文件必须是 JSON 对象。")
    mapping: dict[str, dict[str, str]] = {}
    for file_name, meta in payload.items():
        if isinstance(meta, dict):
            mapping[file_name] = {
                "module": str(meta.get("module", "")),
                "test_type": str(meta.get("test_type", "")),
                "priority": str(meta.get("priority", "")),
            }
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="批量入库历史测试用例知识库（md/docx）")
    parser.add_argument("--dir", required=True, help="历史测试用例目录")
    parser.add_argument(
        "--mapping",
        default="",
        help="可选 JSON 映射文件，按文件名配置 module/test_type/priority",
    )
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"目录不存在: {root}")

    mapping = _load_mapping(Path(args.mapping).resolve()) if args.mapping else {}
    files = sorted(
        [*root.rglob("*.md"), *root.rglob("*.docx")],
        key=lambda p: str(p).lower(),
    )
    if not files:
        print("未发现 md/docx 文件。")
        return

    total_chunks = 0
    for path in files:
        meta = mapping.get(path.name, {})
        chunks = index_testcase_knowledge_file(
            file_path=path,
            module=meta.get("module", ""),
            test_type=meta.get("test_type", ""),
            priority=meta.get("priority", ""),
        )
        total_chunks += chunks
        print(
            json.dumps(
                {
                    "file": str(path),
                    "chunks": chunks,
                    "module": meta.get("module", ""),
                    "test_type": meta.get("test_type", ""),
                    "priority": meta.get("priority", ""),
                },
                ensure_ascii=False,
            )
        )

    print(f"indexed_files={len(files)}")
    print(f"indexed_chunks={total_chunks}")


if __name__ == "__main__":
    main()
