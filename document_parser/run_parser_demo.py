import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from document_parser import parse_markdown, parse_docx, section_to_dict

md_text = (BASE_DIR / "test.md").read_text(encoding="utf-8")
md_result = section_to_dict(parse_markdown(md_text))

docx_result = section_to_dict(parse_docx(BASE_DIR / "test.docx"))

print("=== Markdown Result ===")
print(json.dumps(md_result, ensure_ascii=False, indent=2))

print("\n=== DOCX Result ===")
print(json.dumps(docx_result, ensure_ascii=False, indent=2))
