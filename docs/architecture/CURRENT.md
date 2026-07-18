---
document_type: architecture-description
decision_status: not-applicable
implementation_status: verified
normative_scope: current
last_verified: 2026-07-18
base_commit: fa7468b68ba60984ad7c416560dccb8f19a60aa7
verification_source: docs/G0A_GATE_EVIDENCE_2026-07-17.json
---

# Current Architecture

本文描述基于上述 subject commit 的当前 dirty worktree；完整输入 fingerprint、subject tree
和历史验证运行由 `verification_source` 指向的 GateEvidence 提供。本文不授权 target 架构。

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
```

## 2. 当前权威数据

| 对象 | 当前格式 | 当前能力 |
|---|---|---|
| LanguageState | `telysta-language-state.v2` | 验证、分域 hash、显式 v1 时间迁移 |
| Blueprint | `telysta-language-blueprint.v2` | 结构验证、Intent/Feature 分离、能力报告 |
| History | `telysta-project-history.v1` | `Genesis` + full `StateRevision` replay |
| Project storage | `telysta-project-file.v1` | 原子保存、恢复、迁移、索引、并发保护 |
| RNG | versioned RngTree v1 | path-derived stream、known-answer tests |
| Data catalog | `telysta-data-manifest.v1` | 元数据验证；当前 catalog payload hash 可为空 |

## 3. 已知边界

- 没有 `telysta-application`；desktop 仍直接依赖 core/storage。
- 内置 Blueprint feature 的 compiler capability 当前均为 `planned`。
- 没有 VerifiedGenesisArtifact 或正式项目创建入口。
- LanguageState v2 的多个领域仍是最小/stringly typed 表达，不是 WS-1 最终 IR。
- 历史保存完整状态修订，尚无 typed linguistic effect 或 ChangeSet reducer。
- DataReference 只验证 dataset 身份和非空定位字段，不验证真实 table/record payload。
- desktop demo checkpoint 是技术 Spike，不属于项目存储。
- Python golden baseline 仍保留已登记 replay 缺陷和不合法词形；不得复制到 Rust。

## 4. 当前依赖纪律

当前 desktop → storage 直接依赖是过渡状态，只能支持已实现的读会话和技术 Spike。
在 application boundary 建立前，不得沿此路径增加新的长期 writer 或领域编排。
