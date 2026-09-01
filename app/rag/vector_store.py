"""
Vector DB for RAG.

Implementation note: production deployments would typically use Chroma /
Qdrant / pgvector with sentence-transformer embeddings pulled from
HuggingFace. That download requires network access to huggingface.co,
which may not be available in every deployment environment. To keep this
a *fully free, fully offline-capable* default, we implement a real vector
index using TF-IDF + cosine similarity (scikit-learn) -- this is a genuine
vector space model, just with sparse lexical vectors instead of dense
neural embeddings. The interface is identical, so swapping in a dense
embedder (sentence-transformers, or Anthropic/OpenAI embeddings) later is
a one-file change -- see `DenseEmbeddingStore` stub at the bottom.
"""
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import DATA_DIR, VECTOR_TOP_K

INDEX_PATH = Path(DATA_DIR) / "vector_index.pkl"


class TfidfVectorStore:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
        self.doc_ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self.matrix = None

    def add_documents(self, docs: list[dict]):
        """docs: list of {id, text, metadata}"""
        for d in docs:
            self.doc_ids.append(d["id"])
            self.documents.append(d["text"])
            self.metadatas.append(d.get("metadata", {}))
        self._reindex()

    def _reindex(self):
        if not self.documents:
            self.matrix = None
            return
        self.matrix = self.vectorizer.fit_transform(self.documents)

    def query(self, text: str, top_k: int = VECTOR_TOP_K) -> list[dict]:
        if self.matrix is None or not self.documents:
            return []
        query_vec = self.vectorizer.transform([text])
        sims = cosine_similarity(query_vec, self.matrix)[0]
        top_idx = np.argsort(sims)[::-1][:top_k]
        results = []
        for i in top_idx:
            if sims[i] <= 0:
                continue
            results.append(
                {
                    "id": self.doc_ids[i],
                    "text": self.documents[i],
                    "metadata": self.metadatas[i],
                    "score": round(float(sims[i]), 4),
                }
            )
        return results

    def save(self, path: Path = INDEX_PATH):
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "doc_ids": self.doc_ids,
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                },
                f,
            )

    def load(self, path: Path = INDEX_PATH):
        if not path.exists():
            return False
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.doc_ids = data["doc_ids"]
        self.documents = data["documents"]
        self.metadatas = data["metadatas"]
        self._reindex()
        return True


class DenseEmbeddingStore:
    """
    Stub showing how to swap in dense embeddings (e.g.
    sentence-transformers/all-MiniLM-L6-v2, or an Anthropic/OpenAI embedding
    endpoint) without changing the rest of the app. Not wired in by default
    because it needs a model download / API key.
    """

    def __init__(self, embed_fn):
        self.embed_fn = embed_fn  # text -> np.ndarray
        self.doc_ids, self.documents, self.metadatas, self.vectors = [], [], [], []

    def add_documents(self, docs: list[dict]):
        for d in docs:
            self.doc_ids.append(d["id"])
            self.documents.append(d["text"])
            self.metadatas.append(d.get("metadata", {}))
            self.vectors.append(self.embed_fn(d["text"]))

    def query(self, text: str, top_k: int = VECTOR_TOP_K) -> list[dict]:
        if not self.vectors:
            return []
        q = self.embed_fn(text)
        sims = cosine_similarity([q], self.vectors)[0]
        top_idx = np.argsort(sims)[::-1][:top_k]
        return [
            {"id": self.doc_ids[i], "text": self.documents[i], "score": float(sims[i])}
            for i in top_idx
            if sims[i] > 0
        ]


_store: TfidfVectorStore | None = None


def get_store() -> TfidfVectorStore:
    global _store
    if _store is None:
        _store = TfidfVectorStore()
        if not _store.load():
            from app.rag.sample_docs import SAMPLE_DOCS

            _store.add_documents(SAMPLE_DOCS)
            _store.save()
    return _store
