#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for Comfy progress event field parsing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.comfy_progress_event_parser import (
    ComfyNodeProgressState,
    clamp_percent,
    compute_sampler_percent,
    fraction_from_progress_data,
    fraction_from_values,
    is_sampler_node,
    normalize_node_id,
    numeric_value,
    optional_percent,
    parse_model_load_progress,
    parse_progress_state_nodes,
    sampler_percent_from_progress_state,
)

_PARSER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "comfy_progress_event_parser.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_comfy_progress_event_parser_imports_no_ui_or_listener_boundaries() -> None:
    """Progress event field parsing must stay independent of Qt and listener code."""

    source = _PARSER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"display_node_id": "display", "node_id": "node"}, "display"),
        ({"display_node_id": "missing", "node_id": "node"}, "node"),
        ({"node_id": "missing", "parent_node_id": "parent"}, "parent"),
        ({"node_id": "missing", "real_node_id": "real"}, "real"),
    ],
)
def test_normalize_node_id_prefers_explicit_backend_identity_fields(
    kwargs: dict[str, str],
    expected: str,
) -> None:
    """Node normalization should preserve the existing backend field priority."""

    assert (
        normalize_node_id(
            all_node_ids={"display", "node", "parent", "real"},
            **kwargs,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        ("owner.1.2", "owner"),
        ("owner:dynamic", "owner"),
    ],
)
def test_normalize_node_id_falls_back_to_comfy_owner_prefix(
    node_id: str,
    expected: str,
) -> None:
    """Node normalization should map Comfy dynamic ids to workflow owners."""

    assert normalize_node_id(node_id=node_id, all_node_ids={"owner"}) == expected


def test_normalize_node_id_returns_none_for_unknown_node() -> None:
    """Unknown backend node ids should remain unresolved."""

    assert normalize_node_id(node_id="unknown", all_node_ids={"owner"}) is None


@pytest.mark.parametrize(
    ("value", "maximum", "expected"),
    [
        (2.0, 4.0, 0.5),
        (-1.0, 4.0, 0.0),
        (5.0, 4.0, 1.0),
        (1.0, 0.0, None),
        (1.0, -1.0, None),
    ],
)
def test_fraction_from_values_bounds_progress_fraction(
    value: float,
    maximum: float,
    expected: float | None,
) -> None:
    """Progress fractions should stay in range and reject invalid maxima."""

    assert fraction_from_values(value=value, maximum=maximum) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"value": 3, "max": 6}, 0.5),
        ({"value": True, "max": 6}, None),
        ({"value": 3, "max": False}, None),
        ({"value": "3", "max": 6}, None),
        ({"value": 3}, None),
    ],
)
def test_fraction_from_progress_data_accepts_numeric_progress_fields(
    data: dict[str, object],
    expected: float | None,
) -> None:
    """Progress event fractions should parse only numeric value and max fields."""

    assert fraction_from_progress_data(data) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"node": "sampler", "value": 5, "max": 10}, 50.0),
        ({"node": "sampler", "value": -1, "max": 10}, 0.0),
        ({"node": "sampler", "value": 11, "max": 10}, 100.0),
        ({"node": "sampler", "value": 1, "max": 0}, None),
        ({"value": 1, "max": 10}, None),
        ({"node": "sampler", "value": "1", "max": 10}, None),
    ],
)
def test_compute_sampler_percent_returns_bounded_sampler_percent(
    data: dict[str, object],
    expected: float | None,
) -> None:
    """Sampler progress payloads should produce a bounded UI percentage."""

    assert compute_sampler_percent(data) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1.0, 0.0),
        (20, 20.0),
        (120.0, 100.0),
        ("20", None),
        (None, None),
    ],
)
def test_optional_percent_clamps_numeric_values(
    value: object,
    expected: float | None,
) -> None:
    """Optional percent fields should clamp numeric payload values."""

    assert optional_percent(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-5.0, 0.0),
        (35.0, 35.0),
        (110.0, 100.0),
    ],
)
def test_clamp_percent_bounds_ui_percent(value: float, expected: float) -> None:
    """UI percentages should stay between zero and one hundred."""

    assert clamp_percent(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3, 3.0),
        (1.25, 1.25),
        (True, None),
        ("3", None),
    ],
)
def test_numeric_value_rejects_non_numeric_progress_values(
    value: object,
    expected: float | None,
) -> None:
    """Progress numeric parsing should reject bools and non-numeric values."""

    assert numeric_value(value) == expected


