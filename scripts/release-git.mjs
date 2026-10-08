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

import { spawnSync } from "node:child_process";

/**
 * Execute Git without a shell and preserve a failed command's diagnostics.
 * @param {string} cwd Repository root.
 * @param {string[]} args Git arguments.
 * @returns {string} Git standard output.
 */
export function git(cwd, args) {
  const result = spawnSync("git", args, { cwd, encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`git ${args.join(" ")} failed.\n${result.stdout ?? ""}\n${result.stderr ?? ""}`);
  }
  return result.stdout ?? "";
}

/**
 * Read full commit identities and messages for one release range.
 * @param {string} cwd Repository root.
 * @param {string | undefined} previousTag Previous Stable release tag.
 * @returns {{hash: string, message: string}[]} Newest-first history.
 */
export function releaseCommits(cwd, previousTag) {
  const fields = git(cwd, ["log", previousTag ? `${previousTag}..HEAD` : "HEAD", "--format=%H%x00%B%x00"])
    .split("\0");
  const commits = [];
  for (let index = 0; index + 1 < fields.length; index += 2) {
    commits.push({ hash: fields[index].trim(), message: fields[index + 1].trim() });
  }
  return commits;
}
