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

"""Verify the application-owned editor search service."""

from __future__ import annotations

from substitute.application.editor_search import (
    EditorSearchMode,
    EditorSearchService,
    TextSearchMatch,
)
from tests.support.node_behavior import build_behavior_snapshot, cube_state


def test_quoted_node_search_scopes_text_matches_to_matching_nodes() -> None:
    """Scope quoted text matches to the node portion of a node-mode query."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "ksampler": {
                        "class_type": "KSampler",
                        "inputs": {
                            "prompt_template": "fox in the forest",
                            "sampler_name": "euler",
                        },
                    },
                    "other": {
                        "class_type": "OtherNode",
                        "inputs": {"prompt_template": "fox in the attic"},
                    },
                }
            )
        },
        stack_order=["A"],
    )
    service = EditorSearchService()

    result = service.build_result(
        snapshot,
        service.build_query(
            mode=EditorSearchMode.NODE,
            raw_text='ksampler "fox"',
        ),
    )

    assert result.matching_nodes == {("A", "ksampler")}
    assert result.navigation_matches == (
        TextSearchMatch("A", "ksampler", "prompt_template", 0, 3),
    )


def test_node_search_uses_authored_card_title_without_comfy_aliases() -> None:
    """Search the visible cube identity rather than its control type."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "positive_prompt": {
                        "class_type": "PrimitiveStringMultiline",
                        "inputs": {"value": "a red fox"},
                    }
                }
            )
        },
        stack_order=["A"],
        definitions_by_class={
            "PrimitiveStringMultiline": {
                "display_name": "Input Text",
                "input": {"required": {"value": ["STRING", {"multiline": True}]}},
            }
        },
    )
    service = EditorSearchService()

    authored_result = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.NODE, raw_text="positive prompt"),
    )
    comfy_result = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.NODE, raw_text="input text"),
    )

    assert authored_result.matching_nodes == {("A", "positive_prompt")}
    assert comfy_result.matching_nodes == set()


def test_field_search_matches_keys_and_effective_labels() -> None:
    """Match both canonical field keys and beautified labels in field mode."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "ksampler": {
                        "class_type": "KSampler",
                        "inputs": {"sampler_name": "euler", "cfg": 7.0},
                    },
                    "vae": {
                        "class_type": "VAELoader",
                        "inputs": {"vae_name": "foo.vae"},
                    },
                }
            )
        },
        stack_order=["A"],
    )
    service = EditorSearchService()

    by_key = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.FIELD, raw_text="sampler_name"),
    )
    assert by_key.matching_nodes == {("A", "ksampler")}
    assert by_key.matching_fields == {("A", "ksampler", "sampler_name")}

    by_label = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.FIELD, raw_text="sampler"),
    )
    assert by_label.matching_nodes == {("A", "ksampler")}
    assert by_label.matching_fields == {("A", "ksampler", "sampler_name")}


def test_field_search_matches_stored_cube_metadata_labels() -> None:
    """Match labels supplied through stored cube metadata."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "upscale_by_factor": {
                        "class_type": "Scaler",
                        "inputs": {"value": 1.5},
                    },
                },
            )
        },
        stack_order=["A"],
        definitions_by_class={
            "Scaler": {
                "input": {"required": {"value": ["FLOAT", {"label": "Scale Factor"}]}}
            }
        },
    )
    service = EditorSearchService()

    result = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.FIELD, raw_text="scale factor"),
    )

    assert result.matching_fields == {("A", "upscale_by_factor", "value")}


def test_text_search_preserves_stable_navigation_order() -> None:
    """Return text matches in alias, node, field, and source order."""

    snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "node_a": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": "dog alpha dog", "seed": 42},
                    }
                }
            ),
            "B": cube_state(
                nodes={
                    "node_b": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": "dog beta"},
                    }
                }
            ),
        },
        stack_order=["A", "B"],
    )
    service = EditorSearchService()

    result = service.build_result(
        snapshot,
        service.build_query(mode=EditorSearchMode.TEXT, raw_text="dog"),
    )

    assert result.navigation_matches == (
        TextSearchMatch("A", "node_a", "prompt_template", 0, 3),
        TextSearchMatch("A", "node_a", "prompt_template", 10, 3),
        TextSearchMatch("B", "node_b", "prompt_template", 0, 3),
    )
