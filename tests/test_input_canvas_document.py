#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Characterize the SugarSubstitute Input CuteCanvas document boundary."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from substitute.application.workflows.input_canvas_document_port import (
    CanvasDocumentMutation,
)
from substitute.presentation.canvas.input.input_document import InputCanvasDocument


def _image(color: QColor) -> QImage:
    """Create one non-null source image for document admission tests."""

    image = QImage(24, 16, QImage.Format.Format_ARGB32)
    image.fill(color)
    return image


def _app() -> QApplication:
    """Return a QApplication before constructing one CuteCanvas widget."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_input_document_keeps_application_and_composition_identity_separate() -> None:
    """Input routes should resolve app UUIDs through a durable composition registry."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    first_image_id = uuid4()
    second_image_id = uuid4()
    first = _image(QColor("red"))
    second = _image(QColor("blue"))

    assert (
        document.ensure_image_cached(first_image_id, first, None)
        is CanvasDocumentMutation.ADDED
    )
    assert (
        document.ensure_image_cached(second_image_id, second, None)
        is CanvasDocumentMutation.ADDED
    )
    assert document.current_image_id() is None
    assert document.set_current_image_id(first_image_id) is True
    assert document.current_image_id() == first_image_id
    assert set(document.canvas.compositionIDs())
    assert first_image_id not in document.canvas.compositionIDs()


def test_input_document_exports_inactive_mask_without_route_mutation() -> None:
    """Generation preflight can read a dirty inactive mask without changing Input focus."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    first_image_id = uuid4()
    second_image_id = uuid4()
    assert (
        document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
        is CanvasDocumentMutation.ADDED
    )
    first_mask_id = document.create_blank_mask(first_image_id, QSize(24, 16))
    assert first_mask_id is not None
    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.ADDED
    )
    assert document.set_current_image_id(second_image_id) is True

    exported = document.export_mask_image(first_mask_id)

    assert exported is not None
    assert exported.size() == QSize(24, 16)
    assert document.current_image_id() == second_image_id


def test_input_document_admission_never_steals_an_existing_route() -> None:
    """Background admission and replacement must leave the active image unchanged."""

    app = _app()
    document = InputCanvasDocument(features=("mask",))
    first_image_id = uuid4()
    second_image_id = uuid4()
    document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
    assert document.set_current_image_id(first_image_id)
    active_composition_id = document.canvas.currentCompositionID()

    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.ADDED
    )
    assert (
        document.ensure_image_cached(second_image_id, _image(QColor("green")), None)
        is CanvasDocumentMutation.REPLACED
    )
    app.processEvents()

    assert document.current_image_id() == first_image_id
    assert document.canvas.currentCompositionID() == active_composition_id


def test_input_document_replacement_preserves_active_masks_and_view() -> None:
    """Regeneration must not replace an active image's composition-owned state."""

    app = _app()
    document = InputCanvasDocument(features=("mask",))
    image_id = uuid4()
    source = _image(QColor("red"))
    document.ensure_image_cached(image_id, source, None)
    assert document.set_current_image_id(image_id)
    mask_id = document.create_blank_mask(image_id, QSize(24, 16))
    assert mask_id is not None
    document.canvas.resize(640, 420)
    document.canvas.show()
    app.processEvents()
    document.canvas.applyZoom(document.canvas.currentZoom() * 1.8)
    zoom = document.canvas.currentZoom()
    viewport = document.canvas.currentViewportRect()
    composition_id = document.canvas.currentCompositionID()

    assert (
        document.ensure_image_cached(image_id, _image(QColor("blue")), None)
        is CanvasDocumentMutation.REPLACED
    )
    app.processEvents()

    assert document.canvas.currentCompositionID() == composition_id
    assert document.current_image_id() == image_id
    assert document.canvas.currentZoom() == zoom
    assert document.canvas.currentViewportRect() == viewport
    assert tuple(
        mask.mask_id for mask in document.canvas.listMasksForComposition(composition_id)
    ) == (mask_id,)


def test_input_document_retires_only_the_requested_unreferenced_composition() -> None:
    """Application reference accounting should control document composition lifetime."""

    _app()
    document = InputCanvasDocument(features=("mask",))
    first_image_id = uuid4()
    second_image_id = uuid4()
    document.ensure_image_cached(first_image_id, _image(QColor("red")), None)
    document.ensure_image_cached(second_image_id, _image(QColor("blue")), None)

    assert document.remove_unreferenced_image(first_image_id) is True
    assert document.contains(first_image_id) is False
    assert document.contains(second_image_id) is True
    assert document.set_current_image_id(first_image_id) is False
    assert document.set_current_image_id(second_image_id) is True
