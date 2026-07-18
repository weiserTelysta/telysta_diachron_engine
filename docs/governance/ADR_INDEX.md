---
document_type: index
decision_status: not-applicable
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-18
---

# Telysta ADR Index

本索引汇总状态，不改变任何 ADR 的决定。状态以各 ADR 正文为准。

文档中的“等价决定”或“Accepted 替代”只允许指向本索引内具名、状态为
`Accepted`、正文显式声明 `supersedes/replaces ADR-xxx` 的 replacement ADR；该 ADR
必须附原决定逐条覆盖矩阵、迁移影响和不低于原决定的独立 reviewer 要求。会议结论、
issue、PR 描述或未登记草案不能替代指定 ADR。

ADR 接受与 Gate 放行采用两阶段证据：先由 review-evidence manifest 绑定决定正文、
subject hash 与 reviewer attestation，完成 ADR 接受；随后最终 GateEvidence 引用
Accepted ADR 和该 Gate 的其余完整证据。不得让同一份“passed GateEvidence”既成为
ADR 接受前置又成为接受 ADR 后才能生成的结果。

| ADR | 状态 | 作用 |
|---|---|---|
| [ADR-004](../adr/ADR-004-tauri-python-sidecar.md) | Superseded | 历史 Tauri + Python sidecar 方案 |
| [ADR-005](../adr/ADR-005-community-driven-language-simulation.md) | Proposed | 社区与使用驱动的下一阶段模拟背景 |
| [ADR-006](../adr/ADR-006-rust-native-core-python-research-bridge.md) | Accepted | Rust 生产权威、Python 研究边界 |
| [ADR-007](../adr/ADR-007-language-state-v3-change-event-ir.md) | Proposed umbrella | LanguageState v3、Change IR、Genesis 总提案 |
| [ADR-008](../adr/ADR-008-registry-bundle-domain-registries.md) | Proposed | RegistryBundle 与分域注册表 |
| [ADR-009](../adr/ADR-009-atomic-change-set-and-usage-observations.md) | Proposed | typed ChangeSet、UsageObservation 与 legacy boundary |
| [ADR-010](../adr/ADR-010-genesis-artifact-trust-boundary.md) | Proposed | VerifiedGenesisArtifact 信任边界 |
| [ADR-011](../adr/ADR-011-project-manifest-run-ledger-job-identity.md) | Proposed | Project/Operation/Run/Job 身份和 lifecycle |
| [ADR-012](../adr/ADR-012-project-package-commit-authority.md) | Proposed | 单 manifest 发布点与不可变对象图 |
| [ADR-013](../adr/ADR-013-rng-compatibility-and-distribution-versioning.md) | Proposed | RNG/distribution/checkpoint 兼容 |
| [ADR-014](../adr/ADR-014-meaning-grammar-lexical-identity-realization-authority.md) | Proposed | Meaning/Grammar/Lexical Identity/Class/Realization 权威边界 |

## 当前实施门

- ADR-006 已授权 Rust 原生生产核心和 Tauri 方向。
- ADR-007～014 尚未共同授权 LanguageState v3、Genesis、typed ChangeSet、
  ProjectManifest、JobStore 或 target project package 的生产实现。
- ADR-011/012/013 必须独立批准并关闭相关 G0A 阻断项后，才能开始 R1 持久化
  walking skeleton。
- G0B 的领域决定必须按 `ADR-008 → ADR-014 → ADR-009 → ADR-010 → ADR-007`
  完成独立评审并依次接受；每个节点可由本索引规则下的 Accepted replacement 占位，
  但 ADR-007 umbrella 节点不得从最终关闭条件中省略。
- ADR-009 的跨 Gate 前置是 ADR-011；ADR-010 的跨 Gate 前置是
  ADR-011/012/013。G0B 领域证据准备不以完整 G0A clean-baseline 证明为前置，但
  相关跨 Gate ADR 未 Accepted 时不得接受对应领域 ADR。即使领域 ADR 已接受，
  LanguageState v3 仍须等待 G1 + G0B。
