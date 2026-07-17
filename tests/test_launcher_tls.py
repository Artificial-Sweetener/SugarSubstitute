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

"""Tests for launcher TLS contexts backed by operating-system trust."""

from __future__ import annotations

import ssl
from pathlib import Path

import truststore
import pytest

from sugarsubstitute_shared.tls import SystemTrustTlsContext


def test_system_trust_tls_context_preserves_peer_and_hostname_verification() -> None:
    """System trust must never weaken certificate or hostname verification."""

    context = SystemTrustTlsContext.create()

    assert isinstance(context, truststore.SSLContext)
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_explicit_ca_file_overrides_native_store_on_every_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit OpenSSL CA configuration should remain portable for operators."""

    ca_file = tmp_path / "private-ca.pem"
    ca_file.write_text("private CA placeholder", encoding="utf-8")
    recorded: list[str] = []
    expected_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def _create_default_context(*, cafile: str) -> ssl.SSLContext:
        """Record the selected explicit CA file without parsing the fixture."""

        recorded.append(cafile)
        return expected_context

    monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
    monkeypatch.setattr(
        ssl,
        "create_default_context",
        _create_default_context,
    )

    context = SystemTrustTlsContext.create()

    assert context is expected_context
    assert recorded == [str(ca_file)]
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
