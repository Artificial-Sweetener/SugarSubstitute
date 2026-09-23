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

"""Compose one mounted prompt-editor shell runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRect
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollBar, QWidget

from ..interactions.clipboard_paste_completion import (
    PromptClipboardPasteCompletionOwner,
)
from .qfluent_chrome import (
    PromptShellChromeHost,
    PromptShellChromeSurface,
    PromptShellQFluentChrome,
)
from .scroll_delegate import (
    PromptShellScrollDelegate,
    PromptShellScrollHost,
    PromptShellScrollSurface,
    PromptShellSignal,
)
from .sizing_controller import (
    PromptShellSizingController,
    PromptShellSizingHost,
    PromptShellSizingSignal,
)
from .widget import PromptEditorShell


@dataclass(frozen=True, slots=True)
class PromptEditorShellRuntimeMount:
    """Describe the concrete Qt mount shared by shell collaborators."""

    widget: QWidget
    chrome_host: PromptShellChromeHost
    scroll_host: PromptShellScrollHost
    sizing_host: PromptShellSizingHost
    shell_viewport: QWidget
    maximum_visible_lines: int | None
    resized: PromptShellSignal
    manual_scroll_height_changed: PromptShellSizingSignal


@dataclass(frozen=True, slots=True)
class PromptEditorShellRuntimeBindings:
    """Bind shell mechanics to late-created projection and feature owners."""

    content_viewport: Callable[[], QWidget | None]
    apply_host_placeholder: Callable[[str], None]
    source_text: Callable[[], str]
    chrome_surface: Callable[[], PromptShellChromeSurface | None]
    scroll_surface: Callable[[], PromptShellScrollSurface | None]
    shell_padding_fill_plane: Callable[[], QWidget | None]
    fill_plane: Callable[[], QWidget | None]
    token_weight_controls: Callable[[], QWidget | None]
    update_backing_fill: Callable[[QRect], None]
    finish_pending_key_edit_block: Callable[[str], None]
    schedule_lora_metadata_catchup: Callable[[], None]
    handle_focus_out: Callable[[], None]
    handle_hide: Callable[[], None]
    handle_move: Callable[[], None]
    handle_viewport_wheel_event: Callable[[QWheelEvent], bool]
    host_scrollbar: Callable[[], QScrollBar]
    handle_viewport_scroll: Callable[[], None]
    handle_resize: Callable[[], None]
    surface_content_height: Callable[[], float]
    projection_line_height: Callable[[], float]
    surface_is_alive: Callable[[], bool]
    update_fill_planes: Callable[[], None]
    resize_handle: Callable[[], QWidget | None]
    ancestor_external_wheel_handler: Callable[[], object | None]


@dataclass(frozen=True, slots=True)
class PromptEditorShellRuntime:
    """Own shell chrome, scrolling, sizing, and paste-completion lifecycle."""

    shell: PromptEditorShell
    chrome: PromptShellQFluentChrome
    scrolling: PromptShellScrollDelegate
    sizing: PromptShellSizingController
    paste_completion: PromptClipboardPasteCompletionOwner


class _PromptEditorShellRuntimeReferences:
    """Resolve the intentional scroll-and-sizing construction cycle once."""

    def __init__(self) -> None:
        """Create unbound construction-only collaborator references."""
        self._scrolling: PromptShellScrollDelegate | None = None
        self._sizing: PromptShellSizingController | None = None

    def bind(
        self,
        *,
        scrolling: PromptShellScrollDelegate,
        sizing: PromptShellSizingController,
    ) -> None:
        """Bind the sole scrolling and sizing owners for the runtime."""
        if self._scrolling is not None or self._sizing is not None:
            raise RuntimeError("Prompt shell runtime references are already bound")
        self._scrolling = scrolling
        self._sizing = sizing

    def sync_surface_scroll_metrics_from_host(self) -> None:
        """Synchronize projection scrolling through the bound scroll owner."""
        self._scrolling_owner().sync_surface_scroll_metrics_from_host()

    def schedule_shell_geometry_sync(self) -> None:
        """Schedule geometry synchronization through the bound scroll owner."""
        self._scrolling_owner().schedule_shell_geometry_sync()

    def handle_surface_content_height_changed(self, height: float) -> None:
        """Publish projection content height through the bound sizing owner."""
        self._sizing_owner().handle_surface_content_height_changed(height)

    def layout_resize_handle(self) -> None:
        """Lay out the resize handle through the bound sizing owner."""
        self._sizing_owner().layout_resize_handle()

    def schedule_manual_height_layout_reapply(self) -> None:
        """Schedule manual-height reapplication through the sizing owner."""
        self._sizing_owner().schedule_manual_height_layout_reapply()

    def observes_manual_resize_bounds_viewport(self, watched: QObject) -> bool:
        """Return whether the sizing owner observes the supplied viewport."""
        return self._sizing_owner().observes_manual_resize_bounds_viewport(watched)

    def _scrolling_owner(self) -> PromptShellScrollDelegate:
        """Return the bound scroll owner or reject premature runtime use."""
        if self._scrolling is None:
            raise RuntimeError("Prompt shell scrolling owner is not bound")
        return self._scrolling

    def _sizing_owner(self) -> PromptShellSizingController:
        """Return the bound sizing owner or reject premature runtime use."""
        if self._sizing is None:
            raise RuntimeError("Prompt shell sizing owner is not bound")
        return self._sizing


def build_prompt_editor_shell_runtime(
    mount: PromptEditorShellRuntimeMount,
    bindings: PromptEditorShellRuntimeBindings,
) -> PromptEditorShellRuntime:
    """Compose shell mechanics and configure the mounted QFluent scroll host."""

    references = _PromptEditorShellRuntimeReferences()
    paste_completion = PromptClipboardPasteCompletionOwner()
    shell = PromptEditorShell(
        host=mount.widget,
        shell_viewport=mount.shell_viewport,
    )
    chrome = PromptShellQFluentChrome(
        host=mount.chrome_host,
        shell_viewport=mount.shell_viewport,
        content_viewport=bindings.content_viewport,
        apply_host_placeholder=bindings.apply_host_placeholder,
        source_text=bindings.source_text,
        surface=bindings.chrome_surface,
        shell_padding_fill_plane=bindings.shell_padding_fill_plane,
        fill_plane=bindings.fill_plane,
        sync_surface_scroll_metrics_from_host=(
            references.sync_surface_scroll_metrics_from_host
        ),
        update_backing_fill=bindings.update_backing_fill,
        finish_pending_key_edit_block=bindings.finish_pending_key_edit_block,
        schedule_lora_metadata_catchup=bindings.schedule_lora_metadata_catchup,
        handle_focus_out=bindings.handle_focus_out,
        handle_hide=bindings.handle_hide,
        handle_move=bindings.handle_move,
        schedule_manual_height_layout_reapply=(
            references.schedule_manual_height_layout_reapply
        ),
        observes_manual_resize_bounds_viewport=(
            references.observes_manual_resize_bounds_viewport
        ),
        schedule_shell_geometry_sync=references.schedule_shell_geometry_sync,
        handle_viewport_wheel_event=bindings.handle_viewport_wheel_event,
    )
    scrolling = PromptShellScrollDelegate(
        host=mount.scroll_host,
        shell_viewport=mount.shell_viewport,
        host_scrollbar=bindings.host_scrollbar,
        surface=bindings.scroll_surface,
        shell_padding_fill_plane=bindings.shell_padding_fill_plane,
        fill_plane=bindings.fill_plane,
        token_weight_controls=bindings.token_weight_controls,
        handle_content_height_changed=(
            references.handle_surface_content_height_changed
        ),
        layout_resize_handle=references.layout_resize_handle,
        handle_viewport_scroll=bindings.handle_viewport_scroll,
        handle_resize=bindings.handle_resize,
        resized=mount.resized,
    )
    sizing = PromptShellSizingController(
        host=mount.sizing_host,
        maximum_visible_lines=mount.maximum_visible_lines,
        manual_scroll_height_changed=mount.manual_scroll_height_changed,
        surface_content_height=bindings.surface_content_height,
        projection_line_height=bindings.projection_line_height,
        surface_is_alive=bindings.surface_is_alive,
        sync_surface_scroll_metrics_from_host=(
            scrolling.sync_surface_scroll_metrics_from_host
        ),
        sync_host_scrollbar_shell=scrolling.sync_host_scrollbar_shell,
        schedule_shell_geometry_sync=scrolling.schedule_shell_geometry_sync,
        update_fill_planes=bindings.update_fill_planes,
        resize_handle=bindings.resize_handle,
        visible_scrollbar=scrolling.visible_scrollbar,
        ancestor_external_wheel_handler=bindings.ancestor_external_wheel_handler,
    )
    references.bind(scrolling=scrolling, sizing=sizing)
    scrolling.configure_host_scroll_delegate()
    return PromptEditorShellRuntime(
        shell=shell,
        chrome=chrome,
        scrolling=scrolling,
        sizing=sizing,
        paste_completion=paste_completion,
    )


__all__ = [
    "PromptEditorShellRuntime",
    "PromptEditorShellRuntimeBindings",
    "PromptEditorShellRuntimeMount",
    "build_prompt_editor_shell_runtime",
]
