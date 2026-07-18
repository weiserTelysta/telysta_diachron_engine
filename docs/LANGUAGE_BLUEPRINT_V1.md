# LanguageBlueprint v1（已废弃）

- 状态：`Superseded`
- 废弃日期：2026-07-14
- 工作包：`GEN-001`
- Wire schema：`telysta-language-blueprint.v1`
- 替代合同：[LanguageBlueprint v2](./LANGUAGE_BLUEPRINT_V2.md)

## 废弃原因

v1 使用 `features: Map<FeatureId, FeatureIntent>`。这意味着一个 feature 只能保存一条
记录，无法同时表达“语料统计先验”和“用户审美偏好”，与项目要求的知识分层相冲突。
它还没有权威 `FeatureRegistry`，所以拼写错误、未知 feature 和错误值域可能越过协议层。

v1 不再由 `LanguageBlueprint` 的普通反序列化入口接受。旧文档必须显式调用
`migrate_language_blueprint_v1_json`，迁移结果会记录：

- 源、目标 schema 与两侧文档 SHA-256；
- 每个旧 feature 对应的新 `IntentId`；
- v1 的冗余 domain 信息，供审计而不继续成为第二份真相；
- 迁移后的 v2 Blueprint。

迁移只修复结构，不宣称目标 feature 已有编译器支持。迁移后仍必须用固定版本的
`FeatureRegistry` 重新验证。
