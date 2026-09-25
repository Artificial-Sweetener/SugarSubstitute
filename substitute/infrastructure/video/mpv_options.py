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

"""Define the closed libmpv option surface for generated local artifacts."""

from __future__ import annotations


def local_video_options(*, video_output: str, audio_output: str) -> dict[str, object]:
    """Return options that isolate playback from user config and remote inputs."""

    return {
        "vo": video_output,
        "ao": audio_output,
        "config": False,
        "load_scripts": False,
        "input_conf": "",
        "input_default_bindings": False,
        "input_vo_keyboard": False,
        "autoload_files": "no",
        "audio_file_auto": "no",
        "sub_auto": "no",
        "save_position_on_quit": False,
        "load_unsafe_playlists": False,
        "access_references": False,
        "demuxer_lavf_o": "protocol_whitelist=file",
        "background": "none",
        "background_color": "#00000000",
    }


__all__ = ["local_video_options"]
