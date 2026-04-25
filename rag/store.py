import os
import hashlib
import re
from typing import List

from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from rag.config import COLLECTION_NAME, EMBEDDING_MODEL, LOCAL_EMBEDDING_DIM, PERSIST_DIRECTORY


class LocalHashEmbeddings(Embeddings):
    """Deterministic local embedding fallback to keep RAG usable offline."""

    def __init__(self, dimensions: int = LOCAL_EMBEDDING_DIM) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\w+|[\u4e00-\u9fff]", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            slot = int(digest, 16) % self.dimensions
            vector[slot] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        if norm <= 0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def _build_openai_embeddings() -> OpenAIEmbeddings:
    load_dotenv()
    return OpenAIEmbeddings(
        model=os.getenv("RAG_EMBEDDING_MODEL", EMBEDDING_MODEL),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
    )


class FallbackEmbeddings(Embeddings):
    def __init__(self, primary: Embeddings, fallback: Embeddings) -> None:
        self.primary = primary
        self.fallback = fallback
        self._using_fallback = False

    def _embed_documents_primary(self, texts: List[str]) -> List[List[float]]:
        return self.primary.embed_documents(texts)

    def _embed_query_primary(self, text: str) -> List[float]:
        return self.primary.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._using_fallback:
            return self.fallback.embed_documents(texts)
        try:
            return self._embed_documents_primary(texts)
        except Exception:
            self._using_fallback = True
            return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        if self._using_fallback:
            return self.fallback.embed_query(text)
        try:
            return self._embed_query_primary(text)
        except Exception:
            self._using_fallback = True
            return self.fallback.embed_query(text)


def _build_embeddings() -> Embeddings:
    try:
        primary = _build_openai_embeddings()
        return FallbackEmbeddings(primary=primary, fallback=LocalHashEmbeddings())
    except Exception:
        return LocalHashEmbeddings()


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_build_embeddings(),
        persist_directory=PERSIST_DIRECTORY,
    )
