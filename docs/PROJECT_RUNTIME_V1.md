---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: telysta-project-history.v1
implementation_path: crates/telysta-core/src/project.rs
implementation_constant: PROJECT_HISTORY_SCHEMA
---

# Project Runtime and Transactions v1

- 状态：`Accepted`

当前项目历史 schema 为 `telysta-project-history.v1`；本合同描述它的运行时、事务和
回放边界，不把它扩展为长期 Project/Operation/Run/Job 目标。
- 完成日期：2026-07-13
- 对应工作：`B-004`、`FND-005`、`FND-006`（`FND-007` 的事件信封基础）
- 实现：`crates/telysta-core/src/project.rs`

`LanguageState` 定义单门语言在一个历史时点的语义快照；本合同定义该快照进入正式项目历史时必须具备的运行与事务边界。它不把 Python `EngineHotState`、日志路径、UI 选择、缓存或桌面 demo checkpoint 当作项目真相。

本合同仍准确描述当前 v1 持久化行为，但单一 `RunContext + ProjectHistory` 不是长期多操作/多任务目标。目标身份、ledger、restart/resume 和迁移边界正由 Proposed [ADR-011](./adr/ADR-011-project-manifest-run-ledger-job-identity.md) 评审；在其 Accepted 前不得把 v1 RunContext 直接扩展成 Project/Operation/Job 最终架构。

## 1. ProjectDataLock

`telysta-project-data-lock.v1` 是被选择的数据 manifest 的不可变项目级副本。

- 未使用经验数据的纯创作项目可以持有空锁；
- 一旦锁定某数据集，其 manifest 必须带有 `contentSha256`；只有远程 URI 而没有 payload hash 的 manifest 不能进入可复现实验；
- 每一条 `EvidenceRecord.dataReferences` 都必须指向该项目锁中的数据集；
- 导入或刷新时可以将锁与 `DataRegistry` 逐项比较，任何版本、URI、许可证、覆盖或 hash 漂移都会失败，而不是静默使用新数据。

当前仓库的 PHOIBLE、Concepticon 与 Grambank 文件仍是元数据 manifest，`contentSha256` 为 `null`，所以它们可用于目录和研究准备，不能被锁入可复现项目。实际纵切只可使用经人工审核、固定 payload hash 的小型样本。

## 2. RunContext

`telysta-run-context.v1` 绑定一次模拟所需的不可变输入：

```text
Project ID + Run ID + TimeModel + root seed
+ engine version + RNG schema + ProjectDataLock + RulePack locks
```

`RunContext.rng_tree()` 是正式随机流入口；`RngTree` 的 root seed、路径规则和 schema 不能由反序列化数据替换。时间引用必须匹配 context 的完整 `TimeModel` 指纹，而不只是 schema。规则包目前只记录锁结构；RuleSpec 编译器完成前它不执行任何规则。

## 3. Versioned project events

`telysta-project-event.v1` 包含：类型化 event ID、run ID、连续 sequence、版本化历史时间与 payload。v1 只有两类 payload：

- `Genesis`：项目历史的唯一第一个事件；
- `StateRevision`：带非空原因的完整、已验证 `LanguageState` 修订。

选择完整状态修订而非直接搬运 Python delta，是为了先建立不可绕过的回放边界：事件必须属于同一 run、序号不能跳跃或重复、时间不能倒退、数据引用必须已锁定，且状态中的 provenance 只能引用已经出现的事件或当前事件，并且其 `createdAt` 必须精确等于被引用事件的 `occurredAt`。

这不是最终的语言学事件模型。`FND-007`、祖语编译和历时纵切将增加词汇、音系、构式、接触与家族的细粒度 payload；它们必须在同一 envelope 与 `StateTransaction` 中实现，不能另建并行写入路径。

## 4. StateTransaction 与回放

`StateTransaction` 是正式项目历史的写入入口：

1. `begin` 只接受合法 `Genesis` 与通过验证的初始 `LanguageState`；
2. `revise_state` 在写入前校验语言身份、时间单调性、数据锁与 provenance；
3. `ProjectHistory` 反序列化时执行完整 replay 验证，非法 JSON 不能成为可读取项目；
4. 回放结果与最后一条事件状态相同。

本合同在 2026-07-13 验收时尚未提供 `FND-008` 的正式原子文件存储、迁移器或 SQLite 索引；这些能力随后已由 [Project Storage v1](./PROJECT_STORAGE_V1.md) 完成。桌面 demo 的双槽 checkpoint 仍仅是历史技术 Spike，不得冒充项目存储；本段记录验收时边界，不定义当前 Next。

## 5. 验收

核心测试覆盖：

- 历史 JSON round-trip 与 replay；
- event run 篡改和未来 provenance event 的拒绝；
- payload hash 缺失的 data lock 拒绝，以及 registry manifest 漂移检测；
- RunContext 反序列化不能改变 RNG schema，且同 seed/path 仍给出同一随机流。

验收命令：

```powershell
cargo fmt --all --check
cargo test -p telysta-core --locked
cargo clippy -p telysta-core --locked -- -D warnings
```
