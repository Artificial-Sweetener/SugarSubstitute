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

"""Recover a stale attached-local draft that matches saved managed state."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from substitute.domain.onboarding import (
    ComfyTargetMode,
    InstallationContext,
    SetupTransactionMode,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.onboarding.draft_recovery")

if TYPE_CHECKING:
    from substitute.application.onboarding.flow_contracts import OnboardingDraftState


class _OnboardingContextLoader(Protocol):
    """Load current persisted onboarding context."""

    def load_draft_context(self) -> InstallationContext:
        """Return the current saved or default context."""


class _BundleLike(Protocol):
    """Expose only draft recovery's onboarding service dependency."""

    @property
    def onboarding_service(self) -> _OnboardingContextLoader:
        """Return the context loader."""


def recover_stale_attached_managed_draft(
    *,
    bundle: _BundleLike,
    draft: OnboardingDraftState,
    transaction_mode: SetupTransactionMode,
) -> OnboardingDraftState:
    """Prefer matching recovered managed-local state for repair retries only."""

    if transaction_mode is not SetupTransactionMode.REPAIR:
        return draft
    if ComfyTargetMode(draft.target_mode) is not ComfyTargetMode.ATTACHED_LOCAL:
        return draft
    context = bundle.onboarding_service.load_draft_context()
    target = context.comfy_target
    if target.mode is not ComfyTargetMode.MANAGED_LOCAL:
        return draft
    if (
        target.endpoint.host != draft.endpoint_host.strip()
        or target.endpoint.port != int(draft.endpoint_port)
        or target.workspace_path != draft.attached_workspace_path
    ):
        return draft
    log_info(
        _LOGGER,
        "Recovered stale attached-local provisioning draft as managed-local.",
        workspace=target.workspace_path,
        host=target.endpoint.host,
        port=target.endpoint.port,
    )
    return replace(
        draft,
        target_mode=ComfyTargetMode.MANAGED_LOCAL.value,
        managed_workspace_path=target.workspace_path or context.managed_comfy_dir,
        attached_workspace_path=target.workspace_path,
        endpoint_host=target.endpoint.host,
        endpoint_port=target.endpoint.port,
    )


__all__ = ["recover_stale_attached_managed_draft"]
