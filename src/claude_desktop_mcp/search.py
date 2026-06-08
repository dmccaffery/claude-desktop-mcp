# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""A deliberately cheap tool-search index.

This is *not* full natural-language semantic search. It is a small, dependency-free
BM25 ranker over each tool's name, description, tags, and parameter text, with a
substring fallback so odd queries still surface something. It is enough to mimic the
discovery behaviour of an Amazon Bedrock AgentCore Gateway semantic search tool.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from claude_desktop_mcp.catalog import ToolSpec

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Tiny stopword list — enough to stop "the/of/a" from dominating short tool corpora.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "i",
        "me",
        "my",
        "do",
        "does",
        "find",
        "get",
        "want",
        "need",
        "please",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-char tokens."""
    return [
        t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in _STOPWORDS
    ]


class SearchIndex:
    """Ranks catalog tools against a query using BM25 with a substring fallback."""

    def __init__(
        self,
        specs: tuple[ToolSpec, ...] | list[ToolSpec],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.specs = list(specs)
        self.k1 = k1
        self.b = b
        self._docs = [tokenize(spec.searchable_text()) for spec in self.specs]
        self._tf = [Counter(doc) for doc in self._docs]
        self._n = len(self._docs)
        total_len = sum(len(doc) for doc in self._docs)
        self._avgdl = (total_len / self._n) if self._n else 0.0
        self._df: Counter[str] = Counter()
        for doc in self._docs:
            self._df.update(set(doc))

    def _idf(self, term: str) -> float:
        n_t = self._df.get(term, 0)
        # BM25 idf with +1 smoothing so it never goes negative for common terms.
        return math.log(1 + (self._n - n_t + 0.5) / (n_t + 0.5))

    def search(self, query: str, top_k: int = 5) -> list[tuple[ToolSpec, float]]:
        """Return up to ``top_k`` (spec, score) pairs, highest score first."""
        if top_k <= 0:
            return []
        terms = tokenize(query)
        scored: list[tuple[float, int]] = []
        for idx in range(self._n):
            tf = self._tf[idx]
            dl = len(self._docs[idx]) or 1
            score = 0.0
            for term in terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                score += self._idf(term) * (freq * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((score, idx))

        if not scored:
            scored = self._substring_fallback(query)

        # Stable, deterministic ordering: score desc, then name asc.
        scored.sort(key=lambda pair: (-pair[0], self.specs[pair[1]].name))
        return [(self.specs[idx], round(score, 4)) for score, idx in scored[:top_k]]

    def _substring_fallback(self, query: str) -> list[tuple[float, int]]:
        """When BM25 finds nothing, fall back to raw substring matching."""
        q = query.strip().lower()
        if not q:
            return []
        hits: list[tuple[float, int]] = []
        for idx, spec in enumerate(self.specs):
            haystack = f"{spec.name} {spec.description}".lower()
            if q in haystack:
                hits.append((0.1, idx))
        return hits
