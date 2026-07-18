---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-012：Project Package、单发布点与 Replay Authority

- 状态：`Proposed`
- 日期：2026-07-17
- 决策范围：R1 project package、history/ledger/dependency objects、staging commit、JobStore 与 query authority
- 前置决策：ADR-006、ADR-011
- 详细合同：[R0A Platform Contract Pack v1](../PLATFORM_CONTRACT_PACK_V1.md)

## 1. 问题

已实现的 `telysta-project-file.v1` 把完整 history 放在一个 `project.json` 中，因此一次原子替换即可定义 commit。ADR-011 引入 ProjectManifest、RunLedger、staging 和 dependency bundle；若把它们实现为多个可变文件并顺序替换，崩溃时会产生 manifest/history/ledger 分裂，违反当前恢复承诺。

## 2. 假设分类

| 断言 | 分类 |
|---|---|
| 权威 commit 必须只有一个发布点 | Hard correctness constraint |
| JobStore/SQLite 可以重建语言历史 | Rejected assumption |
| content-addressed object store 足以支撑目标规模 | Engineering hypothesis；R1 benchmark 复验 |
| 所有内容永久保留 | Product preference；由 retention/export policy 决定 |

## 3. 提议决定

目标 project package 使用：

```text
project-root/
  project.json                 # 唯一可变 publish point
  objects/<sha256>             # 先写、不可变、内容寻址
  jobs/...                     # 操作状态，不属于语言 semantic state
  staging/...                  # 未提交隔离结果
  projections/...              # 可删除重建
  migrations/...               # source archive + journal
```

`project.json` 是唯一可变发布点；它包含 ProjectManifest 以及对完整 history、RunLedger、DependencyBundle 和其他权威不可变对象的 hash 引用。一个项目的权威语义由“已发布 manifest + 它可达且 hash 正确的 object graph”构成。缺失、篡改或 schema 不兼容的可达对象使项目不可执行，不允许从 jobs、staging 或 projection 猜测修复。

本 ADR 唯一拥有 `ProjectAuthorityHash` 的规范组合与发布顺序。该 hash 对
ProjectId、manifest schema、`StateSemanticHash`、`HistoryHeadHash`、
DependencyBundle head、RunLedger head、项目内 `UsageCorpus` root 和全部权威
object-root references 的规范组合求摘要；candidate manifest 中的
`projectAuthorityHash` 字段本身必须排除。ADR-014
拥有 `StateSemanticHash` 覆盖，ADR-009 拥有 `HistoryHeadHash`，本 ADR 只组合并发布
两者，不重新定义其语义。

commit 必须：

1. 持有 project write lease 并验证 expected manifest/history hash；
2. 通过 application/core 重验 staging；
3. 写入并 fsync 所有新不可变对象；
4. 构造不含 `projectAuthorityHash` 字段的完整 candidate manifest，计算
   `ProjectAuthorityHash`，填入字段后重新验证全部可达引用；
5. 写 recovery record；
6. 仅一次原子替换并校验新 `project.json`；
7. 之后再收敛 Job disposition；Job 更新失败不得触发第二次语义提交。

未被任一有效 manifest、保留 ledger、migration archive 或 active staging 引用的 object 才能 GC。SQLite/projection 不参与 authority。JobStore 记录执行事实，但删除它不会改变已提交 Project/LanguageState。

## 4. 兼容与迁移

- v1 loader 行为保持不变；正常 load 不猜测 v2；
- v1 → target migration 先归档 source bytes/hash，生成 `LegacyHistoryBoundary` 与全部对象，最后发布一次新 manifest；
- 迁移中断后只能恢复到完整 source 或完成完整 target；
- 不从 v1 state diff 推断 Operation、Run、ChangeProcess 或 community provenance；
- project package schema、object schema 和 manifest schema 分别版本化。

## 5. 被否决方案

- **多个可变 JSON 顺序替换**：无法提供崩溃原子性；
- **SQLite 成为唯一 authority**：当前没有迁移、审计、故障和长期兼容证据；
- **继续把所有内容塞进单一大 JSON**：可作 v1 基线，但会放大大历史写放大并阻碍 dependency bundle；是否长期保留只能由 R1 benchmark 决定；
- **从 JobStore 恢复 commit**：把可删除执行状态变成第二权威。

## 6. 后果与验证

优点是 commit point 明确、不可变对象可去重、staging 与 published state 分离；代价是 loader/GC 必须验证 object graph，可达性与 migration fault injection 成为必测路径。

Accepted 前必须具名记录 code owner、independent architecture/storage reviewer 和
independent migration reviewer，作者和 owner 不占 independent reviewer 槽位；并冻结
schema、纯状态机/故障矩阵、planning fixture、`ProjectAuthorityHash` 排除自身字段的
known-answer 向量和 migration/GC/replay 验收设计。这些评审材料不得写 target package，
也不是 R1 实现。

当前尚未定义 `ProjectAuthorityHash` canonicalizer/coverage manifest，也没有可重算的
排除自身 known-answer 向量；ADR-011 planning record 中的重复十六进制值只是格式
sentinel，不是 known-answer 或执行证据。因此本 ADR 保持 `Proposed`，不得标记
`Accepted`。

ADR-011/012/013 Accepted 且 G0A=`passed` 后，R1 才能以 deterministic fake operation
实现 package writer，并实际执行 crash boundary、并发 stale commit、对象篡改/缺失、
GC reachability、v1 migration 中断和 clean-checkout replay；这些 executable 结果属于
G1，而不是 ADR-012 的循环接受前置。本文本身不授权当前代码写入 target package。
