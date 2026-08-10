# 公告与 Onboarding 最终生产验收

- 正式站点：`http://101.32.190.42/`
- 统一入口：`/register`、`/login`
- 业务基线：`f7f39da`
- Actions：`31365399020`（success）
- `/api/health`：`200`
- 本轮：`No new business deployment required`

## 最终状态

- `ANNOUNCEMENT_CLEANUP_VERIFIED`
- `ONBOARDING_RETURN_FLOW_VERIFIED`

## Fresh user 与新增方向验收

使用产品正常注册创建专用 QA 账号：`onboarding_acceptance_1786359273255`。密码未写入源码、Git 或报告。

| 验收项 | 状态 | 证据 |
|---|---|---|
| Fresh user registration | PASS | `/register` → 注册成功 → `/api/me=200` |
| First onboarding Back | PASS | 第 1 步 → 第 2 步 → 上一步 → 第 1 步 |
| Back preserves expected state | PASS | 未跳个人主页、已注册首页或旧 UI |
| Complete Programming onboarding | PASS | 真实 UI 选择 Python / 零基础 / 免费模式 |
| Programming active track | PASS | `/api/me` 返回 `active_track_type=programming` |
| 11408 initially unregistered | PASS | API 中无 active `exam_408` track |
| Programming → 11408 onboarding | PASS | Profile → 切换到 11408，进入 onboarding |
| 11408 Cancel | PASS | 点击“取消并返回” |
| Return to Programming | PASS | 回到新版 Programming Home |
| active track unchanged | PASS | 取消后仍为 `programming` |
| 11408 not falsely completed | PASS | 取消后无 active `exam_408` track |
| Refresh persistence | PASS | 刷新后仍为 Programming Home，active track 仍为 `programming` |
| No legacy UI | PASS | 未出现旧页面或旧导航 |
| Console business errors | PASS | 0 |
| Unexpected Network failures | PASS | 0 |

## 公告验收

- 空标题、空内容、单字符测试值：后端均返回 `400`。
- 合法公告：管理员发布后普通用户可见。
- 撤销后：`/api/announcements/active` 不再返回该公告。
- 正式环境历史测试公告 `id=1`、`id=2` 已撤回，未删除真实历史记录。
- 验收公告已清理。

## QA 账号最终状态

- 账号：`onboarding_acceptance_1786359273255`
- 创建方式：产品 `/register`
- 最终 active track：`programming`
- `exam_408`：未完成、未激活
- 未修改已有正式用户，未手工写入 tracks、onboarding 或 membership。
- 账号保留为 QA 复现账号，未删除、未停用；密码不记录。

## 截图

- [fresh-user-registration-onboarding.png](screenshots/fresh-user-registration-onboarding.png)
- [fresh-user-onboarding-back.png](screenshots/fresh-user-onboarding-back.png)
- [programming-package-free-plan.png](screenshots/programming-package-free-plan.png)
- [programming-to-exam-onboarding-new-account.png](screenshots/programming-to-exam-onboarding-new-account.png)
- [programming-restored-after-exam-cancel-new-account.png](screenshots/programming-restored-after-exam-cancel-new-account.png)
- [programming-restored-after-exam-cancel-refresh.png](screenshots/programming-restored-after-exam-cancel-refresh.png)

详细机器结果：[final-onboarding-acceptance.json](final-onboarding-acceptance.json)
