from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import time
from typing import Any


@dataclass
class RerankResult:
    items: list
    rerank_mode: str
    rerank_enabled: bool
    rerank_latency_ms: int
    degraded: bool
    degraded_reason: str


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


def _slice_candidates(candidates: list, final_top_n: int) -> list:
    return candidates[:final_top_n]


def _rerank_lite(
    query: str,
    candidates: list,
    final_top_n: int,
) -> list:
    ranked = sorted(
        candidates,
        key=lambda item: _score(
            query=query,
            text=getattr(item, "text", ""),
            base_score=float(getattr(item, "score", 0.0)),
        ),
        reverse=True,
    )
    return _slice_candidates(ranked, final_top_n)


@lru_cache(maxsize=1)
def _load_cross_encoder(model_name: str, local_files_only: bool) -> Any:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(
        model_name,
        local_files_only=local_files_only,
    )


def _rerank_cross_encoder(
    query: str,
    candidates: list,
    final_top_n: int,
    model_name: str,
    local_files_only: bool,
    timeout_ms: int,
) -> RerankResult:
    start = time.time()
    cross_encoder = _load_cross_encoder(model_name, local_files_only)
    load_and_prepare_ms = int((time.time() - start) * 1000)
    if timeout_ms > 0 and load_and_prepare_ms > timeout_ms:
        raise TimeoutError("cross-encoder load exceeded timeout")

    if not candidates:
        return RerankResult(
            items=[],
            rerank_mode="cross_encoder",
            rerank_enabled=True,
            rerank_latency_ms=load_and_prepare_ms,
            degraded=False,
            degraded_reason="",
        )

    pairs = [(query, str(getattr(item, "text", ""))) for item in candidates]
    scores = cross_encoder.predict(pairs)
    total_latency_ms = int((time.time() - start) * 1000)
    if timeout_ms > 0 and total_latency_ms > timeout_ms:
        raise TimeoutError("cross-encoder predict exceeded timeout")

    ranked = sorted(
        zip(candidates, scores, strict=False),
        key=lambda pair: float(pair[1]),
        reverse=True,
    )
    items = [item for item, _score_value in ranked[:final_top_n]]
    if not items:
        raise ValueError("cross-encoder returned empty items")

    return RerankResult(
        items=items,
        rerank_mode="cross_encoder",
        rerank_enabled=True,
        rerank_latency_ms=total_latency_ms,
        degraded=False,
        degraded_reason="",
    )


def rerank(
    query: str,
    candidates: list,
    enable_rerank: bool = True,
    mode: str = "lite",
    cross_encoder_model: str = "",
    cross_encoder_local_files_only: bool = True,
    timeout_ms: int = 0,
    final_top_n: int = 5,
) -> RerankResult:
    if final_top_n <= 0:
        return RerankResult(
            items=[],
            rerank_mode="disabled" if not enable_rerank else mode,
            rerank_enabled=enable_rerank,
            rerank_latency_ms=0,
            degraded=False,
            degraded_reason="",
        )

    if not enable_rerank:
        return RerankResult(
            items=_slice_candidates(candidates, final_top_n),
            rerank_mode="disabled",
            rerank_enabled=False,
            rerank_latency_ms=0,
            degraded=False,
            degraded_reason="",
        )

    start = time.time()
    try:
        if mode == "cross_encoder":
            return _rerank_cross_encoder(
                query=query,
                candidates=candidates,
                final_top_n=final_top_n,
                model_name=cross_encoder_model,
                local_files_only=cross_encoder_local_files_only,
                timeout_ms=timeout_ms,
            )

        ranked = _rerank_lite(
            query=query,
            candidates=candidates,
            final_top_n=final_top_n,
        )
        latency_ms = int((time.time() - start) * 1000)
        return RerankResult(
            items=ranked,
            rerank_mode="lite",
            rerank_enabled=True,
            rerank_latency_ms=latency_ms,
            degraded=False,
            degraded_reason="",
        )
    except Exception as exc:
        degraded_reason = f"{type(exc).__name__}: {exc}".strip()
        if mode != "cross_encoder":
            latency_ms = int((time.time() - start) * 1000)
            return RerankResult(
                items=_slice_candidates(candidates, final_top_n),
                rerank_mode=mode,
                rerank_enabled=True,
                rerank_latency_ms=latency_ms,
                degraded=True,
                degraded_reason=degraded_reason,
            )

        fallback_start = time.time()
        fallback_items = _rerank_lite(
            query=query,
            candidates=candidates,
            final_top_n=final_top_n,
        )
        fallback_latency_ms = int((time.time() - start) * 1000)
        _ = fallback_start
        latency_ms = int((time.time() - start) * 1000)
        return RerankResult(
            items=fallback_items,
            rerank_mode="lite",
            rerank_enabled=True,
            rerank_latency_ms=max(latency_ms, fallback_latency_ms),
            degraded=True,
            degraded_reason=degraded_reason,
        )
