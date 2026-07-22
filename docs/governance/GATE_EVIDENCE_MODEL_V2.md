---
document_type: governance-policy
decision_status: proposed
implementation_status: in-progress
normative_scope: migration
last_verified: 2026-07-19
owner: unassigned
reviewers: []
---

# GateEvidence v2：Subject 与 Attestation 分离

> **2026-07-19 实施状态：** 本模型仍为 Proposed。COR-05 已在当前工作树实现 hermetic
> runner、非零执行守卫和 fail-closed 输出，并通过 hostile tests；COR-07 也已形成
> Rust 1.88.0/Windows exact-gate 本地实现候选。这些都不是独立复核或 GateEvidence pass。
> 并发 verifier lease、Linux/fresh-checkout CI provenance、后续普通提交与 milestone
> attestation 生命周期、R0A-07 和 reviewer provenance 仍未闭合。后续由 COR-06/07
> 负责；若 pass/attestation 意义无法向后兼容，必须以 v3 取代，不能原地改写 v2 历史语义。

## 目标

GateEvidence 证明一个已经提交的 subject revision，不证明承载证据文件的提交自身。这样可以
避免“证据必须先存在才能计算自己的 commit”这一循环，同时保留本地可审计和 fresh-checkout
复验能力。

## 身份模型

- `subjectCommit` 是实际经过验证的代码、合同和测试提交。
- `subjectTree` 是该提交的 Git tree，防止只记录一个未经校验的文本标签。
- 仓库首次采用本模型时，必须先提交一份明确为 `blocked` 的 GateEvidence seed 与派生
  `STATUS.md`，使 fresh checkout 能运行生成器；之后这两个路径的变化才属于
  attestation-only。
- GateEvidence 与派生的 `STATUS.md` 可以在 subject 之后的 attestation commit 中提交。
- 从 subject 到当前 attestation revision，只允许改变生成的 GateEvidence 与 STATUS。
- attestation 之后一旦出现其他代码或合同变化，旧证据自动失效，必须重新验证。

blocked 草案可以描述 subject 上方的 dirty worktree；passed 决定只允许证明 committed、clean
subject，并要求具名 owner、独立 reviewer、完整软件门禁和已接受的架构决定。

## 三层验证

1. Manifest validation：只验证 Schema、必需证据、引用和内部一致性，跨平台稳定。
2. Subject validation：使用 Git 对象验证 subject commit/tree、祖先关系、attestation-only
   diff，并从 subject blob 重新计算合同、fixture 与 lock-file hash。
3. Gate policy evaluation：从 ADR 状态、合同证据、软件运行、owner/reviewer 和 waiver 推导决定。

历史运行环境记录在 `verificationRuns`。验证者不需要复制证据生产机器的绝对路径；CI 的每个
平台仍必须重新运行自身门禁，最终 decision job 聚合这些结果。

### COR-05 本地实现边界

- 每次 `--verify` 在任何 preflight 或命令之前先持久化 blocked checkpoint；旧 passed
  不能在本次验证失败或进程中止后继续作为权威状态。
- v2 formal `verificationRun` 必须同时绑定本次 attempt 的完整 environment、subject
  commit/tree 和 lock-file hashes。任一部分无法诚实捕获时，生成器持久化 blocked 和
  可表达的软件失败明细，但不复制历史环境、不伪造 formal run；partial-attempt 的结构化
  表达若有必要，必须在 COR-06 中版本化 schema。
- GateEvidence JSON 是唯一权威源，STATUS 是派生视图。每个文件使用同目录临时文件、
  flush/fsync 和 replace；若两文件发布撕裂，生成器优先保持 evidence blocked，随后重写
  STATUS，无法重写则删除 STATUS，下一次从 evidence 重建。
- 这不是通用的多文件事务：断电/文件系统故障仍可能发生在两个 replace 之间；并发 verifier
  也尚无跨进程 lease。任何 pass 发布前仍需独立复核、clean subject、单 verifier 约束，
  并在 COR-05 closure 中决定是否补 lease。
- 本地验证记录：`python -I scripts/pytest_runner.py tests/core/test_pytest_runner.py
  tests/core/test_gate_evidence_generator.py -q` 得到 `33 passed`，runner 报告
  `collected=33, executed=33`。该记录只证明当前工作树的实现检查点，不是 Gate attestation。

### COR-07 本地实现边界

- 当前 locked graph 的最高依赖 `rust-version` 为 1.88.0；workspace manifest、精确
  toolchain、generator 与 CI 使用同一候选版本。Windows exact gate 已在本地通过。
- v2 policy amendment：保留既有 `rustVersionMeetsWorkspace` 字段，但当前 validator
  要求记录的 Rust 与 Cargo 都精确等于 workspace MSRV，不再允许较新版本冒充最低版本
  证明；schema 的版本字符串仍可表达历史 run，而旧 run 已由协议/fingerprint 变化失效。
- v2 `verificationRun` 只能记录生成该 run 的单次真实环境；它不能把“CI workflow 已
  编写”表达成 Linux/Windows 两个平台已经受信运行。
- 远端 provider、workflow/run/check identity、artifact digest、平台聚合与过期语义属于
  COR-06/v3。正式模型确定前，不在 v2 自由字符串中伪造这些 provenance。
- 因此 Linux/fresh-checkout CI 未产生受信证据前，COR-07/P1-19/R0A-08 保持 open，
  G0A 保持 blocked。

passed 决定中的 owner 必须使用稳定账户身份。每名 reviewer attestation 必须记录 provider、
stable account ID、login、角色、精确 subject commit/tree、远程或签名评审引用、结论、UTC
时间和利益冲突声明。G0A 至少覆盖 architecture 与 migration 两种独立评审角色；显示名称或
任意自由字符串不能作为独立性证据。

## v1 迁移

- v1 文件只作为历史输入保留，不原地改变其 Schema 含义。
- v1 到 v2 的首次刷新必须清除所有 passing software result 和 verification claim。
- v1 的 `baseCommit` 迁移为当前 `subjectCommit`；`subjectTree` 从 Git 对象读取。
- v1 的 passed 决定不得自动继承，必须降为 blocked 并重新完成 v2 验证。

## Waiver

Waiver 必须绑定 requirement、审批者、理由和 UTC 到期时间，并在每次验证时与当前 UTC 时间
比较。clean subject、完整软件门禁和核心 ADR 接受条件不可豁免。
