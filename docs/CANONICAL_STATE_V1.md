# Legacy Canonical State v1

- 状态：`Accepted for migration baseline`
- Schema：`telysta.legacy-state.v1`
- 哈希：SHA-256
- RNG：`legacy-rng-tree-v1`
- 适用范围：Python 旧引擎黄金场景、语义差异定位和 Rust 迁移对照

本文定义的是旧引擎的只读观察格式，不是未来 Rust `LanguageState` 的最终项目 schema。

## 规范化规则

- 实体、DAG、事件引用 ID 统一为非空字符串；旧整数 ID 在边界转换为十进制字符串；
- 词典按实体 ID 排序并表示为数组，避免映射插入顺序影响结果；
- DAG 节点排序，边按 source、target、era、type 排序；
- 集合排序，映射 key 排序，枚举转换为值；
- `-0.0` 规范为 `0.0`，NaN 和 infinity 拒绝进入语义状态；
- event 顺序保留，因为事件先后具有语义；
- 时间戳、绝对路径、日志和耗时不进入语义哈希；
- lexicon key 与实体 ID 不一致、重复规范 ID 和空 ID 立即失败。

## 分域哈希

每个场景输出：

- lexicon hash；
- DAG hash；
- typology hash；
- event sequence hash；
- full semantic hash。

领域哈希用于定位变化来源。黄金哈希只保证同版本确定性，不证明输出在语言学上正确；语言质量由硬约束、性质测试、多 seed 诊断和专家评审判断。

## RngTree

Python 基线通过版本化路径派生独立随机流，例如：

```text
root
├── genesis.lexicon
├── evolution.era.10.sound
├── evolution.era.10.homophone
├── evolution.era.10.typology
├── epoch.1.domain_injection
└── branch.north.era.3
```

路径通过版本、根 seed 和 segment 列表计算 SHA-256，前 64 bit 作为 Python/NumPy 生成器 seed。Rust 必须建立自己的明确 RNG 合约和版本；不承诺复刻 Python `random.Random` 内部状态。

## 黄金场景

`legacy-golden-v1` 包含：

1. `genesis`；
2. `flat_10`；
3. `epoch_injection`；
4. `branch`；
5. `mock_llm`。

运行：

```powershell
.\.venv\Scripts\python.exe scripts\baseline_report.py --seed 888
```

版本化期望值位于 `tests/fixtures/golden/legacy_v1.json`。当前已知缺陷必须保留在报告中，不能通过静默更新 fixture 掩盖。

当前 seed 888 基线明确记录：genesis 有 22 个音系非法存活形式；Epoch 边界注词/复合事件和 Branch 事件尚未完整暴露。它们是后续 A-003/A-004 的修复输入，而不是被黄金 fixture 认可为正确行为。
