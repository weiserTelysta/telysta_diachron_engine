# 模块迁移矩阵

- 状态：`A-004 completed baseline`
- 审计日期：2026-07-13
- 静态报告 schema：`telysta.module-inventory.v1`
- 生成命令：`.\.venv\Scripts\python.exe scripts\module_inventory.py --format markdown`

> **历史基线说明（2026-07-16）：** 本矩阵保存 A-004 时点的 Python 可达性和迁移证据。`A-005 前`、旧 Phase 或旧工作包编号只说明当时的决策门，不是当前 Next；现在每个迁移工作包必须先满足 G0A/G0B、rolling-wave Ready 条件及对应 Accepted ADR。表中的 Python 类和函数只能作为行为证据，不能成为 Rust 生产架构。

## 审计证据与限制

当前静态报告识别到 87 个 `app` 模块，其中 65 个可从 `main.py` 或 `streamlit_app.py` 静态到达，57 个被测试直接引用，22 个不在现有生产入口的静态可达路径上。

该报告只分析 Python AST import，不能证明动态注册、字符串配置、数据文件、反射或用户脚本没有引用模块。因此“不可达”只表示进入 `Experimental` 或 `Remove` 审查，不构成直接删除授权。删除仍受 [代码与模块清理计划](./CLEANUP_PLAN.md) 的门槛约束。

## 迁移决策

| 能力组 | 当前模块 | 静态证据 | 决策 | Rust/产品目标 | 最晚决策门 |
|---|---|---|---|---|---|
| 入口与 Web UI | `main.py`、`streamlit_app.py`、`ui/` | 两个生产入口；UI 依赖进程 session 和全局目录 | Deprecated | Tauri workspace；保留 CLI 仅作迁移诊断 | Phase F |
| 旧应用编排 | `app.engine.session`、`demo` | Session 从两个入口可达；demo 只由 CLI 调用 | Legacy Reference | Rust Application Service、Tauri command/event API | PLT-002 |
| 运行地基 | `core.config`、`settings`、`logging`、`event_bus`、`console` | 多数生产模块依赖；含全局单例与目录状态 | Remove by replacement | `ProjectManifest/OperationContext/RunSpec`、独立 Job/Attempt、结构化 tracing、任务范围日志 | FND-005/006、PLT-006 |
| 随机与基线 | `core.rng`、`storage.canonical`、`engine.golden` | 生产与测试均使用；A-002 新增 | Legacy Reference | Rust 版本化 RNG、semantic state report；Python 保留对照 | FND-003/004 |
| 状态与历史 | `storage.hot_state`、`event_log`、`history` | HotState 可达；History 仅测试可达；A-003 有 8 个 xfail | Replace | `LanguageState`、transaction、event reducer、snapshot/migration | FND-002/006/007/008 |
| 创世词汇与词源模型 | `lexicon.models`、`generator`、`factory`、`dag` | 模型/生成器在主路径；DAG 由 HotState 使用 | Legacy Reference | typed Root/Lexeme/Sense/Derivation graph 与 ProtoLanguageCompiler | GEN-003/004 |
| 旧演化循环 | `engine.evolution`、`epoch`、`vocabulary` | 主路径可达；含直接状态修改与未记录事件 | Replace | 单一 `ChangeProcess`、TimeModel、需求驱动扩词 | FND-009、EVO、LEX |
| 音系原语与 IR | `phoneme`、`ir`、`rule_compiler`、`validator` | 高测试引用与主路径引用 | Integrate as specification | Rust feature inventory、natural class、RuleSpec IR、合法性 gate | GEN-003、RUL-003 |
| 现行音变算子 | `operators/`、`native_backend`、`erosion` | 四个算子在主循环启用；其余多为测试证据 | Legacy Rule Reference | RulePack 内置规则与 Rust executor；规则不逐文件直译 | EVO-001/002、RUL |
| 测试/未接入音系后端 | `regex_backend`、`conflict_resolver`、`compensatory_lengthening` | 仅测试或静态不可达 | Experimental | 保留测试向量；RUL 阶段决定 FST/IR 用途 | RUL-003 |
| 词汇历史算子 | `analogy`、`fossil`、`grammaticalization*`、`homophone_resolver`、`irregular`、`pathways`、`typology_drift` | 主循环直接调用，但多个操作绕过统一事件 | Integrate as behavior evidence | 变化过程中的类推、语法化、音系重组和 repair 子过程 | EVO-003–007 |
| 接触与借词 | `lexicon.borrowing` | 测试引用但当前主循环不可达 | Integrate | `ContactEngine`；来源、适配、层次和边统一事件化 | FAM-003 |
| 重复复合实现 | `engine.vocabulary.CompoundingEngine`、`morphology.compounding` | 两套不同 API；前者主路径、后者不可达 | Duplicate | 一个 Rust `WordFormationStrategy::Compound` | LEX-003 |
| 范例矩阵 | `exemplar.matrix`、`collapse` | 仅测试链可达；有性能基准 | Research Only | 仅在扩展规模基准证明需要时设计 Rust 数据布局 | 性能决策门 |
| 句法与 CSG | `syntax.csg`、`semantic_graph`、`pipeline`、`morphological_*`、`surface_phonology`、`generation_tree`、`feature_blackboard` | demo/Branch 可达，非主演化结果 | Integrate as research evidence | Grammar/Discourse IR、ConstructionInventory、Realizer | GRM-001–006 |
| 原型句装配 | `syntax.assembler`、`lexicalization` | 主要用于 demo 或 pipeline 局部功能 | Experimental | 以 Grammar Realizer 取代；不迁移 IPA 拼接行为 | GRM-006 |
| Branch/Profile | `language.branch`、`evolution_profile` | demo 和黄金场景可达；独立循环、无持久边界 | Legacy Reference, Replace | FamilyGraph + 统一 ChangeProcess；不保留平行循环 | FAM-001/002 |
| LLM 适配 | `llm/`、backends、contracts、sanitizer | Session/演化可达；Mock 有测试价值 | Integrate | Rust schema/transaction 最终裁决；凭据与网络置于应用服务层 | PLT-003、SPH-001 |
| 数据与 fixtures | `data/`、`tests/fixtures/` | 运行时与黄金场景依赖 | Core Data | 版本、许可证、CLDF 互操作和 Rust data manifest | DAT-001–004 |

## 所有权与迁移规则

本矩阵建立时，仓库没有记录可核实的人类 owner，因此没有虚构负责人。A-005 已完成；现在每个后续 Rust 工作包进入 `Ready` 前仍必须在任务卡中补充：负责人、输入/输出 schema、对应矩阵行、迁移输入样本、黄金场景、删除门和回退策略。

迁移时遵循以下顺序：

1. 先保留 Python 行为证据、数据和失败场景；
2. 在 Rust 建立目标领域模型与不变量；
3. 用相同输入比较语义报告，而不是要求复刻已知错误；
4. Rust 路径成为权威后停止对应 Python 生产调用；
5. Python 代码转为 `Legacy Reference`、`Research Only` 或按门槛删除；
6. 更新本矩阵、[路线图](./ROADMAP.md)和清理计划。

## A-005 前冻结项（历史基线，约束仍适用于未迁移领域）

- 不新增大批音变、语法化规则或 UI 页面；
- 不删除静态不可达模块；
- 不把 Python `EngineHotState`、`EpochManager` 或 `BranchLanguage` 原样翻译成 Rust；
- 不在 Python 回放器上进行超过特征测试所需的大规模修复；
- 不允许 Python 和 Rust 在同一项目文件中长期双写状态。
