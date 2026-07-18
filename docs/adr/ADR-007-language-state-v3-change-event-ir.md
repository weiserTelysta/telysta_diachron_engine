---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-007：LanguageState v3、Typed ChangeEvent 与 GenesisArtifact

- 状态：`Proposed umbrella`
- 日期：2026-07-14
- 决策范围：祖语编译器、语言状态、历史事件、项目创建与后续 SpeechCommunity
- 前置决策：ADR-006
- 研究背景：ADR-005 提供分阶段研究动机，但不是本 ADR 或 WS-1 的接受前置

本 ADR 提出 LanguageState v3 的待评审总体方向，四个原评审分歧由以下子 ADR 给出可独立评审的决策；方向只有在本 ADR Accepted 后才冻结，任何实施仍须满足本 umbrella 的依赖闭合、对应 Accepted ADR，以及 G1 + G0B：

- [ADR-008：RegistryBundle 与分域特征注册表](./ADR-008-registry-bundle-domain-registries.md)；
- [ADR-014：Meaning–Grammar–Lexical Identity/Class–Realization Authority](./ADR-014-meaning-grammar-lexical-identity-realization-authority.md)；
- [ADR-009：原子 ChangeSet、UsageObservation 与 v2 历史边界](./ADR-009-atomic-change-set-and-usage-observations.md)；
- [ADR-010：GenesisArtifact 信任边界与项目创建](./ADR-010-genesis-artifact-trust-boundary.md)。

ProjectManifest、RunLedger、Operation、Job 与 Attempt 的身份和迁移语义由 [ADR-011](./ADR-011-project-manifest-run-ledger-job-identity.md) 独立决定。ADR-011 不是本 umbrella ADR 的子 ADR，但正式项目创建、后台执行和多次操作落盘必须同时满足它。

## 1. 背景

当前 `telysta-language-state.v2` 已经提供稳定身份、时间绑定、证据、provenance、分域 hash 和跨域引用验证，适合作为 Rust 权威状态的地基。但它仍是最小架构 Spike：

- `Phoneme` 没有版本化区别特征、异音和分布；
- `ProsodyState` 不能表达音节语法、重音、声调或韵律词；
- `Morpheme` 没有形式、异形体、特征束和范式位置；
- `Construction` 的 semantic frame 是无约束字符串，不能表达角色、线性化、一致或交替；
- `FeatureAssertion.value` 是字符串，LanguageState 未使用 Blueprint 的 FeatureRegistry 验证值域；
- `StateRevision` 保存完整替换状态，不能作为可解释的语言变化历史；
- 项目创建接受单 Genesis history，而不是只能由编译器产生的封闭产物。

在该模型上直接实现 `SpeechCommunity`，将产生无法持久化社群作用结果、无法表达变化机制以及后续大规模迁移的风险。因此，`GEN-001.2 Domain Model Hardening` 必须先于 `GEN-002 SpeechCommunity`。

## 2. 决策

### 2.1 新持久化版本

下一次领域模型升级使用 `telysta-language-state.v3`。v2 保持只读与显式迁移支持，不在原 schema 上静默增加字段或改变语义。

### 2.2 一个 RegistryBundle envelope

Blueprint、Genesis 编译器、LanguageState 和 UI 使用同一个版本化 RegistryBundle lock。Bundle 内使用音系、形态句法和语义分域 registry，但共享：

- `FeatureId` 和 typed `FeatureValue`；
- 值域、控制级别、依赖、不兼容项；
- compiler capability；
- registry version 与 semantic hash。

LanguageState 的类型学 assertion 必须引用对应分域 registry 中存在的 feature 和合法 value。未知或计划中但未实现的 feature 不能被伪装为已编译状态。完整决策见 ADR-008。

### 2.3 LanguageState v3 最小表达能力

#### Phonology

- `SegmentDefinition`：IPA、区别特征、音类与来源；
- `Phoneme`：对比单位和允许 realization；
- `Allophone`：结构环境、语体/社群条件和表面实现；
- `PhonotacticGrammar`：音节、边界、局部和非局部加权约束；
- `ProsodicSystem`：mora、syllable、foot、stress、tone、prosodic word。

#### Morphology

- `Morpheme`：意义/功能与抽象身份；
- `MorphemeForm` / `Allomorph`：音系形式、条件和来源；
- `MorphosyntacticFeatureBundle`：版本化语法特征；
- `Paradigm` / `ParadigmCell` / `InflectionClass`：格位、范式单元、缺陷和不规则来源；
- `WordForm`：Lexeme + 规范化 FeatureBundle/ParadigmCell 的稳定词形身份；
- `RealizationUnit`：区分 single-owner Allomorph exponent、multi-contribution fusion 与 no-span zero；
- ordered `MorphOccurrence` / `MorphologicalTemplate`：词素重复、顺序、贡献、融合与 typed boundary。

