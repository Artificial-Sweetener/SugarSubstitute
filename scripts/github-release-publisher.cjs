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

const {
  createInstallerReleaseNotes,
  DEFAULT_REPOSITORY,
} = require("./release-notes-preamble.cjs");

/**
 * Delegate GitHub authentication checks to the official publisher.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Promise<void>} Verification completion.
 */
async function verifyConditions(pluginConfig, context) {
  const github = await loadGitHubPlugin();
  await github.verifyConditions(githubConfig(pluginConfig), context);
}

/**
 * Publish a GitHub Release with installer guidance above conventional notes.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Promise<Record<string, unknown>>} Published release metadata.
 */
async function publish(pluginConfig, context) {
  const github = await loadGitHubPlugin();
  return github.publish(
    githubConfig(pluginConfig),
    withInstallerReleaseNotes(pluginConfig, context),
  );
}

/**
 * Add a distribution channel while retaining the release installation guide.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Promise<Record<string, unknown>>} Updated release metadata.
 */
async function addChannel(pluginConfig, context) {
  const github = await loadGitHubPlugin();
  return github.addChannel(
    githubConfig(pluginConfig),
    withInstallerReleaseNotes(pluginConfig, context),
  );
}

/**
 * Delegate successful-release follow-up to the official GitHub publisher.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Promise<void>} Follow-up completion.
 */
async function success(pluginConfig, context) {
  const github = await loadGitHubPlugin();
  await github.success(githubConfig(pluginConfig), context);
}

/**
 * Delegate failed-release reporting to the official GitHub publisher.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Promise<void>} Failure-report completion.
 */
async function fail(pluginConfig, context) {
  const github = await loadGitHubPlugin();
  await github.fail(githubConfig(pluginConfig), context);
}

/**
 * Return a copied semantic-release context with GitHub-only guidance.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @param {Record<string, unknown>} context Semantic-release context.
 * @returns {Record<string, unknown>} Context carrying the GitHub release body.
 */
function withInstallerReleaseNotes(pluginConfig, context) {
  const nextRelease = context.nextRelease;
  if (!nextRelease || typeof nextRelease !== "object") {
    throw new Error("Semantic-release context is missing nextRelease.");
  }
  const version = nextRelease.version;
  if (typeof version !== "string") {
    throw new Error("Semantic-release context is missing nextRelease.version.");
  }
  const repository =
    typeof pluginConfig.repository === "string"
      ? pluginConfig.repository
      : process.env.GITHUB_REPOSITORY || DEFAULT_REPOSITORY;
  const installerNotes = createInstallerReleaseNotes(repository, version);
  const conventionalNotes =
    typeof nextRelease.notes === "string" ? nextRelease.notes : "";
  return {
    ...context,
    nextRelease: {
      ...nextRelease,
      notes: `${installerNotes}\n${conventionalNotes}`,
    },
  };
}

/**
 * Remove adapter-only settings before calling the official publisher.
 *
 * @param {Record<string, unknown>} pluginConfig Publisher configuration.
 * @returns {Record<string, unknown>} Official GitHub plugin configuration.
 */
function githubConfig(pluginConfig) {
  const { repository: _repository, ...config } = pluginConfig;
  return config;
}

/**
 * Load the official ESM GitHub publisher from this CommonJS adapter.
 *
 * @returns {Promise<typeof import("@semantic-release/github")>} GitHub plugin.
 */
async function loadGitHubPlugin() {
  return import("@semantic-release/github");
}

module.exports = {
  addChannel,
  fail,
  publish,
  success,
  verifyConditions,
  withInstallerReleaseNotes,
};
