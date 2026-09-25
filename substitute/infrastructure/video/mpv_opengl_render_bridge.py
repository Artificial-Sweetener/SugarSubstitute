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

"""Own libmpv's OpenGL render context independently of playback state."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import cast

from substitute.infrastructure.video.mpv_player_factory import MpvPlayerProtocol

RenderContextFactory = Callable[..., object]


class MpvOpenGLRenderBridge:
    """Bind one libmpv client to a caller-owned OpenGL framebuffer."""

    def __init__(self, module: object, player: MpvPlayerProtocol) -> None:
        """Retain native factories and an independently synchronized context."""

        self._module = module
        self._player = player
        self._lock = RLock()
        self._context: object | None = None
        self._get_proc_wrapper: object | None = None

    def initialize(
        self,
        get_proc_address: Callable[[str], int],
    ) -> None:
        """Create the render context against the caller's current GL context."""

        with self._lock:
            if self._context is not None:
                return

            def resolve(_context: object, name: bytes) -> int:
                """Resolve one OpenGL symbol without importing Qt."""

                return get_proc_address(name.decode("ascii"))

            wrapper_factory = cast(
                Callable[[Callable[[object, bytes], int]], object],
                getattr(self._module, "MpvGlGetProcAddressFn"),
            )
            self._get_proc_wrapper = wrapper_factory(resolve)
            context_factory = cast(
                RenderContextFactory,
                getattr(self._module, "MpvRenderContext"),
            )
            self._context = context_factory(
                self._player,
                "opengl",
                opengl_init_params={"get_proc_address": self._get_proc_wrapper},
            )

    def poll_update(self) -> bool:
        """Acknowledge native render state from the caller's GUI thread."""

        with self._lock:
            context = self._context
            if context is None:
                return False
            update = cast(Callable[[], bool], getattr(context, "update"))
            return bool(update())

    def render(self, *, framebuffer: int, width: int, height: int) -> None:
        """Render one frame into the caller's current OpenGL framebuffer."""

        with self._lock:
            context = self._context
            if context is None:
                return
            render = cast(Callable[..., None], getattr(context, "render"))
            render(
                opengl_fbo={
                    "fbo": framebuffer,
                    "w": width,
                    "h": height,
                    "internal_format": 0,
                },
                flip_y=True,
            )

    def report_swap(self) -> None:
        """Report presentation of the most recently rendered frame."""

        with self._lock:
            if self._context is not None:
                cast(Callable[[], None], getattr(self._context, "report_swap"))()

    def release(self) -> None:
        """Release native render resources before the mpv client terminates."""

        with self._lock:
            context = self._context
            if context is None:
                return
            cast(Callable[[], None], getattr(context, "free"))()
            self._context = None
            self._get_proc_wrapper = None


__all__ = ["MpvOpenGLRenderBridge"]
