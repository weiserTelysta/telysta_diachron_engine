# Telysta Agent Operating Model

- 状态：`Accepted`
- 日期：2026-07-14
- 适用范围：Codex、Cursor、CI 修复 Agent、研究 Agent 与后续项目插件

## 1. 目标

Telysta 的 Agent 不是通用代码补全器，而是受证据和领域合同约束的共同研究者。Agent 必须同时保护三类正确性：

1. **软件正确性**：类型、事务、存储、迁移、回放和并发安全；
2. **模型正确性**：规则按定义改变正确的语言对象；
3. **科学有效性**：生成分布和历史轨迹有实证依据、独立验证和不确定性说明。

测试通过只能证明相应测试覆盖的性质，不能自动证明一门生成语言自然、可用或具有历史可信度。

## 2. 权威边界

| 领域 | 权威实现 | Agent 行为 |
|---|---|---|
| 生产语言状态、事件、模拟、存储 | Rust | 所有写入通过版本化命令、事务和迁移 |
| 旧输出基线、统计实验、数据分析 | Python | 只读对照或研究，不成为第二写入者 |
| 桌面交互 | Tauri + TypeScript/Svelte | 消费 Rust schema，不复制业务真值 |
| LLM | 可选辅助层 | 解析、提议、解释；不得直接提交状态 |
| 外部数据 | 版本化 manifest + payload lock | 记录来源、hash、许可证、覆盖和限制 |

