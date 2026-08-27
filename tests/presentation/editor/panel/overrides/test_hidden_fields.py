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

"""Regression tests for override manager hidden-field behavior."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)


def test_apply_global_overrides_updates_editor_hidden_keys() -> None:
    """Fallback hidden-field application should hide tuple-scoped pinned fields."""

    snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "A": {
                "ksampler": {
                    "sampler_name": ResolvedFieldSpec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        field_type="STRING",
                        constraints={},
                        meta_info={},
                        field_info=None,
                        value="euler",
                        field_behavior=FieldBehavior(
                            field_key="sampler_name",
                            override_behavior=OverrideBehavior(
                                override_key="sampler_name",
                                pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                                toolbar_order=20,
                            ),
                        ),
                    )
                }
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )

    class DummyEditor:
        def __init__(self) -> None:
            self._hidden: set[object] | None = None

        def current_behavior_snapshot(self) -> EditorBehaviorSnapshot:
            return snapshot

        def refresh_node_behavior_state(self, **_kwargs: object) -> None:
            raise RuntimeError("force fallback")

        def set_hidden_field_keys(self, hidden: set[object]) -> None:
            self._hidden = set(hidden)

    class DummyWorkflow:
        def __init__(self) -> None:
            self.stack_order = ["A"]
            self.cubes = {
                "A": SimpleNamespace(
                    buffer={
                        "nodes": {"ksampler": {"inputs": {"sampler_name": "euler"}}}
                    }
                )
            }
            self.global_overrides = {
                "sampler_name": {"value": "heun", "mode": "global"}
            }

    class DummyMW:
        def __init__(self) -> None:
            self._wf = DummyWorkflow()
            self.active_editor_panel = DummyEditor()

        def get_active_workflow(self) -> DummyWorkflow:
            """Return the workflow governed by the manager."""

            return self._wf

    mw = DummyMW()
    mgr = GlobalOverridesManager(
        mw,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    mgr.sync_state_from_workflow()

    mgr.apply_global_overrides()

    assert mw.active_editor_panel._hidden == {("A", "ksampler", "sampler_name")}
