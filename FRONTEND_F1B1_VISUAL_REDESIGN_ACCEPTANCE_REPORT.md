# FRONTEND_F1B1 Visual Redesign Acceptance Report

## 1. Before critique

The F1B1 baseline had correct real-contract behavior but repeated the same heading → description → divider → row structure across My Exam, setup, and catalogue. The configured exam page did not establish a focused identity field, setup read as browser-native settings rows, and framework-only state read as a generic empty state. The baseline screenshots are retained at `%TEMP%/zhixue-f1b1-vqa/screenshots/`.

## 2. Design direction and concept decisions

**Technical Editorial 70% + Academic Dossier 30%.** Warm paper remains the canvas; deep ink is reserved for active identity/focus; primary blue is the structural location marker; coral remains a non-textual accent. Numbering, long rules, chapter labels, and index/action columns create the technical-document rhythm. No gradient, glass surface, card grid, fake metric, progress claim, or invented learning content was introduced.

## 3. My Exam redesign

- Configured profiles use a deep-ink `01 备考档案` identity field containing only actual year, direction, and existing action.
- `02 科目范围` is an indexed learning path rather than an admin-like list.
- CS408 is the single integrated deep-ink active row with its factual modules and existing action.
- Framework-only subjects retain a deliberate, quieter index row and status action.
- Unconfigured profiles use the same dossier grammar without inventing a profile value.

## 4. Setup redesign

- Recast as a preparation configuration workbench with an editorial four-step rail.
- Native radio and checkbox inputs remain inside labels; selection is indicated by a rule and modest blue surface shift.
- The review area contains only selected direction, subject IDs, and target year, with the existing save action as its only primary action.

## 5. Subjects catalogue redesign

- Recast as `全国统考科目目录` / Academic Index.
- Backend-provided categories become chapter labels; rows use an index, factual metadata, status, and aligned action column.
- Active CS408 has an integrated ink-band treatment while framework-only rows remain selectable and intentionally quieter.

## 6. Framework-only redesign

- Recast as a content-status dossier with subject identity, actual availability language, selection relation, and existing actions.
- The adjacent construction uses only a non-semantic coordinate grid and outline: it represents no modules, progress, papers, or knowledge graph.

## 7. Shared visual primitives and tokens

- `DossierHeader`, `IndexRow`, `TechnicalRule`, and `ConfigurationStepRail` provide the practical shared pattern set.
- `exam-product-pages.css` confines the technical-editorial composition to F1B1 exam pages.
- **New tokens:** none. Existing paper, ink, blue, grid, typography, duration, and spacing tokens are reused.

## 8. Responsive and accessibility

- At 390px the configuration rail is a compact horizontal index; subject row actions move beneath identity content; no horizontal overflow was found in E2E smoke checks.
- The 1024px page preserves the dossier rather than treating tablet as stretched mobile.
- All controls retain native input semantics, associated labels, focus behavior, and 44px-scale interactive controls. Motion remains transition-only and is disabled by the global reduced-motion rule.
- Real-contract Axe scans: **0 violations**. Console errors in visual acceptance: **0**.

## 9. Before/after visual ledger

| Area | Before problem | After solution |
| --- | --- | --- |
| Composition | Repeated linear page skeleton | Dossier identity field, index structure, and workbench composition distinguish each page |
| Information density | Large passive regions with weak relationships | Aligned metadata, structural rules, and index/action columns carry real information |
| Brand continuity | Application pages lost the homepage's laboratory character | Deep ink, paper, blue coordinates, bilingual technical annotations, and editorial type reconnect the surfaces |
| Typography | Similar headings across unrelated page roles | Dossier titles, chapter labels, and metadata now have discrete editorial roles |
| Surface hierarchy | Paper read as a single flat plane | Paper canvas, ruled open regions, and one focused ink surface create four-level hierarchy |
| Row anatomy | Generic list rows with detached buttons | Number, identity, status, and action share one structured row |
| Action hierarchy | Every row treated action similarly | CS408 keeps the strong primary action; framework actions use a quieter text-style treatment |
| Mobile behavior | Desktop form/list stacked mechanically | Compact rail and reflowed index/action anatomy retain legibility and touch targets |

## 10. Screenshots

All captured with real F1B1 VQA contract fixtures at `%TEMP%/zhixue-f1b1-vqa/screenshots/`.

