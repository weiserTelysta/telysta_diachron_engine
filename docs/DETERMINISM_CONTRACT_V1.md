---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: telysta-rng-tree.v1
implementation_path: crates/telysta-core/src/rng.rs
implementation_constant: RNG_TREE_SCHEMA
---

# Determinism Contract v1

- 状态：`Accepted`
- 完成日期：2026-07-13
- 对应工作：`B-003`、`FND-003`、`FND-004`；项目级绑定见 `B-004`
- 实现：`crates/telysta-core/src/hash.rs`、`crates/telysta-core/src/rng.rs`、`crates/telysta-core/src/project.rs`

## 语义 Hash

`telysta-semantic-hash.v1` 对通过验证的 `LanguageState` 计算完整 SHA-256 与以下分域 hash：

```text
identity / evidence / phonology / prosody / morphology
constructions / lexicon / pragmatics / orthography / typology / provenance
```

派生 `CorpusStatistics`、搜索索引、缓存、日志、UI 选择和任务状态不属于语义状态，因此不进入 hash。分域 hash 用于定位变化：词形变化可以改变 `lexicon` 与 `full`，但不得伪造 `phonology` 的变化。

## 路径派生 RNG

`telysta-rng-tree.v1` 从 root seed 和稳定点分路径推导独立流，例如：

```text
genesis.phonology
genesis.lexicon
era.0042.sound-change
branch.northern.contact
```

流的 key 只依赖 schema、root seed 和 path；它不依赖其他流是否被创建、调用次数或调用顺序。输出以 SHA-256 counter mode 产生，`uniform` 使用拒绝采样避免 modulo bias。路径只允许小写 ASCII、数字、`-` 和 `_` 的点分段。

## 使用规则

1. 生产模拟不得使用全局随机源；
2. 每个随机决策必须声明其完整路径；
3. 添加新模块只能新增新路径，不能改变既有路径；
4. Golden Scenario 比较 full 与分域 hash；
5. 项目 manifest 必须记录 RNG schema、root seed、引擎版本、规则包和数据 manifest 版本。

`telysta-run-context.v1` 现承担上述项目级绑定，并把带 payload hash 的数据 manifest 副本写入 `ProjectDataLock`。当前未下载 payload 的目录 manifest 不能进入可复现项目；完整约束见 [Project Runtime and Transactions v1](./PROJECT_RUNTIME_V1.md)。

这个合同保证可复现性，不保证语言学真实性。祖语生成仍必须通过音系、类型学、来源和历时质量门。

## 兼容性评审注记

2026-07-17 的 R0A 复核发现：现有 raw stream 已有 schema，但 bounded distribution、counter overflow、checkpoint cursor 与跨实现 known-answer 尚未独立版本化。提议的兼容策略、明确算法和测试向量见 [ADR-013](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md)。ADR-013 仍为 Proposed；本注记不改变已接受的 v1 输出或授权新的持久化 writer。
