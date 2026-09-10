# Frontend Review Checklist

权威规范：`docs/UI_DESIGN_SPEC.md`。本清单是其「审核视角」的逐项展开。
每项只允许三种结论：PASS / FAIL / N/A（不适用时注明原因）。

## A. Design Tokens 与一致性

> 判定原则：检查项目**当前**的 Design Token implementation（具体位置由 frontend
> architecture 决定，不固定为某个文件路径）。frontend 已初始化但不存在统一 token
> system → FAIL；frontend 尚未初始化 → 本节整体判定为 N/A（而非 FAIL）。

- [ ] 颜色是否来自当前 Design Token implementation 的语义 token，无随机 hex（如 `#2761ef`）
- [ ] 字号是否来自 token 层级，无随机字号
- [ ] 圆角是否来自统一 scale，无 `10/14/18/22/24/28px` 等随机值
- [ ] shadow 是否来自 token，无黑色重阴影 / 大面积漂浮
- [ ] spacing 是否使用固定 scale，无 `margin-top: 37px` 之类魔法值
- [ ] 是否出现无意义 gradient（按钮/文字/背景渐变滥用）
- [ ] 是否出现 glassmorphism（大面积 backdrop blur）
- [ ] 是否出现 glow / neon / 发光边框
- [ ] 过渡时长/缓动是否统一（未到处硬编码）

## B. 结构与组件

- [ ] 是否有 Card abuse（标题、导航、大区块都套 Card）
- [ ] 是否有 Card 套 Card 套 Card
- [ ] 是否用 emoji 代替 UI icon（应统一用 Lucide 等 icon library）
- [ ] typography hierarchy 是否清晰（size + weight + whitespace，非大量颜色）
- [ ] button hierarchy 是否清晰（Primary / Secondary / Ghost / Danger）
- [ ] 一个视觉区域是否只有一个 Primary
- [ ] Primary action 是否明确（用户一眼知道下一步做什么）

## C. 学习任务优先

- [ ] 页面是否回答了「在哪 / 学到哪 / 下一步做什么」
- [ ] 首屏是否只有非常明确的 Primary Action，而非大量同权重 CTA
- [ ] 是否「功能入口优先」而非「学习任务优先」（若功能优先 → FAIL）
- [ ] 是否像管理后台式学生首页 / 大量无意义 KPI

## D. 状态与反馈

- [ ] Loading 是否用 Skeleton 而非整页 spinner
- [ ] Empty State 是否说明「为什么为空 + 下一步做什么」
- [ ] Error State 是否统一且有文字说明
- [ ] Toast 是否统一

## E. Responsive 与 Accessibility

- [ ] Desktop / Tablet / Mobile 是否都覆盖（移动端非简单缩小）
- [ ] Sidebar→Drawer、多栏 Workspace→Tabs/Stacked、Card 3→2→1 是否正确降级
- [ ] contrast 是否足够
- [ ] keyboard focus 是否可见
- [ ] icon button 是否有 aria-label / tooltip
- [ ] 图片是否有 alt
- [ ] 状态是否不只靠颜色表达
- [ ] 点击区域是否足够
- [ ] 表单错误是否有文字说明

## F. 文案

- [ ] 文案是否短、具体、明确、行动导向
- [ ] 是否出现「开启智慧学习之旅 / AI 赋能未来 / 解锁学习潜能」等模板化文案
- [ ] 按钮是否使用动作型文字（继续学习 / 开始练习 / 运行代码…）

## G. 边界与保护

- [ ] 是否修改了 backend / 数据库 / API（若仅为视觉需求 → FAIL）
- [ ] 是否删除/重命名/移动了 `reference/`、`design/`、`design-references/` 素材
- [ ] 是否删除现有真实业务能力

## H. 工程验证（如实报告）

- [ ] lint（无脚本则标注 N/A）
- [ ] typecheck（无脚本则标注 N/A）
- [ ] tests（无测试则标注 N/A，**不得伪造通过**）
- [ ] build（无脚本则标注 N/A）

---

## 结论

- 任一「必须项」FAIL 且未被修复 → 总结论 `FAIL`。
- 全部通过或仅剩已记录在案的豁免 → `PASS`。
- 输出：PASS/FAIL + 具体文件 + 问题 + 修改建议。
