# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: MIT

"""The cheap search index should surface sensible matches."""

from __future__ import annotations

from claude_desktop_mcp.catalog import CATALOG
from claude_desktop_mcp.search import SearchIndex, tokenize

INDEX = SearchIndex(CATALOG)


def test_tokenize_drops_stopwords_and_short_tokens() -> None:
    assert tokenize("How do I find an order?") == ["order"]


def test_order_query_ranks_orders_domain_first() -> None:
    results = INDEX.search("find a customer order", top_k=5)
    assert results, "expected matches"
    top_spec, top_score = results[0]
    assert top_spec.domain == "orders"
    assert isinstance(top_score, float)


def test_slack_query_ranks_slack_domain_first() -> None:
    results = INDEX.search("send a message to a slack channel", top_k=5)
    assert results[0][0].domain == "slack"


def test_top_k_is_respected() -> None:
    assert len(INDEX.search("order", top_k=3)) == 3
    assert INDEX.search("order", top_k=0) == []


def test_results_sorted_by_descending_score() -> None:
    scores = [score for _, score in INDEX.search("weather forecast", top_k=5)]
    assert scores == sorted(scores, reverse=True)


def test_unmatched_query_falls_back_or_returns_empty() -> None:
    # A nonsense token yields no BM25 hits and no substring hit -> empty, no error.
    assert INDEX.search("zzqqxx", top_k=5) == []
    # A substring that appears in a name still resolves via the fallback.
    assert INDEX.search("payout", top_k=5)
