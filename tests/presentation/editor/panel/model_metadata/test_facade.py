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

"""Test model metadata and progress presentation through EditorPanel."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType, SimpleNamespace

from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from substitute.application.model_metadata import ModelMetadataRefreshEvent


class _ModelPicker:
    """Record model progress and event-driven metadata refreshes."""

    def __init__(self, refreshed: bool = False) -> None:
        """Initialize the configured refresh result."""

        self.refreshed = refreshed
        self.progress_calls: list[tuple[float | None, bool]] = []
        self.events: list[ModelMetadataRefreshEvent] = []

    def set_model_load_progress(
        self,
        *,
        percent: float | None,
        active: bool,
    ) -> None:
        """Record one model-load progress update."""

        self.progress_calls.append((percent, active))

    def refresh_metadata_for_event(self, event: ModelMetadataRefreshEvent) -> bool:
        """Record one metadata event and return the configured refresh outcome."""

        self.events.append(event)
        return self.refreshed


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_model_field_load_progress_routes_only_to_model_picker(
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    """EditorPanel should route progress only through indexed model pickers."""

    panel_module = _panel_module()
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(panel_module, "ModelPickerField", _ModelPicker)
    picker = _ModelPicker()
    widget_map = {
        ("Cube", "checkpoint", "ckpt_name"): picker,
        ("Cube", "sampler", "steps"): object(),
    }
    panel = SimpleNamespace(
        _field_registry=SimpleNamespace(widget_map=widget_map),
        input_widgets_by_field_key=widget_map,
    )

    panel_module.EditorPanel.set_model_field_load_progress(
        panel,
        cube_alias="Cube",
        node_name="checkpoint",
        field_key="ckpt_name",
        percent=37.5,
        active=True,
    )
    panel_module.EditorPanel.set_model_field_load_progress(
        panel,
        cube_alias="Cube",
        node_name="sampler",
        field_key="steps",
        percent=37.5,
        active=True,
    )
    panel_module.EditorPanel.set_model_field_load_progress(
        panel,
        cube_alias="Missing",
        node_name="checkpoint",
        field_key="ckpt_name",
        percent=37.5,
        active=True,
    )

    assert picker.progress_calls == [(37.5, True)]
    assert "Applied model-load progress to model picker" in caplog.text
    assert "Model-load progress target widget is not a model picker" in caplog.text
    assert "Model-load progress target widget was not found" in caplog.text


def test_clear_model_field_load_progress_clears_tracked_model_pickers(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel cleanup should clear every tracked model picker once."""

    panel_module = _panel_module()
    monkeypatch.setattr(panel_module, "ModelPickerField", _ModelPicker)
    picker = _ModelPicker()
    widget_map = {
        ("Cube", "checkpoint", "ckpt_name"): picker,
        ("Cube", "checkpoint", "alt"): picker,
        ("Cube", "sampler", "steps"): object(),
    }
    panel = SimpleNamespace(
        _field_registry=SimpleNamespace(widget_map=widget_map),
        input_widgets_by_field_key=widget_map,
    )

    panel_module.EditorPanel.clear_model_field_load_progress(panel)

    assert picker.progress_calls == [(None, False)]


def test_refresh_model_metadata_for_event_delegates_to_model_pickers(
    monkeypatch: MonkeyPatch,
) -> None:
    """EditorPanel should target model picker refreshes for metadata events."""

    panel_module = _panel_module()
    monkeypatch.setattr(panel_module, "ModelPickerField", _ModelPicker)
    event = ModelMetadataRefreshEvent(
        kind="checkpoints",
        value="models/base.safetensors",
        relative_path="models/base.safetensors",
        sha256="ABC123",
        provider_status="found",
    )
    refreshed_picker = _ModelPicker(True)
    deferred_picker = _ModelPicker(False)
    refresh_reasons: list[str] = []
    panel = SimpleNamespace(
        _field_registry=SimpleNamespace(
            entries=lambda: (
                SimpleNamespace(widget=refreshed_picker),
                SimpleNamespace(widget=deferred_picker),
            )
        ),
        _preset_context_refresh=SimpleNamespace(
            refresh=lambda *, reason: refresh_reasons.append(reason)
        ),
    )

    refreshed_count = panel_module.EditorPanel.refresh_model_metadata_for_event(
        panel,
        event,
    )

    assert refreshed_count == 1
    assert refreshed_picker.events == [event]
    assert deferred_picker.events == [event]
    assert refresh_reasons == ["model_metadata_event_refreshed"]
