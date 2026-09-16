import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const FILE = "C:/Users/26477/Desktop/课程文件/大二上/数据库/第一章-20260824/ch06.pptx";
const buf = fs.readFileSync(FILE);
const U = "奶12";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
const api = ctx.request;

async function del(id) {
  const r = await api.delete(`${BASE}/api/materials/${id}?username=${encodeURIComponent(U)}`);
  return { status: r.status(), body: await r.json().catch(() => ({})) };
}
async function upload(course_id, subject_key, subject) {
  const r = await api.post(`${BASE}/api/materials/upload`, { multipart: { file: { name: path.basename(FILE), mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation", buffer: buf }, username: U, course_id, subject_key, subject, source_type: "user_upload" } });
  const j = await r.json().catch(() => ({}));
  return { status: r.status(), material_id: j?.material_id, code: j?.detail?.code };
}
async function list(course_id, subject_key) {
  const r = await api.get(`${BASE}/api/materials?username=${encodeURIComponent(U)}&course_id=${course_id}&subject_key=${subject_key}`);
  const j = await r.json().catch(() => ({}));
  return { status: r.status(), ids: (j?.materials||[]).map(m => m.id), names: (j?.materials||[]).map(m => m.file_name || m.original_filename) };
}

console.log("DELETE 11408 数据结构 ch06.pptx (id=36):", JSON.stringify(await del(36)));
console.log("course-learning 数据库系统 列表 (应仍含 id=37):", JSON.stringify(await list("database_systems", "database_systems")));
console.log("重新上传到 11408 数据结构 (应允许):", JSON.stringify(await upload("data_structure_11408", "data_structure", "11408 数据结构")));
await browser.close();
