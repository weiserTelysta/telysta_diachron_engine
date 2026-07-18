# 代码与模块清理计划

- 状态：`Accepted`
- 基线日期：2026-07-12
- 原则：清理是架构工作，不是按文件名猜测用途后批量删除

> **范围说明（2026-07-16）：** 本文的删除门、证据保留和停止双写规则仍为 Accepted；第 3 节是 2026-07-12 对旧 Python 原型的初始清单，不是当前实现顺序。其中 Regex、Epoch、BorrowingInjector、`evolve_one_era()` 等名称只用于迁移定位，不授权继续建设 Python 生产路径。当前目标与 Next 必须由 Rust 权威边界、模块迁移矩阵、三份主计划和 Accepted ADR 共同决定。

## 1. 目标

- 仓库中的产品能力与主流程真实能力一致；
- 消除重复算法和不同步的平行演化管线；
- 隔离仍有研究价值但尚未产品化的实验模块；
- 降低客户端迁移和规则扩展时的维护成本；
- 保留行为基线，避免清理造成无声语义漂移。
- 支持 Rust 领域级整体替换，并避免形成长期 Python/Rust 双核心。

清理贯穿全部路线阶段，不再等待一个独立的“清理阶段”。Rust 成为某个领域的权威实现后，对应 Python 生产路径立即进入迁移、只读参考或删除流程。

## 2. 分类标准

| 状态 | 定义 | 处理方式 |
|---|---|---|
| Core | 主流程使用，有明确产品价值 | 保留、补边界测试 |
| Integrate | 有独特价值，但未进入主流程 | 指定接入阶段和验收条件 |
| Experimental | 研究性实现 | 移入明确实验边界，不对外宣称完成 |
| Duplicate | 与另一实现职责重叠 | 选择权威实现，先迁移调用再删除 |
| Deprecated | 已有替代品 | 发出弃用说明，经过迁移窗口后删除 |
| Remove | 不可达、无独特价值、无数据依赖 | 在独立提交中删除 |
| Legacy Reference | 旧生产实现，仅用于迁移对照 | 冻结功能，保留黄金向量，Rust 切换后退出生产入口 |
| Research Only | 数据分析或模型实验 | 保留在明确研究边界，不得写正式项目状态 |

## 3. 初始模块清单

下表是审计后的初步分类。A-004 已通过可重复 AST 导入报告和测试可达性复核；完整的证据、模块分组与 Rust 去留决策见 [模块迁移矩阵](./MODULE_MIGRATION_MATRIX.md)。动态注册和数据文件引用仍须在删除前逐项复核。

| 模块/能力 | 初始状态 | 建议 |
|---|---|---|
| Phoneme / Inventory / Rule IR | Legacy Reference | 提取不变量与测试向量，在 Rust 中按新 IR 重建 |
| Native phonology backend | Legacy Reference | 作为迁移期正确性参考，不作为长期生产后端 |
| Regex backend | Integrate | 明确产品用途，否则转 Experimental |
| ExemplarMatrix / collapse | Integrate | 接入批处理主流程或停止性能能力宣称 |
| BorrowingInjector | Integrate | 进入 Epoch 接触语言事务 |
| 两套 CompoundingEngine | Duplicate | 合并为一个领域服务 |
| HistoryRebuilder | Legacy Reference, Replace | 用测试暴露缺失状态；权威回放在 Rust 重建 |
| BranchLanguage 独立演化循环 | Duplicate | 改用统一 `evolve_one_era()` |
| CSG Pipeline | Integrate / Research | 提取语义覆盖需求，是否迁移由新 Grammar/Discourse IR Spike 决定 |
| Assembler | Experimental | 与 CSG 职责比较后决定去留 |
| LLM contracts / sanitizer / mock | Integrate | 保留测试合同；生产提案边界迁移到 Rust schema 和事务裁决 |
| Streamlit UI | Deprecated | Tauri 等价后删除 |
| 全局 settings / snapshot / EventBus | Remove by replacement | Rust Project/Operation/Job scope、query/event journal 与 StateTransaction 权威路径切换后删除 |

## 4. 删除门槛

删除任何生产模块前必须回答：

1. 是否被生产入口直接或间接导入？
2. 是否被动态注册、字符串配置或数据文件引用？
3. 是否定义了仍需支持的序列化格式？
4. 是否包含唯一算法、测试 fixture 或语言学知识？
5. 替代实现是否覆盖同一行为？
6. 是否存在旧项目迁移需求？

只有在主流程不可达、没有数据依赖、没有独特价值且已有明确替代或正式放弃时，才能标记 `Remove`。

## 5. 标准清理流程

每个清理主题独立执行：

1. 建立调用图与运行时证据；
2. 添加特征测试，记录当前可观察行为；
3. 选择权威实现；
4. 迁移生产调用和测试；
5. 标记弃用并记录数据兼容性；
6. 删除旧实现；
7. 运行黄金场景，比较语义哈希；
8. 更新模块清单和路线图。

对于大规模 Rust 重构，允许一个工作包整体替换一个领域，但还必须：

1. 明确领域边界、权威写路径和停止双写日期；
2. 将旧行为区分为“必须兼容”“有意修正”“正式放弃”；
3. 提供旧项目输入样本和迁移 manifest；
4. 在 Rust 纵切通过后移除旧生产入口，而不是无限期保留 feature flag；
5. 将仍有研究价值的 Python 代码移入研究边界，不与生产包混放。

禁止在一次提交中同时完成大量无关删除、格式变更和行为重写。

## 6. 语义变化记录

如果清理会有意改变语言结果，PR 必须记录：

- 哪些黄金场景发生变化；
- 变化前后状态哈希；
- 变化属于 bug fix、设计修正还是随机模型调整；
- 是否需要提高项目格式或规则包版本；
- 用户是否能够继续打开旧项目。

格式整理、重命名和模块移动不应改变语义哈希。

## 7. 完成标准

- 每个生产能力只有一个权威实现；
- 不再存在独立的 Flat、Epoch、Branch 演化算法；
- 实验模块有清晰目录与免责声明；
- README 的功能描述只包含主流程可达能力；
- 不存在由全局状态维持的跨运行隐式依赖；
- 正式发行版不依赖 Python sidecar，不存在第二个生产模拟核心；
- 删除提交均有黄金场景或特征测试证据。
