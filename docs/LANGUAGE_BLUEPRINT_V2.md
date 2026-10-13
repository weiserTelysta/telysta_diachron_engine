---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: telysta-language-blueprint.v2
implementation_path: crates/telysta-core/src/blueprint.rs
implementation_constant: LANGUAGE_BLUEPRINT_SCHEMA
---

# LanguageBlueprint v2

- 状态：`Accepted`
- 完成日期：2026-07-14
- 工作包：`GEN-001.1`
- 实现：`crates/telysta-core/src/blueprint.rs`
- Wire schema：`telysta-language-blueprint.v2`
- 注册表 schema：`telysta-feature-registry.v1`
- 验证报告：`telysta-blueprint-validation-report.v2`

## 1. 定位

`LanguageBlueprint` 是可审计的用户意图合同，不是半成品 `LanguageState`。它记录用户
希望怎样的语言、依据是什么、哪些要求可权衡，但不直接生成音位、词条或语法结构。
领域编译器必须把 Blueprint 编译为合法 `StateTransaction`，并通过 Genesis 质量门。

Blueprint 使用规范 JSON、稳定 SHA-256、类型化实体 ID、整数 basis points 和严格
反序列化校验。相同文档产生相同 hash；v1 文档不得静默读成 v2。

## 2. Intent 与 Feature 分离

v2 的权威结构是 `intents: Map<IntentId, BlueprintIntent>`。每条 intent 独立保存：

- `featureId`：希望影响的语言特征；
- `desiredValue`：布尔、整数、类别、整数范围或类别集合；
- `control`：`locked`、`preferred`、`emergent` 或 `hypothetical`；
- `priorityBasisPoints`：多个可权衡意图间的确定性优先级；
- `evidenceIds`：证据、先验、研究假说或创作偏好的来源；
- `explanation`：供用户和专家审计的理由。

多个 Intent 可以指向同一个 Feature。经验先验和创作偏好因此能分别保留，不再被一个
map 槽位强迫合并。不同值的多个硬锁会报告 `locked_intent_conflict`；硬锁覆盖不同的
普通偏好会报告 `preference_overridden`，但不会抹掉原始意图。

控制方式与证据性质是两个维度：

| EvidenceClass | 可用 control |
|---|---|
| `hardConstraint` | `locked` |
| `empiricalPrior` | `preferred`、`emergent` |
| `researchHypothesis` | `hypothetical` |
| `creativePreference` | `locked`、`preferred`、`emergent` |

## 3. FeatureRegistry

Feature 的 domain、值域、允许的 control、依赖、不兼容项和编译器能力只由版本化
`FeatureRegistry` 定义。Blueprint 不重复声明 domain，避免 UI、协议和引擎各有一份
互相漂移的元数据。

当前内置注册表 `telysta-phonology-features.v1` 有 12 个音系/韵律入口：辅音与元音
音位数量、音长、声调、最大声母/韵尾规模、重音、音节重量、辅音群容忍度、元音和谐、
发声态对立和鼻化元音对立。每项都有明确值域，未知 feature 和错误值类型会返回结构化
诊断。

当前 12 项的 `compilerCapability` 都是 `planned`。这是一条刻意保留的真实性边界：
协议已经能验证用户要求，但领域编译器尚未证明能实现它们。

## 4. 两级验证

`validation_report(registry)` 区分：

1. 文档结构有效：身份、证据、控制、时间和数值边界合法；
2. 当前可编译：无错误诊断，且所有目标 feature 的能力都是 `supported`。

报告包含 Blueprint hash、注册表版本与 hash、按 domain 的意图计数、
`readyForCompilation` 和诊断列表。`compiler_unavailable` 是警告，但会使
`readyForCompilation=false`。UI 不得把“结构有效”显示为“可以生成”。

## 5. 项目与桌面边界

`validate_against_context` 额外检查 Blueprint 起始年份、模拟时域溢出、证据数据引用和
`ProjectDataLock`。正式 Genesis 还必须把 Blueprint hash、注册表 hash、规则包锁和 RNG
合同锁入运行上下文；这部分随 Genesis 编译器交付。

Tauri `validate_blueprint` 使用 Rust v2 类型和内置注册表返回同一份验证报告。
桌面 JSON inspector 发送 `blueprintJson` 原文，Rust 直接解析；JavaScript 的
JSON.parse 仅用于语法提示，解析结果不进入 IPC，避免 i64 改值或小数转成整数。
旧 `blueprint` typed 参数仍兼容；两种参数必须恰有一个非 null 值，双传/都缺失拒绝。
这是当前只读适配器的保真修复，不改变 schema、hash 算法或开放 Genesis。
JSON inspector 只是专家协议入口；未来 Quick/Expert UI 必须生成同一 wire
document，不能建立另一套参数模型。

## 6. 验收与路线交接

已覆盖 v2 round-trip、多 Intent 指向同一 Feature、v1 显式迁移、注册表值域、未知
feature、控制限制、依赖/不兼容诊断、锁冲突、编译器能力、RunContext 时间边界，以及
Tauri 命令级验证。

GEN-001.1 只完成输入合同修复，不授权直接修改生产领域 schema。当前先关闭 G0B，并在
G1 平台就绪、相关 ADR Accepted 后，以 WS-1 小纵切完成原 `GEN-001.2 Domain Model
Hardening` 所涵盖的 Blueprint、LanguageState、Registry、Compiler、typed change 与
GenesisArtifact 边界。`GEN-002 SpeechCommunity v1` 不再是 Genesis 之后的直接 Next，
它属于 Story Language Kit 之后的 G3B/WS-2。各 Genesis 编译器只有在真实实现和验证
完成后，才能逐项把 capability 从 `planned` 提升为 `supported`。
只有验证报告 `readyForCompilation=true` 且 Genesis 硬错误为零，桌面端才可开放项目创建。
