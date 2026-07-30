# Knowledge status audit

代码层面已改为使用 `user_id + course_id + knowledge_point_code` 隔离，C、C++、Python、Java 通过独立 course id 隔离；只有叶子节点显示状态管理按钮，父级只显示汇总统计。

线上 `http://101.32.190.42/` 已真实验证：Python 叶子“Python 语言特点与设计哲学”从“未学习”改为“学习中”，刷新后仍为“学习中”，再改为“已学习”（后端枚举值 `mastered`）。切换 C++ 后返回 Python，状态仍保持；选中父级时只显示汇总和“不能手动设置”，没有编辑按钮。

浏览器 Console 记录到 Statsig 对 `https://ab.chatgpt.com` 的外部请求超时；该错误与知识点接口无关，Network 仍需在浏览器 DevTools 中补充确认。
