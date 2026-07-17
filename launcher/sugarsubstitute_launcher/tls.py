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


class SystemTrustTlsContext:
    """Own secure launcher TLS context creation across supported platforms."""

    @staticmethod
    def create() -> ssl.SSLContext:
        """Return a hostname-verifying context backed by current system trust."""

        explicit_ca_file = os.environ.get("SSL_CERT_FILE")
        context = (
            ssl.create_default_context(cafile=explicit_ca_file)
            if explicit_ca_file is not None and Path(explicit_ca_file).is_file()
            else truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        )
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context
