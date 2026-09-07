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

"""Persist recoverable setup failure state without masking its cause."""

from __future__ import annotations

from typing import Protocol

from substitute.domain.onboarding import SetupTransaction, SetupTransactionFailure
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.onboarding.transaction_failure_recorder")


class SetupFailureTransactionService(Protocol):
    """Record one failure on an active setup transaction."""

    def record_failure(
        self,
        transaction_id: str,
        failure: SetupTransactionFailure,
    ) -> SetupTransaction:
        """Persist recoverable failure details."""


def record_setup_transaction_failure(
    *,
    service: SetupFailureTransactionService,
    transaction_id: str,
    error: Exception,
) -> None:
    """Persist failure detail while preserving the original exception."""

    try:
        detail = str(error).strip() or type(error).__name__
        service.record_failure(
            transaction_id,
            SetupTransactionFailure(
                code=type(error).__name__,
                message=detail,
                recoverable=True,
                diagnostic_detail=detail,
            ),
        )
    except Exception as transaction_error:
        log_warning(
            _LOGGER,
            "Failed to record onboarding transaction failure.",
            transaction_id=transaction_id,
            error=transaction_error,
        )


__all__ = ["SetupFailureTransactionService", "record_setup_transaction_failure"]
