#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Rebind rendered node-card text without rebuilding editable controls."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.localization import NodePresentationService
from substitute.domain.localization import NodePresentationRequest
from substitute.presentation.editor.panel.widgets.field_row import FieldRowTextTarget
from substitute.presentation.qt_label_text import literal_label_text
from substitute.presentation.widgets.tooltips import bind_fluent_tooltip


@dataclass(frozen=True, slots=True)
class NodeTitleTextTarget:
    """Identify title widgets whose locale-owned properties change together."""

    owner: QWidget
    label: CaptionLabel
    tooltip_targets: tuple[QWidget, ...]


class NodeCardPresentationBinding(QObject):
    """Apply one immutable card request against the current catalog generation."""

    def __init__(
        self,
        *,
        owner: QWidget,
        service: NodePresentationService,
        request: NodePresentationRequest,
    ) -> None:
        """Observe language changes while retaining only this card's widget targets."""

        super().__init__(owner)
        self._owner = owner
        self._service = service
        self._request = request
        self._title_target: NodeTitleTextTarget | None = None
        self._field_targets: dict[str, FieldRowTextTarget] = {}
        owner.installEventFilter(self)

    def set_title_target(self, target: NodeTitleTextTarget) -> None:
        """Register the card header target built after its body rows."""

        self._title_target = target

    def add_field_targets(self, targets: tuple[FieldRowTextTarget, ...]) -> None:
        """Register stable field targets emitted by the row-composition owner."""

        for target in targets:
            self._field_targets[target.field_key] = target

    def retranslate(self) -> None:
        """Apply one fresh presentation snapshot without replacing input widgets."""

        presentation = self._service.present(self._request)
        self._owner.setProperty("node_title_source", presentation.title_source.value)
        self._owner.setProperty(
            "node_search_aliases", list(presentation.search_aliases)
        )
        title_target = self._title_target
        if title_target is not None:
            title_target.label.setText(literal_label_text(presentation.title))
            title_target.owner.setAccessibleName(presentation.title)
            title_target.owner.setAccessibleDescription(presentation.card_tooltip or "")
            bind_fluent_tooltip(
                title_target.owner,
                presentation.card_tooltip,
                *title_target.tooltip_targets,
                show_delay_ms=600,
            )
        for field_key, target in self._field_targets.items():
            field = presentation.fields.get(field_key)
            if field is None:
                continue
            if target.label is not None:
                target.label.setText(literal_label_text(field.label))
            target.field_widget.setAccessibleName(field.label)
            target.field_widget.setAccessibleDescription(field.tooltip or "")
            bind_fluent_tooltip(
                target.tooltip_owner,
                field.tooltip,
                *target.tooltip_targets,
                show_delay_ms=600,
            )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Refresh this card when Qt propagates a committed language change."""

        if watched is self._owner and event.type() == QEvent.Type.LanguageChange:
            self.retranslate()
        return False


__all__ = ["NodeCardPresentationBinding", "NodeTitleTextTarget"]
