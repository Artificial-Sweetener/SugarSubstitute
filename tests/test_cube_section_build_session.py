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

"""Focused tests for cube-section build-session behavior."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "cube_section_build_session.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)


def test_cube_section_build_session_preserves_supplied_node_order() -> None:
    """Build sessions should trust the shared node-card order supplied upstream."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.cube_section_build_session"
    )
    session = mod.CubeSectionBuildSession(
        panel=SimpleNamespace(),
        route_key="Cube",
        cube_state=SimpleNamespace(buffer={}),
        cube={
            "nodes": {
                "vectorscopecc": {"class_type": "VectorscopeCC", "inputs": {}},
                "ksampler": {"class_type": "KSampler", "inputs": {}},
                "positive_prompt": {"class_type": "CLIPTextEncode", "inputs": {}},
            }
        },
        behavior_snapshot=SimpleNamespace(),
        field_specs_by_node={},
        node_order=["vectorscopecc", "ksampler", "positive_prompt"],
        grid_layout=SimpleNamespace(),
        widget=SimpleNamespace(),
    )

    assert session._node_order == ["vectorscopecc", "ksampler", "positive_prompt"]
    assert session.first_usable_reached is True
    assert session.deferred_node_count == 0


def test_cube_section_build_session_skips_failed_node_and_continues() -> None:
    """One unbuildable node card should not abort restored cube projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.cube_section_build_session"
    )
    added_widgets: list[object] = []
    build_calls: list[str] = []

    class _Card:
        """Minimal node-card double for cube-section build tests."""

        def __init__(self) -> None:
            self.destroyed = SimpleNamespace(connect=lambda _slot: None)
            self.properties: dict[str, object] = {}

        def setProperty(self, key: str, value: object) -> None:
            """Record dynamic Qt property writes."""

            self.properties[key] = value

    def build_node_card(
        node_name: str,
        *_args: object,
        **_kwargs: object,
    ) -> object:
        """Fail one node and build the next."""

        build_calls.append(node_name)
        if node_name == "missing_options":
            raise RuntimeError("Failed to resolve options")
        return _Card()

    class _Panel:
        """Minimal panel double exposing card-wrapper registry helpers."""

        def __init__(self) -> None:
            """Initialize an empty card-wrapper registry."""

            self.card_wrappers: dict[tuple[str, str], object] = {}

        def build_node_card(
            self, node_name: str, *args: object, **kwargs: object
        ) -> object:
            """Build a node card through the local failing/succeeding fake."""

            return build_node_card(node_name, *args, **kwargs)

        def register_card_wrapper(
            self,
            alias: str,
            node: str,
            wrapper: object,
        ) -> None:
            """Register the current wrapper for the requested node."""

            self.card_wrappers[(alias, node)] = wrapper

        def remove_card_wrapper_if_current(
            self,
            alias: str,
            node: str,
            wrapper: object,
        ) -> None:
            """Remove the wrapper only when it still owns the registry key."""

            if self.card_wrappers.get((alias, node)) is wrapper:
                self.card_wrappers.pop((alias, node), None)

    panel = _Panel()

    session = mod.CubeSectionBuildSession(
        panel=panel,
        route_key="Cube",
        cube_state={"buffer": {}},
        cube={
            "nodes": {
                "missing_options": {"class_type": "KSampler", "inputs": {}},
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
            }
        },
        behavior_snapshot=SimpleNamespace(
            resolved_nodes_by_alias={
                "Cube": {
                    "missing_options": SimpleNamespace(
                        card=SimpleNamespace(card_mode=SimpleNamespace(value="field"))
                    ),
                    "prompt": SimpleNamespace(
                        card=SimpleNamespace(card_mode=SimpleNamespace(value="prompt"))
                    ),
                }
            },
            card_decisions_by_alias={"Cube": {}},
        ),
        field_specs_by_node={"missing_options": {}, "prompt": {}},
        node_order=["missing_options", "prompt"],
        grid_layout=SimpleNamespace(
            addWidget=lambda widget: added_widgets.append(widget)
        ),
        widget=SimpleNamespace(defer_update_cube_height=lambda: None),
    )

    assert session.step() is False
    assert session.step() is True

    assert build_calls == ["missing_options", "prompt"]
    assert session._skipped_card_count == 1
    assert session._built_card_count == 1
    assert session.node_outcomes[0].kind == "build_error"
    assert session.node_outcomes[1].kind == "built"
    assert len(added_widgets) == 1


def test_cube_section_build_session_preserves_successful_masonry_insertion_order() -> (
    None
):
    """The build session should add visible cards in its supplied stable order."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.cube_section_build_session"
    )
    added_node_names: list[str] = []

    class _Card:
        """Record the node identity carried into masonry insertion."""

        def __init__(self, node_name: str) -> None:
            """Store identity and expose the Qt-like card surface."""

            self.node_name = node_name
            self.destroyed = SimpleNamespace(connect=lambda _slot: None)

        def setProperty(self, _key: str, _value: object) -> None:
            """Accept card variant properties without changing identity."""

    class _Panel:
        """Build a card for every node and ignore wrapper bookkeeping."""

        def build_node_card(
            self,
            node_name: str,
            *_args: object,
            **_kwargs: object,
        ) -> _Card:
            """Return a card carrying the requested node name."""

            return _Card(node_name)

        def register_card_wrapper(self, *_args: object) -> None:
            """Accept wrapper registration."""

        def remove_card_wrapper_if_current(self, *_args: object) -> None:
            """Accept wrapper cleanup."""

    node_order = ["third", "first", "second"]
    behavior = SimpleNamespace(
        card=SimpleNamespace(card_mode=SimpleNamespace(value="standard"))
    )
    session = mod.CubeSectionBuildSession(
        panel=_Panel(),
        route_key="Cube",
        cube_state={"buffer": {}},
        cube={
            "nodes": {
                node_name: {"class_type": "PrimitiveNode", "inputs": {"value": 1}}
                for node_name in node_order
            }
        },
        behavior_snapshot=SimpleNamespace(
            resolved_nodes_by_alias={
                "Cube": {node_name: behavior for node_name in node_order}
            },
            card_decisions_by_alias={"Cube": {}},
        ),
        field_specs_by_node={
            node_name: {"value": SimpleNamespace(meta_info={})}
            for node_name in node_order
        },
        node_order=node_order,
        grid_layout=SimpleNamespace(
            addWidget=lambda widget: added_node_names.append(widget.node_name)
        ),
        widget=SimpleNamespace(defer_update_cube_height=lambda: None),
    )

    session.finish()

    assert added_node_names == node_order


