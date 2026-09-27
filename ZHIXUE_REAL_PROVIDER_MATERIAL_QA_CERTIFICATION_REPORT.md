# ZHIXUE_REAL_PROVIDER_MATERIAL_QA_CERTIFICATION_REPORT

**轮次**：真实 LLM provider 的 Material → Retrieval → Answer → Citation 最终认证。
**日期**：2026-09-22 ｜ **未 commit / 未 push / 未 deploy** ｜ `HEAD = 8b4d0b6e`（保留）。
**范围**：未重设计页面，未新增功能。本轮**未改动任何产品代码**（只新增测试与验收脚本）。

---

## 1. 环境

| 项 | 值 |
|---|---|
| provider 凭据 | **存在**（仅报告存在性，全程未输出任何 secret；`backend/.env` 未被本会话直接读取，由应用自身 `load_dotenv()` 载入） |
| 运行方式 | **独立隔离运行时**，非 canonical harness（原因见下） |
| 数据库 | temp DB `.f1c6tmp/realqa/real.db`，`alembic upgrade head` 从零建立 |
| provenance | `DATA_ORIGIN=TEST` + `APP_ENV=test` → `EXCLUDED_FROM_TRAINING`，训练导出永不采纳 |
| 用户数据 | `e2e_seed.seed()` 新建的 `realqa_learner`，非 production 用户 |
| `backend/app.db` | **全程未触碰**：md5 `5ed902ec…` / size 64917504 / mtime Sep 20 12:03，前后一致 |
| 密钥泄漏检查 | uvicorn 日志扫描 `sk-*` / `api_key=` → **0 命中** |

**为什么不用 canonical harness**：`scripts/e2e_harness.py` 明确 scrubs 每个 `*_API_KEY`
（"Never inherit a real provider credential into the harness process"）。这是它正确的安全属性，
我没有为了本轮去改它。因此用了一个同样隔离、但保留真实凭据的独立运行时：
自有 temp DB、`TEST` provenance、非 production 用户、真实 AI Gateway / Router / provider contract。

**真实调用量**：2 次补全（1 次 API 级 + 1 次 UI 级）。无批量调用。

---

## 2. 唯一事实与对照

- `frontend/.iaaccept/acceptance-fixture-alpha.md`：含
  `ZX_ACCEPTANCE_FACT_921 = 红杉算法的冻结窗口为 37 分钟。`
- `frontend/.iaaccept/acceptance-fixture-beta.md`（对照）：主题为循环队列与顺序存储二叉树；
  **刻意不含** 红杉算法 / 冻结窗口 / 37 分钟，也不含任何关于该事实的元描述。

---

## 3. 全链路真实执行（无 stub generator）

```
UPLOAD       POST /course-learning/courses/{数据结构}/materials   HTTP 200,200  multipart/form-data
PARSE        alpha/beta parse_status = success，各 1 个 chunk（已等待真实解析完成）
PERSISTENCE  两份资料出现在课程资料列表
INDEX        material_chunks + material_chunks_fts 均有行
RETRIEVAL    rag_sources = ["acceptance-fixture-alpha.md"]；references[0] alpha，score 28.1
             CONTROL_MATERIAL_CITED = NO（beta 未被召回）
GATEWAY      经过应用自身的 AI Gateway → Router → provider adapter（唯一已配置凭据的那家）
ANSWER       11.7s 生成，非模板；正文给出 37 分钟
CITATION     引用资料（1）→ acceptance-fixture-alpha.md + 该资料原文摘录
HISTORY      刷新后回答与引用均恢复
```

### 答案原文（真实 provider 输出）

> 一、核心回答
> 根据你资料库中的内容，**红杉算法的冻结窗口是 37 分钟**。
> 二、原因说明
> 资料片段 `acceptance-fixture-alpha.md` 明确给出唯一事实：
> `ZX_ACCEPTANCE_FACT_921 = 红杉算法的冻结窗口为 37 分钟`
> 因此，仅依据这门课程提供的资料，答案就是 **37 分钟**。
> 三、建议操作 …当前问题的答案只应依据资料确定为 **37 分钟**。

---

## 4. PASS 条件逐条核对

| 条件 | 结果 |
|---|---|
| uploaded material appears in material list | **YES** |
| parse/index complete | **YES** |
| retrieval evidence contains uploaded material | **YES**（`rag_sources` 与 `references` 均指向 alpha） |
| control material is not cited | **YES**（beta 未被召回，也未出现在引用块） |
| assistant answer contains the unique fact semantically | **YES**（明确表述为 37 分钟） |
| assistant answer does not invent contradictory value | **YES**（全文仅出现 37 分钟，无其他分钟数） |
| citation points to the uploaded material | **YES**（`acceptance-fixture-alpha.md`） |
| citation excerpt contains supporting evidence | **YES**（摘录含 `ZX_ACCEPTANCE_FACT_921 … 37 分钟`） |
| learner UI does not expose raw material id / request_id / internal metadata | **YES**（无 `material_id` / `chunk_id` / `request_id` / provider 名） |
| refreshed chat history preserves answer + citation | **YES** |

