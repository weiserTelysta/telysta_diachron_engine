# Project、Operation、Run、Job 与 Attempt 合同草案

- 状态：`ADR-011 acceptance evidence / planning only`
- 日期：2026-07-17
- 对应工作包：`R0A-02`、`R0A-03`
- 决策来源：[ADR-011](./adr/ADR-011-project-manifest-run-ledger-job-identity.md)
- 机器可读草案：[ADR_011_SCHEMA_DRAFT_V1.json](./ADR_011_SCHEMA_DRAFT_V1.json)
- Schema 记录 fixture：[`tests/fixtures/adr_011_schema_records_v1.json`](../tests/fixtures/adr_011_schema_records_v1.json)
- 序列 fixture：[`tests/fixtures/adr_011_sequences_v1.json`](../tests/fixtures/adr_011_sequences_v1.json)

本文保留 ADR-011 的规划评审材料，不是生产持久化格式。当前不可变输入 v2
唯一合同见 [ADR-011 §14](./adr/ADR-011-project-manifest-run-ledger-job-identity.md#14-r1-01a-不可变输入合同)；
它拒绝本草案 spec v1/sentinel，不隐式迁移，不修改旧 history/storage/Tauri 命令。

## 1. 用户可见问题

用户需要在同一项目中多次创世、创作、模拟、比较、取消、重试和迁移，同时明确区分：

- “我要求系统做什么”；
- “哪组确定性输入被执行”；
- “后台任务是否完成”；
- “哪个结果真正进入语言历史”；
- “旧项目中哪些历史来源已经不可知”。

如果这些问题仍由一个 `run_id` 表达，取消、恢复、作者修改和模拟提交都会产生错误 provenance，甚至让 Job 重试改变语言历史身份。

## 2. 最小对象与不变量

| 对象 | 权威职责 | 不得承担的职责 |
|---|---|---|
| `ProjectManifest` | 项目身份、history heads、event store root、RunLedger head、迁移元数据 | UI 选择、worker lease、进度和日志 |
| `OperationSpec/Context` | 一次用户或系统语义请求、base history、全部模型/数据/规则/registry/RNG 锁、actor provenance | worker 尝试、可变进度、隐式重试参数 |
| `RunSpec` | Operation 下一个 candidate/replicate/counterfactual 的不可变确定性输入 | 提交决定、Job 生命周期 |
| `RunLedgerEntry` | Operation/Run 声明、staging 来源和 commit/abandon/reject disposition | LanguageState 副本、worker 心跳 |
| `JobRecord` | 持久化调度、cursor、cancel/interrupted/completed 和 staging locator | ChangeSet identity、语言 semantic hash |
| `AttemptRecord` | initial/restart/resume 的一次 worker 尝试 | 修改 RunSpec 或覆盖旧 Attempt |
| `CheckpointRecord` | 完整恢复锁、RNG frontier、staging prefix 与 checksum | “尽量恢复”或缺锁后的语义推断 |

硬不变量：

1. `ProjectId → OperationId → zero-or-many RunId → JobId → AttemptId` 使用不同强类型 ID；
2. `ChangeSet` 必须引用 `OperationId`，可引用 producing `RunId`，不得引用 `JobId/AttemptId` 作为语义身份；
3. OperationSpec 与 RunSpec 登记后不可原地改变；改变参数、seed、base history、模型、数据或规则必须创建新 Operation；
4. Job `Completed` 只证明 durable staging 完成，不等于 Operation committed；
5. restart 保持 Operation/Run/Job 不变并创建新 Attempt；resume 还必须锁定完整 checkpoint 与 RNG frontier；
6. commit 使用 `OperationId + expected_history_hash`，并原子更新 history、RunLedger disposition 与 manifest head；
7. legacy v1 迁移只创建 `LegacyImport + LegacyHistoryBoundary`，不得为旧 event 推断虚假的 Operation 或机制。

规划期 Schema 的五类 ID 值已由 R1-01A 的独立 Rust 强类型封装交叉检查；
字节语法与兼容边界统一见 [ADR-011 §4](./adr/ADR-011-project-manifest-run-ledger-job-identity.md#4-决策分离五类身份)。
当前 `EntityId v1` 目录没有扩张，Operation/Job/Attempt 不进入其 parser。
planning schema 的 proposed-kind 标签保留原评审上下文；值检查通过不代表整份
记录 schema、父子关系、锁、hash 或 disposition 获得生产验证。

2026-10-14 修订：采用固定输入 Operation；candidate/replicate 仅通过唯一
`role + runKey` 派生流根，不能 override 父 parameter/model/seed/budget。
sweep/替代模型改变输入时创建新 Operation。预算和完整 frontier 的唯一语义定义
见 [ADR-013 §3.4](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md#34-counter-overflow-与-resume)。
schema validator 之外还须检查这些跨记录关系；当前 unit helpers 是 planning oracle，
不能签发生产 validated context。rootSeed 已同步 ADR-013 的规范十进制字符串
决定；新 v2 输入声明在 Rust 落实该编码，不表示旧 RunContext、Tauri command、
frontier/cursor 或可执行上下文已升级。原 schema/Node/Rust 交叉检查保持规划范围。

ProjectManifest 的 authority hash/profile/coverage 唯一见
[ADR-012 §3.2](./adr/ADR-012-project-package-commit-authority.md#32-authority-hash-覆盖与规范字节已接受开发合同)。
planning schema 已显式加入 stateSemanticHashes 与 dependency bundle root；
state/history branch key 集必须相等。主 record bundle 的 hash 仍是格式 sentinel；
[独立 known-answer review vectors](../tests/fixtures/project_authority_hash_review_v1.json)
才有可重算规范字节，二者不得混用。工具只校验 manifest 局部关系，不验证可达图。

## 3. 与当前 v1 的迁移映射

| 当前 v1 | 目标解释 | 迁移限制 |
|---|---|---|
| `ProjectHistory.context.project_id` | `ProjectManifest.projectId` | 只有通过现有 ID 验证后才沿用 |
| 单一 `RunContext` | `LegacyImport Operation` 的 source lock | 不能把它解释为项目全部真实操作的共同 Run |
| `ProjectEvent.run_id` | legacy archive 内的旧执行标签 | 不批量转换成每个事件的 Operation provenance |
| `Genesis/StateRevision` 全状态事件 | `LegacyHistoryBoundary` 的输入 archive | 不从 state diff 推断音变、类推、社群或因果过程 |
| `ProjectFile.historySha256` | source artifact/history integrity evidence | 新 manifest/history/ledger hash 另行计算，不复用旧 hash 含义 |
| desktop demo checkpoint | 技术 Spike 或迁移测试向量 | 不进入 ProjectManifest、RunLedger 或正式 JobStore |
| `ProjectSession.run_id` | v1 read-model 字段 | 新 UI 必须分别展示 Operation、Run 和 Job；迁移期不得改写旧项目 |

迁移必须先归档原始 bytes 和 checksum，再在隔离 staging 生成目标工件；目标验证或原子发布失败时只保留原项目和诊断，不产生半迁移目录。

## 4. 四条序列 fixture 的判定

### 4.1 Genesis

`Genesis Operation → candidate Run → Job/Attempt → verified staging → atomic ProjectManifest + Genesis boundary + RunLedger commit`。失败时不得出现可打开的空项目。

### 4.2 Authoring

同步作者修改可以只有 Operation，没有后台 Run/Job；它仍需 actor provenance、base history、canon impact 和 committed ChangeSet。没有随机行为时显式使用 `NoRng`。

### 4.3 Simulation

一个 Simulation Operation 可以登记多个 Run。多个 Job 可以全部 `Completed`，但只有用户选择且通过验证的 Run 能提交；其余结果保留为未提交研究证据，不能自动成为语言历史。

同一 Operation 下的这些 Run 继承相同输入；不同参数/模型/seed 的比较使用多个
Operation，按 ADR-011 的固定输入决定处理。

### 4.4 Legacy import

迁移器保存 source schema/hash/archive 和 provenance discontinuity，创建单个 LegacyImport Operation 与 LegacyHistoryBoundary。未知旧操作保持未知。

## 5. 故障与负例矩阵

| 故障点 | 必须观察到的结果 | 禁止结果 |
|---|---|---|
| 相同 idempotency key、不同 request hash | 拒绝并返回既有 Operation 冲突 | 覆盖或创建第二个隐式 Operation |
| staging 的 base history 已过期 | 保留为 stale staging，拒绝 commit | 自动 rebase 或覆盖新 head |
| checkpoint 缺 RNG frontier/依赖锁 | 只允许 restart | UI 将 best-effort 标成 resume |
| 同一 Run 的完整 Attempt 输出 hash 不同 | determinism failure，全部隔离 | 选择“看起来最好”的结果提交 |
| crash：history 已写、ledger/manifest 未写 | 恢复到完整 pre-commit 或 post-commit | 可加载的分裂项目 |
| crash：manifest 已发布、Job 尚未 Completed | 以 manifest/history/ledger 收敛 Job | 重复提交 ChangeSet |
| JobStore 丢失 | 已提交语言历史不变 | 从 Job 日志重构权威语言状态 |
| v1 event 无法映射机制 | 保留未知 legacy boundary | 伪造逐事件 Operation/community/process |

fixture 的负例只登记期望判定和稳定错误码；R1 的 production implementation 必须再增加 storage fault injection、property、cancel-race、restart/resume 和 migration tests。

## 6. crate 与客户端责任矩阵

| 边界 | 负责 | 不负责 |
|---|---|---|
| `telysta-core` | typed IDs、Operation/Run 语义锁、ChangeSet 引用、canonical validation/hash | async worker、文件替换、Tauri DTO |
| `telysta-application` | command/idempotency、Operation/Run 注册、Job 提交、staging 重验、commit 编排 | 自行判断语言 effect 合法、绕过 StateTransaction |
| `telysta-storage` | manifest/history/ledger 原子事务、JobStore、staging/GC、migration journal | 生成语言变化、把 derived index 当权威 |
| Tauri/CLI | versioned command/query、用户选择、进度与恢复选项展示 | 构造 OperationContext、RunLedger、JobRecord 或 ProjectManifest |
| Python research | 生成 ExperimentSpec、参数/数据提案和对照报告 | 写 manifest/ledger、签发 validated context、提交 ChangeSet |

架构结论：当前 `ProjectHistory` 和 desktop demo worker 只能作为迁移来源和故障 fixture，不能直接重命名后扩展成目标实现。

## 7. 语言学与 provenance 评审

身份分层足以表达以下差异：

- `Authoring Operation`：作者批准、破格、canon 扩充或 retcon；
- `Structural ChangeSet`：已验证的语言结构变化，但不自动宣称社会传播；
- `Simulation Operation/Run`：锁定 TheoryProfile 后得到的候选机制结果；
- `LegacyHistoryBoundary`：只证明旧状态被导入，不证明未知过程；
- `Job/Attempt`：计算和恢复事实，不是语言学事件。

因此它可以避免把作者决定、机制模拟、结构提交和旧历史未知性混成一个 run。但 ADR-009 的 typed `ChangeLocus`、ADR-010 的 Genesis trust boundary 仍必须分别 Accepted，ADR-011 本身不授权 LanguageState v3 或真实传播模型。

## 8. 当前评审结论

| ADR-011 接受条件 | 证据 | 状态 |
|---|---|---|
| 最小 schema 草案 | `ADR_011_SCHEMA_DRAFT_V1.json` + `adr_011_schema_records_v1.json`；Draft 2020-12 validator 与 Rust grammar cross-check | Ready for review |
| Genesis/Authoring/Simulation/legacy fixtures | `adr_011_sequences_v1.json` | Executable review checks added |
| stale/idempotency/restart/resume/crash 设计 | 第 5 节与 negative cases | Ready for review |
| core/application/storage/Tauri 责任矩阵 | 第 6 节 | Architecture self-review complete |
| provenance 语言学边界 | 第 7 节 | Linguistic self-review complete |
| v1 migration 可停止/回滚/不伪造 | 第 3–5 节 | Migration self-review complete |

2026-10-16 ADR-011 已获三个独立 AI 会话的本地开发合同接受，人工等待按用户要求移除。评审来源与范围见 [AI 接受记录](./evidence/AI_LOCAL_DEVELOPMENT_V1.json)；planning schema 仍不是生产格式，后续 writer 必须版本化并实际验证。
