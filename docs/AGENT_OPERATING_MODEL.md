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
