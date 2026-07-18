---
document_type: governance-policy
decision_status: proposed
implementation_status: in-progress
normative_scope: migration
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# GateEvidence v2：Subject 与 Attestation 分离

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
