# Agent Skill Allowlist 与供应链规则

- 状态：`Accepted`
- 日期：2026-07-14
- 默认策略：未列入 allowlist 的网络 Skill 不得直接安装或运行

## 1. 已批准的官方 Skill

来源：`openai/skills` 的 `skills/.curated`，安装时使用官方 `skill-installer`，默认跟随 `main`。正式 CI 或团队镜像接入前应记录实际 commit。

| Skill | 状态 | 允许用途 | 禁止用途 |
|---|---|---|---|
| `security-best-practices` | Installed | Rust/Tauri/Python 安全编码审计 | 自动修改外部系统或凭据 |
| `security-threat-model` | Installed | 项目文件、规则包、IPC、LLM 和插件边界威胁建模 | 将威胁模型当成渗透授权 |
| `playwright` | Installed | 本地桌面 webview/前端流程和回归测试 | 未授权操作生产网站或用户账户 |
| `jupyter-notebook` | Installed | 类型学、音系、敏感性和统计实验 | 成为生产状态写入路径 |
| `gh-fix-ci` | Installed | 读取 GitHub CI 失败并提出或实施仓库内修复 | 合并、发布或更改仓库权限 |

这些 Skill 自 2026-07-14 起安装到用户 `CODEX_HOME`，从下一轮 Agent 会话开始可用。

## 2. 条件批准

以下 Skill 只有在相应产品阶段启动时才安装：

| Skill | 启用条件 |
|---|---|
| `figma-use` | APP 信息架构已有稳定任务模型 |
| `figma-create-design-system-rules` | 设计 token 与组件边界已决定 |
| `figma-implement-design` | Rust/TypeScript wire schema 已稳定 |
| `speech` | `PhoneticRealizer` 能输出确定性窄式表示 |
| `sentry` | 桌面测试发布且已决定遥测、隐私和保留策略 |

## 3. 社区 Skill 审查门

安装任意非 allowlist Skill 前必须：

1. 记录仓库、路径、commit、作者和许可证；
2. 完整阅读 `SKILL.md` 与所有引用文件；
3. 审查脚本、网络请求、子进程、文件写入和凭据访问；
4. 在隔离目录试运行，不接触真实项目和密钥；
5. 明确触发条件，避免与项目专用 Skill 竞争；
6. 记录卸载和回滚方式；
7. 经代码评审后才加入本 allowlist。

禁止从搜索结果直接执行脚本，禁止使用浮动 URL 作为发布构建依赖，禁止让 Skill 绕过仓库的事务、测试或审批边界。

## 4. 项目专用 Skill

个人 marketplace 已创建 `telysta-agent` v0.1.0，位置为 `~/plugins/telysta-agent`。它是
开发者本地可选工具，不随本仓库交付，也不能计入 clean-checkout 或产品能力。当前包含：

| Skill | 状态 | 作用 |
|---|---|---|
| `rust-domain-guardian` | Validated, awaiting forward test | 审查 Rust schema、事件、事务、回放和迁移 |
| `linguistic-architecture-review` | Validated, awaiting forward test | 审查语言学表达能力、因果历史和用户使用需求 |
| `simulation-validation` | Validated, awaiting forward test | 区分软件、模型与科学验证并设计证据矩阵 |

三项 Skill 和 `telysta-agent` plugin manifest 已通过官方 validator。结构验证只证明包格式有效；在真实任务中观察触发准确性和输出质量前，不将其标记为成熟。

项目专用 Skill 优先复用仓库脚本和权威文档，不在 Skill 中复制大型领域规范。每个 Skill 必须说明：

- 精确触发条件；
- 必读合同；
- 允许的读写范围；
- 输出 schema；
- 必须运行的门；
- 停止条件和人工评审点。
