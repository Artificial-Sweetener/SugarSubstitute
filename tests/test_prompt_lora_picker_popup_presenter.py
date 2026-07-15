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

"""Tests for LoRA picker popup presenter ownership."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
)
from substitute.presentation.editor.prompt_editor.commands import PromptCommandResult
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
    PromptLoraPickerSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptLoraPickerActivationSignal,
    PromptLoraPickerPopupPresenter,
    PromptLoraPickerPopupView,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)


@pytest.fixture(autouse=True)
def _cleanup_presenter_parent_widgets() -> Iterator[None]:
    """Delete presenter parent widgets created by these focused tests."""

    yield
    app = QApplication.instance()
    if app is None:
        return
    for widget in QApplication.topLevelWidgets():
        if widget.objectName() == "promptLoraPickerPresenterTestParent":
            widget.close()
            widget.deleteLater()
    app.processEvents()


class _ActivationSignal:
    """Capture and emit fake picker activations."""

    def __init__(self) -> None:
        """Initialize with no connected callbacks."""

        self.callbacks: list[Callable[[object], None]] = []

    def connect(self, slot: Callable[[object], None]) -> object:
        """Record one activation slot."""

        self.callbacks.append(slot)
        return object()

    def emit(self, item: object) -> None:
        """Emit one item to every connected callback."""

        for callback in self.callbacks:
            callback(item)


class _Popup:
    """Fake LoRA picker popup view."""

    def __init__(self, *, visible: bool = True) -> None:
        """Initialize popup state."""

        self.activation_signal = _ActivationSignal()
        self.loraActivated: PromptLoraPickerActivationSignal = self.activation_signal
        self.visible = visible
        self.hidden = False
        self.deleted = False
        self.set_loras_calls: list[tuple[PromptLoraCatalogItem, ...]] = []

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether this popup should be treated as visible."""

        return self.visible

    def hide(self) -> None:
        """Record popup hiding."""

        self.hidden = True

    def deleteLater(self) -> None:  # noqa: N802
        """Record scheduled deletion."""

        self.deleted = True

    def set_loras(self, items: Iterable[PromptLoraCatalogItem]) -> None:
        """Record refreshed LoRA rows."""

        self.set_loras_calls.append(tuple(items))


class _DataSource:
    """Fake LoRA picker data source."""

    def __init__(
        self,
        *,
        ready: bool = True,
        items: tuple[PromptLoraCatalogItem, ...] = (),
        readiness: CatalogSnapshotReadiness = CatalogSnapshotReadiness.WARM,
    ) -> None:
        """Initialize source state."""

        self._ready = ready
        self.items = items
        self.readiness = readiness
        self.snapshot_reads = 0
        self.schedule_text_calls: list[PromptLoraCatalogItem] = []
        self._schedule_service = PromptLoraScheduleService()

    @property
    def lora_picker_ready(self) -> bool:
        """Return whether the picker can open."""

        return self._ready

    @property
    def lora_picker_snapshot(self) -> PromptLoraPickerSnapshot:
        """Return fake prepared picker rows and record foreground reads."""

        self.snapshot_reads += 1
        return PromptLoraPickerSnapshot(
            identity=CatalogSnapshotIdentity(),
            status=CatalogSnapshotStatus(self.readiness),
            items=self.items,
            catalog_revision=1,
            dirty=False,
        )

    def schedule_text_for_lora(self, selected_lora: PromptLoraCatalogItem) -> str:
        """Return real scheduler-safe LoRA text."""

        self.schedule_text_calls.append(selected_lora)
        return self._schedule_service.schedule_text(selected_lora)


class _PopupFactory:
    """Fake popup factory."""

    def __init__(self) -> None:
        """Initialize with no created popups."""

        self.created: list[_Popup] = []
        self.positions: list[QPoint] = []
        self.items: list[tuple[PromptLoraCatalogItem, ...]] = []
        self.parents: list[QWidget] = []
        self.thumbnail_caches: list[PromptLoraThumbnailCache] = []

    def __call__(
        self,
        parent: QWidget,
        items: Iterable[PromptLoraCatalogItem],
        *,
        thumbnail_cache: PromptLoraThumbnailCache,
        global_position: QPoint,
    ) -> PromptLoraPickerPopupView:
        """Create one fake popup."""

        popup = _Popup()
        self.created.append(popup)
        self.positions.append(QPoint(global_position))
        self.items.append(tuple(items))
        self.parents.append(parent)
        self.thumbnail_caches.append(thumbnail_cache)
        return popup


class _TextInsertionExecutor:
    """Record picker insertion commands."""

    def __init__(self) -> None:
        """Initialize with no inserted text."""

        self.insertions: list[tuple[str, str]] = []

    def insert_context_menu_text(
        self,
        insertion_text: str,
        *,
        command_name: str = "context_menu_insert_text",
    ) -> PromptCommandResult[object]:
        """Record one insertion request."""

        self.insertions.append((insertion_text, command_name))
        return PromptCommandResult(
            command_name=command_name,
            status="noop",
            reason="test_double",
        )


def test_lora_picker_presenter_does_not_open_when_feature_is_disabled() -> None:
    """Disabled picker state should suppress popup creation."""

    presenter, data_source, factory, _ = _presenter(ready=False)

    presenter.open_lora_picker()

    assert factory.created == []
    assert data_source.snapshot_reads == 0


