# R0A Platform Contract Pack v1

- 状态：`Review-ready planning contract / production implementation forbidden`
- 日期：2026-07-17
- 对应工作包：`R0A-03`
- 身份前置：[ADR-011](./adr/ADR-011-project-manifest-run-ledger-job-identity.md)
- 发布与存储提案：[ADR-012](./adr/ADR-012-project-package-commit-authority.md)
- RNG 前置：[ADR-013](./adr/ADR-013-rng-compatibility-and-distribution-versioning.md)

本文冻结 R1 walking skeleton 的边界和验收协议，不冻结 LanguageState v3、Genesis、Grammar、ChangeProcess 或语言学模型。ADR-011～013 未 Accepted 且 G0A 未关闭前，本文只能用于 fixture、假任务和评审，不能成为新的生产 writer。

## 1. 用户问题与范围

用户必须能够关闭桌面窗口、取消或重启后台任务、比较多个候选、在历史已经变化时保留旧结果，并在多年后知道一个项目能否原样重演。平台必须回答五个互不混淆的问题：

1. 用户请求了什么语义操作；
2. 哪一组锁定输入被运行；
3. 后台执行进行到哪里；
4. 哪个 staging 结果被提交；
5. 当前安装是否仍能执行、只能调用 legacy runner，或只能审计归档。

R0A-03 只覆盖 application、JobStore、journal/cursor、staging、query、dependency bundle、ReplayCapability 和存储发布边界。它不声称任何生成结果具有语言学真实性。

## 2. 假设分类

| 断言 | 分类 | 处理 |
|---|---|---|
| Rust 是 Project、Operation、Run、历史与存储的唯一生产 authority | Hard architecture constraint | Webview、Python、LLM 不得写权威状态 |
| 一次 commit 只能有一个可恢复的发布点 | Hard correctness constraint | 采用 ADR-012 的 manifest publish point |
| Job 进度和日志可以丢失而不改变语言历史 | Hard semantic constraint | JobStore 独立于 semantic state |
| SQLite 更适合大项目 | Research hypothesis | R1 benchmark 后决定；不能先设为 authority |
| 用户偏好即时进度动画 | Creative/product preference | 由可补取 journal 投影，不改变协议 |

## 3. 责任与依赖方向

```text
Tauri / CLI
    ↓ versioned DTO only
telysta-application
    ↓ validated contexts / use cases
telysta-core          telysta-storage
    ↑ domain rules       ↑ package, job, staging, query persistence
    └────────────────────┘
```

| 边界 | 负责 | 禁止 |
|---|---|---|
| `telysta-core` | typed identity、Operation/Run locks、StateTransaction、领域验证、semantic hash | async runtime、文件系统、Tauri DTO |
| `telysta-application` | command/idempotency、授权、注册 Operation/Run、调度、staging 重验、commit use case | 直接改文件、复制 reducer、构造第二 LanguageState |
| `telysta-storage` | project package、单发布点、JobStore、staging、GC、query projection、migration journal | 产生语言学 effect、从 Job 日志重建历史 |
| Tauri/CLI | 版本化请求、展示、用户确认、路径 capability | 反序列化后自行授予 OperationContext、写完整 state |
| Python/LLM | 提案、解释、实验输入和报告 | 签发 validated context、提交 ChangeSet、写 manifest/ledger |

`telysta-application` 必须是新的独立 crate。`core` 不依赖 application/storage/Tauri/async；`application` 不依赖 desktop；desktop 不直接调用 storage writer。依赖方向用 CI 测试固定。

## 4. Application command/query 合同

每个 wire 对象都有独立 schema，而不是只依赖一个通用 envelope：

```text
CommandRequest  = schemaVersion + requestId + commandSchema + payload
                + idempotencyKey? + expectedHistoryHash?
CommandResponse = schemaVersion + requestId + resultSchema + payload
CommandError    = schemaVersion + requestId + stableCode + retryability
                + fieldPath? + currentHistoryHash? + details
DomainEvent     = schemaVersion + projectId + sequence + eventSchema
                + payloadHash + payload
```

硬规则：

- mutation 必须声明 idempotency key；相同 key + 相同 canonical request 返回同一 Operation/Job，相同 key + 不同请求返回稳定冲突码；
- `requestId` 只用于追踪，不成为 Operation、Run、Job 或 ChangeSet 身份；
- 所有错误必须区分 `never_retry`、`retry_same_request`、`retry_after_refresh`、`restart_only`；
- DTO 中未知 schema 被拒绝或进入显式 migration，不使用 serde default 猜测新语义；
- Webview 只接收分页 projection、diff、诊断和 opaque capability token，不接收可写完整 LanguageState；
- Tauri `emit` 只是低延迟提示，客户端必须能按 cursor 补取遗漏事件。

## 5. JobStore、journal 与 cursor

Job 状态机遵守 ADR-011，最小执行序列为：

```text
Queued → Running → CancelRequested → Cancelled | Failed | Completed
crash: Running → Interrupted → Restartable | Resumable
```

`JobRecord` 保存当前状态和最后 durable event sequence；`AttemptRecord` append-only；`JobEvent` 使用每 Job 单调、无重复的 `u64` sequence。`list_job_events(job_id, after_sequence, limit)` 必须：

- 返回 `(events, nextCursor, hasMore, retainedFrom)`；
- 在 cursor 已被 retention 删除时返回 `cursor_expired` 和可重建 Job snapshot；
- 让相同 cursor 重试得到相同已保留窗口；
- 不把日志文本、百分比或 Tauri 事件当作完成证明；
- 只有 durable staging 已校验并记录后才能标记 `Completed`。

