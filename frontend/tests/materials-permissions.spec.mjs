import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const USERNAME = "奶12";

// A small unique-by-content upload payload; content differs per test via a
// random suffix so each run creates a fresh file and avoids cross-run dedup.
function fakePdfBuffer() {
  const marker = Math.random().toString(36).slice(2);
  return Buffer.from(`%PDF-1.4\n% regression-test-${marker}\n%%EOF`, "utf8");
}

test.describe("material permissions", () => {
  test("duplicate is rejected within the same domain", async ({ request }) => {
    const buf = fakePdfBuffer();
    const upload = (course_id, subject_key, subject) =>
      request.post(`${BASE}/api/materials/upload`, {
        multipart: {
          file: { name: "regression.pdf", mimeType: "application/pdf", buffer: buf },
          username: USERNAME, course_id, subject_key, subject, source_type: "user_upload",
        },
      });

    const first = await upload("data_structure_11408", "data_structure", "11408 数据结构");
    expect(first.status()).toBe(200);

    const dup = await upload("operating_system_11408", "operating_system", "11408 操作系统");
    expect(dup.status()).toBe(409);
    const dupBody = await dup.json();
    expect(dupBody.detail.code).toBe("MATERIAL_DUPLICATE");

    // cleanup
    const firstBody = await first.json();
    await request.delete(`${BASE}/api/materials/${firstBody.material_id}?username=${encodeURIComponent(USERNAME)}`);
  });

  test("cross-domain upload of the same content is allowed", async ({ request }) => {
    const buf = fakePdfBuffer();
    const upload = (course_id, subject_key, subject) =>
      request.post(`${BASE}/api/materials/upload`, {
        multipart: {
          file: { name: "regression.pdf", mimeType: "application/pdf", buffer: buf },
          username: USERNAME, course_id, subject_key, subject, source_type: "user_upload",
        },
      });

    const exam = await upload("computer_organization_11408", "computer_organization", "11408 计算机组成原理");
    expect(exam.status()).toBe(200);
    const course = await upload("computer_organization", "computer_organization", "计算机组成原理");
    expect(course.status()).toBe(200);

    // delete exam copy; course-learning copy must survive
    const examBody = await exam.json();
    await request.delete(`${BASE}/api/materials/${examBody.material_id}?username=${encodeURIComponent(USERNAME)}`);

    const courseBody = await course.json();
    const list = await request.get(`${BASE}/api/materials?username=${encodeURIComponent(USERNAME)}&course_id=computer_organization&subject_key=computer_organization`);
    const listBody = await list.json();
    expect((listBody.materials || []).map((m) => m.id)).toContain(courseBody.material_id);

    // cleanup course copy
    await request.delete(`${BASE}/api/materials/${courseBody.material_id}?username=${encodeURIComponent(USERNAME)}`);
  });

  test("/api/me returns per-domain material quota", async ({ request }) => {
    const r = await request.post(`${BASE}/api/me`, { data: { username: USERNAME } });
    expect(r.status()).toBe(200);
    const body = await r.json();
    const plans = body.user.service_plans;
    expect(plans.exam_11408).toBeTruthy();
    expect(plans.exam_11408.single_file_limit_mb).toBeGreaterThan(0);
    expect(plans.exam_11408.material_storage_limit_mb).toBeGreaterThan(0);
    expect(typeof plans.exam_11408.material_used_mb).toBe("number");
    expect(plans.course_learning).toBeTruthy();
  });
});
