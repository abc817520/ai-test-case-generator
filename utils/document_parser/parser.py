from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentSection:
    level: int
    title: str
    content: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    children: list["DocumentSection"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "title": self.title,
            "content": self.content,
            "tables": self.tables,
            "children": [child.to_dict() for child in self.children],
        }


def section_to_dict(section: DocumentSection) -> dict[str, Any]:
    return section.to_dict()