取消是协作请求，不是假装线程已停止。worker 在声明的 safe point 检查 cancel；强制终止后由 lease/heartbeat 判定 `Interrupted`。没有完整 checkpoint lock 的 UI 只能显示 Restart。

## 6. Staging、commit 与 GC

长任务不持有 project write lease。它写入由 `OperationId/RunId/JobId/AttemptId` 定位的隔离 staging，至少包含：

- artifact schema、canonical content hash 和大小；
- base/expected history hash；
- OperationSpec/RunSpec hash 与 dependency bundle hash；
- engine/compiler/reducer/RNG/distribution locks；
- validator report、产生 Attempt 和完成时间；
- 如果可 Resume，checkpoint schema、RNG frontier、已写分片和 checksum。

commit 顺序固定为：重新读取 head → 验证 expected hash → 重新验证 staging → 经 `StateTransaction` 产生权威结果 → 先写不可变对象 → 原子发布新 manifest。Job 完成、staging 完成和 commit 完成是三个不同事实。

GC 只删除：无 manifest/ledger 引用、超过 TTL、没有 active lease、且 retention policy 允许的 staging。冲突或 determinism failure 的结果先进入 quarantine/审计保留；不得以“失败所以无用”为由立即删除证据。

## 7. Query projection

query 是绑定某一 history hash 的派生读模型。每页响应至少返回 `projectionSchema`、`projectionVersion`、`asOfHistoryHash`、稳定排序键和 cursor。若 head 已变化：

- 需要一致快照的查询返回 `projection_stale`；
- 明确允许旧快照的 compare/explain 可继续，但 UI 必须显示基点；
- projection 缺失、损坏或版本过旧时可删除重建；
- projection 绝不参与 commit、replay 或 semantic hash。

## 8. DependencyBundle 与 ReplayCapability

每个可重演 Operation/Run 必须引用 content-addressed `DependencyBundle`，其中每项记录：kind、schema、content hash、版本、许可证/来源、兼容 ABI/IR 和本地可用性。仅保存 URI、包名或“latest”不构成 replay lock。

| Capability | 含义 | 允许行为 |
|---|---|---|
| `Native` | 当前 Rust engine 可验证并执行全部锁 | replay、restart；锁完整时 resume |
| `Legacy` | 固定 legacy runner/compat adapter 可执行，输出仍需当前边界重验 | 隔离 replay；不能静默升级语义 |
| `ArchiveOnly` | 输入或执行器不可用/不再许可，但 bytes、hash、日志和结果可审计 | 查看、导出、解释限制；禁止伪 replay |
| `Unavailable` | 必需 payload 缺失或 hash 不符 | 阻止执行并给出精确缺项 |

capability 是对一个具体 Operation/Run + dependency bundle + app build 的判定，不是项目永久标签。安装新兼容包后可重新计算，但不得重写旧 ledger。

## 9. 存储权威与 v1 迁移

当前 `telysta-project-file.v1` 仍是唯一已实现权威格式。R1 目标不能让 manifest、history 和 ledger 通过三次独立替换冒充原子事务。ADR-012 建议：

1. content-addressed history/ledger/dependency 对象先写入并校验；
2. 只有一个可变 `ProjectManifest` publish point 指向完整 object graph；
3. manifest 原子替换成功才表示 commit；未引用对象可由 GC 回收；
4. JobStore 是独立操作事实源，不能成为项目语义恢复来源；
5. SQLite 仍是可删除 projection，除非后续 benchmark + 新 ADR 明确改变。

v1 迁移先归档原 bytes/hash，再构造 `LegacyHistoryBoundary` 和不可变对象，最后一次性发布目标 manifest。失败时只能看到完整 v1 或完整 v2，不得让 loader 猜测半迁移目录。

## 10. R1 假任务验收矩阵

R1 必须用不依赖 LanguageState v3 的 deterministic fake operation 证明：

| 场景 | 必须通过 |
|---|---|
| 相同请求重复提交 | 同一 Operation/Job；不重复执行或提交 |
| 相同 idempotency key、不同 payload | 稳定冲突错误 |
| 两个 staging 基于同一 head | 最多一个 commit；另一个保留 stale |
| Tauri 漏掉事件/重启 | cursor 补取并恢复 snapshot |
| worker 强杀 | lease 过期后进入 Interrupted；无双 worker |
| checkpoint 缺依赖/RNG frontier | Restart only |
| commit 各写入边界崩溃 | 重开后仅完整 pre/post state |
| 删除 JobStore/index | 已提交项目不变，projection 可重建 |
| dependency payload 缺失/篡改 | Unavailable；不从 URI 猜测替代 |
| v1 migration 中断 | 原 bytes 保留；恢复或回滚确定 |

对应验证类别必须包含 unit、property、schema compatibility、fault injection、migration corpus、cross-process replay、IPC E2E 和性能基线。

## 11. 当前结论与审批门

本合同已把 R1 的 crate、API、Job、journal、staging、query、dependency、replay 和 storage 边界收敛到可实现的 walking skeleton，并显式暴露 v1 单文件存储与 ADR-011 多对象目标之间的冲突。

它仍不能被标记为 Accepted：

- ADR-011 的身份与迁移决定尚无独立批准；
- ADR-012 的单发布点/package authority 尚无 code owner、storage reviewer 和 migration reviewer；
- ADR-013 的 RNG compatibility 尚无独立 determinism reviewer；
- 当前仓库没有 reviewed clean-checkout baseline，也没有具名 owner/capacity。

在上述条件满足前，允许补 fixture、fake-task protocol 和 fault matrix；禁止创建新的 production writer、JobStore、ProjectManifest v2 或桌面 mutation command。
