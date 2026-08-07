#!/usr/bin/env node

/**
 * Regression checks for the authenticated Workbench bootstrap contract.
 * This script never prints credentials, cookie values, or tokens.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { chromium } from "playwright";

const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(?:[A-Za-z]:)/, (value) => value.slice(1)));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const ONLINE_SCRIPT = path.join(SCRIPT_DIR, "programming_workbench_online_acceptance.mjs");
const BOOTSTRAP_SCRIPT = path.join(SCRIPT_DIR, "programming_workbench_login_bootstrap.mjs");
const BASE_URL = "http://101.32.190.42/";
const ORIGIN = new URL(BASE_URL).origin;
const REPORT_PATH = path.join(PROJECT_ROOT, "verification-results", "programming-workbench-auth-bootstrap-regression.json");

function runAuthCheck(statePath, reportDir) {
  const result = spawnSync(
    process.execPath,
    [ONLINE_SCRIPT, "--auth-check-only", "--auth-state", statePath, "--report-dir", reportDir],
    { cwd: PROJECT_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
  return result.status == null ? 20 : result.status;
}

function writeState(filePath, state) {
  fs.writeFileSync(filePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

function baseState() {
  return {
    cookies: [],
    origins: [{
      origin: ORIGIN,
      localStorage: [{ name: "ai_study_platform_user", value: JSON.stringify({ username: "acceptance-regression" }) }],
    }],
  };
}

function record(cases, name, passed, details) {
  cases.push({ name, status: passed ? "passed" : "failed", ...details });
}

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "ai-study-auth-regression-"));
const reportDir = path.join(tempRoot, "reports");
fs.mkdirSync(reportDir, { recursive: true });
const cases = [];
let realStatePath = "";
try {
  const missingPath = path.join(tempRoot, "missing.json");
  record(cases, "missing_storage_state", runAuthCheck(missingPath, reportDir) === 20, { expected_exit: 20 });

  const localOnlyPath = path.join(tempRoot, "local-only.json");
  writeState(localOnlyPath, baseState());
  record(cases, "local_storage_without_cookie", runAuthCheck(localOnlyPath, reportDir) === 20, { expected_exit: 20 });

  const fakeCookiePath = path.join(tempRoot, "fake-cookie.json");
  const fakeState = baseState();
  fakeState.cookies.push({
    name: "ai_session",
    value: "regression-invalid-session",
    domain: "101.32.190.42",
    path: "/",
    expires: -1,
    httpOnly: true,
    secure: false,
    sameSite: "Lax",
  });
  writeState(fakeCookiePath, fakeState);
  record(cases, "fake_cookie", runAuthCheck(fakeCookiePath, reportDir) === 20, { expected_exit: 20 });

  const hasCredentials = Boolean(process.env.ACCEPTANCE_USERNAME && process.env.ACCEPTANCE_PASSWORD);
  if (!hasCredentials) {
    record(cases, "real_login_and_reload", true, { status: "skipped_missing_env" });
    record(cases, "logout_invalidates_old_state", true, { status: "skipped_missing_env" });
  } else {
    realStatePath = path.join(tempRoot, "real-login.json");
    const bootstrap = spawnSync(
      process.execPath,
      [BOOTSTRAP_SCRIPT, "--auto", "--base-url", BASE_URL, "--auth-state", realStatePath],
      { cwd: PROJECT_ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
    );
    const authPass = bootstrap.status === 0 && runAuthCheck(realStatePath, reportDir) === 0;
    record(cases, "real_login_and_reload", authPass, { expected_exit: 0 });

    let logoutPass = false;
    if (authPass) {
      const browser = await chromium.launch({ headless: true });
      const context = await browser.newContext({ storageState: realStatePath });
      const page = await context.newPage();
      await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 45_000 });
      const logoutStatus = await page.evaluate(async () => {
        const response = await fetch("/api/logout", { method: "POST", credentials: "include" });
        return response.status;
      });
      await context.close();
      await browser.close();
      logoutPass = logoutStatus >= 200 && logoutStatus < 300 && runAuthCheck(realStatePath, reportDir) === 20;
    }
    record(cases, "logout_invalidates_old_state", logoutPass, { expected_logout: 200, expected_old_state_exit: 20 });
  }

  const failures = cases.filter((item) => item.status === "failed");
  const skipped = cases.filter((item) => item.status === "skipped_missing_env");
  const report = {
    audit: "programming-workbench-auth-bootstrap-regression",
    generated_at: new Date().toISOString(),
    origin: ORIGIN,
    status: failures.length ? "failed" : skipped.length ? "blocked_missing_env" : "passed",
    cases,
    sensitive_values_written: false,
    cookie_values_written: false,
  };
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(`AUTH_BOOTSTRAP_REGRESSION status=${report.status} passed=${cases.filter((item) => item.status === "passed").length} failed=${failures.length} skipped=${skipped.length}`);
  process.exitCode = failures.length ? 1 : 0;
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
