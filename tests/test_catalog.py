# Copyright 2026 Deavon M. McCaffery
# SPDX-License-Identifier: Apache-2.0

"""The catalog must be large and well-formed."""

from __future__ import annotations

from claude_desktop_mcp.catalog import CATALOG

_VALID_TYPES = {"string", "integer", "number", "boolean", "array"}


def test_catalog_has_at_least_101_tools() -> None:
    assert len(CATALOG) >= 101


def test_tool_names_are_unique() -> None:
    names = [spec.name for spec in CATALOG]
    assert len(names) == len(set(names))


def test_every_input_schema_is_valid_json_schema() -> None:
    for spec in CATALOG:
        schema = spec.input_schema()
        assert schema["type"] == "object"
        properties = schema["properties"]
        assert isinstance(properties, dict)

        for prop_name, prop in properties.items():
            assert prop["type"] in _VALID_TYPES, (
                f"{spec.name}.{prop_name}: {prop['type']}"
            )
            assert prop.get("description"), (
                f"{spec.name}.{prop_name} missing description"
            )
            if prop["type"] == "array":
                assert "items" in prop

        # ``required`` must reference declared properties only.
        for required_name in schema.get("required", []):
            assert required_name in properties


def test_searchable_text_includes_name_and_tags() -> None:
    spec = next(s for s in CATALOG if s.name == "orders_get_order")
    text = spec.searchable_text()
    assert "orders get order" in text
    assert "purchase" in text  # domain synonym tag


def test_gateway_name_uses_agentcore_triple_underscore_namespacing() -> None:
    spec = next(s for s in CATALOG if s.name == "orders_get_order")
    assert spec.bare_name == "get_order"
    assert spec.gateway_name() == "orders___get_order"


def test_every_tool_splits_cleanly_into_target_and_action() -> None:
    # gateway_name must round-trip back to a unique, domain-prefixed identifier.
    seen: set[str] = set()
    for spec in CATALOG:
        gw = spec.gateway_name()
        target, _, action = gw.partition("___")
        assert target == spec.domain
        assert action == spec.bare_name and action
        assert gw not in seen, f"duplicate gateway name: {gw}"
        seen.add(gw)