def test_parse_progress_state_nodes_normalizes_backend_node_identity() -> None:
    """Progress-state parsing should normalize child nodes to workflow owners."""

    progress_states = parse_progress_state_nodes(
        data={
            "nodes": {
                "ignored-key": {
                    "node_id": "24.0.1",
                    "display_node_id": "24",
                    "state": "running",
                    "value": 5,
                    "max": 10,
                },
                "21": {
                    "state": "finished",
                    "value": 1,
                    "max": 1,
                },
            }
        },
        all_node_ids={"21", "24"},
    )

    assert progress_states == (
        ComfyNodeProgressState(
            node_id="24.0.1",
            owner_node_id="24",
            state="running",
            value=5.0,
            maximum=10.0,
        ),
        ComfyNodeProgressState(
            node_id="21",
            owner_node_id="21",
            state="finished",
            value=1.0,
            maximum=1.0,
        ),
    )


def test_parse_progress_state_nodes_ignores_malformed_entries() -> None:
    """Malformed progress-state entries should not produce parsed nodes."""

    assert (
        parse_progress_state_nodes(
            data={
                "nodes": {
                    "bad-shape": "running",
                    "bad-state": {"state": "paused", "value": 1, "max": 1},
                    "bad-value": {"state": "running", "value": "1", "max": 1},
                    "bad-max": {"state": "running", "value": 1, "max": None},
                }
            },
            all_node_ids={"1"},
        )
        == ()
    )


def test_parse_progress_state_nodes_returns_empty_tuple_without_node_mapping() -> None:
    """Missing progress-state node mappings should parse as no update."""

    assert parse_progress_state_nodes(data={"nodes": []}, all_node_ids={"1"}) == ()


@pytest.mark.parametrize(
    ("node_id", "expected"),
    [
        ("1", True),
        ("2", True),
        ("3", False),
        ("4", False),
    ],
)
def test_is_sampler_node_matches_sampler_class_types(
    node_id: str,
    expected: bool,
) -> None:
    """Sampler detection should remain based on prompt node class type."""

    assert (
        is_sampler_node(
            node_id,
            {
                "1": {"class_type": "KSampler"},
                "2": {"class_type": "custom_sampler"},
                "3": {"class_type": "VAEDecode"},
                "4": "malformed",
            },
        )
        is expected
    )


def test_sampler_percent_from_progress_state_uses_most_advanced_running_sampler() -> (
    None
):
    """Running sampler progress-state entries should yield the highest percent."""

    progress_states = (
        ComfyNodeProgressState(
            node_id="1",
            owner_node_id="1",
            state="running",
            value=2.0,
            maximum=10.0,
        ),
        ComfyNodeProgressState(
            node_id="2",
            owner_node_id="2",
            state="running",
            value=9.0,
            maximum=10.0,
        ),
        ComfyNodeProgressState(
            node_id="3",
            owner_node_id="3",
            state="finished",
            value=10.0,
            maximum=10.0,
        ),
    )

    assert (
        sampler_percent_from_progress_state(
            progress_states=progress_states,
            prompt_nodes={
                "1": {"class_type": "KSampler"},
                "2": {"class_type": "KSampler"},
                "3": {"class_type": "KSampler"},
            },
        )
        == 90.0
    )


def test_sampler_percent_from_progress_state_ignores_non_sampler_and_invalid_entries() -> (
    None
):
    """Only running sampler entries with a positive maximum should count."""

    progress_states = (
        ComfyNodeProgressState(
            node_id="1",
            owner_node_id=None,
            state="running",
            value=8.0,
            maximum=10.0,
        ),
        ComfyNodeProgressState(
            node_id="2",
            owner_node_id="2",
            state="running",
            value=8.0,
            maximum=0.0,
        ),
        ComfyNodeProgressState(
            node_id="3",
            owner_node_id="3",
            state="running",
            value=8.0,
            maximum=10.0,
        ),
    )

    assert (
        sampler_percent_from_progress_state(
            progress_states=progress_states,
            prompt_nodes={"3": {"class_type": "VAEDecode"}},
        )
        is None
    )


