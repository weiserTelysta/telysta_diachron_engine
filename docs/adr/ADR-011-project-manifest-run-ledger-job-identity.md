---
document_type: adr
decision_status: accepted
implementation_status: partial
normative_scope: target
last_verified: 2026-10-16
owner: "ai:/root (execution coordinator)"
reviewers:
  - ai:/root/ai_architecture_acceptance
  - ai:/root/ai_migration_acceptance
  - ai:/root/ai_linguistic_provenance_acceptance
---

# ADR-011：ProjectManifest、RunLedger 与 Job Identity

- 状态：`Accepted for AI-reviewed local development; production implementation remains staged`
- 日期：2026-07-16
- 决策范围：项目身份、语义操作、确定性运行、后台 Job/Attempt、staging/commit、恢复与现有单 RunContext 历史迁移
- 前置决策：ADR-006
- 设计上下文：ADR-007、ADR-009、ADR-010；这些 ADR 不构成本 ADR 的循环前置

2026-10-16 经三个独立 AI 会话接受为本地开发技术合同；执行模式、用户授权及
接受范围见 [Agent 操作模型 §3.1](../AGENT_OPERATING_MODEL.md#31-用户授权的-ai-本地开发审阅2026-10-16)。
这不是目标 writer、迁移器、语言学真实性或跨平台发布已验证的声明。

## 1. 用户与工程问题

一个长期项目会经历 Genesis 编译、作者扩充、规则 dry-run、正式结构变化、模拟实验、retcon、迁移和导入。如何让用户能够安全地执行、取消、恢复和重试这些操作，同时保证：

- 一个项目可以保存多次操作和多次模拟，而不是永远绑定到单个 RunContext；
- 语义输入、随机流、模型锁和历史基点不可被执行层静默改变；
- Job 重试、worker 崩溃或进度更新不会改变语言状态身份；
- 只有经过验证的 staging result 能原子进入权威历史；
- 旧项目不会因迁移而获得被伪造的逐事件机制或运行来源？

## 2. 当前问题

当前 `ProjectHistory` 将一个 `RunContext` 与全部事件放在同一 envelope。该结构适合作为最小地基，但会把以下不同概念压成一个 run：

- 项目长期身份；
- 一次作者或模拟意图；
- 一组不可变的确定性执行输入；
- 后台调度、取消和崩溃恢复；
- worker 的一次具体执行尝试。

如果直接在该结构上扩展 Job 或多轮模拟，将产生以下歧义：重新运行是否创建新历史、Resume 是否可以改变 seed、作者修改属于哪个 run、并发 staging 如何判定过期，以及 JobId 是否会污染 semantic hash。

## 3. 假设分类

| 假设 | 分类 | 处理方式 |
|---|---|---|
| 项目、语义操作、确定性运行、Job 和 Attempt 必须拥有不同身份 | Hard architecture constraint | 使用不同的 typed ID 和 schema |
| 同一语义运行的调度重试不得改变语言结果 | Hard determinism constraint | RunSpec 不可变；Attempt 不参与语义输入 |
| Job 状态是语言历史的一部分 | Unsupported assumption | JobStore 与权威语言历史分离 |
| 崩溃 checkpoint 足以安全 Resume | Conditional engineering claim | 只有完整锁和恢复 schema 通过验证时才允许 Resume |
| 可以从 v1 事件差异恢复每次真实操作 | Unsupported assumption | 迁移为显式 LegacyHistoryBoundary，不伪造 Operation 来源 |

## 4. 决策：分离五类身份

```text
ProjectId
└── OperationId
    └── RunId (zero, one, or many)
        └── JobId (persistent scheduling unit)
            └── AttemptId (one worker execution)
```

五种 ID 使用不同 `EntityKind` 或等价的强类型封装，不能互换、复用或仅依靠字符串前缀区分。

2026-10-16 R1-01A 身份切片采用等价封装：Rust `execution_identity` 模块定义
`ProjectId`、`OperationId`、`RunId`、`JobId`、`AttemptId`，词汇版本为
`telysta-execution-id.v1`。wire 值仍为 `telysta:<kind>:<local-value>` 字符串，
local-value 直接复用现有 v1 的验证函数，不新增或放宽语法。所有构造与 serde
入口均检查固定 kind；私有字段、不同类型和 compile-fail checks 防止身份互换。
这不是项目或记录 schema，也不证明 ID 对应对象已登记、属于某个父对象或可提交。

现有 `telysta-entity-id.v1` kind 目录保持冻结；其 parser 继续拒绝 operation、job、
attempt。仅已有 Project/Run 支持从旧 `EntityId` 的显式、检查 kind 的转换，
保留原 bytes，不自动迁移历史或推断来源。新记录必须独立声明身份词汇与自身
schema；本片尚未实现 OperationSpec/RunSpec、registry、ledger 或 writer。

### 4.1 ProjectManifest

`ProjectManifest` 是项目容器和当前权威 head 的入口，至少锁定：

- manifest schema/version；
- ProjectId；
- 创建来源或 GenesisArtifact hash；
- 一个或多个命名 history/branch head 及其 semantic hash；
- RunLedger schema 与当前 ledger hash/head；
- 权威事件存储格式和根 hash；
- 项目内 UsageCorpus 的不可变 root hash；
- registry、迁移与项目格式兼容信息；
- ADR-012 唯一拥有的 `ProjectAuthorityHash`；计算时排除
  `projectAuthorityHash` 字段本身。

Manifest 不保存 UI 选择、进度百分比、当前窗口、日志路径或 worker lease。更新 history head、ledger disposition 和 manifest 必须属于同一个可恢复 commit；物理实现采用 [ADR-012](./ADR-012-project-package-commit-authority.md) 提议的“先写不可变对象、再原子发布唯一可变 manifest”，而不是把多文件顺序替换称为事务。任何一步失败时不得留下可加载的分裂项目。

### 4.2 Operation 与 OperationContext

`OperationId` 标识一次语义请求。第一版 `OperationKind` 至少预留：

- `Genesis`；
- `Authoring`；
- `Simulation`；
- `Migration`；
- `Retcon`；
- `Import`。

每个 Operation 保存不可变、版本化的 `OperationSpec`：

- OperationId、kind、ProjectId 和目标 history/branch；
- base/expected history hash；Genesis 创建操作可以使用显式空基点；
- 用户已确认的命令输入和 command schema；
- engine/compiler/reducer 版本；
- RegistryBundle、data、RulePack、TheoryProfile 和其他模型锁；
- TimeModel/time reference；
- RNG schema、root seed 和稳定 path contract；无随机行为时显式标记 `NoRng`；
- provenance actor/source 与 AuthorIntervention 信息；
- canonical request hash 和 idempotency key。

本轮 Proposed 决定采用**固定输入 Operation**：OperationSpec 同时锁定
`parameterSha256`。parameter sweep、替代 TheoryProfile、不同 seed 或改变基点的
counterfactual 各自创建新的 Operation；研究分组可以关联它们，但不能以分组标签
绕过 Operation 身份和幂等边界。不在本版引入可变的实验/变体目录。

`OperationContext` 是 Rust application service 对 OperationSpec、项目基点和所有锁完成验证后构造的内存能力。反序列化一个字段相同的 JSON 不能直接获得已验证 OperationContext。

OperationSpec 一经登记不得原地修改。改变参数、模型、数据、规则、seed、目标 history 或基点必须创建新的 OperationId。这样不会用一次“重试”重新解释旧历史。

### 4.3 Run 与 RunLedger

`RunId` 标识 Operation 下的一组不可变确定性执行输入。普通操作通常有一个 Run；candidate/replicate 可以在同一 Operation 下登记多个 Run，但参数、模型、数据、规则、root seed 与预算必须继承 Operation。改变这些输入的 sweep/counterfactual 使用不同 Operation。只进行同步验证且不需要执行产物的作者操作可以没有后台 Run，但仍必须拥有 OperationId。

每个 `RunSpec` 至少锁定：

- RunId 与父 OperationId；
- canonical OperationSpec hash；
- 该 run 的参数、replicate/candidate identity；
- RNG schema、root seed、run path root 和 distribution version；
- 全部模型、数据、registry、rule、compiler/reducer 锁；
- base history hash；
- input semantic hash 与预期输出类型/schema。

每个 Run 有已声明的 `role + runKey`，该二元组在 Operation 内唯一；`runKey`
是 1–64 字节的合法 RNG 单段值。随机流根确定为
`Operation.rngLock.pathRoot + "." + role + "." + runKey`，不能由 Attempt、
调度顺序或新生成的随机 ID 派生。除该 pathRoot 外，Run rngLock 与父锁相同；
`Run.parameterSha256 == Operation.parameterSha256`。NoRng 操作仍为 NoRng。

`RunLedger` 是项目级、版本化、append-only 的语义审计账本。它保存：

- `OperationDeclared`；
- `RunRegistered`；
- staging result 的 schema/content hash；
- `OperationCommitted`、`OperationAbandoned`、`OperationRejected` 或 `OperationInvalidated` 等语义 disposition；
- committed ChangeSet/event IDs 与提交后的 history hash。

RunLedger 不保存 worker 心跳、实时进度、日志游标或取消按钮状态。它是操作来源和提交关系的权威记录，但不是第二份 LanguageState；结构状态仍只由 Genesis/Legacy boundary 与已提交 typed ChangeSet 回放得到。ChangeSet 必须引用 OperationId，并可在 provenance 中引用 producing RunId。

### 4.4 JobStore、Job 与 Attempt

`JobId` 是 application 层的持久化调度单位，引用一个已经登记的 RunId。`JobStore` 至少保存：

- JobId、RunId 与 project scope；
- `Queued / Running / CancelRequested / Cancelled / Failed / Interrupted / Completed` 状态；
- 当前和既往 AttemptId；
- worker lease、heartbeat、进度/event cursor；
- checkpoint 元数据；
- staging result locator/hash；
- error、cancel reason 和 restart/resume eligibility；
- Job schema/version 与完整性校验。

`AttemptId` 标识一个 worker 对该 Job 的一次具体执行。每次首次启动、Restart 或 Resume 都创建新的 AttemptId；旧 Attempt 记录不可覆盖。Attempt 可以读取前一 Attempt 的合格 checkpoint，但不能修改 RunSpec。

JobStore 是 Rust 权威的执行状态，但不是语言结构、历史机制或模型证据的事实来源。JobId、AttemptId、heartbeat、progress、日志路径和执行耗时不进入 LanguageState、ChangeSet effect 或语言 semantic hash。

## 5. Operation、Run、Job 与提交生命周期

```text
canonical request
→ validate and register OperationSpec
→ register immutable RunSpec(s)
→ submit idempotent Job
→ one or more Attempt(s)
→ durable validated staging result + Job Completed
→ optional explicit StateTransaction + expected history hash
→ Operation committed or left uncommitted/abandoned
```

### 5.1 请求与提交幂等性

客户端提交必须携带 project-scoped idempotency key。Application service 保存：

```text
(ProjectId, command schema, idempotency key)
→ canonical request hash
→ OperationId
→ optional RunId / JobId
```

- 相同 key 和相同 canonical request 重复提交时，返回已有 Operation/Run/Job，不创建重复对象。
- 相同 key 与不同 request hash 必须返回冲突，不能覆盖旧请求。
- 同一 Run 默认只能有一个当前 Job；恢复流程复用 JobId 并新增 AttemptId。
- Operation 最多提交一次相同语义结果。重复 commit 若 OperationId、ChangeSet hash 和预期 post-history hash 全部相同则返回已有成功结果；任一项不同则冲突并停止。

### 5.2 Restart

Restart 从 RunSpec 的初始状态重新执行：

- OperationId、RunId、JobId 和全部语义锁保持不变；
- 创建新的 AttemptId；
- 不读取旧 checkpoint 作为计算状态；
- 旧 staging result 不得自动参与提交；
- 同一 Run 的确定性结果 hash 应与其他完整 Attempt 相同。

若相同 RunSpec 的完整 Attempt 产生不同语义结果，Job 进入确定性失败，所有结果留在隔离 staging 供诊断，不能选择“看起来更好”的一个提交。

### 5.3 Resume

Resume 从经过验证的 checkpoint 继续，并创建新的 AttemptId。只有 checkpoint 同时锁定并通过以下检查时才允许 Resume：

- checkpoint schema/version 与恢复器版本；
- OperationSpec 和 RunSpec canonical hash；
- engine/compiler/reducer、registry、data、rule 与 TheoryProfile locks；
- base history hash；
- 每个已使用 RngTree stream 的 path、counter/frontier 和 distribution version；
- 已完成阶段、staging prefix hash 与输出 schema；
- checkpoint checksum 和完整性状态。

缺少任一项、版本不兼容、项目基点变化或 checkpoint 无法完整验证时，UI/API 只能提供 Restart，不能把“尽量继续”标为 Resume。

### 5.4 Staging 与原子提交

长任务只写隔离 staging，不持有项目写 lease。staging result 至少锁定 OperationId、RunId、RunSpec hash、base history hash、result schema/content hash 和完整验证报告。

提交时 application service 必须：

1. 重新读取 ProjectManifest 和当前 history head；
2. 验证 expected history hash 仍等于 OperationSpec 的基点；
3. 重验 staging、全部模型/数据/registry/rule locks 和领域不变量；
4. 构造 Proposed/Validated ChangeSet；
5. 通过 StateTransaction 原子应用；
6. 写入新的不可变 history/RunLedger 对象，并通过一次 manifest 替换原子发布完整 object graph；
7. 返回已存在或新产生的 committed operation result。

Job 的 `Completed` 只表示确定性执行和 durable staging 已完成，不表示语言变化已经提交。对于“计算后等待用户选择”的流程，Job 可以先 Completed，而 Operation 保持 staged；对于 Genesis 创建等把执行与提交组合成一个原子 use case 的流程，只有组合事务完成后 Job 才能收敛为 Completed。UI/API 必须分别显示 Job execution state 与 Operation disposition。

若 history head 已改变，结果可以保留为可检查的 stale staging，但不能自动 rebase 或提交。用户必须基于新 head 创建新的 OperationId。

### 5.5 取消、崩溃与恢复

- CancelRequested 只影响 Job/Attempt，不撤销已经原子提交的 ChangeSet。
- 取消或 worker 崩溃不能写入部分权威事件、部分 ledger commit 或半个 manifest head。
- worker lease 过期后 Running 变为 Interrupted；系统根据 checkpoint 验证结果显示 Resumable 或 Restartable。
- 对组合执行/提交用例，storage commit 已成功而 Job 状态尚未来得及更新时，恢复逻辑以已发布 manifest 可达且 hash 正确的 history/RunLedger object graph 为准，把 Job 收敛为 Completed，不重复提交。
- JobStore 丢失不允许破坏已提交语言历史；可以从 RunLedger 和 staging journal 重建可证明的最小终态，但不能虚构进度和 Attempt 细节。

## 6. 不同 OperationKind 的边界

### Genesis

项目创建预先分配 ProjectId，并在隔离 staging 中执行 Genesis Operation。只有 ADR-010 的 VerifiedGenesisArtifact 重验通过后，storage 才能原子写入：

- ProjectManifest；
- Genesis Operation/RunLedger records；
- Genesis history/event；
- 不可变的空 UsageCorpus root；
- 初始 history head。

失败时预分配 ID 可以保留在诊断记录中，但不能出现可打开的半项目。

### Authoring 与 Retcon

作者选择、显式例外、Canon 扩充和 retcon 都是 Operation，不是第二个状态写入者。即使操作同步完成，也必须保存 author provenance、base history hash、impact report 和 committed ChangeSet。没有使用随机数时必须显式 `NoRng`，不能隐式创建随机流。

### Simulation 与实验

Simulation Operation 可以登记输入相同、runKey 不同的 candidate/replicate。替代 TheoryProfile、参数 sweep 或不同 seed 的 counterfactual 分属新 Operation；比较界面可将其组成研究分组。只有用户明确选择且通过领域验证的结果才能产生 committed ChangeSet。未选择、失败或仅用于校准的 Run 仍可留在 RunLedger/研究工件中，但不会自动成为语言历史。

### Migration 与 Import

Migration/Import Operation 必须保存源 schema、源 artifact/history hash、迁移器或导入器版本、原始归档位置、损失报告和机制 provenance discontinuity。它们不能把无法知道的旧状态差异描述为已知语言变化。

## 7. 权威、hash 与 replay 边界

| 工件 | 是否权威 | 进入语言 semantic hash | 可否重建/删除 |
|---|---|---|---|
| ProjectManifest heads | 是，项目入口与提交指针 | 通过所指权威 history 间接决定 | 不可凭缓存替代 |
| Genesis / Legacy boundary + typed ChangeSet | 是，语言结构历史 | 是 | 不可删除 |
| RunLedger Operation/Run/commit relation | 是，操作与来源审计 | 不直接改变结构 hash；其被事件引用的语义锁进入事件/hash | 不可从 Job 日志推测重建 |
| JobStore / Attempt | 仅对执行生命周期权威 | 否 | 可按受控规则清理；已提交终态可收敛重建 |
| staging result | 否，提交候选 | 否 | 可清理；提交后由权威事件表示结果 |
| snapshot / SQLite index / progress cache | 否，派生优化 | 否 | 必须可重建 |

Project load 必须验证 manifest、history 和 RunLedger 的引用完整性。事件引用不存在的 OperationId、ledger 声称提交但 history 没有对应结果、或 manifest head 与事件链不一致时必须停止加载或进入显式恢复流程，不能择一当作真值。

## 8. 现有 v1 ProjectHistory 迁移

当前单一 `ProjectHistory { context: RunContext, events }` 不得通过给每个旧事件批量填充相同 OperationId 来伪造真实操作边界。显式迁移采用以下策略：

1. 在任何写入前归档原始项目/history 字节并记录 source schema、checksum、history hash 和 state hash；
2. 创建新 ProjectManifest，沿用经过验证的 ProjectId；
3. 在 RunLedger 中创建一个 `LegacyImport` Operation，锁定原 RunContext、源 history hash、迁移器版本和 provenance discontinuity；
4. 将旧机制历史保留为只读 source archive，并以 ADR-009 的 `ImportedCheckpoint` / `LegacyHistoryBoundary` 建立新权威起点；
5. 不从完整状态 diff、旧 event 名称或共享 RunContext 推断逐事件 Operation、community、process 或因果机制；
6. authority graph 内的 migration record 保存 source→target ID map、source/target
   state/history canonical hashes、损失/降级报告和 importer/dependency locks，但不得
   保存 target `ProjectAuthorityHash`；
7. 原子发布成功后可以生成 detached migration receipt 记录该
   `ProjectAuthorityHash`；receipt 不得被 candidate manifest、RunLedger、migration
   archive/root 或任何权威 object 引用，也不参与 load、recovery、authority hash 或
   GC reachability，缺失它不改变项目语义；
8. 边界之后的所有生产变化使用新的 OperationId、RunSpec 和 typed ChangeSet；
9. 相同源文件和迁移版本重复执行必须返回同一目标或已完成记录，不能重复追加 LegacyImport。

如果旧项目无法满足源 schema 或完整性验证，迁移停止并保留原文件；不得用“最佳努力”生成可写的新项目。

## 9. API 与存储边界

- Tauri/CLI 只能提交版本化 command DTO、idempotency key 和用户选择，不能构造 OperationContext、RunLedger、JobRecord 或 ProjectManifest。
- `telysta-application` 是创建 Operation、登记 Run、提交 Job、验证 staging 和协调 commit 的唯一 use-case 边界。
- `telysta-core` 定义并验证 Project/Operation/Run 的领域身份、语义锁、ChangeSet 引用和 hash；它不依赖 Tauri 或 async worker。
- `telysta-storage` 提供 ADR-012 的 project package 单发布点、不可变 object graph、JobStore 和 staging 生命周期，但不能自行决定一个语言变化是否合法。
- Python 可以提出 ExperimentSpec、参数或候选数据，但不能签发 OperationContext、提交 ChangeSet、修改 RunLedger disposition 或写 ProjectManifest。
- API 查询必须区分 Operation status、Run evidence、Job state 和 Attempt history，不能把 `Completed job` 等同于 `Committed language change`。

## 10. 验收标准

- 一个项目可以顺序保存 Genesis、两个 Authoring Operation 和多个未提交/已提交 Simulation Run，重开后身份与引用不变；
- 两个并发 Operation 从同一 base 产生 staging 时，最多一个能在 head 未变化的条件下提交，另一个成为显式 stale result；
- 相同 idempotency key + 相同请求返回同一 Operation/Job；相同 key + 不同请求被拒绝；
- Restart 和 Resume 都创建新的 AttemptId，但不改变 OperationSpec、RunSpec、RNG 路径或语义结果；
- 缺少任一恢复锁时 Resume 被拒绝并只允许 Restart；
- 相同 Run 的完整 Attempt 结果 hash 不同会阻止提交；
- 重复 commit 不会重复追加 ChangeSet，冲突结果不能覆盖已有提交；
- crash 可发生在 staging、不可变 history/ledger object 写入、manifest replace 和 Job completion 各边界，恢复后项目只能是提交前或提交后的完整状态；
- JobStore 删除或损坏不会改变已提交 LanguageState；manifest/history/ledger 不一致会被检测；
- v1 项目通过显式 LegacyHistoryBoundary 迁移，原始归档可验证，且不会产生虚假的逐事件 Operation provenance；
- hostile deserialization 不能伪造 validated OperationContext、RunSpec、checkpoint eligibility 或 committed disposition；
- property、replay、migration、idempotency、cancel-race 和故障注入测试覆盖上述边界。

## 11. 后果

正面影响：

- 项目可以承载真实的多轮作者工作和多次模拟；
- 语义操作、确定性运行和后台执行失败不再互相污染；
- 重试、恢复、并发提交和来源解释具有统一身份模型；
- Job 实现可以演进，而不改变语言历史和 semantic hash；
- 旧项目迁移不会伪造历史机制。

成本与风险：

- 需要新的 manifest、不可变 object graph、JobStore schema、可达性验证与 GC；
- operation/run/job/attempt 的 UI 文案必须清晰，否则用户仍会把运行完成误解为变化已提交；
- append-only ledger 和长期实验会增长，需要保留、压缩和导出策略；
- current ProjectHistory 和 desktop demo worker 都只能作为迁移来源或技术 Spike，不能直接扩展成最终模型。

## 12. 本 ADR 不决定

- SpeechCommunity、PopulationVariationState 或 ChangeProcess 的具体 schema；
- 最终 event segmentation、SQLite 布局或对象存储实现；
- 多人协作、云同步或分布式 Job 调度；
- 插件执行边界；
- 模型校准和专家评审结论。

这些事项不能改变本 ADR 的身份分层；若需要改变 Project、Operation、Run、Job、Attempt 或 commit/replay 的意义，必须新增或替代 ADR。

## 13. 接受条件

本 ADR 的技术接受条件如下；第 1 项人员安排已按用户授权改用独立 AI，
其余材料经本轮独立审阅。以下验收设计不等于相应生产实现已完成：

1. 具名 code owner、independent architecture reviewer、linguistics reviewer 和 migration reviewer 已登记；作者和 owner 不占任一 independent reviewer 槽位；
2. ProjectManifest、OperationSpec、RunSpec、RunLedger、JobRecord、AttemptRecord 和 checkpoint 的最小 schema 草案，并由 Draft 2020-12 validator 对实际记录 fixture 执行根对象、未知字段、ID、RNG 与 migration 负例；
3. Genesis、Authoring、Simulation 和 v1 migration 四条 sequence fixture；
4. 至少一组并发 stale-result、重复请求、Restart、Resume 与 commit-crash 故障注入测试设计；
5. storage、application、core 和 Tauri 的责任矩阵通过架构评审；
6. 语言学评审确认 Operation/ChangeSet provenance 足以区分作者干预、结构变化、模拟结果和未知 legacy 边界；
7. migration 评审确认现有项目有可停止、可回滚且不伪造机制的路径。

在状态改为 `Accepted` 前，不得改变现有持久化 ProjectHistory 的身份、正式回放语义或生产项目创建入口。

评审材料已整理为 [Project、Operation、Run、Job 与 Attempt 合同草案](../PROJECT_OPERATION_JOB_CONTRACT_DRAFT.md)，包括规划期 schema、实际记录 fixture、四条序列 fixture、负例、责任矩阵和迁移评审。Schema 记录由 Draft 2020-12 validator 验证，并以 Rust 测试交叉检查已接受 EntityId/RngPath 值语法；技术材料与独立 AI 接受分别记录；当前已接受的是设计合同，生产格式与 writer 仍按实际实现切片验证。
