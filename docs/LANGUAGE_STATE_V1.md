---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: telysta-language-state.v2
implementation_path: crates/telysta-core/src/state.rs
implementation_constant: LANGUAGE_STATE_SCHEMA
---

# Canonical LanguageState v2（含 v1 迁移基线）

> `LanguageState` 的当前持久化 schema 已升级为 `telysta-language-state.v2`，以保存
> 精确时间模型指纹。v1 时间引用只能通过 [Time Model v2 Migration](./TIME_MODEL_V2_MIGRATION.md)
> 中定义的显式迁移进入当前格式；本文其余状态建模约束仍作为设计基线。

- 状态：`Accepted`
- 完成日期：2026-07-13
- 对应工作：`B-002`、`FND-002`
- 实现：`crates/telysta-core/src/state.rs`

`telysta-language-state.v2` 是当前 Rust 实现中一门语言在任意历史时点的唯一语义快照。v1
保留为显式时间迁移基线。两者都不复刻 Python `EngineHotState`，也不是 UI、缓存或任务
运行时的容器。

## 语义状态

```text
LanguageState
├── language identity + versioned time reference
├── evidence records + typological assertions
├── phonology + prosody
├── morphology + constructions
├── lexicon + sense graph + registers
├── orthography
├── family position
└── provenance ledger
```

音位、词素、构式、词位、义项、家族节点、类型学特征和证据均使用稳定的 `EntityId`。每个当前语义实体都必须具有 provenance：创建事件、时间模型版本、事件类别和证据引用。状态拒绝缺失来源、无效引用、孤立义项、未知音位、错误语体、错误实体类型或晚于状态时点的来源记录。

## 证据与偏好边界

每条证据记录属于以下之一：

- `HardConstraint`：违反即拒绝；
- `EmpiricalPrior`：改变候选或过程的权重；
- `ResearchHypothesis`：可关闭、需明确引用；
- `CreativePreference`：用户创作选择，不表述为经验规律。

非创作类证据必须有 citation。每一条类型学断言必须至少引用一条证据记录；这防止无来源的“类型学事实”直接进入语言状态。具体的 CLDF 数据集、许可证、版本和抽样记录由 [Data Governance v1](./DATA_GOVERNANCE_V1.md) 的 manifest 合同提供。

## 规范化与派生视图

所有集合使用稳定 ID 排序；`canonical_json()` 在序列化前重新验证状态。`CorpusStatistics` 由 state 计算，包含音位、词素、构式、词位、义项和语体数量，但不参与持久化或语义 hash。日志、缓存、搜索索引、UI 选项、任务进度和随机生成器状态同样不得进入 `LanguageState`。

## 已知边界

v2 定义当前单语言语义快照。项目级 `RunContext`、数据锁、版本化事件信封与
`StateTransaction` v1 已由 [Project Runtime and Transactions v1](./PROJECT_RUNTIME_V1.md)
定义；它以完整状态修订保证回放边界，但尚未定义：

- 词汇、DAG、类型学、语法和接触的细粒度事件 payload，以及项目原子存储；
- `SpeechCommunity`、完整 `FamilyGraph`、迁徙和接触执行器；
- Feature Registry、实际 payload 导入和经验先验抽样；
- 祖语编译器、RuleSpec、范式实现或质量评分。

这些边界是刻意保留的：schema 先保证能承载它们，而不在缺少证据与纵切验证时伪造语言学结论。

## 验收

核心测试验证最小语言 state 的 canonical JSON round-trip、派生统计不泄漏到语义序列化、provenance 覆盖、音位/词位引用完整性，以及从外部 JSON 加载时的同等校验。