#### Constructions and meaning

- Sense-owned typed `PredicateFrameId`、`ArgumentRole` 与 `FrameAlternation`；
- language-specific `GrammarInventory` 与 `LexicalClassDefinition`；它们引用 RegistryBundle 而不复制 feature 定义；
- selection、valency、agreement、linearization 和 alternation；
- typed sense relations，不使用无类型 related ID 集合；
- information structure、reference tracking 和 register condition 的可扩展边界。

#### Lexicon and usage

- `Lexeme` 保存有序形态分析、音系分析、义项和语体；
- `Sense`、`PredicateFrame`、`WordForm` 和 `Lexeme` 使用 ADR-014 冻结的 owner 与 identity-continuity 规则；
- `LexemeFamily` 保存词根、派生、复合和同源关系；
- 使用频率和 corpus observation 作为版本化观察或派生数据，不混入不可复现的运行时统计。

LanguageState v3 锁定 `telysta-entity-id.v2`。v1 kind 目录不静默扩张；迁移保留既有 ID bytes，新 v3 kind、stable-key 与 local occurrence ID 语义由 ADR-014 决定。

### 2.4 Typed ChangeSet

`StateRevision` 只保留为 v2 迁移来源；v3 生产历史使用过程级原子 ChangeSet 和 ordered typed effects：

- `SoundChangeApplied`
- `PhonemeMerged`
- `PhonemeSplit`
- `AllophonePhonemicized`
- `LexemeIntroduced` / `LexemeReplaced`
- `BorrowingAdapted`
- `AnalogyApplied`
- `ParadigmRestructured`
- `ConstructionReanalyzed`
- `GrammaticalizationAdvanced`
- `SemanticShifted`
- `OrthographyReformed`

Meaning/Grammar/Lexical effect 必须进一步遵守 ADR-014 对 Sense、PredicateFrame、FrameAlternation、LexicalClass assignment、WordForm、Allomorph、Paradigm 与 Construction 生命周期的有限 typed effect；不得退回无类型 `EntityUpdated`。

每个 ChangeSet 内的 effect/event projection 使用在 reduction 前预分配的
`ChangeSetId + stable effect index` 身份；该身份不依赖 post-state 或
`ChangeSetContentHash`。每个事件必须保存：

- preallocated effect/event identity、OperationId、time、typed ChangeLocus 与 process；
- precondition 与 structural environment；
- affected entity IDs；
- typed effect；
- rule/data/evidence locks；
- provenance；
- deterministic reducer 所需数据。

`ChangeLocus` 允许 WS-1 使用不依赖虚构社区的 `LanguageStructure { languageId, lectId }`，并为后续阶段保留 `SpeechCommunity { communityId, lectId }`。社区作用域只有在对应 SpeechCommunity/Variation ADR 接受后才能进入生产历史。ChangeSet 引用语义操作的 `OperationId`；JobId 和 AttemptId 只属于执行层，不能成为事件意义或 reducer 身份的一部分。完整决定见 ADR-009 与 ADR-011。

历史回放以 `VerifiedGenesisArtifact` 所产生的 Genesis root 或唯一 `LegacyHistoryBoundary` 加 typed ChangeSet 为权威。`StateSemanticHash` 只承诺当前状态，`HistoryHeadHash` 承诺 root 与有序 ChangeSet；committed ChangeSet 不进入它所引用的 post `StateSemanticHash`。快照是性能优化，不是第二事实来源。UsageObservation、派生统计和 v2 导入边界见 ADR-009。

### 2.5 GenesisArtifact

正式项目创建只接受由 application service 调用唯一 Rust
`GenesisVerifier::verify_and_seal` 构造的 `VerifiedGenesisArtifact` capability。
`ProtoLanguageCompiler` 只产生候选，独立 evaluator 只产生报告与 attestation，任一方都
不能单独取得 verified capability。可序列化 `GenesisArtifactEnvelope` 始终是不可信数据。
verified capability 至少锁定：

- LanguageState v3、`StateSemanticHash`、state/EntityId/hash schemas；
- Blueprint document 与 hash；
- RegistryBundle version/hash；
- Meaning/Grammar/Lexical/Realization contract bundle 与 HashCoverageManifest；
- Genesis TheoryProfile / ModelLock；
- data payload locks；
- rule-pack locks；
- RNG schema/root-seed contract；
- compiler/grammar/realizer/analyzer/validator versions；
- Capability Matrix、TaskPack 与 independent evaluator locks；
- candidate identity/hash、capability report 与 typed gaps；
- Genesis quality report 和分项结果；
- provenance ledger。

