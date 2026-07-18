# Telysta 重构前基线报告

- 状态：`Accepted`
- 采样日期：2026-07-14
- 目的：为 Agent 治理、LanguageState v3 和 Genesis 编译器重构提供不可歪曲的现状证据

## 1. 验证结果

| 门 | 结果 | 说明 |
|---|---|---|
| Rust workspace tests | 59 passed | `telysta-core` 44、desktop 3、storage 12 |
| Rust Clippy | Passed | `--workspace --all-targets -- -D warnings` |
| Python tests | 519 passed, 8 xfailed | xfail 均为已登记的 legacy 回放缺陷 |
| Legacy Genesis | 207 alive words, 22 hard errors | `phonotactically illegal alive forms` |

验证命令：

```powershell
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
.\.venv\Scripts\python.exe -m pytest -q
```

## 2. 已知 legacy 回放缺陷

严格 `xfail` 当前覆盖：

1. snapshot 未恢复持久化 DAG；
2. snapshot 未恢复 Swadesh 保护集合；
3. rebuilder 没有类型学 read model；
4. event decoder 丢弃 replay-relevant 字段；
5. 借词父节点丢失；
6. fossil 父节点丢失；
7. compound 双父节点丢失；
8. Epoch 注词改变 Hot State 但未写入事件日志。

这些缺陷不在 Python 中进行全面修补；它们是 Rust typed event、reducer 和迁移测试的验收样本。

## 3. 当前 Rust 能力边界

已具备：

- 稳定实体 ID、精确时间和路径派生 RNG；
- 版本化 LanguageState、RunContext、ProjectHistory；
- semantic hash、事务、回放验证；
- 原子项目存储、恢复、迁移、索引重建和写并发保护；
- LanguageBlueprint v2 输入合同与 capability 报告。

尚不具备：

- 生产 `ProtoLanguageCompiler`；
- 足以表达异音、音系配列语法、范式和 typed constructions 的领域模型；
- typed linguistic delta event；
- SpeechCommunity/ChangeProcess 的生产模拟；
- 正式项目创建、可用语言和文学任务门。

## 4. 当前 Python 生成边界

- Genesis 使用固定 `CV/CVC/CVCV/CCVC` 模板独立生成词形；
- 生成路径未保证所有 CCVC 形式经过修复；
- 主演化注册四个硬编码音变算子；
- 逐词概率变化不等同于社群创新、扩散和系统重组；
- 演示句为 IPA 拼接，不证明完整形态句法能力。

## 5. 基线使用规则

- 黄金 hash 用于检测未解释的行为变化，不用于强制复制已知错误；
- Genesis 硬错误必须在新 Gate 3 降到零；
- 新模型若改变 schema 或 hash，必须记录原因、迁移和新 fixture；
- “测试数量增加”不能替代模型验证；
- 此报告应由后续自动化脚本生成或核验，避免手工状态漂移。
