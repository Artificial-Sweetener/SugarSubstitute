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

"""Expose shared launch-splash session primitives for launcher and app startup."""

from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
from sugarsubstitute_shared.launch_splash.protocol import (
    SplashSessionMessage,
    SplashSessionMessageError,
    decode_splash_session_message,
    encode_splash_session_message,
)
from sugarsubstitute_shared.launch_splash.server import (
    SplashSessionMessageHandler,
    SplashSessionServer,
)
from sugarsubstitute_shared.launch_splash.session import (
    SplashSessionSpec,
    create_splash_session_spec,
    splash_cancel_signal_path,
    splash_session_args,
    splash_session_from_args,
)

__all__ = [
    "SocketSplashSessionClient",
    "SplashSessionMessage",
    "SplashSessionMessageError",
    "SplashSessionMessageHandler",
    "SplashSessionServer",
    "SplashSessionSpec",
    "create_splash_session_spec",
    "decode_splash_session_message",
    "encode_splash_session_message",
    "splash_cancel_signal_path",
    "splash_session_args",
    "splash_session_from_args",
]
