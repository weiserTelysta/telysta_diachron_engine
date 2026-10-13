---
document_type: runbook
decision_status: not-applicable
implementation_status: implemented
normative_scope: migration
last_verified: 2026-10-12
---

# G0A 独立评审与 Clean Baseline 交接

## 目的与边界

本交接包把 G0A 的待审合同、工作树纳入范围和提交顺序变成可复核流程。它不接受 ADR，
不指定或冒充人员，不创建 Git 提交，也不改变 Gate 决定。现存
[G0A GateEvidence](../G0A_GATE_EVIDENCE_2026-07-17.json) 已是 v3 的本地
`blocked` 候选，尚未形成可信 attestation；在有效 v3 evidence 明确为 `passed`
之前，G0A fail closed，R1 持久化 walking skeleton 继续冻结。

## 一次性生成交接清单

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\g0a_handoff.py --check --json
```

报告固定记录：

- 当前 `HEAD` commit/tree；
- 每个待审 ADR、合同、Gate schema/policy 和 RNG fixture 的 SHA-256；
- 所有 Git worktree 条目，并将其分为 subject candidate 与 attestation-only；
- 被禁止纳入基线的虚拟环境、缓存、构建目录、日志和临时文件；
- 必须单独复核的删除、重命名和冲突。

`subjectReadyForStagingReview=true` 只表示清单完整且没有明显瞬态/危险条目，不表示代码正确、
ADR 已接受或 Gate 已通过。`cleanSubjectReadyForVerification=true` 只有在 subject candidate
已全部进入提交、工作树只可能剩余两份生成证据时才成立。

## 独立评审对象

架构 reviewer 必须逐项核对：

1. [ADR-011](../adr/ADR-011-project-manifest-run-ledger-job-identity.md)：Project、
   Operation、Run、Job、Attempt 身份是否分离；retry/resume 是否保持语义输入不变；旧项目
   是否明确进入 legacy boundary。
2. [ADR-012](../adr/ADR-012-project-package-commit-authority.md)：是否只有一个可变 manifest
   发布点；崩溃恢复是否只能得到完整的提交前或提交后状态；writer authority 是否唯一。
3. [ADR-013](../adr/ADR-013-rng-compatibility-and-distribution-versioning.md)：RNG path、
   distribution version、overflow、checkpoint 和 replay 兼容规则是否足够精确。
4. [Platform Contract Pack](../PLATFORM_CONTRACT_PACK_V1.md)：Tauri、application service、
   storage、job runtime 与 Rust domain authority 是否没有第二写入者。
5. Proposed [GateEvidence v3 model](./GATE_EVIDENCE_MODEL_V3.md)、
   [manifest schema](../GATE_EVIDENCE_MANIFEST_V3.schema.json)、
   [G0A policy v2](../G0A_POLICY_V2.json) 与
   [policy schema](../G0A_POLICY_V2.schema.json)：policy/subject/attestation 是否无自引用，
   requirement 与 canonical WBS 是否闭合，passed 是否只能从 accepted terminal evidence、
   完整直接门禁、delivery readiness、具名独立评审和受信远端 provenance 推导。v1 policy
   与 v2 schema 只能作为 fail-closed 迁移输入。

迁移 reviewer 必须额外核对 legacy v1 项目、RNG known answers、checkpoint 失配、
stale writer、崩溃窗口和回滚路径。作者自审或自动化工具输出不能替代独立评审。

## 人工决定记录

每份待接受 ADR 必须在同一个 subject revision 中记录：

- `decision_status: accepted`（仅在 reviewer 明确同意后）；
- 真实 `owner`；
- 至少一名与 owner 不同的具名 reviewer；
- 评审范围、结论、尚存异议和日期；
- 若结论要求改变实体身份、writer 或 replay 语义，先修订 ADR 与 fixture，再重新评审，
  不能带条件偷偷进入实现。

R0A/R1 rolling-wave 记录还必须给出实际可用容量、估算方式、WIP 上限、timebox 和超限降范围
规则。未知信息保持 `unassigned`，不得用 Agent 名称、占位邮箱或推测日期填充。

## Clean subject 与 attestation 顺序

1. 运行 `g0a_handoff.py --check --json`，逐项审查所有 subject candidate；不要使用
   `git add -A` 代替纳入判断。
2. 按[清理计划](../CLEANUP_PLAN.md)单独处理删除/重命名；缓存、构建产物和本机状态必须移出
   subject，必要时补充精确 `.gitignore` 规则。
3. 完成独立评审、owner/capacity 记录和所有源代码/合同修改，运行本地完整门禁。
4. 创建 subject commit。重新运行：

   ```powershell
   .\.venv\Scripts\python.exe scripts\g0a_handoff.py --check --require-clean-subject
   ```

5. 从该 subject 的 fresh checkout 执行
   `.\.venv\Scripts\python.exe scripts\generate_gate_evidence.py --verify`。软件结果必须绑定
   subject commit/tree 和当次运行环境。
6. 仓库首次采用 v3 流程时，subject 必须包含一份可由生成器读取并强制迁移为
   `blocked` v3 candidate 的 GateEvidence seed 与派生 STATUS，使 fresh checkout 可以
   fail closed 启动。v1/v2 seed 不继承旧 pass；只有 policy evaluator、terminal evidence、
   delivery readiness、远端 provenance 和独立评审全部无错误时才允许生成 `passed`
   candidate。随后单独提交 GateEvidence 与派生 `STATUS.md` 作为 attestation commit。
7. attestation 后若任何非生成路径发生变化，证据自动失效，回到第 1 步。

## 当前仍需由人完成

- 指定可追责 owner、独立 architecture reviewer 与 migration reviewer；
- 对 ADR-011/012/013、G0A policy v2 与 GateEvidence v3 给出可审计结论；
- 给出真实容量、估算、WIP 与 timebox；
- 审阅并创建 clean subject commit 与后续 attestation commit。

在这些输入缺失时，正确结果是保持 `blocked`，而不是降低 Gate 标准。
