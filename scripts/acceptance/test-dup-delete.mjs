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

async function upload(course_id, subject_key, subject) {
  const r = await api.post(`${BASE}/api/materials/upload`, {
    multipart: {
      file: { name: path.basename(FILE), mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation", buffer: buf },
      username: U, course_id, subject_key, subject, source_type: "user_upload",
    },
  });
  const j = await r.json().catch(() => ({}));
  return { status: r.status(), code: j?.detail?.code, material_id: j?.material_id, detail: j?.detail };
}

console.log("1) 11408 数据结构 上传 ch06.pptx:", JSON.stringify(await upload("data_structure_11408", "data_structure", "11408 数据结构")));
console.log("2) 11408 操作系统 上传同一文件:", JSON.stringify(await upload("operating_system_11408", "operating_system", "11408 操作系统")));
console.log("3) course-learning 数据库系统 上传同一文件:", JSON.stringify(await upload("database_systems", "database_systems", "数据库系统")));
console.log("4) course-learning 编译原理 上传同一文件:", JSON.stringify(await upload("compiler_principles", "compiler_principles", "编译原理")));

await browser.close();