def test_parse_model_load_progress_returns_typed_update_with_source_metadata() -> None:
    """Model-load parsing should validate payloads and enrich source metadata."""

    resolver_calls: list[tuple[str, set[str]]] = []

    def resolve_source_metadata(
        source_node_id: str,
        all_node_ids: set[str],
    ) -> tuple[str | None, str | None]:
        resolver_calls.append((source_node_id, all_node_ids))
        return ("Cube", "checkpoint")

    update = parse_model_load_progress(
        data={
            "version": 1,
            "prompt_id": "pid-1",
            "node_id": "24.0.0.1",
            "display_node_id": "24",
            "source_node_id": "2",
            "source_input_key": "ckpt_name",
            "phase": "dynamic_vram_staging",
            "state": "running",
            "percent": 140,
            "value": 2048,
            "max": 4897,
            "unit": "mb",
            "model_class": "SDXL",
            "model_name": "example.safetensors",
            "detail": "2048MB of 4897MB staged",
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"2", "24"},
        source_metadata_resolver=resolve_source_metadata,
    )

    assert update is not None
    assert update.workflow_id == "wf-1"
    assert update.prompt_id == "pid-1"
    assert update.node_id == "24.0.0.1"
    assert update.display_node_id == "24"
    assert update.phase == "dynamic_vram_staging"
    assert update.state == "running"
    assert update.percent == 100.0
    assert update.value == 2048.0
    assert update.maximum == 4897.0
    assert update.unit == "mb"
    assert update.model_class == "SDXL"
    assert update.model_name == "example.safetensors"
    assert update.source_node_id == "2"
    assert update.source_input_key == "ckpt_name"
    assert update.source_cube_alias == "Cube"
    assert update.source_workflow_node_name == "checkpoint"
    assert update.detail == "2048MB of 4897MB staged"
    assert resolver_calls == [("2", {"2", "24"})]


@pytest.mark.parametrize(
    "data",
    [
        {"version": 99, "phase": "dynamic_vram_staging", "state": "running"},
        {"version": 1, "phase": None, "state": "running"},
        {"version": 1, "phase": "bad", "state": "running"},
        {"version": 1, "phase": "dynamic_vram_staging", "state": "bad"},
        {
            "version": 1,
            "prompt_id": "other-prompt",
            "phase": "dynamic_vram_staging",
            "state": "running",
        },
    ],
)
def test_parse_model_load_progress_rejects_malformed_or_stale_payloads(
    data: dict[str, object],
) -> None:
    """Malformed or stale model-load events should not emit typed updates."""

    update = parse_model_load_progress(
        data=data,
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"24"},
        source_metadata_resolver=lambda _node_id, _node_ids: (None, None),
    )

    assert update is None


def test_parse_model_load_progress_requires_prompt_or_known_owner_identity() -> None:
    """Prompt-less model-load events should still identify a known owner node."""

    update = parse_model_load_progress(
        data={
            "version": 1,
            "node_id": "missing",
            "phase": "dynamic_vram_staging",
            "state": "running",
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"24"},
        source_metadata_resolver=lambda _node_id, _node_ids: (None, None),
    )

    assert update is None


def test_parse_model_load_progress_accepts_promptless_known_display_node() -> None:
    """Prompt-less model-load events can be routed by known display node identity."""

    update = parse_model_load_progress(
        data={
            "version": 1,
            "display_node_id": "24",
            "phase": "requested",
            "state": "unknown",
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids={"24"},
        source_metadata_resolver=lambda _node_id, _node_ids: (None, None),
    )

    assert update is not None
    assert update.prompt_id is None
    assert update.node_id is None
    assert update.display_node_id == "24"
    assert update.phase == "requested"
    assert update.state == "unknown"