def test_lora_picker_presenter_opens_with_prepared_rows_and_menu_position() -> None:
    """Opening should create a popup from prepared rows at the menu position."""

    item = _item(prompt_name="characters/midna")
    menu_pos = QPoint(12, 34)
    cursor_pos = QPoint(56, 78)
    cache = PromptLoraThumbnailCache()
    presenter, data_source, factory, _ = _presenter(
        items=(item,),
        thumbnail_cache=cache,
        menu_position=menu_pos,
        cursor_position=cursor_pos,
    )

    presenter.open_lora_picker()

    assert data_source.snapshot_reads == 1
    assert factory.items == [(item,)]
    assert factory.positions == [menu_pos]
    assert factory.thumbnail_caches == [cache]


def test_lora_picker_presenter_replaces_existing_popup() -> None:
    """Opening a second picker should retire the previous popup."""

    presenter, _, factory, _ = _presenter(items=(_item(),))

    presenter.open_lora_picker()
    first_popup = factory.created[0]
    presenter.open_lora_picker()

    assert first_popup.hidden is True
    assert first_popup.deleted is True
    assert len(factory.created) == 2


def test_lora_picker_presenter_uses_cursor_position_without_menu_position() -> None:
    """Opening without a context-menu anchor should use the cursor position."""

    cursor_pos = QPoint(90, 123)
    presenter, _, factory, _ = _presenter(
        items=(_item(),),
        menu_position=None,
        cursor_position=cursor_pos,
    )

    presenter.open_lora_picker()

    assert factory.positions == [cursor_pos]


def test_lora_picker_presenter_refreshes_visible_popup_rows() -> None:
    """Visible popup refresh should replace rows from prepared snapshots only."""

    first = _item(prompt_name="characters/midna")
    second = _item(prompt_name="characters/mineru")
    presenter, data_source, factory, _ = _presenter(items=(first,))
    presenter.open_lora_picker()
    popup = factory.created[0]
    data_source.items = (second,)

    assert presenter.refresh_visible_lora_picker() is True

    assert data_source.snapshot_reads == 2
    assert popup.set_loras_calls == [(second,)]


def test_lora_picker_presenter_uses_empty_rows_for_cold_snapshot() -> None:
    """Cold prepared state should open a cheap empty picker without refreshing."""

    item = _item()
    presenter, data_source, factory, _ = _presenter(
        items=(item,),
        readiness=CatalogSnapshotReadiness.COLD,
    )

    presenter.open_lora_picker()

    assert data_source.snapshot_reads == 1
    assert factory.items == [()]


def test_lora_picker_presenter_ignores_missing_or_hidden_popup_refresh() -> None:
    """Refresh should be a no-op when no visible popup is owned."""

    presenter, data_source, factory, _ = _presenter(items=(_item(),))

    assert presenter.refresh_visible_lora_picker() is False
    presenter.open_lora_picker()
    factory.created[0].visible = False

    assert presenter.refresh_visible_lora_picker() is False
    assert data_source.snapshot_reads == 1


def test_lora_picker_presenter_inserts_selected_lora_schedule_text() -> None:
    """Activation should insert schedule text through the command adapter."""

    item = _item(prompt_name=r"illustrious\characters\safe_midna")
    presenter, data_source, factory, executor = _presenter(items=(item,))
    presenter.open_lora_picker()

    factory.created[0].activation_signal.emit(item)

    assert data_source.schedule_text_calls == [item]
    assert executor.insertions == [
        (
            r"<lora:illustrious\characters\safe_midna:1.00>",
            "context_menu_insert_text",
        )
    ]


def test_lora_picker_presenter_ignores_invalid_activation_payload() -> None:
    """Only catalog-item activations should insert text."""

    presenter, data_source, factory, executor = _presenter(items=(_item(),))
    presenter.open_lora_picker()

    factory.created[0].activation_signal.emit(object())

    assert data_source.schedule_text_calls == []
    assert executor.insertions == []


def _presenter(
    *,
    ready: bool = True,
    items: tuple[PromptLoraCatalogItem, ...] = (),
    readiness: CatalogSnapshotReadiness = CatalogSnapshotReadiness.WARM,
    thumbnail_cache: PromptLoraThumbnailCache | None = None,
    menu_position: QPoint | None = QPoint(10, 20),
    cursor_position: QPoint = QPoint(30, 40),
) -> tuple[
    PromptLoraPickerPopupPresenter,
    _DataSource,
    _PopupFactory,
    _TextInsertionExecutor,
]:
    """Return a presenter with deterministic fake collaborators."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    parent = QWidget()
    parent.setObjectName("promptLoraPickerPresenterTestParent")
    data_source = _DataSource(ready=ready, items=items, readiness=readiness)
    factory = _PopupFactory()
    executor = _TextInsertionExecutor()
    presenter = PromptLoraPickerPopupPresenter(
        parent=parent,
        data_source=data_source,
        thumbnail_cache=thumbnail_cache or PromptLoraThumbnailCache(),
        text_insertion_executor=executor,
        popup_factory=factory,
        last_context_menu_global_pos=(
            lambda: None if menu_position is None else QPoint(menu_position)
        ),
        cursor_global_position=lambda: QPoint(cursor_position),
    )
    return presenter, data_source, factory, executor


def _item(
    *,
    prompt_name: str = r"illustrious\characters\Midna",
) -> PromptLoraCatalogItem:
    """Return one LoRA catalog item for presenter tests."""

    basename = prompt_name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    return PromptLoraCatalogItem(
        display_name=basename,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=r"illustrious\characters",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=basename.casefold(),
    )