| Required capture | After file |
| --- | --- |
| 1440×900 My Exam | `desktop-exam-redesign.png` |
| 1440×900 Setup | `desktop-setup-redesign.png` |
| 1440×900 Subjects | `desktop-subjects-redesign.png` |
| 1440×900 Framework | `desktop-framework-redesign.png` |
| 390×844 My Exam | `mobile-exam-redesign.png` |
| 390×844 Setup | `mobile-setup-redesign.png` |
| 390×844 Subjects | `mobile-subjects-redesign.png` |
| 1024×768 My Exam | `tablet-exam-redesign.png` |
| Homepage desktop/mobile regression | `homepage-after-redesign-desktop.png`, `homepage-after-redesign-mobile.png` |

Before evidence used for direct comparison: `desktop-exam-configured.png`, `desktop-setup.png`, `desktop-subjects.png`, `desktop-math-1.png`, `mobile-exam-configured.png`, `mobile-setup.png`, `tablet-exam-configured.png`, and `tablet-exam-unconfigured.png` in the same directory.

## 11. Verification

- `npm run check` — PASS: 7 files / 19 unit tests.
- `npm run build` — PASS.
- `EXAM_VQA=1 npm run test:e2e` — PASS: 8 Chromium E2E tests, including real-contract configured/unconfigured/profile, framework-only, desktop/mobile/tablet captures, homepage regression, Axe, and console checks.

## 12. Changed files and final gates

- Frontend presentation/components, visual tests, smoke-test console filtering, and this report only.
- Backend files changed: **0**.
- Database migration: **not required**.

| Gate | Result |
| --- | --- |
| FUNCTIONAL_SEMANTICS_CHANGED | NO |
| MY_EXAM_VISUAL_REDESIGN | PASS |
| SETUP_VISUAL_REDESIGN | PASS |
| SUBJECT_CATALOG_VISUAL_REDESIGN | PASS |
| FRAMEWORK_VISUAL_REDESIGN | PASS |
| TECHNICAL_EDITORIAL_DIRECTION | PASS |
| ACADEMIC_DOSSIER_DIRECTION | PASS |
| GENERIC_AI_DASHBOARD_PATTERN / CARD_GRID_PATTERN | NO / NO |
| FAKE_METRICS / FAKE_CONTENT | 0 / 0 |
| DESKTOP / TABLET / MOBILE_VISUAL_QA | PASS / PASS / PASS |
| HOMEPAGE_VISUAL_REGRESSION | NO |
| AXE_VIOLATIONS / CONSOLE_ERRORS | 0 / 0 |
| TYPECHECK / LINT / UNIT_TESTS / BUILD / E2E | PASS / PASS / PASS / PASS / PASS |
| FRONTEND_F1B1_VISUAL_REDESIGN_COMPLETE | YES |
| FRONTEND_F1B2_READY | YES |

**Blockers:** None.

## VR2 application density polish

- Desktop dossier height is reduced from 15rem to 11.5rem (about 23%), the title scale is reduced by about 13%, and desktop page/section spacing is tightened so the first `/exam` viewport includes the dossier and active study-path content.
- `01` remains a structural index but is smaller and lower-opacity. The active 408 row remains the sole ink-active subject but is shorter, so it reads as a catalogue row rather than a second hero.
- Internal uppercase English microcopy was removed. `考研学习 / EXAM PREPARATION` remains the single space-level bilingual identity; page-level labels are Chinese-first.
- The catalogue's generated category letter was removed because it was not a backend-provided stable category identity.
- Setup and framework-only page structure is unchanged; only the same type/label density rules were synchronized.

| VR2 gate | Result |
| --- | --- |
| APPLICATION_INFORMATION_DENSITY | PASS |
| SECOND_HERO_EFFECT | NO |
| BILINGUAL_MICROCOPY_OVERUSE | NO |
| ACTIVE_408_HIERARCHY | PASS |
| HOMEPAGE_VISUAL_REGRESSION | NO |
| AXE_VIOLATIONS | 0 |

VR2 required screenshots were refreshed in `%TEMP%/zhixue-f1b1-vqa/screenshots/`: `desktop-exam-redesign.png`, `desktop-subjects-redesign.png`, `mobile-exam-redesign.png`, and `desktop-setup-redesign.png`.
