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

"""Create verified TLS contexts backed by the operating system trust store."""

from __future__ import annotations

import os
from pathlib import Path
import ssl

import truststore


EXTRA_CA_FILE_ENV = "SUGARSUBSTITUTE_EXTRA_CA_FILE"


class SystemTrustTlsContext:
    """Own secure TLS context creation across supported application layers."""

    @staticmethod
    def create() -> ssl.SSLContext:
        """Return a hostname-verifying context backed by current system trust."""

        extra_ca_file = os.environ.get(EXTRA_CA_FILE_ENV)
        explicit_ca_file = os.environ.get("SSL_CERT_FILE")
        context: ssl.SSLContext
        if extra_ca_file is not None and Path(extra_ca_file).is_file():
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(cafile=extra_ca_file)
        elif explicit_ca_file is not None and Path(explicit_ca_file).is_file():
            context = ssl.create_default_context(cafile=explicit_ca_file)
        else:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context


__all__ = ["EXTRA_CA_FILE_ENV", "SystemTrustTlsContext"]