只有 `readyForCompilation=true`、required capability 全部 supported、Genesis hard errors 和 forbidden-reading acceptance 为零时才能构造 capability。来自磁盘或 IPC 的 envelope 一律按其锁定的精确依赖完整重验；Tauri 不得手工拼装或反序列化一个“看起来像”verified artifact 的任意 JSON 来绕过应用服务验证。完整信任边界见 ADR-010。

## 3. 不在本 ADR 中决定

- 最终 MaxEnt 或其他音系配列训练算法；
- 全部语法 feature 集；
- SpeechCommunity 的人口学参数；
- ChangeProcess 的具体扩散统计模型；
- 神经语音、LLM 或任意代码插件；
- Quality Lab 的最终权重。

这些能力依赖本 ADR 的表达边界，但需单独工作包和证据。

## 4. 实施顺序

1. 冻结 v2 fixture、迁移测试、source hashes，并为 v3 冻结 `StateSemanticHash` / `HistoryHeadHash` / `ProjectAuthorityHash` 非循环测试向量；
2. 独立接受 ADR-011/012/013，并在 G0A=`passed` 后才以 fake semantic operation 实现 ProjectManifest、RunLedger 与 JobStore 平台边界，不冻结 v3；
3. 在 G0B 接受 ADR-008 的 RegistryBundle 与共享 typed FeatureValue；
4. 接受 ADR-014，冻结 Meaning/Grammar/Lexical Identity/Class/Realization、query purity 与 state-only migration 边界；
5. 接受 ADR-009 的 ChangeSet、UsageObservation 与 legacy history 边界；
6. 接受 ADR-010 的 GenesisArtifact 与唯一项目创建边界，并最终接受本 umbrella ADR；
7. G1 + G0B 后为 phonology/prosody 建立 v3 类型与 hard invariants；
8. 为 morphology/construction/meaning 建立 v3 类型与 hard invariants，并通过唯一 `LegacyHistoryBoundary` 实现 v2 state-only 显式迁移；
9. 实现 ADR-009 的 ChangeSet、reducers、UsageObservation 边界和 replay；
10. 实现 ADR-010 的 GenesisArtifact，完成最小祖语编译纵切；
11. 通过专家阶段评审，并接受独立的 SpeechCommunity/Variation 决策后才进入相应生产 schema。

每一步都必须保持 workspace 可编译，并提供版本化 round-trip、拒绝无效反序列化、迁移和 replay 测试。允许按领域纵切迁移，不允许在一个提交中同时重写所有领域和桌面 UI。

## 5. 验收标准

- Blueprint 与 LanguageState 不再维护两套 feature 值域；
- 每个 Genesis 音段、词素、词形和构式都能完成结构分析；
- Genesis hard errors 为零才可创建项目；
- 语言变化事件能回答“何时、何地、为何、改变了什么”；
- replay 与在线状态的 `StateSemanticHash` 和 `HistoryHeadHash` 分别相等，且 ChangeSet post hash 不形成自引用；
- v2 项目只能通过显式迁移进入 v3；
- v2 历史只产生一个 `LegacyHistoryBoundary` persisted root；
- UI 无法绕过 compiler capability 和 Genesis gate；
- 外部语言学评审未发现阻断性表达缺口。

## 6. 风险与控制

| 风险 | 控制 |
|---|---|
| v3 范围过大 | 按 phonology、morphology/construction、event 三个纵切交付 |
| 类型设计过早冻结理论 | 核心保持 typed extension points，争议理论放在版本化 registry/rule pack |
| 迁移丢失 v2 信息 | 保留原始归档、迁移审计 hash 和失败即停止策略 |
| typed event 数量膨胀 | 共享 envelope 与小型 effect IR，不回退到无类型字符串 |
| 性能下降 | 先保证语义和回放，快照/索引只做可重建优化 |
| Python 对照诱导 bug-for-bug 迁移 | 以目标不变量、硬错误和专家门裁决差异 |

## 7. 子 ADR 接受条件

原评审问题已经分配到 ADR-008、ADR-014、ADR-009 与 ADR-010：

1. ADR-008 决定共享 RegistryBundle envelope 与分域 registry；
2. ADR-014 决定 Meaning/Grammar/Lexical Identity/Class/Realization、query purity、semantic hash 与 state-only migration；
3. ADR-009 决定独立的版本化 UsageCorpus、派生统计边界、原子 ChangeSet，以及包含 `ImportedCheckpoint` payload 的唯一 `LegacyHistoryBoundary`；
4. ADR-010 决定内存 capability、反序列化重验和 Tauri/application-service 创建边界。

只有四个子 ADR 经过具名 domain/code owner 与独立 architecture、linguistics、
migration reviewer 评审、状态改为 `Accepted`，本 umbrella ADR 才能改为
`Accepted`；作者和 owner 均不得占任一 independent reviewer 槽位。在此之前不得修改
持久化实体意义、v3 replay 语义或正式项目创建入口。
