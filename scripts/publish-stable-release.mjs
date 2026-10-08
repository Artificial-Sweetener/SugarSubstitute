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
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { prepareStableRelease, RELEASE_METADATA_FILES } from "./prepare-stable-release.mjs";

/**
 * Run a release command without shell interpolation and fail at its boundary.
 * @param {string} command Executable name.
 * @param {string[]} args Argument vector.
 * @param {string} cwd Repository root.
 * @returns {string} Command standard output.
 */
export function runReleaseCommand(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed.\n${result.stdout ?? ""}\n${result.stderr ?? ""}`);
  }
  return result.stdout ?? "";
}

/**
 * Publish qualified Stable bytes after an atomic authorized Git push.
 *
 * Existing drafts resume only when their remote tag matches the prepared tree.
 * Assets remain private until every upload succeeds. Failed commands stop the
 * transaction and retain its draft for an explicit retry.
 *
 * @param {{root: string, directory: string, version: string, repository: string, pushUrl: string, branch: string, serverUrl?: string}} release Qualified release and push authority.
 * @param {typeof runReleaseCommand} run Process adapter.
 * @returns {Promise<void>} Publication completion.
 */
export async function publishStableRelease(release, run = runReleaseCommand) {
  const { root, directory, version, repository, pushUrl, branch } = release;
  if (branch !== "main" || !pushUrl) {
    throw new Error("Stable publication requires main and an authorized push URL.");
  }
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw new Error("Stable publication requires a GitHub owner/repository.");
  }
  const tag = `v${version}`;
  const pages = JSON.parse(run("gh", ["api", "--paginate", "--slurp", `repos/${repository}/releases?per_page=100`], root));
  if (!Array.isArray(pages) || pages.some((page) => !Array.isArray(page))) {
    throw new Error("GitHub release inventory is malformed.");
  }
  const existing = pages.flat().find((item) => item.tag_name === tag);
  if (existing && !existing.draft) {
    if (existing.prerelease) throw new Error("The Stable tag identifies a prerelease.");
    return;
  }
  if (run("git", ["status", "--porcelain", "--untracked-files=no"], root).trim()) {
    throw new Error("Stable publication requires clean tracked source.");
  }
  const tags = run("git", ["tag", "--list", tag], root).trim();
  const date = tags
    ? new Date(run("git", ["show", "-s", "--format=%cI", tag], root).trim()).toISOString().slice(0, 10)
    : undefined;
  const prepared = await prepareStableRelease({ ...release, date });
  if (tags) {
    run("git", ["diff", "--exit-code", tag, "--"], root);
    const localTag = run("git", ["rev-parse", `refs/tags/${tag}`], root).trim();
    const remoteTag = run("git", ["ls-remote", "--exit-code", pushUrl, `refs/tags/${tag}`], root).trim().split(/\s+/)[0];
    if (localTag !== remoteTag) throw new Error("The remote Stable tag differs from the prepared tree.");
  } else {
    run("git", ["add", "--", ...RELEASE_METADATA_FILES], root);
    const changes = run("git", ["diff", "--cached", "--name-only"], root).trim();
    if (changes) {
      run("git", ["commit", "-m", `chore(release): ${version} [skip ci]\n\n${prepared.notes}`], root);
    }
    run("git", ["tag", tag], root);
    run("git", ["push", "--atomic", pushUrl, "HEAD:refs/heads/main", `refs/tags/${tag}:refs/tags/${tag}`], root);
  }
  const repoArgs = ["--repo", repository];
  if (existing) {
    run("gh", ["release", "upload", tag, ...prepared.assets, ...repoArgs, "--clobber"], root);
    run("gh", ["release", "edit", tag, ...repoArgs, "--notes-file", prepared.notesPath], root);
  } else {
    run("gh", ["release", "create", tag, ...prepared.assets, ...repoArgs,
      "--draft", "--verify-tag", "--title", tag, "--notes-file", prepared.notesPath], root);
  }
  run("gh", ["release", "edit", tag, ...repoArgs, "--draft=false", "--prerelease=false", "--latest"], root);
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) {
  const root = resolve(fileURLToPath(new URL("../", import.meta.url)));
  await publishStableRelease({
    root,
    directory: resolve(root, ".local-release-channel"),
    version: process.argv[2] ?? process.env.CANDIDATE_VERSION ?? "",
    repository: process.env.GITHUB_REPOSITORY ?? "",
    pushUrl: process.env.SUGAR_SUBSTITUTE_RELEASE_REPOSITORY_URL ?? "",
    branch: process.env.GITHUB_REF_NAME ?? "",
    serverUrl: process.env.GITHUB_SERVER_URL ?? "https://github.com",
  });
}