def test_cube_section_build_session_classifies_unbuilt_node_outcomes() -> None:
    """Skipped node cards should explain why each node was not rendered."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.cube_section_build_session"
    )
    field_spec = SimpleNamespace(meta_info={})
    resolved_behavior = SimpleNamespace(
        card=SimpleNamespace(card_mode=SimpleNamespace(value="field"))
    )
    hidden_decision = SimpleNamespace(visible=False)

    class _Panel:
        """Panel double that returns no node-card widgets."""

        def build_node_card(self, *_args: object, **_kwargs: object) -> None:
            """Return no widget so the session records a skip outcome."""

            return None

    session = mod.CubeSectionBuildSession(
        panel=_Panel(),
        route_key="Cube",
        cube_state={"buffer": {}},
        cube={
            "nodes": {
                "missing_behavior": {
                    "class_type": "MissingBehavior",
                    "inputs": {"value": 1},
                },
                "missing_specs": {
                    "class_type": "MissingSpecs",
                    "inputs": {"value": 1},
                },
                "connection_only": {
                    "class_type": "ConnectionOnly",
                    "inputs": {"value": ["upstream", 0]},
                },
                "factory_none": {
                    "class_type": "FactoryNone",
                    "inputs": {"value": 1},
                },
                "hidden_by_policy": {
                    "class_type": "HiddenByPolicy",
                    "inputs": {"value": 1},
                },
            }
        },
        behavior_snapshot=SimpleNamespace(
            resolved_nodes_by_alias={
                "Cube": {
                    "missing_specs": resolved_behavior,
                    "connection_only": resolved_behavior,
                    "factory_none": resolved_behavior,
                    "hidden_by_policy": resolved_behavior,
                }
            },
            card_decisions_by_alias={"Cube": {"hidden_by_policy": hidden_decision}},
        ),
        field_specs_by_node={
            "missing_specs": {},
            "connection_only": {"value": field_spec},
            "factory_none": {"value": field_spec},
            "hidden_by_policy": {"value": field_spec},
        },
        node_order=[
            "missing_behavior",
            "missing_specs",
            "connection_only",
            "factory_none",
            "hidden_by_policy",
        ],
        grid_layout=SimpleNamespace(addWidget=lambda _widget: None),
        widget=SimpleNamespace(defer_update_cube_height=lambda: None),
    )

    while not session.step():
        continue

    outcomes = {outcome.node_name: outcome.kind for outcome in session.node_outcomes}
    assert outcomes == {
        "missing_behavior": "missing_behavior",
        "missing_specs": "missing_field_specs",
        "connection_only": "connection_only",
        "factory_none": "factory_returned_none",
        "hidden_by_policy": "hidden_by_policy",
    }


def test_cube_section_build_session_owner_is_extracted_from_coordinator() -> None:
    """Build-session behavior should live in the dedicated session owner."""

    session_source = SESSION_SOURCE.read_text(encoding="utf-8")
    coordinator_source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "class CubeSectionBuildSession" in session_source
    assert "class CubeSectionBuildSession" not in coordinator_source
