---
document_type: governance-policy
decision_status: proposed
implementation_status: in-progress
normative_scope: current
last_verified: 2026-07-19
owner: unassigned
reviewers: []
---

# Telysta 文档治理策略

## 1. 目标

文档必须区分决定、实现、计划、证据和历史记录。代码通过测试并不意味着目标能力
已经交付；Proposed ADR 也不授权生产实现。

## 2. 必需元数据

除索引和显式登记的 legacy 文档外，规范性 Markdown 文件必须在文件开头记录
YAML front matter：

```text
文档类型
决策状态
实现状态
规范范围
最后核验
源提交（状态快照和证据类文档必需）
owner/reviewers（需要批准的决定必需）
```

字段含义：

| 字段 | 可用值 |
|---|---|
| `document_type` | `adr`、`architecture-description`、`architecture-target`、`capability-plan`、`contract`、`evidence`、`governance-policy`、`index`、`legacy`、`migration-contract`、`migration-plan`、`operational-status`、`plan`、`product-plan`、`research`、`roadmap`、`runbook` |
| `decision_status` | proposed、accepted、superseded、not-applicable |
| `implementation_status` | not-started、in-progress、partial、implemented、verified、generated、historical |
| `normative_scope` | current、migration、target、historical |

只有 `scripts/docs_check.py` 的 `LEGACY_METADATA_EXEMPTIONS` 显式登记的旧文档可以暂时
保留原有状态行；新文件不能通过添加 `Status` 文本获得 legacy 身份。新建和实质修订文档
必须迁移到 YAML front matter，迁移完成后从 exemption 中删除。
治理策略在具名评审前保持 `proposed`，不得由编写者自行标记为 `accepted`。

## 3. Current、Target 与 Migration

- `Current` 只描述当前代码和已接受合同。
- `Target` 描述计划到达的架构，必须标明所需 Gate 和 ADR。
- `Migration` 描述从 current 到 target 的安全路径、停止条件、兼容和回滚。
- 同一段落若同时讨论 current 与 target，必须显式标注，不得使用模糊的“系统将会”。

三个架构视图分别见：

- [Current Architecture](../architecture/CURRENT.md)
- [Target Architecture](../architecture/TARGET.md)
- [Migration Map](../architecture/MIGRATION.md)

## 4. 状态和证据

- Gate 状态只从版本化 GateEvidence 读取。
- `STATUS.md` 是 GateEvidence 和主计划的可读汇总，不得独立改变决定。
- 基线报告必须带日期和源提交，不能作为永久“当前状态”。
- 文档声称某项能力 Implemented 时，必须引用实现路径和验证命令。
- 外部研究结论必须区分 hard constraint、empirical prior、research hypothesis
  和 creative preference。

当前 G0A 的治理合同指针是 Proposed [G0A policy v2](../G0A_POLICY_V2.json) 及其
[schema](../G0A_POLICY_V2.schema.json)，以及 Proposed
[GateEvidence v3 model](./GATE_EVIDENCE_MODEL_V3.md) 和
[manifest schema](../GATE_EVIDENCE_MANIFEST_V3.schema.json)。这些文件定义当前决定
必须满足的闭合结构，但在独立评审、有效 v3 evidence 与 attestation 形成前不构成
`accepted` 或 `passed`。v1 policy 与 v1/v2 evidence schema 仅保留为迁移输入。

## 5. 变更规则

- 不通过静默改文档掩盖实现偏差。
- 改变持久化实体身份、writer、replay、插件执行边界或因果规则时，先停止并处理 ADR。
- 大规模文件移动只能在 clean-checkout 基线后进行，并保留替代链接或迁移记录。
- legacy 文档只保留历史价值，不进入当前执行优先级。

## 6. 自动检查

`scripts/docs_check.py` 至少检查本地链接、索引覆盖、必需元数据、Gate 放行守卫、
schema 常量和 desktop command 文档一致性。工作树 fingerprint 改变时，所有
`SoftwareVerificationEvidence` 必须失效；只有实际执行的协议可以恢复 `pass`。
GateEvidence v3 必须锁定 G0A policy v2，区分 subject revision 与承载证据的
attestation revision，验证完整 delivery readiness 和远端 provenance，并拒绝
attestation-only 范围之外的后续变更。当前实现候选或 schema 通过本身不能恢复
`passed`；检查进入 `scripts/check.py` 和 CI。
