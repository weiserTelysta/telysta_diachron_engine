# Telysta Diachron Engine 文档索引

本目录同时保存当前状态、执行计划、架构决策、合同、研究证据和历史资料。
阅读顺序与冲突裁决规则见[文档权威与阅读顺序](./governance/AUTHORITY_ORDER.md)。

## 日常阅读入口

- [执行记录与恢复入口](./WORK_LOG.md)：本轮工作、验证结果和下一断点。
- [产品开发执行计划](./PRODUCT_DEVELOPMENT_PLAN.md#22-当前执行队列)：唯一工作队列与启动门。
- [当前架构](./architecture/CURRENT.md)：实际已实现的能力和限制。
- [开发环境](./DEVELOPMENT_SETUP.md)：安装、启动与质量检查。

可试用的 [Rosé Pine 作者流程原型](../experiments/meaning-workbench/README.md)
仅用于形成性研究；没有生成语言或写正式项目的能力。

[当前状态](./STATUS.md)由证据生成；G0A 当前决策为 `blocked`。
[路线图](./ROADMAP.md)仅概览交付顺序；[能力地图](./LANGUAGE_SIMULATOR_PLAN.md)
保存领域设计。[目标架构](./architecture/TARGET.md)、[迁移地图](./architecture/MIGRATION.md)
和[Agent 操作模型](./AGENT_OPERATING_MODEL.md)按需查阅。

以下目录保留合同、研究与迁移证据的精确入口，不要求每次通读。

## 治理、执行证据与开发

- [文档治理策略](./governance/DOCUMENT_POLICY.md)
- [文档权威与阅读顺序](./governance/AUTHORITY_ORDER.md)
- [ADR Index](./governance/ADR_INDEX.md)
- [计划优化记录（2026-07-16）](./PLAN_OPTIMIZATION_2026-07-16.md)
- [审计修正执行计划（2026-07-18）](./AUDIT_CORRECTION_PLAN_2026-07-18.md)：把 P0/P1 缺陷映射到现有 WBS、Gate、负例、迁移与清理放行条件。
- [审计缺陷控制台账（2026-07-18）](./AUDIT_DEFECT_LEDGER_2026-07-18.md)：P0/P1 的工作包、fixture、Gate、责任与关闭证据。
- [G0A GateEvidence（2026-07-17）](./G0A_GATE_EVIDENCE_2026-07-17.json)：当前为 v3 的 `blocked` 本地候选；格式迁移不等于可信 attestation 或 Gate 通过。
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

## 维护规则

当前队列只在执行计划维护，实际执行只在 WORK_LOG 记录，动态 Gate 只在证据维护。
历史评审不作为当前完成声明；旧 schema、ADR 与迁移 fixture 保留兼容入口。
文档合并先消除重复正文并保留链接，不在基线未验收时批量移动或删除合同。
