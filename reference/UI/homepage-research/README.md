# Homepage Design Research

设计参考截图（只读研究用，正式前端代码不得引用这些截图）。

> 说明：截图为真实浏览器访问公开首页所得。部分 SPA 站点在无登录/首次加载状态下可能是
> 未完全渲染的骨架屏（如 khan/datacamp 文件较小）；设计要点以文字结论为准，截图仅作
> 方向参考，非逐像素模仿对象。

| filename | product | source URL | capture date | what to learn | what NOT to copy |
| --- | --- | --- | --- | --- | --- |
| `brilliant_home_reference_01.png` | Brilliant | https://brilliant.org/ | 2026-09-10 | 用「可交互的图形/示意图」而不是文字卡片承载内容；留白与 typography 建立品质；首页第一焦点是「体验」而非「入口目录」 | 不要复制其具体插画/交互实现 |
| `codecademy_home_reference_01.png` | Codecademy | https://www.codecademy.com/ | 2026-09-10 | 把「继续学习」+「进度」作为首页核心；课程/技能用有辨识度的封面承载；内容优先于工具导航 | 不要照搬其暗色/具体组件 |
| `datacamp_home_reference_01.png` | DataCamp | https://www.datacamp.com/ | 2026-09-10 | 学习路径/职业轨道可视化；课程封面有独立视觉；progress 沿路径表达 | 不要照搬其 track 卡片与配色 |
| `khan_learner_home_reference_01.png` | Khan Academy | https://www.khanacademy.org/ | 2026-09-10 | 颜色按「语义+强度」组织（Subtle/Default/Strong），颜色表达含义而非装饰；learner home 内容优先 | 不要照搬其具体 token 命名/组件 |
| `coursera_home_reference_01.png` | Coursera | https://www.coursera.org/ | 2026-09-10 | 课程卡带缩略封面（真实课程视觉），搜索/分类驱动；封面让内容有视觉重量 | 不要照搬其营销/搜索型首页结构 |

## 共性结论（为什么它们不像 admin dashboard）

1. **内容有视觉载体**：课程/科目用封面、图示、路径节点表达，而不是纯文字标签列表。
2. **首页有单一视觉焦点**：第一眼是「继续学习 / 下一步 / 体验」，而不是并排的等权卡片矩阵。
3. **进度是可感知的路径/图形**，而不是每个卡片里塞一条灰色 progress bar。
4. **颜色有强度与语义层次**，不是「白卡片 + 灰底 + 一个蓝按钮」。
5. **Card 是选择性使用**，且尺寸/构成随内容变化，不是所有区域同一种圆角矩形。
6. **Typography 承载个性**，标题/正文有明显层级与节奏，而非纯中性文案。
