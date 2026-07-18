---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-009：原子 ChangeSet、UsageObservation 与 v2 历史边界

- 状态：`Proposed`
- 日期：2026-07-14
- 决策范围：LanguageState v3 变化事件、事务、回放、语料观察与 v2 历史迁移
- 前置决策：ADR-006、ADR-008、ADR-011、ADR-014
- 设计上下文：ADR-007 umbrella；ADR-011 先固定 Operation/Run 与 Job/Attempt 身份，ADR-014 固定 ChangeSet 所作用的语言实体、Meaning/Grammar/Realization 与 query purity，本 ADR 再决定 ChangeSet/UsageObservation 如何引用这些身份

## 1. 用户与研究问题

如何保存一次语言过程对多个实体产生的联合变化，使用户能够解释和回放结果，同时不把不可恢复的旧状态差异伪装成已知历史机制？

## 2. 假设分类

| 假设 | 分类 | 处理方式 |
|---|---|---|
| 一个语言过程的联合效果必须全成或全败 | Hard constraint | 原子 ChangeSet |
| 在线状态与回放状态必须语义相等 | Hard constraint | precondition/postcondition hash 与 reducer 测试 |
| 使用频率可能影响变化 | Research hypothesis / empirical prior | 通过版本化 observation 和 process model 表达 |
| v2 完整状态差异能恢复真实变化机制 | Unsupported assumption | 明确拒绝 |

## 3. 决策：ChangeSet 是生产变化的原子单位

生产历史使用一个过程级 `ChangeSet` envelope。`ChangeSetId` 在 reduction 前由
Operation 与 proposal 的非显示性 stable key 分配；ordered effect 使用
`ChangeSetId + stable effect index` 得到 owner-scoped `EffectId`/event projection
identity。两者都不依赖 post-state hash 或 `ChangeSetContentHash`。Envelope 至少包含：

- preallocated ChangeSet identity、ordered effect identity、process identity 与语义 `OperationId`；
- time 与 typed `ChangeLocus`；
- precondition `StateSemanticHash`；
- expected `HistoryHeadHash`；
- typed structural environment；
- ordered typed effects；
- affected entity IDs；
- rule/data/evidence/registry locks；
- provenance；
- reducer version 与所需 RNG path；
- postcondition `StateSemanticHash`。

一个 `ChangeSet` 可以包含多个小型 effect，例如音段更新、词形更新、范式槽位更新和来源边更新。所有 effect 先针对同一个前置状态完成验证，再由 `StateTransaction` 原子提交。任何 effect 失败时不得留下部分状态或部分事件。

effect IR 保持 typed、有限和可迁移；不能退回任意 JSON patch、字符串命令或完整状态替换。

Hash 计算必须遵循 ADR-014 的非循环方向：

```text
pre StateSemanticHash + expected HistoryHeadHash
→ validate ordered effects
→ reduce to post StateSemanticHash
→ compute ChangeSetContentHash
→ compute next HistoryHeadHash(parent + ChangeSetContentHash + post StateSemanticHash)
```

LanguageState 的 `StateSemanticHash` 不包含 committed ChangeSet envelope、history node 或 RunLedger。ChangeSet 保存 post-state hash 不会反向进入该 post-state hash；完整历史由 `HistoryHeadHash` 承诺。ADR-012 唯一拥有 `ProjectAuthorityHash` 的规范组合与单 manifest 发布；本 ADR 只提供其中的 state/history 输入，不重新定义项目发布 hash。

Reducer 写入 state-level provenance 时只能引用 reduction 前已确定的 EventId/OperationId 和 typed source edge；依赖 post-state hash 才能计算的 `ChangeSetContentHash` 不得写回同一个 post state。

这里的 EventId 是上述 preallocated EffectId 的历史投影名称，不是从
`ChangeSetContentHash` 派生的 content-address。`ChangeSetContentHash` 只承担完整性，
不能替代语义身份。

### 3.1 OperationId 是语义来源，JobId 不是

`OperationId` 标识产生提案或提交的语义操作，例如 Genesis、Authoring、Simulation、Migration、Retcon 或 Import。它引用 ADR-011 定义的不可变 OperationSpec/OperationContext，并使 ChangeSet 能回答“这一变化来自哪一次明确请求和哪组锁”。

`RunId` 可以作为模型执行或实验复现的 provenance 链接；`JobId` 和 `AttemptId` 只描述调度、重试、恢复和 worker 执行。Job 或 Attempt 的变化不得改变 ChangeSet identity、effect 语义、RNG 路径或 LanguageState semantic hash。相同 Operation/Run 经不同 Attempt 得到不同语义结果时必须作为确定性或恢复错误停止，不能提交两个结果。

### 3.2 ChangeLocus

第一版使用闭合、版本化的作用位置联合类型：

```text
ChangeLocus =
  LanguageStructure {
    language_id,
    lect_id
  }
  | SpeechCommunity {
      community_id,
      lect_id
    }
```

- `LanguageStructure` 表示对某个 language/lect 已常规化结构的作用位置，不要求 SpeechCommunity 已存在；WS-1 的结构 ChangeSet 只能使用该分支。
- `SpeechCommunity` 表示一个已经存在且可验证的 community/lect 聚合。它只有在 SpeechCommunity、Variation 和 replay 边界的独立 ADR 接受后才能进入生产历史。
- ChangeSet envelope 不再要求伪造一个 community 字段。需要社区证据的 process 若没有合法 community locus 必须被验证器拒绝。
- 新 locus variant 会改变持久化和 replay 语义，必须通过新 ADR 与显式迁移加入，不能用自由字符串扩展。

