# Mobile IA Stage 2 Report

## Final status

**MOBILE_IA_STAGE2_BLOCKED**

The Mobile-only implementation, build, lint, and unauthenticated responsive checks passed. Authenticated Mobile and PC-to-Mobile data synchronization could not be verified because this run had no existing authenticated browser session and no test credentials were supplied. Authentication was not bypassed, injected, or mocked.

## Modified files

- `frontend/src/mobile/MobileApp.jsx`
  - Preserves learning-space separation and adds a Mobile 11408 past-paper training route.
  - Carries real course, chapter, and knowledge-point IDs plus their returned display names from the knowledge bottom sheet into the AI landing page and onward into a new chat.
  - Reuses existing 11408 past-paper attempt creation, read, and submit APIs.
  - Keeps AI history classification and current chat functionality: real history, file/image upload, message editing, regeneration, and branches.
- `frontend/src/mobile/MobileApp.css`
  - Limits the knowledge bottom sheet to `80dvh`, keeps it scrollable and safe-area padded, and adds AI-context and paper-attempt layout rules.

No backend, database, API definition, PC Web, authentication, or production configuration was changed.

## Mobile IA structure

```text
Mobile global shell
├── 首页
├── 学习
├── AI
├── 练习
└── 我的 (learning-space switch center)
    ├── 课程学习
    │   ├── 首页 (/m)
    │   ├── 知识点 (/m/learn)
    │   │   └── 课程 → 章节 → 知识点 → Bottom Sheet
    │   ├── AI (/m/ai?space=course)
    │   ├── 练习 (/m/tasks)
    │   └── 我的
    └── 11408考研中心
        ├── 首页 (/m/11408)
        ├── 学习计划 / 章节
        ├── 真题 → 真题训练 (/m/11408/paper/:subject/:attemptId)
        ├── 错题
        ├── AI智能训练
        └── 我的
```

The 11408 content sections remain inside its independent center; course pages do not render true-paper, wrong-question, or 11408 AI-training entries.

## Real API correspondence

| Mobile capability | Existing API reused |
| --- | --- |
| Current course and knowledge tree | `GET /api/course-learning/courses`, `GET /api/knowledge-map` |
| Mastery read/write | `GET /api/knowledge-map`, `PATCH /api/knowledge-map/progress` |
| Course practice | `GET /api/practice/questions`, `POST /api/practice/submit-result` |
| AI histories and messages | `GET /api/chat/history`, `GET /api/chat/sessions/{id}`, `POST /api/chat` |
| AI attachments | `POST /api/materials/upload`, `GET /api/materials/{id}/status` |
| 11408 plan / papers / wrong questions / AI questions | Existing `/api/exam/11408/...` GET endpoints |
| 11408 real-paper training | `POST /api/exam/11408/{subject}/past-paper-attempts`, `GET /api/exam/11408/{subject}/past-paper-attempts/{id}`, `POST /api/exam/11408/{subject}/past-paper-attempts/{id}/submit` |
| Account / membership / quota / store | Existing `/api/me/*`, `/api/membership/*` endpoints |

## Functionality completed in code

- Profile has no Stage number, internal ID, or quota summary. It exposes avatar, nickname, password, email, learning-space selection, membership, quota, and store actions backed by existing APIs.
- Knowledge point tree displays only returned chapter and knowledge-point labels; internal codes are used as request identifiers only.
- Knowledge Bottom Sheet opens from the bottom, has a backdrop-close action, uses `max-height: 80dvh`, scrolls independently, and is above the fixed navigation.
- The sheet no longer displays learning count, correct rate, recent learning, or weak-point report metrics.
- AI explanation now goes to `/m/ai` with the bottom navigation still present. It carries `course_id`, `chapter_id`, `knowledge_id`, plus returned display names. The AI landing page presents that context before starting a chat.
- AI chat retains independent message scrolling and fixed safe-area composer; its header uses course/chapter/knowledge display names when the context supplied them.
- 11408 uses `AI智能训练`, not `AI预测`.
- A paper only shows `开始训练` when the service returned a valid paper year. The action creates a real server attempt and loads real server questions; it is not an inert button.

## Backend-limited items

- PC and Mobile use the same `knowledge-map/progress` field. It supports only `not_started`, `review_due`, `learning`, and `mastered`. These are truthfully labelled 未掌握、薄弱、一般、掌握. There is no separate server value for 熟练, so a fake fifth status was not added.
- The wrong-question API returns real count and list data, but no generic "retry this mixed wrong-question set" attempt contract was found. No inert `重新训练` button was added.
- A profile signature is shown only if returned by the existing profile API; no unverified signature-write capability was invented.

## Verification

### Static checks

| Check | Result |
| --- | --- |
| `npm.cmd run build` | PASS — generated `dist/assets/index-BpA9OTxA.js` |
| `npm.cmd exec eslint src/mobile/MobileApp.jsx` | PASS |
| Search for `AI预测`, `seed1`, `seed2`, `seed3`, `chapter_code`, report-only metrics in active Mobile source | No matching active Mobile UI strings |

### Browser checks

Local URL: `http://localhost:5173`

| Viewport | Routes checked | Result |
| --- | --- | --- |
| 360×800 | `/m`, `/m/learn`, `/m/ai`, `/m/11408`, `/m/profile` | Login guard rendered; no horizontal overflow; no console errors |
| 390×844 | Same routes | Login guard rendered; no horizontal overflow; no console errors |
| 412×915 | Same routes | Login guard rendered; no horizontal overflow; no console errors |

### Required cross-device verification

| Scenario | Result |
| --- | --- |
| PC changes mastery → Mobile refresh shows same status | BLOCKED: no authenticated PC/Mobile test session |
| Mobile changes mastery → PC refresh shows same status | BLOCKED: no authenticated PC/Mobile test session |
| Authenticated course / 11408 / AI / paper-attempt UI flow | BLOCKED: no authenticated browser session or supplied test account |

