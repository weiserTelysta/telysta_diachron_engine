# Telysta Diachron Engine 文档索引

本目录同时保存当前状态、执行计划、架构决策、合同、研究证据和历史资料。
阅读顺序与冲突裁决规则见[文档权威与阅读顺序](./governance/AUTHORITY_ORDER.md)。

## 开始这里

1. [当前状态](./STATUS.md)：当前 Gate、允许/禁止声明和下一执行顺序。
2. [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md)：R0A/R0B–R7 WBS、依赖、Stop/Go 和当前执行队列。
3. [项目路线图](./ROADMAP.md)：当前目标、阶段顺序和验收标准。
4. [专业语言模拟器实施总计划](./LANGUAGE_SIMULATOR_PLAN.md)：完整能力地图与 G0A/G0B/G1–G7 质量门。
5. [Current Architecture](./architecture/CURRENT.md)：当前代码实际实现。
6. [Target Architecture](./architecture/TARGET.md)：尚受 Gate/ADR 约束的目标架构。
7. [Migration Map](./architecture/MIGRATION.md)：current 到 target 的安全切换顺序。
8. [Agent Operating Model](./AGENT_OPERATING_MODEL.md)：Agent 权威边界、工作闭环和停止条件。

## 治理、执行证据与开发

- [文档治理策略](./governance/DOCUMENT_POLICY.md)
- [文档权威与阅读顺序](./governance/AUTHORITY_ORDER.md)
- [ADR Index](./governance/ADR_INDEX.md)
- [计划优化记录（2026-07-16）](./PLAN_OPTIMIZATION_2026-07-16.md)
- [审计修正执行计划（2026-07-18）](./AUDIT_CORRECTION_PLAN_2026-07-18.md)：把 P0/P1 缺陷映射到现有 WBS、Gate、负例、迁移与清理放行条件。
- [审计缺陷控制台账（2026-07-18）](./AUDIT_DEFECT_LEDGER_2026-07-18.md)：P0/P1 的工作包、fixture、Gate、责任与关闭证据。
- [G0A GateEvidence（2026-07-17）](./G0A_GATE_EVIDENCE_2026-07-17.json)：当前决策为 `blocked`；该存量 v1/v2 记录尚不满足 Proposed v3 合同。
- [G0A policy v2](./G0A_POLICY_V2.json)：当前应审查的 Proposed G0A requirement、terminal evidence 与 delivery-readiness policy；尚未获得独立接受。
- [G0A policy v2 schema](./G0A_POLICY_V2.schema.json)：上述 Proposed policy 的封闭结构与精确 R0A/R1 工作包集合。
- [GateEvidence v3 治理模型](./governance/GATE_EVIDENCE_MODEL_V3.md)：当前应审查的 Proposed policy lock、subject/attestation、delivery readiness 与远端 provenance 合同。
- [GateEvidenceManifest v3 schema](./GATE_EVIDENCE_MANIFEST_V3.schema.json)：上述 Proposed v3 证据结构；现有证据尚未形成有效 v3 attestation。
- [G0A 独立评审与 Clean Baseline 交接](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)：可复现清单、评审职责与 subject/attestation 提交顺序。
- [GateEvidence v2 治理模型](./governance/GATE_EVIDENCE_MODEL_V2.md)：v3 迁移前的 subject/attestation 合同与历史实现说明，不再足以支持当前 G0A pass。
- [GateEvidenceManifest v2 schema](./GATE_EVIDENCE_MANIFEST_V2.schema.json)：现有证据的迁移输入 schema，不再是当前 G0A 的通过性 schema。
- [G0A policy v1](./G0A_POLICY_V1.json)：已被 v2 合同取代的迁移输入；不得为当前决定恢复旧 pass。
- [GateEvidenceManifest v1 schema](./GATE_EVIDENCE_MANIFEST_V1.schema.json)：历史迁移输入，不再用于新决定。
- [ADR-011 planning schema](./ADR_011_SCHEMA_DRAFT_V1.json)：仅用于评审和 fixture，不是生产格式。
- [ADR-011 接受证据合同草案](./PROJECT_OPERATION_JOB_CONTRACT_DRAFT.md)
- [R0A Platform Contract Pack v1](./PLATFORM_CONTRACT_PACK_V1.md)
- [重构前基线报告](./BASELINE_REPORT_2026-07-14.md)
- [开发环境与质量检查](./DEVELOPMENT_SETUP.md)
- [Rust Desktop Shell Spike](./RUST_DESKTOP_SPIKE.md)
- [Agent Skill Allowlist](./SKILL_ALLOWLIST.md)

