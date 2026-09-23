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

"""Share per-model update availability with picker controls on the Qt thread."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal

from sugarsubstitute_shared.model_updates import ModelUpdateProposal


class ModelUpdatePickerBridge(QObject):
    """Publish checked versions and route explicit family-opening requests."""

    changed = Signal()
    familyRequested = Signal(str)
    dismissRequested = Signal(str)
    pageOptOutRequested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Start without any update badges or pending requests."""

        super().__init__(parent)
        self._proposals_by_sha: dict[str, ModelUpdateProposal] = {}

    def replace(self, proposals: Sequence[ModelUpdateProposal]) -> None:
        """Replace the exact available-update projection after a checked refresh."""

        updated = {
            proposal.current.sha256.casefold(): proposal for proposal in proposals
        }
        if updated == self._proposals_by_sha:
            return
        self._proposals_by_sha = updated
        self.changed.emit()

    def proposal_for_sha(self, sha256: str | None) -> ModelUpdateProposal | None:
        """Return one installed model's matching update without a provider call."""

        if not sha256:
            return None
        return self._proposals_by_sha.get(sha256.casefold())

    def request_family(self, sha256: str | None) -> bool:
        """Request history only for an available, exact installed identity."""

        proposal = self.proposal_for_sha(sha256)
        if proposal is None:
            return False
        self.familyRequested.emit(proposal.current.sha256.casefold())
        return True

    def request_dismissal(self, sha256: str | None) -> bool:
        """Dismiss only a checked update for this exact local model."""

        proposal = self.proposal_for_sha(sha256)
        if proposal is None:
            return False
        self.dismissRequested.emit(proposal.current.sha256.casefold())
        return True

    def request_page_opt_out(self, sha256: str | None) -> bool:
        """Disable checks for the provider page of this exact visible icon."""

        proposal = self.proposal_for_sha(sha256)
        if proposal is None:
            return False
        self.pageOptOutRequested.emit(proposal.current.sha256.casefold())
        return True

    def remove(self, sha256: str) -> None:
        """Clear one resolved update badge without disturbing other models."""

        normalized = sha256.casefold()
        if normalized not in self._proposals_by_sha:
            return
        self._proposals_by_sha.pop(normalized)
        self.changed.emit()

    def remove_page(self, model_id: int) -> None:
        """Clear every badge that belongs to one opted-out provider page."""

        remaining = {
            sha256: proposal
            for sha256, proposal in self._proposals_by_sha.items()
            if proposal.current.model_id != model_id
        }
        if remaining == self._proposals_by_sha:
            return
        self._proposals_by_sha = remaining
        self.changed.emit()


__all__ = ["ModelUpdatePickerBridge"]
