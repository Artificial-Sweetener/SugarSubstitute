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

"""Tests for the reusable managed text asset modal."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

import pytest
from PySide6.QtWidgets import QHBoxLayout, QWidget
from shiboken6 import delete, isValid

from substitute.application.managed_text_assets import (
    CreateManagedTextAssetRequest,
    ManagedTextAsset,
    ManagedTextAssetKind,
    RenameManagedTextAssetRequest,
)
from substitute.application.prompt_editor import (
    wildcard_management_prompt_feature_profile,
)
from substitute.presentation.managed_text_assets import (
    ManagedTextAssetCreateAction,
    ManagedTextAssetModal,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)
from substitute.presentation.managed_text_assets import (
    managed_text_asset_modal as managed_text_asset_modal_module,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "managed text asset modal Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _FakeManagedTextAssetService:
    """Record managed text asset calls for modal contract tests."""

    def __init__(self) -> None:
        """Initialize deterministic assets and text content."""

        self.assets: dict[str, ManagedTextAsset] = {
            "a.txt": _asset("a.txt", "alpha", "TXT Wildcards"),
            "b.csv": _asset("b.csv", "beta", "CSV Wildcards"),
        }
        self.text: dict[str, str] = {"a.txt": "one\n", "b.csv": "value\n"}
        self.saved_text: list[tuple[str, str]] = []
        self.refreshed = False

    def list_assets(self) -> tuple[ManagedTextAsset, ...]:
        """Return assets in insertion order."""

        return tuple(self.assets.values())

    def read_asset_text(self, asset_id: str) -> str:
        """Return stored source text for one asset."""

        return self.text[asset_id]

    def save_asset_text(self, asset_id: str, text: str) -> ManagedTextAsset:
        """Record and persist one text save."""

        self.saved_text.append((asset_id, text))
        self.text[asset_id] = text
        return self.assets[asset_id]

    def create_asset(
        self,
        request: CreateManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Create one fake asset."""

        suffix = ".csv" if request.kind is ManagedTextAssetKind.CSV else ".txt"
        asset_id = f"{request.label}{suffix}"
        asset = _asset(
            asset_id,
            request.label,
            "CSV Wildcards" if suffix == ".csv" else "TXT Wildcards",
        )
        self.assets[asset_id] = asset
        self.text[asset_id] = request.content
        return asset

    def rename_asset(
        self,
        request: RenameManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Rename one fake asset."""

        old_asset = self.assets.pop(request.asset_id)
        suffix = ".csv" if request.asset_id.endswith(".csv") else ".txt"
        asset_id = f"{request.label}{suffix}"
        asset = _asset(asset_id, request.label, old_asset.group)
        self.assets[asset_id] = asset
        self.text[asset_id] = self.text.pop(request.asset_id)
        return asset

    def delete_asset(self, asset_id: str) -> None:
        """Delete one fake asset."""

        self.assets.pop(asset_id)
        self.text.pop(asset_id)

    def set_asset_enabled(
        self,
        asset_id: str,
        enabled: bool,
    ) -> ManagedTextAsset:
        """Set and return one fake asset's participation state."""

        asset = replace(self.assets[asset_id], enabled=enabled)
        self.assets[asset_id] = asset
        return asset

    def refresh(self) -> None:
        """Record cache refresh."""

        self.refreshed = True


def test_managed_text_asset_modal_loads_assets_and_preserves_switched_edits() -> None:
    """Switching assets should preserve unsaved editor text in memory."""

    app = ensure_qapp()
    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    modal.show()
    process_events(app)

    assert modal._current_asset_id == "a.txt"
    assert modal._editor.toPlainText() == "one\n"

    modal._editor.setPlainText("edited alpha")
    modal._select_asset("b.csv")
    modal._select_asset("a.txt")
    process_events(app)

    assert modal._editor.toPlainText() == "edited alpha"


def test_managed_text_asset_modal_switching_assets_resets_editor_undo_history() -> None:
    """Selecting another asset should not leave undo history from the previous asset."""

    app = ensure_qapp()
    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    modal.show()
    process_events(app)

    modal._editor.setPlainText("edited alpha")
    modal._select_asset("b.csv")
    process_events(app)

    assert modal._editor.toPlainText() == "value\n"

    modal._editor.undo()

    assert modal._editor.toPlainText() == "value\n"


def test_managed_text_asset_modal_save_current_clears_dirty_state() -> None:
    """Saving the current asset should call the service and disable Save."""

    app = ensure_qapp()
    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    modal.show()
    process_events(app)

    modal._editor.setPlainText("saved alpha")
    modal._save_current()

    assert service.saved_text == [("a.txt", "saved alpha")]
    assert modal._save_button.isEnabled() is False


def test_managed_text_asset_modal_rows_are_text_only() -> None:
    """Asset rows should not expose per-file enabled checkboxes."""

    app = ensure_qapp()
    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    modal.show()
    process_events(app)

    entry = modal._entries["a.txt"]

    assert not hasattr(entry.row, "checkbox")


def test_managed_text_asset_modal_replaces_deleted_fallback_parent() -> None:
    """Replace a cached Qt parent after its underlying object is destroyed."""

    app = ensure_qapp()
    app.closeAllWindows()
    process_events(app)
    stale_parent = managed_text_asset_modal_module._fallback_parent()
    delete(stale_parent)

    replacement = managed_text_asset_modal_module._fallback_parent()

    assert isValid(stale_parent) is False
    assert isValid(replacement) is True
    assert replacement is not stale_parent


def test_managed_text_asset_modal_apply_saves_text_only() -> None:
    """Apply should persist dirty text and refresh caches."""

    app = ensure_qapp()
    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    modal.show()
    process_events(app)

    modal._editor.setPlainText("applied alpha")
    modal._apply_and_close()

    assert service.saved_text == [("a.txt", "applied alpha")]
    assert service.refreshed is True


def test_managed_text_asset_modal_gives_editor_more_width() -> None:
    """The editor pane should receive the larger body stretch factor."""

    service = _FakeManagedTextAssetService()
    modal = _modal(service)
    body_item = modal.viewLayout.itemAt(1)
    assert body_item is not None
    body = body_item.widget()
    assert body is not None
    body_layout = body.layout()

    assert isinstance(body_layout, QHBoxLayout)
    assert body_layout.stretch(0) == 7
    assert body_layout.stretch(1) == 18


def test_managed_text_asset_modal_uses_owner_window_height() -> None:
    """The modal content should take 90 percent of the top-level owner height."""

    app = ensure_qapp()
    owner = QWidget()
    owner.resize(1200, 800)
    owner.show()
    process_events(app)
    service = _FakeManagedTextAssetService()
    modal = _modal(service, parent=owner)
    modal.show()
    process_events(app)

    assert modal.widget.height() == 720

    owner.resize(1200, 600)
    process_events(app)

    assert modal.widget.height() == 540


def test_managed_text_asset_modal_reports_operation_errors_through_presenter() -> None:
    """Operation failures should use the unified error modal presenter."""

    ensure_qapp()
    service = _FakeManagedTextAssetService()
    presented: list[dict[str, Any]] = []
    modal = _modal(
        service,
        error_presenter=type(
            "_Presenter",
            (),
            {"show_exception_report": lambda _self, **kwargs: presented.append(kwargs)},
        )(),
    )
    failure = RuntimeError("save failed")
    modal._current_asset_id = "a.txt"

    modal._report_error(
        title="Unable to save asset",
        operation="wildcard_modal.save_asset",
        error=failure,
    )

    assert presented[0]["title"] == "Unable to save asset"
    assert presented[0]["stage"] == "managed_text_assets"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "wildcard_modal.save_asset"
    assert context.values["asset_title"] == "Wildcard files"
    assert context.values["current_asset_id"] == "a.txt"


def _modal(
    service: _FakeManagedTextAssetService,
    *,
    parent: QWidget | None = None,
    error_presenter: Any | None = None,
) -> ManagedTextAssetModal:
    """Create a managed text asset modal with deterministic prompt dependencies."""

    return ManagedTextAssetModal(
        title="Wildcards",
        asset_title="Wildcard files",
        empty_text="No files.",
        service=service,
        create_actions=(
            ManagedTextAssetCreateAction(
                label="New TXT",
                kind=ManagedTextAssetKind.PROMPT_TEXT,
            ),
        ),
        prompt_runtime_services=PromptEditorRuntimeServices(
            autocomplete_gateway=EmptyPromptAutocompleteGateway(),
            wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
            prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
        ),
        prompt_feature_profile=wildcard_management_prompt_feature_profile(),
        error_presenter=error_presenter,
        parent=parent,
    )


def _asset(
    asset_id: str,
    label: str,
    group: str,
) -> ManagedTextAsset:
    """Return one fake managed text asset."""

    return ManagedTextAsset(
        id=asset_id,
        label=label,
        group=group,
        subtitle=asset_id,
        kind=ManagedTextAssetKind.CSV
        if asset_id.endswith(".csv")
        else ManagedTextAssetKind.PROMPT_TEXT,
        editable=True,
        can_rename=True,
        can_delete=True,
    )
