# 作者流程研究原型

对应 `R0B-06P / FormativeJourney.r0b`。在浏览器打开 [index.html](./index.html)，
或在仓库根目录运行 `python3 -m http.server 8080 --bind 127.0.0.1` 后访问
`http://127.0.0.1:8080/experiments/meaning-workbench/`。

原型探索描述需求、输入自有 canon、关联 5–10 项人工意图笔记、固定例句的
八项澄清练习、比较方案概念、回看缺口和
导出 Markdown 研究草稿。方案没有生成器，历史/音频没有伪造输出；选择只表示
作者偏好。`telysta-formative-draft.v1` 是研究笔记标识，不是语言、Blueprint、
TaskPack 或正式 JourneyPack schema。没有 Rust/Tauri 桥接、网络请求或持久化；
仅用户点击导出时下载自己的草稿。

视觉采用 [Rosé Pine](https://rosepinetheme.com/palette/)；颜色为创作偏好。
包含键盘焦点、原生表单、状态提示与窄屏布局。浏览器自动化只验证交互和布局，
不能宣称 WCAG 认证、非专家可用性或 G0B 通过。

```bash
node --test experiments/meaning-workbench/app.test.cjs
```

可选的真实浏览器检查：在独立开发工具环境安装 `playwright==1.63.0` 及其
Chromium，再用该环境的 Python 执行
`python -I scripts/check_workbench_browser.py`。检查离线加载、中文导出、编辑后
草稿失效、文本注入防护、键盘焦点及 390/720 CSS px 重排；截图与导出保存在
`target/workbench-browser/`。720 px 仅模拟 1440 px 窗口 200% 时的重排宽度，
不替代手动浏览器缩放或辅助技术测试。工具依赖不进入生产锁文件。

形成性试用前固定以下协议，再邀请作者使用自己的 3–5 条创作材料：

1. 先记录替代工具、既有工作流、目标与不愿改变的 canon，不展示“预期正确答案”。
2. 作者以“材料序号 | 意图”将 5–10 项笔记关联到自有材料，保留未知项；
   再做固定过河句的八项澄清练习。练习选择数不能计作真实材料意图任务成功。
   研究者与作者核对每项关联和意义；原型仅检查序号，不自动分析或判定成功。
   比较两个方案，说明未知项与草稿的用途；编辑材料后必须重新核对序号关联。
3. 观察误以为已经生成语言/验证历史/播放声音的情况，按误完成记录；不靠满意度计成功。
4. 记录求助、失败、恢复和放弃原因；键盘与 200% 缩放参与任务，允许拒绝或退出。
5. 经作者允许再保留导出草稿。原始材料与身份留在本地；不把 synthetic 演示记作真实作者证据。

本轮无真实参与者，研究结果为 **尚未采集**。自测不能填补独立 reviewer、
样本、正式产品 evidence contract 或 Accepted ADR。下一步应根据真实失败
修订流程，再由 R0B-06 映射为正式合同；不得从本原型复制权威语言 schema。
