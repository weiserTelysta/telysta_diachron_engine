---
document_type: architecture-description
decision_status: not-applicable
implementation_status: verified
normative_scope: current
last_verified: 2026-10-14
verification_source: docs/G0A_GATE_EVIDENCE_2026-07-17.json
---

# Current Architecture

本文描述当前实现。完整的 subject commit、subject tree、输入 fingerprint
和历史验证运行仅由 `verification_source` 指向的 GateEvidence 提供，避免在本文中复制会失效的动态哈希。
本文不授权 target 架构。

## 1. 组件图

```text
Tauri static webview
  ├─ versioned command/event DTO
  ├─ direct telysta-core calls
  └─ direct telysta-storage ProjectRuntime calls

telysta-core
  ├─ EntityId / TimeModel
  ├─ LanguageState v2
  ├─ LanguageBlueprint v2 + FeatureRegistry
  ├─ DataManifest / DataReference
  ├─ RngTree v1
  ├─ RunContext / ProjectHistory / StateTransaction
  └─ demo worker contract

telysta-storage
  ├─ telysta-project-file.v1
  ├─ atomic file replacement + recovery copy
  ├─ migration journal
  ├─ SQLite derived event index
  ├─ write lease + expected-history hash
  └─ ProjectRuntime sessions

Python app/
  └─ legacy baseline and research laboratory; not a production writer

experiments/meaning-workbench/
  └─ non-authoritative R0B-06P author-flow prototype; no production bridge

scripts/concepticon_slice.py + experiments/concepticon-slice/
  └─ offline research selection and record membership; no production writer

scripts/project_authority_review.py + review-only Python/Rust tests
  └─ mutable ADR-012 canonical-byte/hash vectors; no package/graph/replay authority

scripts/linguistic_review.py + experiments/linguistic-execution/
  └─ pinned built-in review groups and case-to-Gate map; production adapters future
      includes five finite orthography relation facets, not a production parser
```

## 2. 当前权威数据

| 对象 | 当前格式 | 当前能力 |
|---|---|---|
| LanguageState | `telysta-language-state.v2` | 验证、分域 hash、显式 v1 时间迁移 |
| Blueprint | `telysta-language-blueprint.v2` | 结构验证、Intent/Feature 分离、能力报告 |
| History | `telysta-project-history.v1` | `Genesis` + full `StateRevision` replay |
| Project storage | `telysta-project-file.v1` | 原子保存、恢复、迁移、索引、并发保护 |
| RNG | versioned RngTree v1 | path-derived stream、known-answer tests |
| Data catalog | `telysta-data-manifest.v1` | 元数据与 pinned payload 原始字节 checksum 校验；catalog hash 可为空；无 table/record membership 校验 |

## 3. 已知边界

- 没有 `telysta-application`；desktop 仍直接依赖 core/storage。
- 内置 Blueprint feature 的 compiler capability 当前均为 `planned`。
- Blueprint inspector 原文经 `blueprintJson` 直接交 Rust 校验，保留旧 typed 参数；
  编辑使旧报告失效，迟到响应绑定请求文本，不写状态。没有开放正式编译入口。
- 没有 VerifiedGenesisArtifact 或正式项目创建入口。
- LanguageState v2 的多个领域仍是最小/stringly typed 表达，不是 WS-1 最终 IR。
- 历史保存完整状态修订，尚无 typed linguistic effect 或 ChangeSet reducer。
- DataReference 只验证 dataset 身份和非空定位字段，不验证真实 table/record payload。
- desktop demo checkpoint 是技术 Spike，不属于项目存储。
- Python golden baseline 仍保留已登记 replay 缺陷和不合法词形；不得复制到 Rust。

## 4. 当前依赖纪律

当前 desktop → storage 直接依赖是过渡状态，只能支持已实现的读会话和技术 Spike。
在 application boundary 建立前，不得沿此路径增加新的长期 writer 或领域编排。

## 5. 2026-10-12 本地修复候选

`telysta-storage` 已补充在 lease 内的 create-if-absent、条件提交的 context/prefix
校验、迁移 archive 与重生成目标复验，以及 load/query 的索引发布锁。
实现与故障矩阵见[存储合同](../PROJECT_STORAGE_V1.md)，实际执行见
[恢复记录](../WORK_LOG.md)。该修复保持 v1 wire、事件身份和回放语义；
独立评审、跨平台 provenance 与 G0A 仍未关闭。正式创建命令仍未开放。
