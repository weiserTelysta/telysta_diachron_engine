---
document_type: governance-policy
decision_status: proposed
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
owner: unassigned
reviewers: []
---

# Telysta 文档权威与阅读顺序

## 1. 分维度权威矩阵

仓库不使用一个总排序覆盖所有问题。先判断冲突属于哪个范围，再使用该范围的权威：

| 范围 | 权威来源 | 不得覆盖 |
|---|---|---|
| Agent 工作流程、安全约束、停止条件 | `AGENTS.md` | Accepted ADR 的领域语义 |
| 持久化身份、writer、replay、插件边界和架构语义 | Accepted ADR | 用户目标与上级安全约束 |
| 当前领域不变量和 wire 合同 | Accepted current contract | 对应 Accepted ADR |
| 当前代码实际行为 | Code + tests | 不得把实现偏差自动升级为决定 |
| Gate 是否通过、被阻断工作能否启动 | GateEvidence | ADR 与合同中的前置条件 |
| 当前 WBS、顺序和产品范围 | Product plan + Roadmap | Accepted ADR 与 Gate |
| 候选模型和研究依据 | Proposed ADR / research review | 不授权生产实现 |
| 历史背景 | Legacy documents | 不进入当前执行权威 |

发现冲突时执行：分类范围 → 找到该范围权威 → 记录偏差 → 修复实现或重新评审决定。
不得因为某份文档排在阅读列表前面，就推断它能覆盖另一范围的权威。

## 2. 核心变更阅读顺序

改变核心领域前依次阅读：

1. [当前状态](../STATUS.md)
2. [产品开发执行计划](../PRODUCT_DEVELOPMENT_PLAN.md)
3. [Roadmap](../ROADMAP.md)
4. [专业语言模拟器实施总计划](../LANGUAGE_SIMULATOR_PLAN.md)
5. [Current Architecture](../architecture/CURRENT.md)
6. [Target Architecture](../architecture/TARGET.md)
7. [Migration Map](../architecture/MIGRATION.md)
8. [Agent Operating Model](../AGENT_OPERATING_MODEL.md)
9. [ADR Index](./ADR_INDEX.md) 中相关 Accepted/Proposed 决定
10. 被修改领域的当前合同、migration 和测试

阅读 Proposed target 不等于获得实施授权。涉及持久化身份、replay 或 writer 的工作必须
同时满足 `AGENTS.md` 停止条件和对应 Gate。

## 3. 当前执行权威

- 当前执行队列：[PRODUCT_DEVELOPMENT_PLAN.md](../PRODUCT_DEVELOPMENT_PLAN.md)
- 当前产品方向：[ROADMAP.md](../ROADMAP.md)
- 当前 Gate 结论：[G0A_GATE_EVIDENCE_2026-07-17.json](../G0A_GATE_EVIDENCE_2026-07-17.json)
- 当前实现地图：[CURRENT.md](../architecture/CURRENT.md)
