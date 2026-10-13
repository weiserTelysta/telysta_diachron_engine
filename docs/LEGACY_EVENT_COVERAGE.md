# Legacy 事件覆盖账本

- 状态：`A-003 completed baseline`
- 范围：Python 旧引擎的状态变更、持久事件和 `HistoryRebuilder`
- 目的：记录当前行为与信息损失；不是为旧事件格式增加长期兼容承诺

## 判定标准

一个事件只有同时满足以下条件才算“可回放”：

1. 所有生产状态变更都生成该事件；
2. 事件进入持久日志；
3. event payload 包含 reducer 所需的全部字段；
4. reducer 应用后，`canonical_legacy_state` 与在线状态相同；
5. 快照保留 reducer 无法由事件重建的初始状态。

## 旧引擎矩阵

| 状态/事件 | 当前生产来源 | Hot State reducer | 写入持久日志 | 旧回放状态 | Rust 合同 |
|---|---|---:|---:|---|---|
| `SOUND_CHANGE` | `EvolutionEngine`、同音消解 | 有 | 有 | 词形可回放；快照 DAG 节点仍丢失 | 词形、历史、来源和规则版本原子变化 |
| `MARK_DEAD` | 同音消解、删除 API | 有 | 主流程有 | 软删除可回放 | 删除原因、保护策略和替代需求可审计 |
| `INJECT_WORD` | `EngineHotState.insert_word`、DomainInjector | 有 | **部分缺失** | 手工记录时可回放；Epoch 注词未记录 | 新词与来源/需求/词根关系同一事务写入 |
| `BORROW_WORD` | `BorrowingInjector` | 有 | 调用者决定 | 父词和来源语言在 decoder 丢失 | 来源语言、适配规则、父词和接触事件必填 |
| `FOSSIL_SPAWN` | `EvolutionEngine` | 有 | 有 | 父词边在 decoder 丢失 | 化石来源、词素角色和边类型必填 |
| `COMPOUND_SPAWN` | `engine.vocabulary.CompoundingEngine` | 有 | **缺失** | 两个父词关系不可回放 | 生成词与全部成分边必须原子事件化 |
| `DAG_EDGE_ADD` | 演化、复合、类推 | 有 | 主流程部分有 | decoder 丢失 parent/type | 显式、可验证的多父边事件 |
| `ERA_ADVANCE` | 演化、Branch | 有 | 主引擎有 | 仅 era 可回放 | 时间坐标由 `TimeModel` 而非整数轮次定义 |
| `EXEMPLAR_UPDATE` | 无生产来源 | 无 | 无 | 不可回放 | 在 Rust schema 中实现或删除该事件类型 |
| `REPLACEMENT_NEEDED` | VocabularyRenewalEngine | 无状态 reducer | 无 | 仅短暂意图，无法审计 | 需求事件与产生的替代词建立因果关联 |
| Typology drift | `TypologyDriftEngine` | 不适用 | **无事件** | 不可回放 | 类型学/语法变化必须产生版本化状态事件 |
| Branch evolution | `BranchLanguage` | 局部 | **无存储边界** | 不可回放 | Branch 与主引擎共用 command/event/reducer |

## 快照覆盖

旧 `EngineHotState.snapshot()` 可写入 `era`、lexicon、DAG 和可选 typology；但旧 `HistoryRebuilder._load_snapshot()` 只读取 era 与 lexicon。因此当前实际回放还会丢失：

- 基础 DAG 节点和边；
- `swadesh_concepts` 保护集合；
- 类型学、形态状态、feature presence 和 morpheme table；
- 任何未来加入 snapshot 的领域状态。

## Rust reducer 最小要求

Rust `StateTransaction` 必须一次性写入 command、验证结果、事件、状态版本和 provenance。replay reducer 不得读取全局目录或依赖 UI 状态；每个事件必须能在无 Python 对象和无隐式默认值的条件下应用。事件缺字段、未知 schema 或非法状态迁移必须显式失败，而不是静默跳过。

## A-003 特征测试

`tests/storage/test_history_replay_features.py` 包含当前可通过的词形/注词/软删除回放，以及严格 `xfail` 的 DAG、Swadesh、类型学、辅助事件字段、借词、化石、复合和 Epoch 注词覆盖。任何 `XPASS` 都会使 CI 失败，要求移除相应缺陷记录并更新账本。

## R0A-10 原始执行材料

```bash
.venv/bin/python -I scripts/legacy_evidence.py --output target/legacy-evidence/new-capture
.venv/bin/python -I scripts/legacy_evidence.py --verify target/legacy-evidence/new-capture
```

输出目录必须不存在。工具以 hermetic runner 对八个来源测试逐项执行
`--runxfail`，要求每项恰好执行一次并真实失败；保存实际 keyframe/event 字节、
JUnit/控制台失败、源码与数据、tracked patch、运行环境和指纹。decoder-only
用例没有持久文件，归档如实保留空清单，不从 planning fixture 伪造 event。
failure fingerprint 只记录实际异常；当前工具不判断异常是否命中了预期
replay-loss 机制。冻结前须独立核对断言位置、异常类型和原始产物，提前发生的
无关异常不能作为对应缺陷已复现的证明。
pytest 的 `current` 导航软链接单独记录描述再移除；语言 artifact 不做换行或
JSON 规范化。目录清单记录逐文件原始字节 SHA-256 与长度。

五个 seed=888 黄金场景另外运行，保留写出的文件、报告、已知非法词形，核对
已有黄金分域/full hash 与 hard errors。该工具不改变旧引擎行为，也不创建
Rust `project.json`。校验拒绝缺失、额外、损坏文件和伪造 review 声明。

格式为 `telysta-legacy-evidence-archive.v1`，仅是研究证据；manifest/checksum
提供完整性检查，不能证明发布者身份、独立评审或科学正确性。当前状态固定为
`local_capture_not_reviewed_or_frozen`，`reviewedSubjectCommit=null`。独立确认
clean subject、平台来源、失败机制、fixture 对应及责任分配后，才能形成正式
R0A-10 关闭材料；本地产物不能自动使 Gate passed。原始大文件放在忽略目录，
本轮具体位置与校验结果见 [执行记录](./WORK_LOG.md)。
