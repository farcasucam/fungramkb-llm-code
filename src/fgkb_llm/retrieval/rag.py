"""Plain RAG over verbalised postulates (R1) or COREL lines (R2).

Two retrievers: TF-IDF over character n-grams (default, no model, deterministic) and a dense one
(``DenseEncoder``: a multilingual sentence-embedding model, e.g. intfloat/multilingual-e5-base, run on
CPU). Dense document embeddings are cached by text, so the per-item corpora of patched deep items
(novel concepts, counterfactuals) only embed their few new documents.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from ..corel.verbalize import verbalise_fact, verbalise_isa
from ..graph.build import _corel_line, approx_tokens
from ..reasoner.asp import Reasoner


@dataclass
class Doc:
    text: str
    concept: str


def build_corpus(reasoner: Reasoner, style: str = "nl", lang: str = "en") -> list[Doc]:
    kb = reasoner.kb
    docs: list[Doc] = []
    for f in reasoner.facts:
        docs.append(Doc(verbalise_fact(kb, f, lang) if style == "nl" else _corel_line(f), f.concept))
    for child, parents in reasoner.parents.items():
        for p in parents:
            if p.startswith("#"):
                continue
            docs.append(Doc(verbalise_isa(kb, child, p, lang) if style == "nl" else f"{child} IS-A {p}", child))
    return docs


class DenseEncoder:
    """Sentence-embedding encoder with a text cache. E5-style models get the "query: " / "passage: "
    prefixes they were trained with."""

    _models: ClassVar[dict] = {}

    def __init__(self, model: str = "intfloat/multilingual-e5-base", device: str = "cpu", batch_size: int = 64):
        self.model_name, self.device, self.batch_size = model, device, batch_size
        self.cache: dict[tuple[str, str], np.ndarray] = {}
        self.e5 = "e5" in model.lower()

    def _model(self):
        key = (self.model_name, self.device)
        if key not in DenseEncoder._models:
            from sentence_transformers import SentenceTransformer

            DenseEncoder._models[key] = SentenceTransformer(self.model_name, device=self.device)
        return DenseEncoder._models[key]

    def _encode(self, texts: list[str], kind: str) -> np.ndarray:
        todo = [t for t in dict.fromkeys(texts) if (kind, t) not in self.cache]
        if todo:
            prefix = (kind + ": ") if self.e5 else ""
            vecs = self._model().encode([prefix + t for t in todo], batch_size=self.batch_size,
                                        normalize_embeddings=True, show_progress_bar=False)
            for t, v in zip(todo, vecs):
                self.cache[(kind, t)] = np.asarray(v, dtype=np.float32)
        return np.stack([self.cache[(kind, t)] for t in texts]) if texts else np.zeros((0, 1), np.float32)

    def documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts, "passage")

    def query(self, text: str) -> np.ndarray:
        return self._encode([text], "query")[0]


class Retriever:
    def __init__(self, docs: list[Doc], embed: Callable[[list[str]], np.ndarray] | None = None,
                 encoder: DenseEncoder | None = None):
        self.docs = docs
        self.embed = embed
        self.encoder = encoder
        texts = [d.text for d in docs]
        if encoder is not None:
            self.matrix = encoder.documents(texts)
        elif embed is None:
            self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
            self.matrix = self.vec.fit_transform(texts)
        else:
            m = np.asarray(embed(texts), dtype=np.float32)
            self.matrix = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)

    def search(self, query: str, k: int = 20) -> list[tuple[Doc, float]]:
        if self.encoder is not None:
            scores = self.matrix @ self.encoder.query(query)
        elif self.embed is None:
            q = self.vec.transform([query])
            scores = (self.matrix @ q.T).toarray().ravel()
        else:
            qv = np.asarray(self.embed([query]), dtype=np.float32)[0]
            scores = self.matrix @ (qv / (np.linalg.norm(qv) + 1e-9))
        idx = np.argsort(-scores)[:k]
        return [(self.docs[i], float(scores[i])) for i in idx]

    def context(self, query: str, budget_tokens: int = 1500, k: int = 50) -> str:
        out, used = [], 0
        for doc, _ in self.search(query, k):
            cost = approx_tokens(doc.text) + 1
            if used + cost > budget_tokens:
                break
            out.append(doc.text)
            used += cost
        return "\n".join(out)
