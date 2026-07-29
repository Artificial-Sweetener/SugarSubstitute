"""Compose the Output transfer adapter and its application-owned lifetime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QMimeData
from substitute.application.execution import TaskSubmitter
from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifactStore,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_drag_provider import (
    OutputTransferDragProvider,
)
from substitute.presentation.canvas.output.output_transfer_clipboard_controller import (
    OutputTransferClipboardController,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
)


@dataclass(slots=True)
class OutputTransferLifecycle:
    """Own one outbound provider, staged artifacts, and runtime dispatcher route."""

    resolver: OutputTransferResolver
    drag_provider: OutputTransferDragProvider
    clipboard_controller: OutputTransferClipboardController
    artifact_store: OutputTransferArtifactStore
    close_drag_submitter: Callable[[], None]
    close_clipboard_submitter: Callable[[], None]
    _is_closed: bool = False

    def close(self) -> None:
        """Cancel transfers and release their dispatcher route and staged files."""

        if self._is_closed:
            return
        self._is_closed = True
        self.clipboard_controller.close()
        self.drag_provider.close()
        self.close_clipboard_submitter()
        self.close_drag_submitter()
        self.artifact_store.close()


def compose_output_transfer_lifecycle(
    *,
    document: OutputCanvasDocument,
    is_image_authorized: Callable[[UUID], bool],
    preference_service: OutputPreferenceService,
    drag_submitter: TaskSubmitter,
    close_drag_submitter: Callable[[], None],
    clipboard_submitter: TaskSubmitter,
    close_clipboard_submitter: Callable[[], None],
    publish_clipboard_mime_data: Callable[[QMimeData], None],
    report_clipboard_failure: Callable[[str], None],
    staging_directory: Path,
) -> OutputTransferLifecycle:
    """Create the shared resolver and its bounded native-drag lifetime."""

    artifact_store = OutputTransferArtifactStore(staging_directory)
    resolver = OutputTransferResolver(
        document=document,
        preference_service=preference_service,
        artifact_store=artifact_store,
        is_image_authorized=is_image_authorized,
    )
    return OutputTransferLifecycle(
        resolver=resolver,
        drag_provider=OutputTransferDragProvider(
            resolver=resolver,
            submitter=drag_submitter,
        ),
        clipboard_controller=OutputTransferClipboardController(
            resolver=resolver,
            submitter=clipboard_submitter,
            publish_mime_data=publish_clipboard_mime_data,
            report_failure=report_clipboard_failure,
        ),
        artifact_store=artifact_store,
        close_drag_submitter=close_drag_submitter,
        close_clipboard_submitter=close_clipboard_submitter,
    )


__all__ = ["OutputTransferLifecycle", "compose_output_transfer_lifecycle"]
