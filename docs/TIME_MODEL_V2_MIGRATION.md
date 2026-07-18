---
document_type: migration-contract
decision_status: accepted
implementation_status: implemented
normative_scope: migration
last_verified: 2026-07-17
implementation_schema: telysta-time-model.v2
implementation_path: crates/telysta-core/src/time.rs
implementation_constant: TIME_MODEL_SCHEMA
---

# Time Model v2：精确模型绑定与迁移

- 状态：`Accepted`
- 完成日期：2026-07-13
- 对应工作：`B-005`
- 实现：`crates/telysta-core/src/time.rs`、`state.rs`、`project.rs`

## 为什么升级

`telysta-time-model.v1` 的 `TimeReference`、`VersionedTimeRange` 与
`ChangeSchedule` 只保存 `timeModelSchema`。这不能区分同一 schema 下具有不同
`origin`、`generationYears` 或 `stepYears` 的模型，因此可能将一个时间轴的年份
错误地用于另一个时间轴。

v2 使用 `telysta-time-model.v2`，并为每个模型计算一个确定性的 SHA-256
`timeModelFingerprint`。指纹的输入包含固定 domain separator、schema、origin、
generation length 与 step length。所有时间引用、范围和日程都同时保存 schema 与
指纹；`RunContext` 会验证两者都属于自己的完整 `TimeModel`。

## 新的不变量

1. 同 schema 不代表同一时间模型；每个引用必须通过 `TimeModel` 的精确指纹校验。
2. `LanguageState` v2 的 provenance 时间必须与 state 的模型指纹一致。
3. 项目回放不仅要求 provenance 引用已出现的事件，还要求
   `ProvenanceEntry.createdAt == ProjectEvent.occurredAt`。
4. 旧格式不会由普通 `Deserialize` 静默接受。

## 显式 v1 → v2 迁移

迁移调用者必须先提供原始时间模型，不能根据 schema 或默认设置猜测：

1. 用 `migrate_legacy_time_model_v1_json` 将 v1 模型迁移为 v2 模型。
2. 将所得模型显式传入 `migrate_legacy_time_reference_v1_json`、
   `migrate_legacy_versioned_time_range_v1_json`、
   `migrate_legacy_change_schedule_v1_json` 或
   `migrate_legacy_language_state_v1_json`。
3. 迁移器仅接受相应的 v1 schema；错误 schema、缺字段或无效模型均失败。

`LanguageState` 的 schema 由 `telysta-language-state.v1` 升级为 v2，因为其
持久化的时间引用结构发生了变化。本合同验收时，项目级历史文件的原子迁移器仍属于
FND-008；该工作随后已由 [Project Storage v1](./PROJECT_STORAGE_V1.md) 完成。旧项目
历史仍只能通过显式迁移载入，不允许猜测性转换。

## 验收

`telysta-core` 测试覆盖：

- 同 schema、不同时间模型的引用与日程拒绝；
- 旧时间模型、时间引用、范围与状态只能经显式源模型迁移；
- 篡改 `RunContext` 的模型或 provenance 的创建时间时，项目历史回放拒绝；
- 既有时间、状态与事务回归测试保持通过。
