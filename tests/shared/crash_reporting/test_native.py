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

"""Verify strict initialization of the native Crashpad client bridge."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import cast

import pytest

from sugarsubstitute_shared.crash_reporting.native import (
    CrashpadInitializationError,
    CrashpadNativeClient,
)
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext


class _StartFunction:
    """Record calls made through the exported native ABI."""

    def __init__(self, *, result: int = 1) -> None:
        """Store the native result and mutable ctypes declarations."""

        self.result = result
        self.argtypes: list[object] = []
        self.restype: object = None
        self.calls: list[tuple[bytes, ...]] = []

    def __call__(self, *arguments: bytes) -> int:
        """Record one native initialization call."""

        self.calls.append(arguments)
        return self.result


class _Library:
    """Expose the bridge symbol expected by the runtime adapter."""

    def __init__(self, start: _StartFunction) -> None:
        """Publish one configurable start function."""

        self.SugarSubstituteCrashpadStart = start


def test_native_client_starts_handler_with_private_database_and_attachment(
    tmp_path: Path,
) -> None:
    """The bridge should receive every path from the authenticated run."""

    handler = tmp_path / "crashpad_handler.exe"
    library_path = tmp_path / "sugarsubstitute_crashpad_client.dll"
    handler.touch()
    library_path.touch()
    context = CrashRunContext.create(
        tmp_path / "diagnostics",
        crashpad_handler=handler,
        crashpad_client_library=library_path,
    )
    attachment = context.incident_root / context.run_id / "python-fault.log"
    start = _StartFunction()
    library = _Library(start)

    CrashpadNativeClient(library_loader=lambda _path: cast(ctypes.CDLL, library)).start(
        context=context,
        application_version="0.22.0",
        attachment_path=attachment,
    )

    assert len(start.calls) == 1
    assert start.calls[0] == (
        str(handler).encode(),
        str(context.crashpad_database).encode(),
        str(context.crashpad_database / "metrics").encode(),
        str(attachment).encode(),
        b"0.22.0",
        context.run_id.encode(),
    )
    assert context.crashpad_database.is_dir()
    assert (context.crashpad_database / "metrics").is_dir()
    assert start.argtypes == [ctypes.c_char_p] * 6
    assert start.restype is ctypes.c_int


def test_native_client_fails_closed_when_packaged_runtime_is_missing(
    tmp_path: Path,
) -> None:
    """A supervised app must not continue without its native crash boundary."""

    context = CrashRunContext.create(
        tmp_path / "diagnostics",
        crashpad_handler=tmp_path / "missing-handler",
        crashpad_client_library=tmp_path / "missing-client",
    )

    with pytest.raises(CrashpadInitializationError, match="incomplete"):
        CrashpadNativeClient().start(
            context=context,
            application_version="0.22.0",
            attachment_path=tmp_path / "fault.log",
        )


def test_native_client_fails_closed_when_crashpad_rejects_registration(
    tmp_path: Path,
) -> None:
    """A false native result must abort startup instead of silently logging."""

    handler = tmp_path / "handler"
    library_path = tmp_path / "client"
    handler.touch()
    library_path.touch()
    context = CrashRunContext.create(
        tmp_path / "diagnostics",
        crashpad_handler=handler,
        crashpad_client_library=library_path,
    )
    library = _Library(_StartFunction(result=0))

    with pytest.raises(CrashpadInitializationError, match="rejected"):
        CrashpadNativeClient(
            library_loader=lambda _path: cast(ctypes.CDLL, library)
        ).start(
            context=context,
            application_version="0.22.0",
            attachment_path=tmp_path / "fault.log",
        )
