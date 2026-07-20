#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Own semantic presentation copy for CivitAI credential status."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, app_text
from substitute.application.ports.civitai_credential_store import (
    CredentialStoreStatus,
)


def api_key_status_text(
    *,
    status: CredentialStoreStatus,
    has_key: bool,
) -> ApplicationMessage:
    """Return live-localizable API key and secure-storage status copy."""

    if status.available:
        return app_text("Configured") if has_key else app_text("No API key configured")
    lead = app_text("Secure credential storage is unavailable.")
    if status.reason is not None and status.remediation is not None:
        return app_text("%1 %2 %3", lead, status.reason, status.remediation)
    if status.reason is not None:
        return app_text("%1 %2", lead, status.reason)
    if status.remediation is not None:
        return app_text("%1 %2", lead, status.remediation)
    return lead


__all__ = ["api_key_status_text"]
