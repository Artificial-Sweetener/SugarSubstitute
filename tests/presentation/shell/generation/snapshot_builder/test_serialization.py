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

"""Tests for shell generation snapshot-building helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    build_recipe_serialization_plan,
    create_recipe_serialization_context,
    serialize_generation_workflow,
)


from tests.presentation.shell.generation.snapshot_builder.support import (
    _behavior_snapshot,
    _workflow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def test_serialize_generation_workflow_passes_supported_kwargs() -> None:
    """Serialization should pass only kwargs supported by the recipe service."""

    calls: list[dict[str, object]] = []

    class _RecipeIoService:
        """Record supported serialization keyword arguments."""

        def serialize_workflow_to_sugar_script(
            self,
            workflow: object,
            *,
            enabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            disabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            global_override_scopes: object,
            serialization_context: object,
            serialization_plan: object,
            prompt_field_overrides: object,
        ) -> str:
            """Record serialization arguments and return Sugar text."""

            calls.append(
                {
                    "workflow": workflow,
                    "enabled": enabled_node_keys_by_alias,
                    "disabled": disabled_node_keys_by_alias,
                    "global": global_override_scopes,
                    "context": serialization_context,
                    "plan": serialization_plan,
                    "prompt_overrides": prompt_field_overrides,
                }
            )
            return "# sugar"

    workflow = _workflow()
    global_scopes = cast(
        Mapping[str, GlobalOverrideSerializationScope],
        {"scope": object()},
    )
    context = object()
    plan = object()
    prompt_overrides = {("A", "node", "field"): object()}

    assert (
        serialize_generation_workflow(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            global_override_scopes=global_scopes,
            serialization_context=context,
            serialization_plan=plan,
            prompt_field_overrides=prompt_overrides,
        )
        == "# sugar"
    )

    assert calls == [
        {
            "workflow": workflow,
            "enabled": {"A": ("enabled_from_bypass",)},
            "disabled": {"A": ("disabled_from_default",)},
            "global": global_scopes,
            "context": context,
            "plan": plan,
            "prompt_overrides": prompt_overrides,
        }
    ]


def test_serialize_generation_workflow_preserves_legacy_serializer_call() -> None:
    """Legacy serializers without optional kwargs should receive only workflow."""

    calls: list[object] = []

    class _RecipeIoService:
        """Record legacy serialization arguments."""

        def serialize_workflow_to_sugar_script(self, workflow: object) -> str:
            """Record the workflow and return Sugar text."""

            calls.append(workflow)
            return "# legacy"

    workflow = _workflow()

    assert (
        serialize_generation_workflow(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            global_override_scopes={"scope": object()},
        )
        == "# legacy"
    )
    assert calls == [workflow]


def test_create_recipe_serialization_context_uses_optional_factory() -> None:
    """Serialization context creation should be optional."""

    context = object()

    assert (
        create_recipe_serialization_context(
            SimpleNamespace(create_serialization_context=lambda: context)
        )
        is context
    )
    assert create_recipe_serialization_context(SimpleNamespace()) is None


def test_build_recipe_serialization_plan_passes_supported_kwargs() -> None:
    """Serialization plan construction should include activation deltas."""

    calls: list[dict[str, object]] = []
    context = object()
    plan = object()

    class _RecipeIoService:
        """Record supported plan keyword arguments."""

        def build_serialization_plan(
            self,
            workflow: object,
            *,
            enabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            disabled_node_keys_by_alias: dict[str, tuple[str, ...]],
            serialization_context: object,
        ) -> object:
            """Record plan arguments and return a plan object."""

            calls.append(
                {
                    "workflow": workflow,
                    "enabled": enabled_node_keys_by_alias,
                    "disabled": disabled_node_keys_by_alias,
                    "context": serialization_context,
                }
            )
            return plan

    workflow = _workflow()

    assert (
        build_recipe_serialization_plan(
            recipe_io_service=_RecipeIoService(),
            workflow=workflow,
            behavior_snapshot=_behavior_snapshot(),
            serialization_context=context,
        )
        is plan
    )
    assert calls == [
        {
            "workflow": workflow,
            "enabled": {"A": ("enabled_from_bypass",)},
            "disabled": {"A": ("disabled_from_default",)},
            "context": context,
        }
    ]


def test_build_recipe_serialization_plan_is_optional() -> None:
    """Missing plan construction support should return None."""

    assert (
        build_recipe_serialization_plan(
            recipe_io_service=SimpleNamespace(),
            workflow=_workflow(),
            behavior_snapshot=_behavior_snapshot(),
            serialization_context=None,
        )
        is None
    )
