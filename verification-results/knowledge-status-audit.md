# Knowledge status audit

代码层面已改为使用 `user_id + course_id + knowledge_point_code` 隔离，C、C++、Python、Java 通过独立 course id 隔离；只有叶子节点显示状态管理按钮，父级只显示汇总统计。

本轮浏览器实际打开了 `http://localhost:5173/`，当前用户只有 11408 入口，没有编程方向入口，因此未执行线上状态修改和刷新恢复。`online_verified=false`，不得据此宣称验收通过。
