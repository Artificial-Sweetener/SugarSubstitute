"""Publish fully materialized Output transfer MIME data on the Qt clipboard."""

from __future__ import annotations

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication


def publish_output_transfer_mime_data(mime_data: QMimeData) -> None:
    """Atomically replace clipboard MIME data on the GUI owner thread."""

    QApplication.clipboard().setMimeData(mime_data)


__all__ = ["publish_output_transfer_mime_data"]
