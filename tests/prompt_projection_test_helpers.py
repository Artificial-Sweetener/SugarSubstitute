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

"""Provide shared Qt helpers for projection-engine prompt-editor tests."""

from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptTokenWeightControls,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintState,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptAutocompleteGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory


class StaticPromptWildcardCatalogGateway:
    """Return deterministic wildcard metadata rows for projection-engine tests."""

    def __init__(
        self,
        resolutions_by_reference: dict[
            tuple[str, str, str | None],
            PromptWildcardResolution,
        ],
    ) -> None:
        """Store deterministic wildcard rows keyed by identifier, form, and column."""

        self._resolutions_by_reference = dict(resolutions_by_reference)

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return configured wildcard rows aligned with the requested order."""

        return tuple(
            self._resolutions_by_reference.get(
                (
                    reference.identifier,
                    reference.wildcard_form,
                    reference.csv_column,
                ),
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                ),
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


def ensure_qapp() -> QApplication:
    """Return a running Qt application for prompt projection tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush several event-loop turns so prompt geometry settles deterministically."""

    for _ in range(cycles):
        app.processEvents()


def show_prompt_editor(
    widgets: list[QWidget],
    *,
    text: str,
    width: int,
    wildcard_gateway: StaticPromptWildcardCatalogGateway | None = None,
    height: int = 340,
    syntaxes: tuple[str, ...] = ("emphasis", "wildcard"),
) -> PromptEditor:
    """Create, show, and populate one prompt editor using the projection engine."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(max(240, width + 48), height)
    gateway = (
        wildcard_gateway
        if wildcard_gateway is not None
        else StaticPromptWildcardCatalogGateway({})
    )
    box = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=gateway,
        prompt_syntax_profile=prompt_syntax_profile(*syntaxes),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    box.setGeometry(20, 20, width, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText(text)
    process_events(app)
    widgets.extend([host, box])
    return box


def surface_for(box: PromptEditor) -> PromptProjectionSurface:
    """Return the live projection surface owned by one prompt editor."""

    return cast(PromptProjectionSurface, getattr(box, "_surface"))


def projection_paint_state_for(box: PromptEditor) -> PromptProjectionPaintState:
    """Return geometry-neutral visual state from the projection layout owner."""

    return surface_for(box)._layout.paint_state  # noqa: SLF001


def token_weight_controls_for(box: PromptEditor) -> PromptTokenWeightControls:
    """Return the live non-clipping token weight controls owned by one prompt editor."""

    return cast(
        PromptTokenWeightControls,
        getattr(box, "_token_weight_control_overlay"),
    )


def emphasis_controls_for(box: PromptEditor) -> PromptTokenWeightControls:
    """Return token weight controls through the legacy test helper name."""

    return token_weight_controls_for(box)
