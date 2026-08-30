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

"""Verify LoRA hover and host-owned context actions."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
    ModelMetadataMenuAction,
    ModelMetadataMenuItem,
)
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_surface_support import (
    PositionEvent,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
)


class _MetadataActionHandler:
    """Record prompt-editor LoRA metadata action targets."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one metadata refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing surface tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing surface tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing surface tests."""

        _ = (target, image_id)


def _metadata_menu_actions(
    items: tuple[ModelMetadataMenuItem, ...],
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return action items from one metadata menu item tuple."""

    return tuple(item for item in items if isinstance(item, ModelMetadataMenuAction))


def test_projection_surface_requests_lora_context_menu_for_token_with_url(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA right-clicks should request a host-owned context menu."""

    ensure_qapp()
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=model_page_url,
    )
    emitted: list[tuple[object, QPoint]] = []
    surface.loraContextMenuRequested.connect(
        lambda emitted_token, global_pos: emitted.append((emitted_token, global_pos))
    )
    cast(Any, surface).token_at_viewport_position = lambda _pos: token

    handled = surface._request_lora_context_menu(  # noqa: SLF001
        QPointF(4.0, 6.0),
        QPoint(40, 60),
    )

    assert handled is True
    assert emitted == [(token, QPoint(40, 60))]


def test_projection_surface_lora_context_menu_requires_url(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA context requests should be skipped when no page URL exists."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=None,
    )
    emitted: list[tuple[object, QPoint]] = []
    surface.loraContextMenuRequested.connect(
        lambda emitted_token, global_pos: emitted.append((emitted_token, global_pos))
    )
    cast(Any, surface).token_at_viewport_position = lambda _pos: token

    handled = surface._request_lora_context_menu(  # noqa: SLF001
        QPointF(4.0, 6.0),
        QPoint(40, 60),
    )

    assert handled is False
    assert emitted == []


def test_projection_surface_lora_tooltip_uses_full_page_and_version_text(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA hover tooltips should expose unelided page and version labels."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Extremely Long CivitAI Collection Page Name",
        lora_version_text="Overly Detailed Version Name",
    )
    cast(Any, surface).token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip == (
        "Model: Extremely Long CivitAI Collection Page Name\n"
        "Version: Overly Detailed Version Name"
    )


def test_projection_surface_lora_tooltip_reports_missing_lora(
    widgets: list[QWidget],
) -> None:
    """Inline LoRA hover tooltips should report missing catalog entries."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=28,
        display_text="Missing",
        detail_text=r"Unknown\Missing",
        exists=False,
    )
    cast(Any, surface).token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip == r"LoRA not found: Unknown\Missing"


def test_projection_surface_lora_tooltip_ignores_non_lora_tokens(
    widgets: list[QWidget],
) -> None:
    """LoRA label tooltips should not appear for other projected token kinds."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    token = PromptProjectionToken(
        token_id="emphasis:0",
        kind=PromptProjectionTokenKind.EMPHASIS,
        source_start=0,
        source_end=8,
        display_text="cat",
    )
    cast(Any, surface).token_at_viewport_position = lambda _pos: token

    tooltip = surface._lora_tooltip_for_hover_event(  # noqa: SLF001
        surface.viewport(),
        PositionEvent(QPointF(4.0, 6.0)),
    )

    assert tooltip is None


def test_prompt_editor_lora_civitai_action_opens_token_url(
    widgets: list[QWidget],
) -> None:
    """The host-owned inline LoRA action should open the token's CivitAI URL."""

    ensure_qapp()
    opened_urls: list[str] = []
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    editor = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_syntax_profile=prompt_syntax_profile("lora"),
        open_url=open_url,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    widgets.append(editor)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        model_page_url=model_page_url,
    )

    presenter = cast(Any, editor)._inline_lora_menu_presenter
    action = presenter.page_action_for_token_context(presenter.token_context(token))

    assert action is not None
    assert action.label == "Go to CivitAI page"
    action.callback()
    assert opened_urls == [model_page_url]


def test_prompt_editor_lora_banner_menu_includes_refresh_action(
    widgets: list[QWidget],
) -> None:
    """The real prompt editor should inject refresh handling into LoRA banners."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    model_page_url = "https://civitai.com/models/100?modelVersionId=200"
    editor = PromptEditor(
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_syntax_profile=prompt_syntax_profile("lora"),
        model_metadata_action_handler=handler,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    widgets.append(editor)
    token = PromptProjectionToken(
        token_id="lora:0",
        kind=PromptProjectionTokenKind.LORA,
        source_start=0,
        source_end=37,
        display_text="Mineru",
        detail_text="mineru",
        lora_backend_value="loras/mineru.safetensors",
        model_page_url=model_page_url,
    )

    presenter = cast(Any, editor)._inline_lora_menu_presenter
    menu_items = presenter.metadata_actions_for_token_context(
        presenter.token_context(token)
    )
    actions = _metadata_menu_actions(menu_items)

    assert [action.label for action in actions] == [
        "Go to CivitAI page",
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[1].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "loras"
    assert getattr(refresh_target, "backend_value") == "loras/mineru.safetensors"