## 当前合同与迁移基线

- [Foundation Model v1](./FOUNDATION_MODEL_V1.md)
- [Time Model v2 Migration](./TIME_MODEL_V2_MIGRATION.md)
- [Canonical LanguageState v2 / v1 migration baseline](./LANGUAGE_STATE_V1.md)
- [Data Governance v1](./DATA_GOVERNANCE_V1.md)
- [Determinism Contract v1](./DETERMINISM_CONTRACT_V1.md)
- [Project Runtime and Transactions v1](./PROJECT_RUNTIME_V1.md)
- [Project Storage v1](./PROJECT_STORAGE_V1.md)
- [Project Session and Desktop Commands v1](./PROJECT_SESSION_V1.md)
- [LanguageBlueprint v2](./LANGUAGE_BLUEPRINT_V2.md)
- [LanguageBlueprint v1（已废弃）](./LANGUAGE_BLUEPRINT_V1.md)
- [Legacy Canonical State v1](./CANONICAL_STATE_V1.md)
- [Legacy 事件覆盖账本](./LEGACY_EVENT_COVERAGE.md)
- [模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)

## 架构决策

- [ADR-004：Tauri + Python Sidecar（已替代）](./adr/ADR-004-tauri-python-sidecar.md)
- [ADR-005：社区驱动的语言模拟](./adr/ADR-005-community-driven-language-simulation.md)
- [ADR-006：Rust 原生生产核心](./adr/ADR-006-rust-native-core-python-research-bridge.md)
- [ADR-007：LanguageState v3 与 Change IR](./adr/ADR-007-language-state-v3-change-event-ir.md)
- [ADR-008：RegistryBundle](./adr/ADR-008-registry-bundle-domain-registries.md)
- [ADR-009：Atomic ChangeSet](./adr/ADR-009-atomic-change-set-and-usage-observations.md)
- [ADR-010：GenesisArtifact 信任边界](./adr/ADR-010-genesis-artifact-trust-boundary.md)
- [ADR-011：Project/Operation/Run/Job identity](./adr/ADR-011-project-manifest-run-ledger-job-identity.md)
- [ADR-012：Project package commit authority](./adr/ADR-012-project-package-commit-authority.md)
- [ADR-013：RNG compatibility](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md)
- [ADR-014：Meaning–Grammar–Lexical Identity/Class–Realization Authority](./adr/ADR-014-meaning-grammar-lexical-identity-realization-authority.md)

## 研究、质量与历史资料

- [语言生成与历时模拟路线严格评审](./RESEARCH_ROUTE_REVIEW_2026-07-14.md)
- [语言学与架构审计（2026-07-18）](./LINGUISTIC_AND_ARCHITECTURE_AUDIT_2026-07-18.md)：当前成果、系统性语言学缺陷、架构根因、理论依据与 Stop/Go。
- [代码与模块清理计划](./CLEANUP_PLAN.md)
- [规则系统与语言质量计划](./RULE_QUALITY_PLAN.md)
- [开发文档（Legacy / Non-authoritative）](./development.md)

