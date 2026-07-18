# ADR-006：Rust 原生生产核心与 Python 研究桥接

- 状态：`Accepted`
- 日期：2026-07-12
- 决策范围：生产引擎、Tauri 边界、Python 定位、迁移与大规模重构
- 替代关系：取代 [ADR-004](./ADR-004-tauri-python-sidecar.md) 中“Python sidecar 作为长期生产核心”的决策；保留其中 Tauri、Svelte/TypeScript、本地优先和最小权限原则

## 背景

现有 Python 原型已经验证了一批音系、词汇、语法化、句法和历史存储思路，也积累了可复用测试。然而目标产品需要同时保证：

- 同版本、同配置和同 seed 的确定性；
- 唯一事务写入口、完整事件回放和项目迁移；
- 长周期、多分支、接触网络和批量实验；
- 强类型 Rule IR、冲突分析和受限扩展；
- 与 Tauri 生命周期、任务取消、权限和打包边界统一；
- 最终桌面产品不要求用户安装 Python。

Rust 的价值不限于性能。它还用于收紧状态不变量、统一桌面后端、减少生产运行时、提供可控并发和建立插件安全边界。当前代码规模仍允许在新功能继续扩张前重建核心边界。

## 决策

1. Rust 成为正式产品中语言状态和模拟结果的唯一权威实现。
2. Tauri 2 + Svelte/TypeScript 保持为桌面产品技术栈，前端只通过版本化 command/event API 访问引擎。
3. 正式发行版不依赖 Python sidecar；Rust application service 直接调用 Rust simulation core。
4. Python 保留为研究桥接层，用于数据清洗、统计分析、模型原型和黄金场景参考，不得直接写入正式项目状态。
5. LLM 只能产生候选语义或规则提案；所有提案必须由 Rust schema、约束和事务层裁决。
6. 允许大规模重构和领域级整体替换，不要求维持现有 Python 类、模块或调用结构。
7. 禁止把现有实现逐行机械翻译为 Rust；新核心以目标领域模型和可验证不变量为准。

## 权威边界

```text
Svelte / TypeScript
        │ Tauri commands and events
        ▼
Rust Application Service
        ├── project / run / cancel / export
        └── query / explain / compare
        │
        ▼
Rust Simulation Core
        ├── model / time / RNG / state
        ├── rules / phonology / grammar
        ├── diachrony / family / contact
        ├── quality / provenance
        └── storage / migration

Python Research Lab
        ├── datasets / statistics / experiments
        └── golden-reference adapters
                 │ proposals and test vectors only
                 └───────────────────────────────► Rust boundary
```

Rust 负责：

- `RunContext`、版本化 `RngTree` 和任务取消；
- `TimeModel`、`LanguageState`、`StateTransaction` 和事件归约；
- 祖语编译、语言变化、家族与接触模拟；
- RuleSpec 编译、dry-run、冲突分析和解释；
- 项目存储、格式迁移、语义哈希和质量诊断；
- Tauri command/event API。

Python 可以负责：

- 经验数据获取、清洗和统计先验构建；
- 新语言学模型的短期实验；
- 批量研究脚本和可视化分析；
- 旧 Python 行为适配器和对照测试。

Python 不得成为正式项目文件的第二写入者，也不得成为发布版模拟结果的另一事实来源。

## 存储与协议原则

- command、event、snapshot、RuleSpec 和 project manifest 均独立版本化；
- 语义哈希使用规范化、跨进程稳定的表示，缓存格式不视为长期项目格式；
- 项目写入使用事务和原子提交，中断后必须恢复到前一个完整状态；
- UI 只能读取查询模型，不能直接修改数据库或拼装领域状态；
- 远程计算如未来出现，应复用 application service 协议，而不是改变领域核心。

## 大规模重构规则

允许重建目录、领域对象、存储格式和执行路径，但必须满足：

1. 先建立旧引擎黄金场景、已知缺陷清单和迁移输入样本；
2. 新旧实现通过相同的领域不变量和语义报告比较；
3. 已知旧缺陷不作为兼容目标，只记录其有意变化；
4. 以领域能力为切换单位，完成一个权威路径后停止双写；
5. 每个切换点提供回退策略、数据迁移说明和删除门槛；
6. 不允许长期维护功能等价的 Python 与 Rust 双核心。

## 迁移序列

1. 建立 Python 旧引擎的确定性基线与黄金场景；
2. 创建 Rust workspace、Tauri shell 和版本化 API；
3. 实现稳定 ID、`TimeModel`、`RunContext`、`RngTree`；
4. 实现 `LanguageState`、事务、事件、快照、回放和迁移；
5. 完成 ADR-005 的最小双分支语言学 Spike；
6. 迁移音系特征、规则 IR、音变执行与祖语编译；
7. 迁移语法、词汇、语义、家族、接触和质量模块；
8. Tauri 直接使用 Rust 核心，停止 Python sidecar 产品路线；
9. 删除被替代的生产 Python 路径，保留独立研究环境。

## 验收条件

- 正式桌面构建在没有 Python 的环境中完成创世、模拟、保存、恢复和导出；
- 同版本同输入的 Rust 结果跨进程可复现；
- 所有生产状态写入经过 Rust `StateTransaction`；
- keyframe 加事件与在线状态语义相等；
- Python 研究工具只能通过版本化数据或命令边界交换结果；
- 每个迁移领域均通过黄金场景、性质测试和迁移测试；
- 发布仓库中不存在仍被生产入口调用的第二模拟核心。

## 后果

正面影响：

- 生产栈由 TypeScript + Rust 构成，减少运行时和打包复杂度；
- 核心不变量、并发、任务取消和项目边界更易强制执行；
- Tauri 与模拟引擎共享安全和生命周期模型；
- RulePack、WASM 扩展和批量模拟具有一致宿主；
- 可以摆脱现有 Python 模块边界，直接建设目标模型。

成本与风险：

- 短期内需要同时维护旧 Python 基线和新 Rust 核心；
- 团队需要建立 Rust、序列化迁移和跨平台构建能力；
- 语言学模型与技术迁移若同时无限扩张，会造成不可验收的大爆炸；
- 一些 Python 库能力需要重新实现、通过数据交换保留或明确放弃。

控制方式是领域级纵切、明确切换门和限时双轨，而不是缩回到长期 Python sidecar。

## 非目标

- 不追求逐行复刻全部 Python 代码；
- 不在地基阶段建设完整 UI、插件市场或神经语音；
- 不因使用 Rust 而跳过语言学验证、经验数据治理和专家评审；
- 不把所有研究脚本迁移到 Rust。
