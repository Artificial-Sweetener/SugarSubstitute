"""Resolve captured Output content before atomically publishing clipboard MIME data."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count

from PySide6.QtCore import QMimeData
from cutecanvas import CanvasContentReference

from substitute.application.execution import (
    ExecutionContext,
    ExecutionLaneSaturatedError,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.presentation.canvas.output.output_transfer_payloads import (
    mime_data_for_transfer,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
    ResolvedOutputTransfer,
)
from sugarsubstitute_shared.localization.application_message import opaque_text


class OutputTransferClipboardController:
    """Own asynchronous, latest-request-wins clipboard publication for Output."""

    def __init__(
        self,
        *,
        resolver: OutputTransferResolver,
        submitter: TaskSubmitter,
        publish_mime_data: Callable[[QMimeData], None],
        report_failure: Callable[[str], None],
    ) -> None:
        """Bind one shared resolver to clipboard publication on its owner thread."""

        self._resolver = resolver
        self._publish_mime_data = publish_mime_data
        self._report_failure = report_failure
        self._request_ids = count(1)
        self._active_request_id = 0
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"output_transfer_clipboard_{id(self):x}",
        )
        self._clipboard_transfer: ResolvedOutputTransfer | None = None

    def copy(self, reference: CanvasContentReference) -> None:
        """Resolve one captured subject without changing Output activation or route state."""

        request_id = next(self._request_ids)
        self._active_request_id = request_id
        self._scope.cancel_all(reason="output_transfer_clipboard_superseded")
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="output_transfer_clipboard",
                parts=(("target_id", str(reference.composition_id)),),
            ),
            context=ExecutionContext(
                operation="output_transfer_clipboard",
                reason="content_context_copy",
                lane="image_decode",
                safe_fields=(("target_id", str(reference.composition_id)),),
            ),
            work=lambda token: self._resolver.resolve(
                reference,
                cancellation_requested=lambda: token.is_cancelled,
            ),
        )
        try:
            handle = self._scope.submit(request)
        except ExecutionLaneSaturatedError as error:
            self._report_failure(str(error))
            return
        handle.add_done_callback(
            lambda outcome: self._publish_outcome(request_id, outcome),
            reason="output_transfer_clipboard_completed",
        )

    def close(self) -> None:
        """Cancel pending clipboard work before the Output surface retires."""

        self._active_request_id = 0
        self._scope.close(reason="output_transfer_clipboard_controller_closed")
        self._release_clipboard_transfer()

    def _publish_outcome(
        self,
        request_id: int,
        outcome: TaskOutcome[ResolvedOutputTransfer | None],
    ) -> None:
        """Publish only the latest successful captured transfer representation."""

        if request_id != self._active_request_id or outcome.status == "cancelled":
            return
        if outcome.status == "failed":
            self._report_failure(_failure_message(outcome.error))
            return
        resolved = outcome.result
        if resolved is None:
            self._report_failure(opaque_text("Output image is no longer available."))
            return
        self._publish_mime_data(mime_data_for_transfer(resolved))
        self._release_clipboard_transfer()
        self._clipboard_transfer = resolved

    def _release_clipboard_transfer(self) -> None:
        """Release the staged file superseded by a later clipboard publication."""

        previous = self._clipboard_transfer
        self._clipboard_transfer = None
        if previous is not None:
            previous.artifact.release()


def _failure_message(error: BaseException | None) -> str:
    """Return a concise transfer failure message without exposing implementation detail."""

    if error is None:
        return opaque_text("Unable to copy the selected output image.")
    return str(error) or opaque_text("Unable to copy the selected output image.")


__all__ = ["OutputTransferClipboardController"]
