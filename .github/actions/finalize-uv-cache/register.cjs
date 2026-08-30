//    SugarSubstitute - The desktop native Qt front-end for ComfyUI
//    Copyright (C) 2026  Artificial Sweetener and contributors
//
//    This program is free software: you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation, either version 3 of the License, or
//    (at your option) any later version.
//
//    This program is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU General Public License for more details.
//
//    You should have received a copy of the GNU General Public License
//    along with this program.  If not, see <https://www.gnu.org/licenses/>.

const fs = require("node:fs");

/** Persist one action input for the post-job cache finalizer. */
function savePostState(name, value) {
  const stateFile = process.env.GITHUB_STATE;
  if (!stateFile) {
    throw new Error(
      "GITHUB_STATE is unavailable; uv cache finalization cannot register.",
    );
  }
  fs.appendFileSync(stateFile, `${name}=${value}\n`, { encoding: "utf8" });
}

savePostState("uv_path", process.env["INPUT_UV-PATH"] ?? "");
savePostState("cache_path", process.env["INPUT_CACHE-PATH"] ?? "");
