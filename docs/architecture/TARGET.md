---
document_type: architecture-target
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-17
owner: unassigned
reviewers: []
---

# Target Architecture

本文组合已接受的平台 ADR 与仍在审阅的领域 ADR。执行授权按用户指定的
[AI 本地开发模式](../AGENT_OPERATING_MODEL.md#31-用户授权的-ai-本地开发审阅2026-10-16)；
目标视图本身不证明功能实现。

## 1. 目标依赖方向

```text
Tauri / CLI
      ↓ versioned DTO
telysta-application
      ├─ command + idempotency
      ├─ Operation/Run registration
      ├─ Job orchestration
      ├─ staging revalidation
      └─ atomic commit use cases
      ↓
telysta-core  ← ports →  telysta-storage
      ├─ typed LanguageState v3
      ├─ Meaning / Grammar / Construction IR
      ├─ Blueprint compiler + VerifiedGenesisArtifact
      ├─ typed ChangeSet + deterministic reducer
      ├─ evaluator contracts
      └─ provenance / replay validation
```

`core` 不依赖 application、storage、Tauri 或 async runtime；desktop 不直接构造或写入
ProjectManifest、RunLedger、JobRecord、LanguageState 或 ChangeSet。

## 2. 目标语言工作流

```text
Author Brief
→ typed LanguageBlueprint
→ deterministic multi-candidate compiler
→ independent evaluator + TaskPack
→ user selects candidate
→ VerifiedGenesisArtifact
→ atomic project creation
→ authoring / structural / simulation Operation
→ ProposedChangeSet
→ validation + canon impact
→ StateTransaction commit
→ replay / explain / export
```

## 3. 目标领域边界

- 音系使用 typed feature bundle、syllable/phonotactic grammar 和可解释约束。
- 形态、意义和构式使用显式 IR，不用自由字符串承担执行语义。
- 结构变化与社会传播分离；未常规化创新不能伪装成 LanguageState 变化。
- 项目历史由 Genesis/Imported boundary + committed typed ChangeSet 重建。
- 偏好、经验先验、研究假设和硬约束分层保存。
- 评价使用可下钻的多维结果，不产生单一不透明“自然度分数”。
- LLM 只能提出、解释和润色；TTS 只消费确定性 PronunciationPlan。

## 4. Target project package

ADR-011/012 已接受的本地开发设计（目标 writer 尚未实现）：

- 一个可变 ProjectManifest 作为唯一发布点；
- history、RunLedger、dependency bundle 和结果为不可变 content-addressed objects；
- JobStore 与语言语义历史分离；
- staging 永不直接成为权威；
- v1 迁移保留 source archive 和 LegacyHistoryBoundary。

## 5. 未决决定

以下事项在 ADR/Gate 关闭前不得实现为生产格式：

- LanguageState v3 的最终实体和聚合边界；
- ProjectManifest/RunLedger/JobStore 的生产 schema 与迁移实现；
- target package 的发布、GC 与恢复实现；
- RNG distribution、cursor 和 checkpoint wire 的生产实现及兼容验证；
- GenesisArtifact 与 evaluator 信任边界；
- plugin/WASM 执行边界。
