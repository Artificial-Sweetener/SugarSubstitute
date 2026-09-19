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

import { createHash, createPrivateKey, createPublicKey, sign } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

const [manifestPath, outputPath, rawMetadataVersion, rawSourceEpoch] =
  process.argv.slice(2);
if (!manifestPath || !outputPath || !rawMetadataVersion || !rawSourceEpoch) {
  throw new Error(
    "Usage: sign-release-metadata MANIFEST OUTPUT METADATA_VERSION SOURCE_DATE_EPOCH",
  );
}
const privateKeyPem = process.env.SUGAR_SUBSTITUTE_RELEASE_SIGNING_KEY;
if (!privateKeyPem) {
  throw new Error("SUGAR_SUBSTITUTE_RELEASE_SIGNING_KEY is required.");
}
const metadataVersion = Number(rawMetadataVersion);
const sourceEpoch = Number(rawSourceEpoch);
if (!Number.isSafeInteger(metadataVersion) || metadataVersion <= 0) {
  throw new Error("Metadata version must be a positive safe integer.");
}
if (!Number.isSafeInteger(sourceEpoch) || sourceEpoch <= 0) {
  throw new Error("Source date epoch must be a positive safe integer.");
}

const key = createPrivateKey(privateKeyPem);
if (key.asymmetricKeyType !== "ed25519") {
  throw new Error("Release signing key must be Ed25519.");
}
// Derive the stable key id from the public SPKI representation.
const publicSpki = createPublicKey(key)
  .export({ format: "der", type: "spki" });
const keyId = createHash("sha256").update(publicSpki).digest("hex");

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const expires = new Date((sourceEpoch + 180 * 24 * 60 * 60) * 1000);
const signed = {
  expires_utc: expires.toISOString().replace(".000Z", "Z"),
  manifest,
  metadata_version: metadataVersion,
};
const canonical = Buffer.from(canonicalJson(signed), "utf8");
const envelope = {
  schema_version: 1,
  signatures: [
    {
      key_id: keyId,
      signature_base64: sign(null, canonical, key).toString("base64"),
    },
  ],
  signed,
};
writeFileSync(outputPath, `${JSON.stringify(envelope, null, 2)}\n`, "utf8");

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}
