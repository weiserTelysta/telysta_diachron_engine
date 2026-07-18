---
document_type: adr
decision_status: proposed
implementation_status: not-started
normative_scope: target
last_verified: 2026-07-18
owner: unassigned
reviewers: []
---

# ADR-008：RegistryBundle 与分域特征注册表

- 状态：`Proposed`
- 日期：2026-07-14
- 决策范围：Blueprint、LanguageState v3、Genesis 编译器、规则编译器与 UI 特征合同
- 前置决策：ADR-006
- 设计上下文：ADR-007 umbrella；本 ADR 可独立评审，ADR-007 不构成循环前置

## 1. 用户与研究问题

如何让用户配置的特征、生成器实现的特征、持久化状态中的特征和 UI 展示的特征保持同一语义，同时避免把音系、形态句法和语义塞入一个不断膨胀的单体注册表？

## 2. 假设分类

| 假设 | 分类 | 处理方式 |
|---|---|---|
| 未知 feature 或非法 value 不能进入权威状态 | Hard constraint | schema/domain validation 拒绝 |
| 不同领域需要不同依赖和兼容规则 | Engineering/domain constraint | 使用分域 registry |
| 某类特征在自然语言中常见 | Empirical prior | 只影响候选权重并记录数据覆盖 |
| 用户偏好某类音系或语法 | Creative preference | 进入 intent，不改变 registry 真值 |

## 3. 决策

使用一个版本化 `RegistryBundle` envelope，内部包含独立的分域 registry，而不是一个单体 `FeatureRegistry`：

- `PhonologyFeatureRegistry`；
- `MorphosyntaxFeatureRegistry`；
- `SemanticFeatureRegistry`；
- 后续领域只能通过版本化 bundle schema 增加。

所有分域 registry 共享以下协议：

- `FeatureId`；
- typed `FeatureValue`；
- `FeatureValueSchema`；
- dependency / incompatibility；
- `CompilerCapability`；
- registry schema/version；
- canonical semantic hash。

`RegistryBundle` 保存每个分域 registry 的 schema、version 和 semantic hash，并对规范排序后的完整目录计算 bundle hash。Blueprint、LanguageState、Genesis 编译器、Rule Compiler 和 UI 必须引用同一个 bundle lock。

LanguageState 不复制第二套值域定义。持久化 assertion 必须包含 feature ID 和 typed value，并在加载、迁移、编译和事务提交时针对锁定 bundle 验证。

`RegistryBundle` 是跨 Blueprint/compiler/state/UI 共用的 feature/value schema 权威，不是某门语言的 Grammar inventory。ADR-014 的 language-specific `GrammarInventory` 拥有该语言的 LexicalClassDefinition、Construction 和关联规则，但只能引用锁定 `MorphosyntaxFeatureRegistry` / `SemanticFeatureRegistry` 中的 typed feature/value；不得复制 FeatureValueSchema、compiler capability 或另建第二套 feature catalog。

`CompilerCapability::Planned` 允许出现在设计目录和验证报告中，但不得被编译为已经实现的 LanguageState。UI 必须显示其不可用状态。

## 4. 数据与持久化影响

- LanguageState v2 不改变；
- LanguageState v3 和 GenesisArtifact 必须锁定 RegistryBundle schema/version/hash；
- 项目需要保存或可离线解析被锁定的 registry payload；
- registry 更新不得静默改变旧项目；需要显式 registry migration；
- bundle hash 变化必须进入迁移审计与语义差异报告。

## 5. API 边界

- Rust 是 registry schema、验证和 canonical hash 的唯一生产权威；
- TypeScript 类型和表单元数据从版本化 Rust 合同生成或由版本化查询命令返回；
- Tauri/Webview 不维护第二套 feature/value 列表；
- Python 只能生成候选数据、统计先验或测试向量，不能签发生产 registry。

## 6. 验收标准

- 具名 domain owner 与独立 architecture、language-domain、migration reviewer 已登记；作者和 owner 不占 independent reviewer 槽位；
- 同一 feature/value 在 Blueprint、LanguageState、RuleSpec 和 UI 中使用同一合同；
- 未知领域、未知 feature、非法 value 和错误依赖均被拒绝；
- `planned` 能力不能通过反序列化或 UI 绕过；
- bundle 和分域 hash 跨进程稳定；
- registry payload 在离线环境可重验；
- v2 fixture 不发生静默语义变化；
- migration 测试能定位具体分域差异。

## 7. 后果

分域 registry 增加少量 envelope 和迁移复杂度，但避免单体 feature 目录形成跨领域耦合，也允许音系、形态句法和语义采用各自适合的依赖与值域规则。
