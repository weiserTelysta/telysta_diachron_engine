# Telysta Diachron Engine

[English README](./README.md)

Telysta Diachron Engine 是一个仍处于早期基础建设阶段、面向**架空语言与历时语言演化**
的本地优先、可审计模拟器。当前仓库尚不能生成一门完整可用的语言。

它用于严肃世界观创作场景：语言不是静态词表，而是会随着时代推进、分支分化与结构漂移不断演进的历史系统。

## 这个项目解决什么问题

多数造语工具停留在随机音节拼接或平面语法模板。Telysta 的目标是建模：

- 跨时代音变（磨损、同化、弱化等）
- 语法化路径（实词降级为语法标记）
- 分域形态漂移（按语法域独立状态迁移）
- 分支语言独立演化（Branch profiles）
- 基于 CSG 的生成管线（语义图作为稳定外部 API）

## 核心架构

Rust 是唯一生产权威，Tauri 是桌面客户端，Python 只保留为 legacy/research 基线。当前
Rust 地基已经具备版本化状态、确定性 RNG、项目事务和存储，但生产 Genesis 编译器和
LanguageState v3 尚未实现。详见 [Current Architecture](./docs/architecture/CURRENT.md)
与 [ADR-006](./docs/adr/ADR-006-rust-native-core-python-research-bridge.md)。

以下条目描述 Python 研究原型能力，不代表已经交付的 Rust 产品能力：

- **符号层**：可测试、可复现的语言学规则算子（音系/形态/句法）
- **神经层**：可选 LLM 侧车用于受控叙事/注释（不直接覆写规则）
- **Hot State + Delta 事件**：内存态演化与事件式历史记录
- **Epoch 编排**：多纪元历史演化与偏置控制

## 仓库结构

- `crates/` — Rust 生产核心与项目存储
- `apps/desktop/` — Tauri 桌面外壳与静态 Webview
- `app/` — Python legacy 基线与研究实现
- `data/` — 语言数据、语法化路径、预设
- `docs/` — 架构与开发文档
- `tests/` — 单元与集成测试
- `main.py` — 旧引擎研究 CLI
- `streamlit_app.py` — 旧引擎研究界面

## 快速开始

### 环境要求

- Rust 1.88.0，用于生产核心和桌面质量检查
- Python 3.10–3.14（推荐 Python 3.13），用于 legacy/research 检查

### 安装依赖

```bash
python -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

Windows 与 Unix 的具体激活命令见[开发环境与质量检查](./docs/DEVELOPMENT_SETUP.md)。
Poetry 在隔离的工具环境中运行，以保证项目 `.venv` 与 `poetry.lock` 精确一致。

安装锁定的 Rust 工具链：

```bash
rustup toolchain install 1.88.0 --component rustfmt --component clippy
```

### 运行旧引擎研究 CLI

Python 输出是研究材料，不是正式 Rust 项目。已知回放信息损失见
[旧引擎覆盖账本](./docs/LEGACY_EVENT_COVERAGE.md)。

```bash
python main.py
```

### 运行测试

```bash
python -I scripts/check.py
cargo +1.88.0 fmt --all --check
cargo +1.88.0 test --workspace --locked
cargo +1.88.0 clippy --workspace --all-targets --locked -- -D warnings
cargo +1.88.0 build -p telysta-desktop --locked
node --check apps/desktop/web/app.js
node --test apps/desktop/tests/app.test.cjs
```

Python 命令只覆盖 legacy/research 基线和文档治理，不能替代 Rust 与桌面质量门。

Linux 桌面构建还需要[开发环境指南](./docs/DEVELOPMENT_SETUP.md)列出的 Tauri 系统依赖。
Windows 上的精确 1.88.0 检查有既往本地记录；本轮 Linux 工作区检查见
[执行记录](./docs/WORK_LOG.md)。Fresh-checkout CI 与独立证据仍待完成，G0A 保持 blocked。

### 运行旧引擎研究界面

```bash
python -m streamlit run streamlit_app.py
```

### 运行 Tauri 基础外壳

```bash
cargo run -p telysta-desktop
```

它当前只提供项目/Blueprint 检查，不是未来的 Genesis 产品流程。

## 当前状态

项目处于“产品化地基”阶段。R0A 正在收口 G0A 所需的仓库、平台与 Project–Operation–Run–Job 合同，R0B 并行冻结 G0B 所需的 WS-1 Meaning/Grammar/Task/Canon 证据。只有 G0A 关闭后才能进入 R1；生产 LanguageState v3 与 Genesis 还必须同时等待 G1 和 G0B。首个产品切入口是 canon-safe、可审计的 Story Language Kit，之后再进入机制性变化和语言家族能力。

规划与架构文档：

- [当前状态](./docs/STATUS.md)
- [文档索引](./docs/README.md)
- [产品开发执行计划](./docs/PRODUCT_DEVELOPMENT_PLAN.md)
- [专业语言模拟器实施总计划](./docs/LANGUAGE_SIMULATOR_PLAN.md)
- [开发环境与质量检查](./docs/DEVELOPMENT_SETUP.md)
- [当前路线图](./docs/ROADMAP.md)
- [Rust 原生生产核心与 Python 研究桥接](./docs/adr/ADR-006-rust-native-core-python-research-bridge.md)
- [社区驱动的语言模拟架构](./docs/adr/ADR-005-community-driven-language-simulation.md)
- [代码与模块清理计划](./docs/CLEANUP_PLAN.md)
- [规则系统与语言质量计划](./docs/RULE_QUALITY_PLAN.md)
- [开发文档](./docs/development.md)

## 许可证

MIT（见 `pyproject.toml` 元数据）。
