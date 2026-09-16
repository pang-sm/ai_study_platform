// P0-A local E2E: 11408 mobile material upload + library select + AI material context.
// Exercises the EXACT payload the mobile UI now sends (subject with "11408 " prefix,
// course_id / subject_key / exam_subject / service_key / material_ids) to prove:
//   1. upload creates a real StudyMaterial owned by the test user with exam_11408 scope
//   2. GET /materials (the same list both PC and Mobile call) shows both files
//   3. POST /chat with material_ids answers the RAG secrets correctly
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:8000";
const SUBJECT_KEY = "computer_organization";
const COURSE_ID = `${SUBJECT_KEY}_11408`;
const SUBJECT = "11408 计算机组成原理";
const ts = Date.now();
const USER = `mobile_v164_test_${ts}`;
const PASS = "v164test123";

const log = [];
const out = (s) => { log.push(s); console.log(s); };

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext();
const api = ctx.request; // shares cookie jar with the context

try {
  // 1. register (sets the auth session cookie)
  const reg = await api.post(`${BASE}/register`, { data: { username: USER, password: PASS } });
  const regBody = await reg.json().catch(() => ({}));
  out(`[register] ${reg.status()} user=${USER} -> ${JSON.stringify(regBody.message || regBody.detail || "")}`);

  // 2. upload file A (mobile flow scope)
  const fileA = Buffer.from("MOBILE_V164_SECRET = 271828\n", "utf8");
  const upA = await api.post(`${BASE}/materials/upload`, {
    multipart: {
      file: { name: "mobile-v164-material.txt", mimeType: "text/plain", buffer: fileA },
      username: USER,
      course_id: COURSE_ID,
      subject_key: SUBJECT_KEY,
      subject: SUBJECT,
      track: "exam_11408",
      save_to_materials: "true",
      source_type: "user_upload",
    },
  });
  const upABody = await upA.json().catch(() => ({}));
  out(`[upload A] ${upA.status()} id=${upABody.material_id} parse=${upABody.parse_status} subject=${upABody.material?.subject} course_id=${upABody.material?.course_id} subject_key=${upABody.material?.subject_key} owner=${upABody.material?.username}`);
  const idA = upABody.material_id;

  // 3. upload file B (simulates PC upload of the same account + subject)
  const fileB = Buffer.from("PC_MOBILE_SHARED_FACT = 161803\n", "utf8");
  const upB = await api.post(`${BASE}/materials/upload`, {
    multipart: {
      file: { name: "pc-mobile-test.txt", mimeType: "text/plain", buffer: fileB },
      username: USER,
      course_id: COURSE_ID,
      subject_key: SUBJECT_KEY,
      subject: SUBJECT,
      track: "exam_11408",
      save_to_materials: "true",
    },
  });
  const upBBody = await upB.json().catch(() => ({}));
  out(`[upload B] ${upB.status()} id=${upBBody.material_id} parse=${upBBody.parse_status} subject=${upBBody.material?.subject}`);
  const idB = upBBody.material_id;

  // 4. list (the endpoint both PC "资料库" and Mobile "从资料库选择" call)
  const list = await api.get(`${BASE}/materials?username=${USER}&course_id=${COURSE_ID}&subject_key=${SUBJECT_KEY}`);
  const listBody = await list.json().catch(() => ({}));
  const names = (listBody.materials || []).map((m) => m.original_filename || m.file_name);
  const ids = (listBody.materials || []).map((m) => m.id);
  out(`[list] ${list.status()} count=${names.length} names=${JSON.stringify(names)} ids=${JSON.stringify(ids)}`);
  out(`[cross-visibility] mobile file listed=${names.includes("mobile-v164-material.txt")} pc file listed=${names.includes("pc-mobile-test.txt")}`);

  // 5. chat with material_ids (A) -> expect 271828
  const chatA = await api.post(`${BASE}/chat`, {
    data: {
      username: USER,
      message: "MOBILE_V164_SECRET 的值是什么？",
      subject: SUBJECT,
      course: SUBJECT,
      subject_key: SUBJECT_KEY,
      exam_subject: SUBJECT_KEY,
      course_id: COURSE_ID,
      service_key: "exam_11408",
      material_ids: [idA],
    },
  });
  const chatABody = await chatA.json().catch(() => ({}));
  const answerA = chatABody.answer || chatABody.content || "";
  out(`[chat A] ${chatA.status()} detail=${JSON.stringify(chatABody.detail || "")} answerHas271828=${answerA.includes("271828")}`);
  out(`[chat A answer] ${answerA.slice(0, 400)}`);

  // 6. chat with material_ids (B) -> expect 161803
  const chatB = await api.post(`${BASE}/chat`, {
    data: {
      username: USER,
      message: "PC_MOBILE_SHARED_FACT 是多少？",
      subject: SUBJECT,
      course: SUBJECT,
      subject_key: SUBJECT_KEY,
      exam_subject: SUBJECT_KEY,
      course_id: COURSE_ID,
      service_key: "exam_11408",
      material_ids: [idB],
    },
  });
  const chatBBody = await chatB.json().catch(() => ({}));
  const answerB = chatBBody.answer || chatBBody.content || "";
  out(`[chat B] ${chatB.status()} detail=${JSON.stringify(chatBBody.detail || "")} answerHas161803=${answerB.includes("161803")}`);
  out(`[chat B answer] ${answerB.slice(0, 400)}`);

  const pass =
    upA.ok() && upB.ok() && list.ok() &&
    names.includes("mobile-v164-material.txt") && names.includes("pc-mobile-test.txt") &&
    answerA.includes("271828") && answerB.includes("161803");
  out(`\n===== RESULT =====`);
  out(`PASS=${pass}`);
  out(`TEST_USER=${USER}`);
  out(`material_id_A=${idA} material_id_B=${idB}`);
} catch (e) {
  out(`[FATAL] ${e.message}`);
  console.error(e);
} finally {
  await browser.close();
  console.log("\n===== FULL LOG =====");
  console.log(log.join("\n"));
}