可选产品 LLM 的 key 预留与默认关闭约定见
[开发环境第 9 节](./DEVELOPMENT_SETUP.md#9-可选-llm-的-api-key-预留)；它不控制开发
工具本身的登录，也不授权 LLM 或多 agent 直接提交语言状态。

## 3. Agent 工作闭环

```text
用户目标
→ 读取权威文档与代码证据
→ 分类 Hard Constraint / Prior / Hypothesis / Preference
→ 设计最小完整纵切
→ 实现与迁移
→ 工程验证
→ 语言学与科学验证
→ 解释变化、限制和剩余风险
```

研究、评审和诊断请求默认只读。只有明确要求实现或执行计划时才修改仓库。普通可逆、非持久化 Spike 可以在工作包中附带 Proposed ADR 供评审，但 Proposed 状态不授予生产实现权限。任何改变持久化实体意义或身份、事件回放语义、权威写入者或插件执行边界的改动都必须立即停止实现，先使对应 ADR 变为 `Accepted`；在此之前只允许文档、fixture 和明确不写正式状态的原型。

### 3.1 用户授权的 AI 本地开发审阅（2026-10-16）

用户明确要求“跳过人工审核的阶段”“先用 AI 代替”，不再等待专家到位。
此决定覆盖旧计划的具名人类 owner/reviewer、专家招募、人力容量及相应审批等待，
开发阶段改用真实独立 AI 会话完成架构、语言学、迁移/恢复与代码审阅。
执行协调者为 `/root`（AI），全局 WIP=1；每轮完成一个可审阅纵切并实际测试，
有阻断 finding 就修复后复审。记录代理身份、输入 hash、结论、范围与未完成项，
不得由作者自审代替独立审阅，不虚构人类、账号、工时或专家资历。

有效开发授权来自该用户决定、已接受的技术 ADR、独立 AI 审阅和对应本地软件门。
旧 G0A policy v2/GateEvidence v3 包含人类身份、远端 provenance 和跨平台发布
前置，其历史 `blocked` 结果保留，但不再作为本地开发的统一禁止开工信号。
不将它篡改成 passed，不伪造 remoteProvenance；当前本地平台检查支持本地实现，
未验证的 Windows/macOS、人工试用、专家认证和科学机制有效性仍不得宣称完成。
真实作者研究作为待取得的产品证据保留，不以 AI 模拟冒充，也不阻塞本地研发。

没有取消工程约束：改变实体/持久化/replay 仍须先完成对应 ADR 的独立 AI 接受；
Rust 唯一权威、版本化协议、typed validation、RngTree、事务、lease/CAS、历史
前缀、迁移与故障验证继续强制。计划中的能力不能显示为 supported，模型证据
与真实语言学/产品证据仍分开。AI 审阅取代审批人员，不取代这些实际证据。

首次平台合同接受及逐角色审阅记录见
[AI 本地开发接受记录](./evidence/AI_LOCAL_DEVELOPMENT_V1.json)。本轮先抽取现有
读会话 application 边界；ProjectManifest/RunLedger/JobStore 的具体生产格式、
writer 与迁移必须在后续独立实现切片中验证，不能从设计接受推断实现已完成。

## 4. 首批专用 Skill

### 4.1 `rust-domain-guardian`

触发范围：`LanguageState`、`ProjectManifest`、`Operation/Run/Job/Attempt`、`ProjectEvent/ChangeSet`、Genesis、RulePack、Storage、Migration。

输出：不变量列表、写入边界、迁移影响、回放影响、测试矩阵和阻断项。

### 4.2 `linguistic-architecture-review`

触发范围：音系、韵律、形态、构式、语义、语用、历时规则和语言质量结论。

输出：硬错误、不支持假设、缺失表达、经验先验、审美偏好和所需验证。

### 4.3 `simulation-validation`

触发范围：生成算法、概率参数、黄金场景、质量指标和专家发布门。

输出：确定性、多 seed 分布、敏感性、反事实、独立验证、异常 seed 和不确定性报告。

在前三项稳定后，再建设 `linguistic-data-governance`、`diachronic-rule-engineering` 和 `product-quality-lab`。

2026-07-14 已建立个人 `telysta-agent` v0.1.0 插件和以上三个首批 Skill，并通过结构验证。下一阶段使用真实的 schema 评审、生成结果审查和多 seed 验证任务进行前向测试；未经前向测试不宣称 Skill 已稳定。

## 5. 质量门

Agent 不得以“代码已完成”替代以下门：

- **Repository Gate**：一条命令检查、锁文件、格式、lint、测试；
- **Contract Gate**：schema、事件、数据和 RNG 均版本化；
- **Replay Gate**：在线状态和回放状态语义等价；
- **Genesis Gate**：硬错误为零，所有形式可分析；
- **History Gate**：变化有环境、时间、采用、重组和来源；
- **Usage Gate**：目标交流任务无随机 fallback；
- **Expert Gate**：审计材料完整且严重结构错误为零。

## 6. Agent 产物要求

核心改动的交付说明必须包含：

- 修改了什么领域能力；
- 对应 ADR、schema 和数据来源；
- 哪些语义 hash 或 fixture 改变；
- 运行了哪些测试；
- 哪些结论仍是假说；
- 已知限制和下一阻断项。

不允许使用“更自然”“更专业”“质量更高”而不给出可验证维度和证据。

## 7. 独立 AI 语言学审阅协议

用户已授权使用不继承作者对话的新模型会话。审阅者从仓库文件自行建立理解，
不得把作者说明、自测通过或其他审阅者意见当成正确性证明。三个方法指南位于：

- [形式模型与反例](../.agents/reviewers/linguistic-formal/AGENT.md)：身份、意义保持、双向分析和退化解；
- [跨语言实证与方法](../.agents/reviewers/linguistic-empirical/AGENT.md)：数据、抽样、论文证据与跨语言偏置；
- [历时解释与作者使用](../.agents/reviewers/linguistic-diachronic/AGENT.md)：过程、历史链、造句、读音与同版本文档。

指南是不同审查方法，不声称模型具有人类专家资历，也不扩大根 AGENTS.md 的权限。
共同要求：

1. 先检查 subject（HEAD、工作树 diff、相关 fixture hash），说明范围与读取限制；
2. 默认只读；实验放仓库外，严禁刷新 GateEvidence、修改 ADR 状态或用户资料；
3. 分别报告已复现软件/模型缺陷、草案决定缺口、实证不足与创作偏好；
4. 每项 finding 给出严重度、置信度、绝对路径/行号、触发反例、实际/预期结果、
   合同或一手证据依据，以及最小修订；不能复现时标注推断或待核实；
5. P0 为广泛权威/数据破坏或虚假发布结论；P1 为主要任务/领域不变量失效；
   P2 为有边界的错误或验收缺口；P3 为不阻断行为的清晰度问题。严重度依据
   当前范围的影响，不能仅因目标能力尚未实现便判为 P1；
6. 结尾列实际检查与未检查项。没有 finding 就明确说明，不凑问题、不宣布
   语言自然、ADR 接受或 Gate 通过；
7. 作者修复后独立复查原反例，记录仍存问题。结果在 WORK_LOG 汇总为 AI
   review；具名会话不自动替代 ADR 所需的 owner、完整合同接受与 Gate 证据。

不同审阅意见由主维护者按证据协调，不靠多数投票判定语言学真值；存在分歧时
保留各自依据与待验证项。科学结论和真实作者研究仍需相应独立数据。
