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

"""Build projection-binding integration test collaborators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    bind_output_canvas_session,
)
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    ImageMeta,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from tests.support.output_canvas.projection_controller_factory import (
    output_canvas_projection_controller_for_test_host,
)
from substitute.presentation.canvas.output.output_canvas_preview_retirement import (
    retire_output_previews_for_completed_slot,
)


class _Signal:
    """Small signal double used by widget method tests."""

    def __init__(self) -> None:
        """Create an empty slot and call recorder."""

        self._slots: list[Any] = []
        self.calls: list[tuple[Any, ...]] = []

    def connect(self, slot: Any) -> None:
        """Record a connected slot."""

        self._slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        """Remove a connected slot or mirror Qt's disconnection failure."""

        if slot not in self._slots:
            raise RuntimeError("slot not connected")
        self._slots.remove(slot)

    def emit(self, *args: Any) -> None:
        """Record and dispatch one signal emission."""

        self.calls.append(args)
        for slot in list(self._slots):
            slot(*args)


def _bind_projection_session(fake: object, session: object) -> None:
    """Bind projection through its owning controller for lightweight host tests."""

    output_canvas_projection_controller_for_test_host(fake).bind_projection_session(
        cast(Any, session),
        retire_completed_preview_slot=lambda slot_key, source_label, reason: (
            retire_output_previews_for_completed_slot(
                fake,
                slot_key,
                source_label=source_label,
                retire_reason=reason,
            )
        ),
    )


def _session_for_projection(
    projection: OutputCanvasProjection,
    *,
    workflow_id: str = "wf",
) -> object:
    """Return an Output session wrapper for widget projection tests."""

    metadata = {
        item.image_id: item.image_meta
        for source in projection.sources
        for item in source.images_by_set.values()
    }
    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup=metadata,
    )


def _meta(*, source_key: str, source_label: str) -> ImageMeta:
    """Return minimal output metadata for projection binding tests."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name=source_label,
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key=source_key,
        source_label=source_label,
    )


def _projection_fake(
    *,
    tabbar: object,
    set_selector_button: object,
    pane_calls: list[object] | None = None,
    pane_current_image: UUID | None = None,
    presented: list[dict[str, object]] | None = None,
) -> SimpleNamespace:
    """Return a lightweight OutputCanvas-like projection binding host."""

    pane_call_log = pane_calls if pane_calls is not None else []
    presented_log = presented if presented is not None else []

    def _set_current_image_id(image_id: object) -> None:
        pane_call_log.append(image_id)

    def _record_present(**kwargs: object) -> None:
        presented_log.append(kwargs)

    pane = SimpleNamespace(
        currentImageID=lambda: pane_current_image,
        setCurrentImageID=_set_current_image_id,
        setControlMode=lambda _mode: None,
    )
    fake = SimpleNamespace(
        tabbar=tabbar,
        image_ids=[],
        metas_by_id={},
        images_by_id={},
        preview_ids_by_source_key={},
        preview_labels_by_source_key={},
        preview_images_by_source_key={},
        grid_scene_ids_by_source_key={},
        grid_layer_ids_by_key={},
        source_groups={},
        active_source_key=None,
        active_set_index=1,
        last_real_set_index=1,
        set_count=0,
        pane=pane,
        set_selector_button=set_selector_button,
        tabbar_container=_NavigationWidget(),
        tabbar_bg=_NavigationWidget(),
        _route_session_boundary=CanvasSessionBoundary(),
        _compare_presenter=SimpleNamespace(present=_record_present),
        _on_tab_changed=lambda _route: None,
        _interaction_controller=SimpleNamespace(
            set_grid_interaction_locked=lambda _locked: None,
        ),
        height=lambda: 400,
        width=lambda: 640,
    )
    fake._navigation_controller = OutputCanvasNavigationController(
        canvas_width=lambda: 640,
        tabbar=lambda: tabbar,
        cached_source_tabbar_width=lambda: int(
            getattr(fake, "_source_tabbar_preferred_width", 0)
        ),
        set_cached_source_tabbar_width=lambda width: setattr(
            fake,
            "_source_tabbar_preferred_width",
            width,
        ),
    )

    def _rebuild_source_tabs(*, active_source_key: str | None) -> None:
        """Mirror the source-tab writes needed by projection binding tests."""

        projection = cast(OutputCanvasProjection, fake._output_projection)
        tabbar_view = cast(Any, tabbar)
        for key in list(tabbar_view.items):
            tabbar_view.removeWidget(key)
        for source in projection.sources:
            tabbar_view.addItem(source.source_key, source.label)
        if active_source_key is not None:
            tabbar_view.setCurrentItem(active_source_key)

    fake._source_tabs_controller = SimpleNamespace(
        rebuild_source_tabs=_rebuild_source_tabs,
        refresh_source_tab_tooltips=lambda: None,
    )
    return fake


def _tabbar(
    *,
    removed: list[str] | None = None,
    added: list[tuple[str, str]] | None = None,
    current: list[str] | None = None,
    items: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Return a recordable source-tab bar double."""

    removed_log = removed if removed is not None else []
    added_log = added if added is not None else []
    current_log = current if current is not None else []
    item_map = {} if items is None else dict(items)

    def _set_current_item(key: str) -> None:
        current_log.append(key)

    def _remove_widget(key: str) -> None:
        item_map.pop(key, None)
        removed_log.append(key)

    def _add_item(key: str, label: str) -> None:
        item_map[key] = label
        added_log.append((key, label))

    tabbar = SimpleNamespace(
        items=item_map,
        currentItemChanged=_Signal(),
        adjustSize=lambda: None,
        hide=lambda: None,
        raise_=lambda: None,
        setGeometry=lambda *_args: None,
        setVisible=lambda _visible: None,
        sizeHint=lambda: SimpleNamespace(width=lambda: 120, height=lambda: 28),
        setCurrentItem=_set_current_item,
        removeWidget=_remove_widget,
        addItem=_add_item,
    )
    return tabbar


class _NavigationWidget:
    """Small widget double for projection-binding navigation chrome refresh."""

    def hide(self) -> None:
        """Accept hide calls."""

    def show(self) -> None:
        """Accept show calls."""

    def setVisible(self, _visible: bool) -> None:  # noqa: N802
        """Accept Qt-style visibility calls."""

    def width(self) -> int:
        """Return a stable default width."""

        return 34

    def height(self) -> int:
        """Return a stable default height."""

        return 28

    def sizeHint(self) -> object:  # noqa: N802
        """Return a Qt-like size hint."""

        return SimpleNamespace(width=lambda: 34, height=lambda: 28)

    def setGeometry(self, *_args: object) -> None:  # noqa: N802
        """Accept geometry calls."""

    def raise_(self) -> None:
        """Accept z-order calls."""

    def lower(self) -> None:
        """Accept z-order calls."""


def _selector() -> SimpleNamespace:
    """Return a recordable selector button double."""

    selector = SimpleNamespace(text="", visible=[])

    def _set_visible(visible: bool) -> None:
        selector.visible.append(visible)

    selector.setText = lambda text: setattr(selector, "text", text)
    selector.setVisible = _set_visible
    return selector