## 4. UsageObservation 边界

版本化使用观察保存于独立的 `UsageCorpus`/observation stream，不直接混入结构 LanguageState：

- observation 保存 token/construction、time、community、register、task、source 和版本；
- corpus 拥有独立 schema 与 semantic hash；
- OperationContext 锁定参与某次模拟的 corpus hash；RunLedger 保存该不可变锁；
- 由 observation 计算的 `CorpusStatistics` 是可重建派生数据，不进入 LanguageState hash；
- 受频率驱动的 ChangeSet 必须引用 observation/corpus lock 和具体 process model；
- observation 的新增不自动等同于结构变化。

`UsageCorpus` 也必须有唯一、可审计的写入边界，但它不是第二个 LanguageState writer：

- application command 先验证 observation schema、source/provenance、typed IDs、
  expected project-manifest corpus root 与 idempotency key；
- 验证后的 `ObservationBatch` 与 corpus-root candidate 都是 immutable
  content-addressed object；项目内 corpus 的新 root 只能作为 ProjectManifest 引用，
  由 ADR-012 的唯一 `project.json` commit 与其他项目权威引用一起发布，不存在第二个
  可变 corpus-head publish point；
- Genesis 与 legacy root 物化都先创建并引用一个不可变的空 corpus root；后续新 root
  产生独立 `UsageCorpusHash`，OperationContext 只能锁定已发布 manifest 所引用的 root；
- UI、LLM、Python research bridge、query service 和 storage adapter 不能自行追加或
  原地改写 corpus；storage port 只执行应用层已授权的物理写入；
- 运行时 cache、统计或 evaluator 输出不得伪装成 observation batch。

如果未来需要跨项目、独立发布的外部 corpus aggregate，必须另写 ADR 决定其身份、
lease、发布与项目锁定边界；WS-1 不允许通过一个可变外部 head 绕过 ADR-012。这样既
保留研究输入的可审计性，又避免运行时缓存或统计值成为第二个权威语言状态或第二个
项目发布点。

## 5. v2 StateRevision 迁移

不尝试从两个完整状态的差异推断真实音变、类推或语法化机制。v2 历史只导入为唯一 persisted replay-root kind `LegacyHistoryBoundary`；不得再并列定义 `LegacyStateBoundary` 或把 `ImportedCheckpoint` 当成第二种 root。

`LegacyHistoryBoundary` 至少包含：

- boundary identity、schema/version 与 target language/lect；
- 一个 `ImportedCheckpoint` payload 及迁移后的 `StateSemanticHash`；
- source schema、原历史 hash、原状态 hash、source archive ref/content hash；
- migration loss report、可选 `MigrationResolutionMap` ref 和迁移器版本；
- 明确的 provenance discontinuity，声明 boundary 之前的机制 provenance 不完整；
- 创建该 boundary 的 Migration/Import OperationId 与 dependency locks；
- 初始 `HistoryHeadHash` 所需的 canonical boundary content hash。

`ImportedCheckpoint` 只是 boundary 内的状态 payload 名称，不拥有独立 replay-root 身份。原始归档保持只读；只有 unresolved hard item 清零并通过 ADR-014 state-only migration validation 的 checkpoint 才能成为可执行 v3 head。迁移后的后续生产变化全部使用 v3 ChangeSet，不把自动 diff 生成的效果描述为实证历史事件。

## 6. 验收标准

- 具名 domain owner 与独立 architecture、linguistics、migration reviewer 已登记；作者和 owner 不占 independent reviewer 槽位；
- 多实体过程只能全成或全败；
- WS-1 可以在没有 SpeechCommunity schema 的情况下提交合法 `LanguageStructure` locus，且不能伪造社区作用位置；
- 每个生产 ChangeSet 引用合法 OperationId；JobId/AttemptId 不进入 effect 语义或 LanguageState hash；
- ChangeSetId/EffectId 在 reduction 前稳定分配，不依赖 post-state/content hash；
- effect 顺序、precondition 和 postcondition 可验证；
- ChangeSet post-state hash 不参与其所引用的 `StateSemanticHash` 计算，不存在 hash 自引用；
- 在线状态与 Genesis root/`LegacyHistoryBoundary` + ChangeSet 回放的 `StateSemanticHash`、`HistoryHeadHash` 分别相等；
- 删除快照后仍能重建权威状态；
- CorpusStatistics 可删除并从 UsageCorpus 重建；
- 项目内 UsageCorpus append 经 expected-root 校验，批次/root 对象不可变，并且只有
  ADR-012 的单 ProjectManifest 发布能使新 root 可见；失败时旧 manifest 仍引用完整旧
  root，未引用对象可由 GC 回收；
- v2 导入只产生一个 `LegacyHistoryBoundary` persisted root，明确暴露 provenance discontinuity；
- 任意完整状态替换不能进入 v3 生产历史；
- property、replay、migration 和故障注入测试覆盖事务边界。

## 7. 后果

历史事件会比完整快照更严格，reducer 和 effect migration 也需要长期维护。相应收益是变化可以回答“何时、何地、在何种环境、由什么依据、改变了哪些实体”，并支持可证伪的历时模型。