---

## 5. Retrieval regression（新增，8 条）

`backend/tests/test_rag_cjk_retrieval.py` —— 覆盖你列出的五项：

1. 精确中文关键词可召回 —— `红杉算法` → alpha
2. 问句式中文可召回 —— 多个中文问句（含 `冻结窗口有多长？` / `红杉算法保持排他的时间是多少？` /
   `调度周期内同一资源的最长占用时间是多久？`）均召回 alpha，**不只一个 acceptance phrase**
3. 无关资料不因通用二字词误召回 —— gamma 整篇不因通用词被召回
4. relevant material 排名优于 control —— alpha 为第 1 且分数严格大于其后
5. 英文/数字查询不回归 —— `ZX_ACCEPTANCE_FACT_921` 仍按整 token 命中，且**不**为标识符生成二字组；
   `what is the freezing window` 仍产出 FTS 词

另加一条**逆向证明**（`test_the_pre_fix_tokenizer_failed_on_a_paraphrased_question`）：
回放修复前的分词器，对「资料写 `顺序表与链表的区别`、问题问 `顺序表和链表的区别`」这类**改写式提问**
返回 0；而对逐字复述的提问仍然有结果 —— 这正是该缺陷长期未被发现的原因。

> **本轮的自我更正**：上一轮我在报告里写「中文问句检索从来没有工作过」，这句话**过强**。
> 准确说法是：**当提问改写了资料措辞时**它才失败（一字之差即可），逐字复述时它一直有效。
> 上面的逆向测试把这个真实失败模式钉死了。

---

## 6. Course QA history（未重做，只确认）

本轮用**真实 provider 的答案**再走一遍并刷新：

```
REFRESH_PRESERVES_ANSWER   = YES
REFRESH_PRESERVES_CITATION = YES
COURSE_QA_TWO_TURN_HISTORY = PASS   （上一轮结论，代码本轮未改，仍然成立）
PERSISTENT_COURSE_QA_HISTORY = YES
```

---

## 7. 闸门

```
backend full suite   1809 passed, 2 skipped, 0 failed   (16:21)   ← 含本轮新增 8 条
frontend typecheck   PASS
frontend lint        PASS (0/0)
frontend vitest      318 passed / 64 files (bounded workers)
frontend build       PASS
check:api-origin     PASS (124 artifacts, no loopback)
app.db               md5 前后一致 → UNCHANGED
```

---

## 8. 输出

```
REAL_PROVIDER_AVAILABLE   = YES
REAL_PROVIDER_PATH        = 应用自身 AI Gateway → Router → 已配置凭据的 provider adapter
                            （独立隔离运行时 127.0.0.1:8013，TEMP DB，DATA_ORIGIN=TEST，APP_ENV=test）
UPLOAD                    = PASS
PARSE                     = PASS
RETRIEVAL                 = PASS
CONTROL_MATERIAL_CITED    = NO
ANSWER_CONTAINS_UNIQUE_FACT = YES
CITATION_SUPPORTS_ANSWER  = YES
REFRESH_PRESERVES_CITATION = YES
CHINESE_RETRIEVAL_REGRESSION = PASS（8 条：关键词 / 多问句 / 精度 / 排名 / 英数与标识符 / 逆向证明）
MATERIAL_QA_CITATION      = PASS
COURSE_QA_TWO_TURN_HISTORY = PASS
P0_REMAINING              = 无
P1_REMAINING              =
- 检索精度（已知、已量化、非阻塞）：中文二字组对通用词区分度有限。本轮用三份同课资料验证
  无关资料不被误召回；若单课程资料量大幅增长，需重新评估是否加入最低分阈值。
- canonical harness 无法做真实 provider 验收（设计如此）。若要把它纳入常规回归，
  需要一个"保留真实凭据"的独立 harness 变体；本轮未改 harness。
READY_FOR_USER_VISUAL_REVIEW = YES
```

**两点实话**：本轮把上一轮 `MATERIAL_QA_CITATION = FAIL` 的**唯一缺口（generator）真正关闭了** ——
用的是真实模型，答案复述了资料中的唯一事实，且只引用了承载该事实的那份资料；
所有结论均来自结构化证据与真实链路，**没有任何一项凭截图判定**。
