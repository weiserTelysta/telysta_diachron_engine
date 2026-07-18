---
document_type: migration-plan
decision_status: proposed
implementation_status: in-progress
normative_scope: migration
last_verified: 2026-07-17
owner: unassigned
reviewers: []
---

# Current-to-Target Migration Map

## 1. 迁移原则

- 按可验证领域纵切迁移，不按旧 Python 目录逐文件翻译。
- 每个切片同时提供 schema、migration、replay、fixture、hash 和用户闭环。
- 不从旧状态 diff 推断未知的语言学因果。
- 不在新 writer 与旧 writer 之间长期双写。
- snapshot、索引和缓存可重建；权威 boundary/event/object 不可由缓存替代。

## 2. 阶段地图

| 阶段 | Current | 迁移动作 | Target / Gate |
|---|---|---|---|
| F0 | dirty local foundation | reviewed Git baseline、clean-checkout evidence | G0A prerequisite |
| F1 | 分散文档和状态口径 | authority/status/current-target-migration/docs-check | governance ready |
| R1 | desktop 直连 core/storage | 新增 `telysta-application`，用 deterministic fake operation 验证 lifecycle | G1 platform walking skeleton |
| WS-1 | State v2/full revision | 冻结 v3 IR、Genesis、Meaning/Grammar、一个 typed structural ChangeSet | G2 executable micro-language |
| Product wedge | inspector UI | Brief→Candidate→Scene→History→Export | G3 Story Language Kit |
| WS-2 | 无传播模型 | innovation/variation/propagation/conventionalization | G4 mechanistic change |
| Family | 单项目语言 | migration/branch/contact/borrowing/family graph | G5 |
| Production | 微型语言 | literary task packs、canon、speech/export、expert audit | G6/G7 |

## 3. R1 前的停止门

只有以下条件同时成立才进入 R1：

- GateEvidence `decision == "passed"`；
- ADR-011/012/013 及相关 storage/application 决定 Accepted；
- clean-checkout 全量质量门可复现；
- owner/reviewer/capacity 已记录；
- 不会把 v1 `RunContext` 或 demo checkpoint 扩展为 target schema。

## 4. R1 walking skeleton

R1 只使用不依赖 LanguageState v3 的 deterministic fake operation：

```text
register Operation/Run
→ submit/restart/resume Job fixture
→ durable staging
→ revalidate
→ one atomic publish
→ reopen
→ remove caches
→ replay same semantic result
```

失败注入必须覆盖崩溃边界、stale commit、重复请求、对象缺失/篡改和 v1 migration
中断。该阶段不生成真实语言，也不开放正式 Genesis。

## 5. WS-1 迁移边界

G1 与 G0B 都关闭后，才按一个端到端纵切实现：

1. v3 最小 typed State/Registry。
2. Meaning/Grammar/Construction 最小双向 IR。
3. 多候选 Genesis 与 independent evaluator。
4. VerifiedGenesisArtifact 创建、保存、重开。
5. 一条 feature-based structural ChangeSet。
6. reducer、rollback、replay、explain 和 IGT。

完成前不得删除 v1/v2 migration fixture 或 Python legacy golden evidence。
