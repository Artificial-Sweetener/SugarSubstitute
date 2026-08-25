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

const childProcess = require("node:child_process");

/** Minimize one disposable uv cache through uv's supported CI operation. */
function pruneCache() {
  const uvPath = process.env.STATE_uv_path;
  const cachePath = process.env.STATE_cache_path;
  if (!uvPath || !cachePath) {
    throw new Error("uv cache finalization state is incomplete.");
  }
  const result = childProcess.spawnSync(
    uvPath,
    ["cache", "prune", "--ci", "--force", "--cache-dir", cachePath],
    { stdio: "inherit" },
  );
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`uv cache pruning failed with exit code ${result.status}.`);
  }
}

pruneCache();
