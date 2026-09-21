#!/usr/bin/env node
// Production-artifact guard for the client API origin.
//
// A shipped bundle must address its own deployment (see src/lib/env.ts). A machine-local
// origin reaching the artifact is a total outage — every visitor's browser calls its own
// localhost — and it shipped once, on 2026-09-21, because nothing checked the built output.
// CI runs this immediately after `npm run build`, before the artifact can reach a server.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = fileURLToPath(new URL('../dist', import.meta.url));
// A port is what makes a loopback origin an addressable dev backend. It is required on
// purpose: TanStack Router embeds a bare `http://localhost` as its history fallback, which
// is not an API origin — do not widen this to match the portless form.
const LOOPBACK_BACKEND_ORIGIN = /\bhttps?:\/\/(?:localhost|127\.0\.0\.1):\d+/g;
const SCANNED_EXTENSIONS = /\.(?:js|mjs|css|html)$/;

// Minified evidence that the bundle derives its API base from the page origin rather than
// carrying one. Property names survive minification, so `window.location.origin` still
// contains this marker; the `/api` prefix is the deployment's proxy mount.
const SAME_ORIGIN_MARKERS = ['location.origin', '/api'];

if (!existsSync(DIST)) {
  console.error(`[api-origin] FAIL — ${DIST} does not exist; run \`npm run build\` first.`);
  process.exit(1);
}

function* artifactFiles(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) yield* artifactFiles(full);
    else if (SCANNED_EXTENSIONS.test(entry.name)) yield full;
  }
}

const relative = (file) => file.slice(DIST.length + 1).split('\\').join('/');
const violations = [];
const sameOriginEvidence = [];
let scanned = 0;

for (const file of artifactFiles(DIST)) {
  scanned += 1;
  const text = readFileSync(file, 'utf8');
  for (const match of text.match(LOOPBACK_BACKEND_ORIGIN) ?? []) {
    violations.push(`${relative(file)}: ${match}`);
  }
  if (SAME_ORIGIN_MARKERS.every((marker) => text.includes(marker))) {
    sameOriginEvidence.push(relative(file));
  }
}

if (violations.length > 0) {
  console.error('[api-origin] FAIL — a machine-local API origin is compiled into the artifact:');
  for (const violation of violations.slice(0, 20)) console.error(`  ${violation}`);
  console.error('  A production bundle must address its own origin; see src/lib/env.ts.');
  process.exit(1);
}

if (sameOriginEvidence.length === 0) {
  console.error('[api-origin] FAIL — the artifact carries no same-origin API base.');
  console.error('  Expected the bundle to derive its API base from the page origin; see src/lib/env.ts.');
  process.exit(1);
}

console.log(
  `[api-origin] OK — ${scanned} artifact files scanned, no loopback origin, ` +
    `same-origin API base present (${sameOriginEvidence[0]}).`,
);
