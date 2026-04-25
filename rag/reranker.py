from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class RerankResult:
    items: list
    rerank_enabled: bool
    rerank_latency_ms: int
    degraded: bool


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\w+|[\u4e00-\u9fff]", text.lower())
    return set(token for token in tokens if token.strip())


def _score(query: str, text: str, base_score: float) -> float:
    q = _tokenize(query)
    t = _tokenize(text)
    if not q or not t:
        return base_score
    overlap = len(q.intersection(t))
    return base_score + overlap / max(len(q), 1)


def rerank(
    query: str,
    candidates: list,
    enable_rerank: bool = True,
    final_top_n: int = 5,
) -> RerankResult:
    import time

    if final_top_n <= 0:
        return RerankResult(items=[], rerank_enabled=enable_rerank, rerank_latency_ms=0, degraded=False)

    if not enable_rerank:
        return RerankResult(
            items=candidates[:final_top_n],
            rerank_enabled=False,
            rerank_latency_ms=0,
            degraded=False,
        )

    start = time.time()
    try:
        ranked = sorted(
            candidates,
            key=lambda item: _score(
                query=query,
                text=getattr(item, "text", ""),
                base_score=float(getattr(item, "score", 0.0)),
            ),
            reverse=True,
        )
        latency_ms = int((time.time() - start) * 1000)
        return RerankResult(
            items=ranked[:final_top_n],
            rerank_enabled=True,
            rerank_latency_ms=latency_ms,
            degraded=False,
        )
    except Exception:
        latency_ms = int((time.time() - start) * 1000)
        return RerankResult(
            items=candidates[:final_top_n],
            rerank_enabled=True,
            rerank_latency_ms=latency_ms,
            degraded=True,
        )