`PLAN_OPTIMIZATION_2026-07-16.md` 只保存一次计划修订的理由和同步清单。被采纳的内容必须回写前三份主计划；在同步完成前，不得只依据该记录启动持久化 schema、回放或插件边界实现。

## 文档状态约定

文档逐步拆分 `decision status`、`implementation status` 与 `normative scope`；定义见
[文档治理策略](./governance/DOCUMENT_POLICY.md)。旧文档原有状态行在迁移完成前继续有效，
但不得把 `Accepted` 误读为“全部实现”，也不得把 `Implemented` 误读为架构决定已批准。

如果本文档与代码行为不一致，应先记录差异，再决定修复代码还是更新决策；不得静默修改文档来掩盖实现偏差。

## 当前执行焦点

截至 2026-07-18，项目仍处于“产品化地基”阶段。当前由 R0A 与 R0B 并行收口：R0A 修复计划、仓库与平台合同并关闭 G0A，R0B 按审计修正计划冻结 WS-1 的领域证据并关闭 G0B。当前不优先扩充规则数量，先完成：

- 建立可复现的黄金场景和状态哈希，作为清理与客户端迁移的安全网；
- 已为历史回放缺陷建立稳定的特征测试和事件覆盖账本；
- 已完成模块可达性、迁移矩阵与去留清单；
- 已完成 Rust workspace、Tauri command/event 边界和 demo 恢复技术 Spike；
- 已完成稳定实体 ID、TimeModel、采用曲线和过程排序合同；
- 已完成可验证的 `LanguageState` v2 与精确时间模型绑定；
- 已完成最小数据来源治理、manifest 与证据引用；
- 已完成 Rust 语义 hash 与路径派生 RNG；
- 已补齐 R0A 平台合同包、Project Package 单发布点 ADR-012 与 RNG compatibility ADR-013 的评审材料，并用 Rust known-answer 测试冻结当前 RNG 输出；三者在独立批准前仍不授权生产实现；
- 已完成项目数据锁、`RunContext`、版本化项目事件与 `StateTransaction` v1；它是当前存储合同，不是长期多 Operation/Job 目标，后者等待 ADR-011 Accepted；
- 已完成原子项目存储、迁移、索引完整性、并发写入保护，以及 Tauri 的正式项目打开、会话读取、刷新和关闭；创建与写入命令等待 Genesis 编译器，不能以空状态替代。
- 已完成 `LanguageBlueprint v2` 合同修复：Intent 与 Feature 分离，UI 与 Rust 引擎共享注册表验证，并明确区分结构有效与编译器可用；
- 已建立 Agent 操作合同、Skill allowlist 和重构前基线；开发者本机另有可选的个人
  `telysta-agent` v0.1.0 插件及三个待前向测试 Skill，它们不属于仓库可复现的产品能力；
- 当前 Next 是关闭 G0A 后进入 R1 平台 walking skeleton，同时继续完成 G0B；只有 G1 与 G0B 都关闭后，才进入 WS-1 的生产领域实现。`GEN-001.2`、SpeechCommunity 与 PopulationVariation 不能绕过对应 Gate 和 Accepted ADR。

`A-001` 开发环境与 CI、`A-002` 黄金场景与状态哈希、`A-003` 历史回放特征测试、`A-004` 模块清单与迁移矩阵、`A-005` Rust Core Shell Spike、`B-001` Foundation Model、`B-001.1` Foundation Repair、`B-002` Canonical LanguageState Schema、`DAT-001` 最小数据治理与 manifest、`B-003` 确定性合同、`B-004` 项目运行与事务合同、`B-005` 时间模型精确绑定、`FND-008` 原子项目存储与迁移、`FND-008.1` 存储完整性与并发收口、`GEN-001.1` LanguageBlueprint v2 合同修复已经完成。`PLT-002` 创建/写入仍等待 VerifiedGenesisArtifact；当前执行队列以产品开发执行计划为准，G0A/G0B/G3B 的修订理由见计划优化记录。
