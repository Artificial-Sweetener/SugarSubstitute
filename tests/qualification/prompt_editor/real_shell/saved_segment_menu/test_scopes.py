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

"""Verify saved prompt-segment menu scopes through the real prompt shell."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import UserPreset
from substitute.presentation.editor.catalog.snapshots import CatalogSnapshotReadiness
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_saved_segment_menu_refreshes_after_diffusion_model_projection(
    tmp_path: Path,
) -> None:
    """A prompt built before its diffusion model should receive current save scopes."""

    model = _model_item(
        kind="diffusion_models",
        backend_value="Anima/hassakuAnima_v11.safetensors",
        display_name="Hassaku (Anima)",
        display_subtitle="v1.1",
        base_model="Anima",
    )
    catalog = _ModelCatalog(
        {"diffusion_models": (model,)},
        memory_cold=True,
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
        model_catalog_service=catalog,
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(
            initial_text="portrait, detailed lighting",
            model_node_type="SimpleSyrup.SimpleLoadAnima",
            model_field_key="diffusion_model",
            model_value="Anima\\hassakuAnima_v11.safetensors",
        )
        panel = shell_harness.shell.editor_panels[field.workflow.workflow_id]
        shell_harness.wait_until(
            lambda: (
                panel.active_model_snapshot_controller.snapshot.status.readiness
                is CatalogSnapshotReadiness.WARM
            )
        )
        target = shell_harness.input.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        shell_harness.wait_for_queued_delivery()

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
        )
        segment_snapshot = cast(Any, field.editor)._segment_preset_controller.snapshot

        assert "Save segment as..." in trace.menu_rows
        assert segment_snapshot.save_state.ready
        assert [
            render_application_text(scope.title)
            for scope in segment_snapshot.save_state.save_scopes
        ] == [
            "Global",
            "Anima",
            "Diffusion model",
        ]
        assert [
            render_application_text(scope.full_label)
            for scope in segment_snapshot.save_state.save_scopes
        ] == [
            "Global",
            "Base model: Anima",
            "Diffusion model: Hassaku (Anima) - v1.1",
        ]
        assert catalog.durable_requests == ["diffusion_models"]
    finally:
        shell_harness.close()


def test_real_shell_empty_entry_reprojection_preserves_anima_segment_scopes(
    tmp_path: Path,
) -> None:
    """Startup reuse with empty entries must retain cube-state model context."""

    model = _model_item(
        kind="diffusion_models",
        backend_value="Anima/hassakuAnima_v11.safetensors",
        display_name="Hassaku (Anima)",
        display_subtitle="v1.1",
        base_model="Anima",
    )
    catalog = _ModelCatalog(
        {"diffusion_models": (model,)},
        memory_cold=True,
    )
    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
        model_catalog_service=catalog,
    )
    try:
        field = shell_harness.workflows.add_anima_prompt_workflow(
            initial_text="portrait, detailed lighting",
            model_value="Anima\\hassakuAnima_v11.safetensors",
        )
        panel = shell_harness.shell.editor_panels[field.workflow.workflow_id]
        shell_harness.wait_until(
            lambda: (
                shell_harness.workflows.probes.probe_prompt_segment_scopes(
                    field
                ).active_snapshot_readiness
                == "warm"
            )
        )
        workflow = shell_harness.shell.workflow_session_service.get_workflow(
            field.workflow.workflow_id
        )
        assert workflow is not None

        panel.load_all_cubes(
            [],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
        )
        shell_harness.workflows.wait_for_prompt_field_absence(field)
        panel.load_all_cubes(
            [(field.workflow.cube_alias, field.workflow.cube_state)],
            cube_states=workflow.cubes,
            stack_order=workflow.stack_order,
        )
        panel.reveal_loaded_cube(field.workflow.cube_alias)
        field = shell_harness.workflows.refresh_prompt_field(field)

        probe = shell_harness.workflows.probes.probe_prompt_segment_scopes(field)
        assert probe.candidate_kind == "diffusion_models"
        assert probe.candidate_value == "Anima/hassakuAnima_v11.safetensors"
        assert probe.active_snapshot_readiness == "warm"
        assert probe.active_snapshot_item_value is not None
        assert probe.active_snapshot_item_value.replace("\\", "/") == (
            "Anima/hassakuAnima_v11.safetensors"
        )
        assert probe.editor_scope_titles == (
            "Global",
            "Anima",
            "Diffusion model",
        )
        dialog_probe = shell_harness.workflows.probes.probe_prompt_segment_dialog(
            field,
            selected_text="portrait, detailed lighting",
        )
        assert dialog_probe.title == "Save segment"
        assert dialog_probe.scope_full_labels == (
            "Global",
            "Base model: Anima",
            "Diffusion model: Hassaku (Anima) - v1.1",
        )
    finally:
        shell_harness.close()


def test_real_shell_saved_segment_menu_allows_global_save_without_model(
    tmp_path: Path,
) -> None:
    """Selected prompt text should remain globally saveable without model context."""

    shell_harness = PromptEditorRealShellScenario(
        artifact_root=tmp_path,
        user_preset_service=UserPresetService(_MemoryPresetRepository()),
    )
    try:
        field = shell_harness.workflows.add_prompt_workflow(initial_text="portrait")
        target = shell_harness.input.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        shell_harness.wait_for_queued_delivery()

        trace = shell_harness.context_menus.trace(
            field,
            clicked_text="portrait",
        )
        segment_snapshot = cast(Any, field.editor)._segment_preset_controller.snapshot

        assert "Save segment as..." in trace.menu_rows
        assert segment_snapshot.save_state.ready
        assert [scope.title for scope in segment_snapshot.save_state.save_scopes] == [
            "Global"
        ]
    finally:
        shell_harness.close()


class _MemoryPresetRepository:
    """Store user presets in memory for real-shell segment tests."""

    def __init__(self) -> None:
        """Initialize an empty preset collection."""

        self.presets: tuple[UserPreset, ...] = ()

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Replace stored presets."""

        self.presets = presets


class _ModelCatalog:
    """Return cached model rows without foreground loading."""

    def __init__(
        self,
        items_by_kind: dict[str, tuple[ModelCatalogItem, ...]],
        *,
        memory_cold: bool = False,
    ) -> None:
        """Store catalog rows by kind."""

        self.items_by_kind = items_by_kind
        self.memory_cold = memory_cold
        self.durable_requests: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Fail if the foreground context lists models."""

        raise AssertionError(f"unexpected model listing for {kind}")

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows for protocol completeness."""

        return self.items_by_kind.get(kind, ())

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return an immediately available catalog snapshot."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached catalog snapshot."""

        if self.memory_cold:
            return None

        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=1,
        )

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached rows for legacy readers."""

        if self.memory_cold:
            return None
        return self.items_by_kind.get(kind, ())

    def load_durable_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the configured authoritative durable snapshot."""

        self.durable_requests.append(kind)
        self.memory_cold = False
        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=2,
        )

    def cached_metadata_snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Return configured rows as a local metadata fallback."""

        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=0,
        )

    def invalidate(self, kind: str | None = None) -> None:
        """Accept invalidation for protocol completeness."""

        _ = kind


def _model_item(
    *,
    kind: str,
    backend_value: str,
    display_name: str,
    base_model: str,
    display_subtitle: str | None = None,
) -> ModelCatalogItem:
    """Return one deterministic model catalog item."""

    basename = backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors")
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=display_subtitle,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="models",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=base_model,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=display_name.casefold(),
    )
