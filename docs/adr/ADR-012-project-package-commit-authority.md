---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-10-14
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

### 3.1 持久化与结果未知的发布（Proposed）

R1 首先验证受支持本地文件系统上的**进程崩溃**一致性。系统崩溃/掉电保证必须另有
平台、文件系统及存储设备的同步能力与故障证据；不能凭 rename 或单文件 fsync
宣称普遍掉电安全。网络盘与不支持所需发布/同步原语的介质不得静默降级成相同保证。

在 project lease 内按以下顺序准备：写完并校验不可变对象 → 同步对象内容及新对象
名称所在目录 → 写完整 candidate manifest、同步其文件 → 写含 pre/post manifest
字节 hash、OperationId、expected authority 和两侧 root references 的 recovery record，
同步记录及其目录 → 调用平台验证过的原子替换原语 → 同步发布名称/目录的持久化
元数据 → 重新读取并验证 manifest 与可达图 → 清理 recovery record 并同步清理 →
返回 committed，再收敛 Job。recovery record 是非语义协调记录，不得进入 authority
graph 或造成 ProjectAuthorityHash 循环；prepared candidate 不是第二发布点。

替换前的明确失败返回 `not_published`；替换结果未知，或替换后同步、读取/校验失败，
返回 `commit_outcome_unknown` 并保持恢复记录和两侧对象，不能回报普通“未提交”、
重新申请语义 Operation、盲目重试提交或立即 GC。恢复必须先在 lease 内读取当前
primary：仅当字节 hash 与 record 的 pre/post 之一相符、对应图完整且全部引用校验
通过时，才能确认该侧结果；其他合法 primary、缺失/损坏 primary 或无法完成验证
均保留材料并进入显式 recovery-required，不能猜测某侧、覆盖 foreign primary。
已确认 post 时重试同一 Operation 返回原提交结果，Job 更新失败只做状态收敛。

平台原语必须分别设计和验证。[Linux fsync 文档](https://man7.org/linux/man-pages/man2/fsync.2.html)
明确文件同步不自动保证目录项持久；Windows 的
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
与 [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
须按其成功/失败状态处理，不能把某个原子替换 API 名称当作同步协议证明。
当前没有实现 target writer 或执行掉电测试。

八个 publication planning states 位于 ADR-011 sequence fixture 的
`publicationReview`；pre/post graph refs 是 review notation，不是实际 payload hash。
其一致性检查不冒充 storage fault injection；G1 必须绑定真实平台调用和图验证。

### 3.2 Authority hash 覆盖与规范字节（Proposed）

本轮选择 `telysta-project-authority-hash-draft.v1`，在 candidate manifest 中用
`authorityHashSchema` 显式锁定。新增 `stateSemanticHashes`（与 `historyHeads`
拥有完全相同的非空 branch key 集）和 `dependencyBundleRootSha256`，避免只在
文字中声称覆盖 state/dependency 却没有对应字段。`historyHeads` 的值为
`HistoryHeadHash`；`stateSemanticHashes` 的值为对应 head 的 `StateSemanticHash`。
两者不是 object 文件的字节 hash，不得互换。其关联仍须由未来 replay 验证。

对通过 planning schema 与跨字段检查的完整 manifest，仅删除**根层**
`projectAuthorityHash` 一个字段，其他字段全部保留。剩余值只有 object、string
与 null；本 profile 拒绝 number、boolean、array 和未知字段。采用
[RFC 8785 §3.2](https://www.rfc-editor.org/rfc/rfc8785#section-3.2) 的此受限子集：
所有层的 key 按未转义字符串的 UTF-16 code units 排序；string 使用该节定义的
控制字符、引号及反斜线转义，其余 Unicode scalar 原样输出；无空白、BOM 或末尾
换行，以 UTF-8 编码。不执行 NFC/NFKC、大小写折叠或 trim。重复 key（包括转义后
相同的 key）、无效 UTF-8、未配对 surrogate 和非 JSON 常量均拒绝，不能先用
会丢弃重复 key 的解析器转换再称为验证过的输入。这里没有实现完整数值 JCS。

```text
preimage = ASCII("telysta-project-authority-hash-draft.v1") + 0x00
         + canonical_manifest_without_root_projectAuthorityHash
ProjectAuthorityHash = lowercase_hex(SHA-256(preimage))
```

覆盖全部 schema 字段，不建立可静默漏掉新字段的白名单。新增字段或修改规范化
规则必须修订版本、ADR 和迁移；当前封闭 schema 会拒绝未知字段。根字段的排除
只解决 hash 自引用，不能豁免 schema 或 checksum 比对：已发布 manifest 的该字段
必须等于重算结果。准备 candidate 时可暂用合法的全零 hash，再填入计算结果。

| 覆盖项 | 意义与边界 |
|---|---|
| schemaVersion、authorityHashSchema、ProjectId | 协议与项目身份 |
| historyHeads 全部 key/value、stateSemanticHashes 全部 key/value | 所有命名 head 与对应结构摘要，不能只覆盖当前 UI branch |
| eventStoreRootSha256、runLedgerHeadSha256、usageCorpusRootSha256、dependencyBundleRootSha256 | 权威不可变对象的原始 payload SHA-256 roots；由其内容引用继续承诺下游对象 |
| migrationMetadata 全部字段，包括显式 null | native/legacy 来源，不能补默认值或推断未知来源 |
| 根 projectAuthorityHash | 唯一排除项；加载时另行校验相等 |

Job、staging、projection、recovery record、detached receipt 不得作为 manifest
字段或被权威对象引用；不是在 hash 中偷偷跳过它们。authority graph 不允许引用
candidate manifest 字节或 target ProjectAuthorityHash，否则出现递归承诺。
loader 必须另行验证每个可达 payload 的原始 hash、schema、引用关系与 replay；
manifest hash 本身不能证明这些事实，也不等同于真实性、作者批准或因果证据。

可重算的两组 [known-answer review vectors](../../tests/fixtures/project_authority_hash_review_v1.json)
和 [只读研究工具](../../scripts/project_authority_review.py)分别固定 native/legacy、
Unicode、排除自身与 domain separation 的规范字节。payload preimages 仅为明确
标记的假对象，不是有效 LanguageState/history/ledger/dependency schema。Python
与 Rust test-only canonicalizer 交叉检查；不是生产 schema、迁移器或 writer。

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

本轮已提出 §3.2 coverage/profile 与可重算的 review known-answer 向量，仍需独立
评审与接受；ADR-011 主 record bundle 中重复十六进制值仍只是格式 sentinel，
不得混同两组材料。可执行研究工具不验证 target object graph 或旧项目迁移，
不构成任何生产接受条件已自动完成；本 ADR 保持 `Proposed`。

ADR-011/012/013 Accepted 且 G0A=`passed` 后，R1 才能以 deterministic fake operation
实现 package writer，并实际执行 crash boundary、并发 stale commit、对象篡改/缺失、
GC reachability、v1 migration 中断和 clean-checkout replay；这些 executable 结果属于
G1，而不是 ADR-012 的循环接受前置。本文本身不授权当前代码写入 target package。
