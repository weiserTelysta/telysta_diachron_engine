# Foundation Model v1：实体 ID 与历史时间

> 时间模型 v1 的运行时约束已由 [Time Model v2 Migration](./TIME_MODEL_V2_MIGRATION.md) 取代。
> 本文保留 v1 的 ID、采用曲线与过程排序设计记录；任何新实现都必须使用 v2 的模型指纹，
> 不得只比较 `timeModelSchema`。

- 状态：`Accepted`
- 完成日期：2026-07-13
- 对应工作：`B-001`、`FND-001`、`FND-010`
- 实现：`crates/telysta-core/src/identity.rs`、`crates/telysta-core/src/time.rs`

本规范定义 Rust 正式核心在决定 `LanguageState` 前必须遵守的两项基础合同：稳定实体标识和历史时间。它不定义祖语、词典、规则或项目文件的完整 schema。

## 1. Stable Entity ID

生产实体 ID 是经过验证的字符串：

```text
telysta:<kind>:<value>
```

`kind` 当前只能是 `project`、`language`、`speech-community`、`lexeme`、`morpheme`、`rule`、`change-process` 或 `event`。`value` 长度为 1–96，只能包含小写 ASCII 字母、数字和连字符，且不能以连字符开头或结尾。Rust 反序列化使用同一验证逻辑；非法字符串不能进入生产状态。

需要从稳定输入推导 ID 时，使用 `ENTITY_ID_SCHEMA`、项目 namespace、实体类型和非显示性 stable key 的 SHA-256 前 128 bit。显示名称不可参与派生，因此改名不会改写身份。派生 hash 不是授权跳过冲突检查的理由：项目写入层仍须拒绝同一 ID 对应不同实体的情况。

### Legacy 迁移

旧 Python 数据不能把整数、字符串或未知值静默转换为 production ID。迁移必须提供带 `sourceSchema` 和目标 `entityKind` 的 `LegacyIdMap`。其中 `integer:1` 与 `text:1` 是不同源键；缺少映射、非规范源键或目标类型不一致都必须失败。字段为私有字段，构造和反序列化均执行相同验证；本合同验收时，实际 legacy adapter 计划由后续 `FND-002` 项目 schema 实现。该工作现已完成，但所有后续迁移仍必须遵守本合同。

## 2. TimeModel

`telysta-time-model.v1` 用有符号整数年份表达项目相对或绝对时间：

- `origin` 是项目时间原点；
- `generationYears` 取 10–100；
- `stepYears` 取 1–1000；
- 每个模拟 step 是由 `origin + index * stepYears` 求出的半开区间 `[start, end)`；
- 世代坐标是精确的分数 `numerator / denominator`，不使用 float。

纪元只是 UI 和叙事视图；任何 `ChangeProcess`、家族节点或事件最终都必须引用此时间坐标。核心现以 `TimeReference` 和 `VersionedTimeRange` 强制保留 `telysta-time-model.v1`；`ChangeSchedule` 拒绝没有匹配 schema 的过程。两个区间仅在共有年份时重叠，边界相接不算并发。

## 3. 采用曲线与过程排序

采用率使用 0–10,000 basis points 的单调、分段线性 `AdoptionCurve`。插值仅用整数，并向下取整；这是可复现合同的一部分，不能由不同平台的浮点函数替换。

`ChangeSchedule` 允许没有因果关系的过程在时间上并发。若过程 B 依赖 A，则 A 的 `[start,end)` 必须在 B 开始前结束；重叠依赖、未知依赖和循环依赖均被拒绝。拓扑排序在可选项之间按稳定实体 ID 排序，确保回放与解释的一致性。

## 4. 持久化边界

`EntityId`、`LegacyIdMap`、`TimeRange`、`TimeReference`、`VersionedTimeRange`、`TimeModel`、`AdoptionCurve` 和 `ChangeSchedule` 在 deserialization 时都重新执行结构与语义验证。加载路径不得构造裸 struct 后绕开验证。在本合同验收时，完整 `LanguageState`、事件格式、快照校验和原子项目写入仍属于后续 `FND-002`、`FND-005` 至 `FND-008`；这些基线工作现已完成，本句只记录当时依赖，不定义当前 Next。

## 5. 验收命令

```powershell
cargo fmt --all --check
cargo test -p telysta-core
cargo clippy -p telysta-core -- -D warnings
cargo check -p telysta-desktop
```

本版本的核心测试覆盖 ID 验证与派生、legacy numeric/text 键区分、年份和世代坐标、半开区间、采用曲线、并发/依赖排序以及无效 JSON 拒绝。

## 6. 验收时的下一步（历史）

本合同验收时的下一工作包是 `B-002`；该工作现已完成。其约束仍有效：Rust `LanguageState` 不得把 Python `EngineHotState` 或 A-005 demo checkpoint 作为 schema 祖型。当前执行顺序以文档索引中的三份主计划为准。
