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

import angular from "conventional-changelog-angular";
import { CommitParser } from "conventional-commits-parser";
import { filterRevertedCommitsSync } from "conventional-commits-filter";
import { writeChangelogString } from "conventional-changelog-writer";

/**
 * Parse and remove reverted conventional commits in newest-first Git order.
 * @param {{message: string, hash: string}[]} commits Commit history.
 * @param {boolean} references Include GitHub issue references in release notes.
 * @returns {object[]} Parsed, non-reverted commits.
 */
function parseCommits(commits, references = false) {
  const preset = angular();
  const parser = new CommitParser({
    ...(references ? {
      referenceActions: ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"],
      issuePrefixes: ["#", "gh-"],
    } : {}),
    ...preset.parser,
  });
  return [...filterRevertedCommitsSync(commits
    .filter(({ message }) => message.trim())
    .map((commit) => ({ ...commit, rawMsg: commit.message, ...parser.parse(commit.message) })))];
}

/**
 * Apply the beta release rules to parsed conventional commits.
 * @param {{message: string, hash: string}[]} commits Newest-first Git history.
 * @returns {"minor" | "patch" | null} Highest required beta release increment.
 */
export function analyzeCommits(commits) {
  let releaseType = null;
  for (const commit of parseCommits(commits)) {
    if (commit.notes.length > 0 || ["feat", "FEAT"].includes(commit.type)) {
      return "minor";
    }
    if (commit.revert || ["fix", "FIX", "perf"].includes(commit.type)) {
      releaseType = "patch";
    }
  }
  return releaseType;
}

/**
 * Generate the canonical conventional history section for a Stable release.
 * @param {{message: string, hash: string}[]} commits Newest-first Git history.
 * @param {{version: string, repository: string, serverUrl: string, previousTag?: string, packageData: object, date?: string}} release Release context.
 * @returns {Promise<string>} Conventional changelog Markdown.
 */
export async function generateReleaseNotes(commits, release) {
  const [owner, repository] = release.repository.split("/");
  return writeChangelogString(parseCommits(commits, true), {
    version: release.version,
    host: release.serverUrl,
    owner,
    repository,
    previousTag: release.previousTag,
    currentTag: `v${release.version}`,
    linkCompare: Boolean(release.previousTag),
    issue: "issues",
    commit: "commit",
    packageData: release.packageData,
    ...(release.date ? { date: release.date } : {}),
  }, angular().writer);
}
