"""Materialize captured Output drag subjects through the shared execution boundary."""

from __future__ import annotations

from itertools import count

from cutecanvas import CanvasContentReference, DragSubject, OutboundMimeProvider

from substitute.application.execution import (
    ExecutionContext,
    ExecutionLaneSaturatedError,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.presentation.canvas.output.output_transfer_payloads import (
    drag_payload_for_transfer,
)
from substitute.presentation.canvas.output.output_transfer_resolver import (
    OutputTransferResolver,
    ResolvedOutputTransfer,
)


class OutputTransferDragProvider(OutboundMimeProvider):
    """Adapt authorized Output transfer resolution to CuteCanvas's drag API."""

    def __init__(
        self, *, resolver: OutputTransferResolver, submitter: TaskSubmitter
    ) -> None:
        """Bind one resolver to the app-owned image execution lane."""

        self._resolver = resolver
        self._request_ids = count(1)
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"output_transfer_drag_{id(self):x}",
        )
        self._active_transfer: ResolvedOutputTransfer | None = None

    def materialize(self, subject: DragSubject, complete):  # type: ignore[no-untyped-def]
        """Resolve one captured reference off-thread and return a cancellable handle."""

        reference = subject.subject_id
        if not isinstance(reference, CanvasContentReference):
            complete(None, ValueError("Output drag did not identify document content."))
            return None
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._request_ids),
                domain="output_transfer_drag",
                parts=(("target_id", str(reference.composition_id)),),
            ),
            context=ExecutionContext(
                operation="output_transfer_drag",
                reason="outbound_drag",
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
            complete(None, error)
            return None
        handle.add_done_callback(
            lambda outcome: self._publish_outcome(outcome, complete),
            reason="output_transfer_drag_completed",
        )
        return _DragTaskCancellation(handle)

    def close(self) -> None:
        """Cancel all pending materialization when the Output surface retires."""

        self._scope.close(reason="output_transfer_drag_provider_closed")
        self._release_active_transfer()

    def _publish_outcome(
        self, outcome: TaskOutcome[ResolvedOutputTransfer | None], complete: object
    ) -> None:
        """Publish only a successful, current resolved transfer to CuteCanvas."""

        if not callable(complete) or outcome.status == "cancelled":
            return
        if outcome.status == "failed":
            complete(None, outcome.error)
            return
        resolved = outcome.result
        if resolved is None:
            complete(None, RuntimeError("Output image is no longer available."))
            return
        self._release_active_transfer()
        self._active_transfer = resolved
        complete(drag_payload_for_transfer(resolved), None)

    def _release_active_transfer(self) -> None:
        """Release the prior staged drag artifact after its native drag has completed."""

        active = self._active_transfer
        self._active_transfer = None
        if active is not None:
            active.artifact.release()


class _DragTaskCancellation:
    """Expose one application task handle through CuteCanvas cancellation."""

    def __init__(self, handle: TaskHandle[ResolvedOutputTransfer | None]) -> None:
        """Store the task handle owned by this one native drag generation."""

        self._handle = handle

    def cancel(self) -> None:
        """Cancel materialization without affecting other Output transfers."""

        self._handle.cancel(reason="outbound_drag_superseded")


__all__ = ["OutputTransferDragProvider"]
