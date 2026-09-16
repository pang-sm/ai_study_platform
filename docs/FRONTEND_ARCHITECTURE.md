# 前端架构决策（Frontend Architecture）

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文档负责**工程架构**，从属于 SSOT；冲突时 SSOT wins。
> 视觉规则以 `docs/UI_DESIGN_SPEC.md` 为准，视觉方向以 `docs/design/ZHIXUE_VISUAL_DIRECTION_V1.md` 为准。

> 智学AI 全新前端（`frontend/`）的长期架构约定。本文记录**决策与边界**，不记录过程日志。
> 当前前端状态见 SSOT §3 / §38：`frontend/` 只有 Clean-Slate 骨架与首页，全新前端 = `NOT_STARTED`。

## 技术基线

- **Runtime**：Node.js 24（`engines` 锁定 `>=24`），npm 为唯一包管理器（禁用 pnpm/yarn/bun）。
- **构建**：Vite 8（Rolldown 内核）。
- **UI**：React 19.2（自动 JSX runtime），不使用 Next.js / SSR / RSC。
- **语言**：TypeScript 5.9，`strict` + `verbatimModuleSyntax` + `noUncheckedIndexedAccess` 等开启。
- **React Compiler**：**DEFERRED**。`babel-plugin-react-compiler@1.0.0` 已稳定，但启用需在 oxc 内核的
  `@vitejs/plugin-react@6` 之上叠加 babel 转换层，本阶段不为稳定性引入；后续可单独开启。

## 架构决策

| 关注点 | 选择 | 说明 |
| --- | --- | --- |
| 路由 | TanStack Router（file-based） | route/params/search 全类型安全，路由级 code-splitting（`autoCodeSplitting`） |
| 服务端状态 | TanStack Query v5 | 禁止 `useEffect + fetch + setLoading` 模式 |
| 表单 | React Hook Form + Zod | `@hookform/resolvers` 集成，本轮仅搭依赖 |
| 运行时校验 | Zod 4 | 环境变量、URL/search params、外部输入 |
| 样式 | Tailwind CSS 4 + CSS 变量 Design Token | Tailwind 是实现工具，`UI_DESIGN_SPEC.md` 是规范 |
| UI primitive | Radix Primitives | 复杂交互（Dialog/Tooltip…）的 behavior/ARIA 层，视觉由本项目 Design System 负责 |
| Icon | lucide-react | 全站唯一 icon library |
| API 客户端 | openapi-fetch + openapi-typescript | 后端 OpenAPI schema 为契约源 |
| 测试 | Vitest + RTL + Playwright | unit/component + E2E |
| a11y | eslint-plugin-jsx-a11y + @axe-core/playwright | 基础检查自动化 |

## State Ownership（状态归属）

- **Server State** → TanStack Query
- **URL State** → TanStack Router（search params）
- **Form State** → React Hook Form
- **Local State** → `useState` / `useReducer`

**本轮不引入** Redux / Zustand / Jotai / MobX。出现真实跨域 client state 需求后再评估 Zustand。

## API 契约（Contract）

```
FastAPI OpenAPI (/openapi.json)
  → openapi-typescript
  → src/types/api.ts（generated，提交进 Git）
  → src/lib/api/client.ts（openapi-fetch createClient<paths>）
  → TanStack Query
  → React
```

- 所有 API 访问必须经 `src/lib/api/client.ts`，组件内禁止 `fetch('/api/...')`。
- 禁止手写 backend DTO 接口；以 `src/types/api.ts` 为唯一类型来源。
- 重新生成：启动 backend 后运行 `npm run api:generate`。
- 环境变量：`VITE_API_BASE_URL`（公开构建数据；**禁止**写入任何 secret / API key）。

## 目录边界

```
src/
  routes/        # 文件路由（TanStack Router，业务页面只加这里）
  components/ui/ # 无业务语义的基础 UI（Button/Container/Spinner/Skeleton）
  components/layout/ # App Shell / NotFound / ErrorState
  features/      # 未来业务特性（auth/courses/postgraduate/programming/…），按需建立
  lib/api/       # 类型化 API client
  lib/query/     # QueryClient
  lib/           # env / utils 等通用模块
  styles/        # tokens.css（Design Token）+ index.css（reset/base）
  types/         # 生成的 API 类型（api.ts）
  test/          # 测试 setup
tests/e2e/       # Playwright
```

## 测试

- `npm run typecheck` / `npm run lint` / `npm run test:run` / `npm run build` / `npm run test:e2e` 均需通过。
- `npm test` 为 watch 模式；CI/Agent 用 `test:run`（不卡住）。
- E2E 通过 Playwright `webServer` 自动启动 dev server；为绕过本机代理，配置了 `NO_PROXY` 与
  `--no-proxy-server`（见 `playwright.config.ts`）。

## 明确禁止（本轮及长期）

Next.js / Nuxt / Remix / TanStack Start / SSR / RSC / Micro Frontend / Module Federation /
Redux / Zustand（暂）/ GraphQL / Apollo / tRPC / shadcn 完整初始化 / Material UI / Ant Design /
Bootstrap / Chakra / Mantine / Styled Components / Emotion / Framer Motion。

## 依赖纪律

- 每增一个 dependency 需回答「解决什么实际问题」；几十行能解决的不过度引入。
- 禁止 beta / rc / canary / experimental；`package-lock.json` 纳入 Git。
- 不使用 `npm audit fix --force`。

## 安全边界

- 禁止 `dangerouslySetInnerHTML`（除非显式 sanitize）。
- 禁止 client secret（API key / token）。
- localStorage 只存非敏感 UI 状态。

## 视觉规范优先级

`docs/UI_DESIGN_SPEC.md`（最高）→ 代码级 Design Token（`src/styles/tokens.css`）→ Tailwind Theme →
Shared UI Components → 业务页面。通用 Skill（frontend-design 等）只是辅助执行方法，不得覆盖项目规范。
