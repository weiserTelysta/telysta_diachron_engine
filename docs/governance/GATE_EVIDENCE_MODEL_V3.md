---
document_type: governance-policy
decision_status: proposed
implementation_status: in-progress
normative_scope: migration
last_verified: 2026-10-14
owner: unassigned
reviewers: []
---

# GateEvidence v3：闭合 Policy、Delivery Readiness 与远端 Provenance

2026-10-16 执行范围变更：用户要求仅本地运行与验证，GitHub 只保存代码。
下文远端条款保留为旧 Proposed 合同背景，不授权再次启用远端任务。须独立
评审本地 clean subject、可重验运行记录与评审同意的替代合同；现有 schema/
policy 先保持原版本，生成器仍拒绝签发 passed，不能直接删掉 predicate 放行。

本地软件诊断使用独立版本的 sidecar，入口与限制统一见
[开发环境：本地原始日志记录](../DEVELOPMENT_SETUP.md#本地原始日志记录)。它只记录
现有命令的输出与输入绑定，不改变本文的 Gate schema、policy 或决定接受状态，
不能填写成 remoteProvenance、受信执行证明或 terminal acceptance evidence。

> **实施边界：** 本文件、[G0A policy v2](../G0A_POLICY_V2.json)、
> [policy schema](../G0A_POLICY_V2.schema.json) 与
> [GateEvidenceManifest v3 schema](../GATE_EVIDENCE_MANIFEST_V3.schema.json)
> 目前仍是 Proposed 合同切片。生成器、验证器与测试已有本地迁移实现候选，但当前
> GateEvidence 与派生 STATUS 尚未形成有效 v3 attestation，也未完成独立评审。不得据此
> 声称 policy v2 已接受、GateEvidence v3 已验证、G0A 已通过或 R1 可以启动。

## 1. 目标

v3 关闭 v2 复审中暴露的三类缺口：

1. Gate requirement 集合必须由版本化 policy 与引导验证器共同锁定，不能继续让
   只覆盖 R0A-01～07 的旧 policy 产生当前决定；
2. R0A-07 不再只检查两个布尔字段，而是锁定 canonical R0A/R1 WBS 中每个工作包的
   owner、独立 reviewer、capacity、estimate、WIP、timebox 与 Stop/Go；
3. passed 必须绑定 clean committed subject、Windows/Linux 远端运行与稳定 provider
   provenance，不能把本地运行或“workflow 已编写”描述为跨平台证明。

GateEvidence JSON 仍是 Gate decision 的唯一机器事实，`STATUS.md` 仍只是可删除重建的
派生视图。Delivery readiness、远端 CI 记录和 release claim 都不得进入 LanguageState、
项目历史或语言 semantic hash。

## 2. Proposed 当前 Policy 身份

迁移完成后，当前 G0A policy 必须同时满足：

- path 为 `docs/G0A_POLICY_V2.json`；
- schema version 为 `telysta-g0a-policy.v2`；
- payload 通过 `docs/G0A_POLICY_V2.schema.json`；
- GateEvidence 的 `gatePolicy.sha256` 与 subject blob 的 policy bytes 一致；
- requirement keys 精确为 `R0A-01`、`R0A-02-ADR011`、`R0A-03`～
  `R0A-10`，不得缺少、增加、改名或降级；
- `requiredWorkPackageIds` 精确覆盖 canonical WBS 的全部 R0A 与 R1 工作包。

`telysta-g0a-policy.v1` 及任何未知、缺失、损坏或 hash 不匹配的 policy 对当前决定一律
视为 obsolete/invalid。实现不得回退到 v1、从 evidence 猜测 policy，或因为旧 policy
曾经产生本地 pass 就继承决定。

## 3. v2 → v3 迁移

任何 GateEvidence v1/v2 输入迁移到 v3 时必须：

1. 先把决定设置为 `blocked`；
2. 清除所有当前 passing software claim、旧 owner/reviewer 结论和 waiver 生效状态；
3. 旧验证运行只保留在版本历史中；迁移器不得把缺少 v3 source/provenance 语义的运行
   复制进当前候选，也不得将其计入 v3 terminal predicate；
4. 重新计算 subject、policy、canonical WBS 和所有 evidence hash；
5. 为十个 requirements 建立完整条目；
6. 在重新验证之前保持 `deliveryReadiness.workPackages` 为空或不完整；
7. 重写派生 STATUS；若无法安全重写，则删除 STATUS 并返回非零。

迁移不得自动创建 `accepted_terminal` evidence、稳定账户、远端 CI provenance、容量、
估算、WIP 或 timebox。无法从受信来源重建的字段必须保持空缺，使决定继续 blocked。

## 4. Requirement 与 terminal evidence

十个 requirement 均不可豁免。R0A-05、R0A-07、R0A-08、R0A-09 与 R0A-10 只有在各自
版本化 terminal evidence 存在、hash 匹配、结果为 `accepted_terminal` 且满足 policy
predicate 时才能成为 passed：

- R0A-05：clean committed subject 与独立 clean-checkout baseline；
- R0A-07：完整 DeliveryReadiness 记录与独立审批；
- R0A-08：policy/runner/fail-closed/verifier lease、精确 MSRV、Windows/Linux
  fresh-checkout CI 与受信 provenance；
- R0A-09：current v1 create-if-absent、append-only history、archive/journal 复验和
  index as-of binding 的故障注入结果；
- R0A-10：legacy raw bytes/hash/directory manifest、已知缺陷 failure fingerprint 与
  Python Legacy Lab 非生产写入边界。

终端 evidence 路径可以在 policy 接受前尚不存在；缺失意味着 blocked，不得创建空壳
`accepted_terminal` 文件来满足路径检查。evidence 的 accepted 状态必须由独立 validator
根据真实结果推导，不能由工作包作者自由填写。

## 5. Delivery readiness

`deliveryReadiness.schemaVersion` 固定为 `telysta-delivery-readiness.v1`。
canonical WBS 由已哈希的 gate policy 绑定；`workPackages` 的 ID 集合必须与
policy 的 `requiredWorkPackageIds` 完全相等。

blocked evidence 可以保留空数组或不完整 readiness 项；passed evidence 必须为每个工作包
记录：

- 稳定账户 owner；
- 至少一名具名、无利益冲突的独立 reviewer；
- 可审计的 `availablePersonHours` 与 capacity 起止日期；
- 以 `person-hours` 为单位的三点 estimate；
- 正整数全局 WIP limit 与具名 WIP slot；
- 有 UTC 起止时刻的 timebox；
- 非空降范围规则、可追溯 approval reference 与 UTC 过期时刻；
- `ready` readiness 状态。

显示名、角色占位符、AI 生成的人名、`unassigned`、团队共享账户或未获本人确认的账户不得
填入 owner/reviewer。schema 验证只能检查结构；独立性、账户真实性、容量承诺和本人同意
必须由 policy evaluator 与外部 attestation 验证。

## 6. Subject、verifier lease 与远端 provenance

passed 只允许证明 clean committed subject。验证应在不可变 clean checkout 上执行，并在
验证、最终 fingerprint、evidence 准备与发布期间持有单 verifier lease。仅在发布前再比较
一次 dirty worktree 不能替代不可变 subject 和 lease。

lease 属于当前检出：使用 `git rev-parse --git-path` 解析实际 metadata 路径，
兼容 `.git` 为文件的 linked worktree；同一检出的并发发布仍拒绝，独立检出不共享
可变输出或锁。该兼容修复不放宽 clean subject、信任验证或正式 attestation 条件。

passed 至少需要 Windows 与 Linux 两个成功 verification run。每个 run 必须绑定同一
subject commit/tree、真实环境、协议列表、lock hashes，以及 provider、repository、
workflow、run ID、job ID、URL 和 artifact digest。本地 Linux 完整门结果见
[执行记录](../WORK_LOG.md)；Windows/Linux fresh-checkout 远端运行和受信
provenance 尚未产生，因此 G0A 必须保持 blocked。

## 7. Fail-closed 启动与发布

实现 v3 的生成器必须在读取任何旧 evidence 时先建立 fail-closed 启动边界：

- evidence 缺失、编码错误、JSON/schema/policy 损坏时返回非零；
- 不根据损坏 bytes 虚构一个可信 v3 manifest；
- 删除可能残留 passed 的派生 STATUS；
- policy v1、未知 policy 或 requirement 集合漂移一律 blocked；
- candidate evidence 与 effective decision 分离，旧 pass 不自动继承；
- evidence/STATUS 发布失败时优先保留 blocked evidence；无法证明原子性时删除 STATUS。

v3 schema 的 conditional 只提供结构防线。生成器仍必须验证 evidence 引用、hash、终端
predicate、时间、账户独立性、subject/attestation diff、lease 和远端 provenance。

2026-10-14 实现边界修正：当前只能检查声明的结构、hash 与本地条件，尚无
认证账户同意、provider 结果及独立 terminal payload 的受信验证器。
`validate_passed_decision` 因而明确拒绝所有 passed 签发，直到该验证能力经独立
评审后实现；不提供 CLI/JSON 放行开关。单元测试中的 synthetic account/provider
仅隔离验证结构谓词，不产生真实可信批准。blocked 候选与本地软件检查继续可运行。

## 8. ReleaseClaim 边界

ReleaseClaimManifest 是 GateEvidence 与 Capability Matrix 的只读发布投影。候选构建必须
`claimsEffective=false`；只有 v3 GateEvidence passed 后才能签发引用 candidate/evidence
hash 的新 immutable effective manifest。ReleaseClaim 不能反向改变 Gate decision，也不能
成为语言状态或项目历史 writer。

本切片不实现 ReleaseClaim schema、generator 或 UI projection。当前不得声称
`foundation-inspector`、`platform-dev-preview`、`0.4-executable-preview` 或
`0.5-canon-alpha` channel 已由机器生效。

## 9. 当前状态与下一实现

当前仍然成立：

- G0A=`blocked`；
- owner、独立 reviewer、capacity 与全部 readiness 尚未登记；
- ADR-011/012/013 尚未完成接受；
- clean committed subject 与 attestation 尚未形成；
- R0A-08/09/10 terminal evidence 尚不存在；
- Windows/Linux 远端 provenance 尚不完整；
- 当前 evidence/STATUS 已迁移为结构有效但明确 `blocked` 的 v3 候选；
- generator/validator/tests 仍是未独立复核的 v3 + policy-v2 本地实现候选。

下一步必须完成 policy/bootstrap validator、schema loader、STATUS renderer 与 hostile
tests 的独立复核，再从 clean checkout 获取 Windows/Linux 受信 provenance，并分别完成
R0A-05/07/08/09/10 terminal evidence。只有这些结果进入 reviewed subject 与后续
attestation 后，才能考虑签发 v3 passed evidence。
