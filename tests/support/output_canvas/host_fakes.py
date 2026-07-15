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

"""Build typed lightweight Output canvas host collaborators."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.composition.assets import (
    output_canvas_asset_lookup,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
)

from .models import session_for_projection


class SignalStub:
    """Small signal double used by widget method tests."""

    def __init__(self) -> None:
        """Create an empty signal with call recording."""

        self._slots: list[Callable[..., None]] = []
        self.calls: list[tuple[object, ...]] = []

    def connect(self, slot: Callable[..., None]) -> None:
        """Connect a callable slot."""

        self._slots.append(slot)

    def disconnect(self, slot: Callable[..., None]) -> None:
        """Disconnect a previously connected slot."""

        if slot not in self._slots:
            raise RuntimeError("slot not connected")
        self._slots.remove(slot)

    def emit(self, *args: object) -> None:
        """Record emitted arguments and notify connected slots."""

        self.calls.append(args)
        for slot in list(self._slots):
            slot(*args)


def bind_fake_output_projection(
    output_mod: Any,
    fake: Any,
    projection: Any,
    *,
    payloads: dict[UUID, object] | None = None,
) -> None:
    """Bind projection and registry-style lookups to a lightweight Output fake."""

    fake._output_projection = projection
    fake._output_session = session_for_projection(projection)
    fake._projection_workflow_id = fake._output_session.workflow_id
    payload_lookup = payloads or {}
    metadata = {
        item.image_id: item.image_meta
        for source in projection.sources
        for item in source.images_by_set.values()
    }
    fake._final_output_payload = lambda image_id: payload_lookup.get(image_id)
    fake._final_output_metadata = lambda image_id: metadata.get(image_id)
    install_fake_output_asset_lookup(output_mod, fake)
    from .projection_fakes import install_fake_output_compare_presenter  # noqa: PLC0415
    from .route_fakes import install_fake_output_qpane_presenter  # noqa: PLC0415

    install_fake_output_compare_presenter(fake)
    install_fake_output_qpane_presenter(fake)


def bind_fake_output_sources(
    output_mod: Any,
    fake: Any,
    sources: Any,
    *,
    active_source_key: str | None = None,
    active_set_index: int = 1,
    set_count: int = 0,
) -> None:
    """Bind source-group projection state to a lightweight Output fake."""

    projection = output_mod.OutputCanvasProjection(
        sources=tuple(sources),
        active_source_key=active_source_key,
        active_set_index=active_set_index,
        active_uuid=None,
        set_count=set_count,
    )
    bind_fake_output_projection(output_mod, fake, projection)


def install_navigation_widget_methods(widget: object, *, width: int) -> None:
    """Install Qt-like geometry methods on simple namespace widget doubles."""

    if not hasattr(widget, "hide"):
        setattr(widget, "hide", lambda: None)
    if not hasattr(widget, "show"):
        setattr(widget, "show", lambda: None)
    if not hasattr(widget, "setVisible"):
        setattr(widget, "setVisible", lambda _visible: None)
    if not hasattr(widget, "width"):
        setattr(widget, "width", lambda: width)
    if not hasattr(widget, "height"):
        setattr(widget, "height", lambda: 28)
    if not hasattr(widget, "sizeHint"):
        setattr(
            widget,
            "sizeHint",
            lambda: SimpleNamespace(width=lambda: width, height=lambda: 28),
        )
    if not hasattr(widget, "setGeometry"):
        setattr(widget, "setGeometry", lambda *_args: None)
    if not hasattr(widget, "raise_"):
        setattr(widget, "raise_", lambda: None)
    if not hasattr(widget, "lower"):
        setattr(widget, "lower", lambda: None)


class NavigationChromeWidget:
    """Small Qt-like widget double for lightweight Output chrome tests."""

    def __init__(self, *, width: int = 34) -> None:
        """Store a deterministic width for size and geometry reads."""

        self._width = width
        install_navigation_widget_methods(self, width=width)


def install_fake_navigation_chrome(fake: Any) -> None:
    """Install navigation chrome collaborators for lightweight Output hosts."""

    tabbar = getattr(fake, "tabbar", None)
    if tabbar is not None:
        install_navigation_widget_methods(tabbar, width=120)
    if not hasattr(fake, "set_selector_button"):
        fake.set_selector_button = NavigationChromeWidget(width=34)
    else:
        install_navigation_widget_methods(fake.set_selector_button, width=34)
    if hasattr(fake, "source_selector_button"):
        install_navigation_widget_methods(fake.source_selector_button, width=72)
    if hasattr(fake, "scene_selector_button"):
        install_navigation_widget_methods(fake.scene_selector_button, width=72)
    if not hasattr(fake, "tabbar_container"):
        fake.tabbar_container = NavigationChromeWidget()
    if not hasattr(fake, "tabbar_bg"):
        fake.tabbar_bg = NavigationChromeWidget()
    if not hasattr(fake, "height"):
        fake.height = lambda: 400
    if not hasattr(fake, "width"):
        fake.width = lambda: 640
    if not hasattr(fake, "_navigation_controller") and tabbar is not None:
        fake._navigation_controller = OutputCanvasNavigationController(
            canvas_width=lambda: int(fake.width()),
            tabbar=lambda: fake.tabbar,
            cached_source_tabbar_width=lambda: int(
                getattr(fake, "_source_tabbar_preferred_width", 0) or 0
            ),
            set_cached_source_tabbar_width=lambda width: setattr(
                fake,
                "_source_tabbar_preferred_width",
                width,
            ),
        )


def install_fake_output_projection_chrome(fake: Any) -> None:
    """Install no-op projection chrome callbacks for lightweight Output hosts."""

    if not hasattr(fake, "_sync_scene_selector_button"):
        fake._sync_scene_selector_button = lambda: None
    if not hasattr(fake, "_sync_set_selector_button"):
        fake._sync_set_selector_button = lambda: None
    if not hasattr(fake, "_sync_source_selector_button"):
        fake._sync_source_selector_button = lambda: None
    if not hasattr(fake, "_update_tabbar_container"):
        fake._update_tabbar_container = lambda: None
    install_fake_navigation_chrome(fake)


def install_fake_output_asset_lookup(output_mod: Any, fake: Any) -> None:
    """Install the composed Output asset lookup expected by widget seams."""

    fake._asset_lookup = output_canvas_asset_lookup(
        payload_lookup=getattr(fake, "_final_output_payload", None),
        metadata_lookup=getattr(fake, "_final_output_metadata", None),
        preview_image_cache=lambda: output_preview_registry(fake).images_by_id(),
    )
    from .preview_fakes import install_fake_output_preview_controller  # noqa: PLC0415
    from .projection_fakes import (  # noqa: PLC0415
        install_fake_output_source_tabs_controller,
    )
    from .route_fakes import (  # noqa: PLC0415
        install_fake_output_qpane_presenter,
        install_fake_output_route_composers,
        install_fake_output_route_presenter,
    )

    install_fake_output_qpane_presenter(fake)
    install_fake_output_preview_controller(output_mod, fake)
    install_fake_output_route_presenter(output_mod, fake)
    install_fake_output_route_composers(output_mod, fake)
    if hasattr(fake, "tabbar"):
        install_fake_output_source_tabs_controller(output_mod, fake)


__all__ = [
    "NavigationChromeWidget",
    "SignalStub",
    "bind_fake_output_projection",
    "bind_fake_output_sources",
    "install_fake_navigation_chrome",
    "install_fake_output_asset_lookup",
    "install_fake_output_projection_chrome",
    "install_navigation_widget_methods",
]
