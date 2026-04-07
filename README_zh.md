# Telysta Diachron Engine

[English README](./README.md)

Telysta Diachron Engine 是一个面向**历时语言演化**的人造语言（Conlang）神经符号引擎。

它用于严肃世界观创作场景：语言不是静态词表，而是会随着时代推进、分支分化与结构漂移不断演进的历史系统。

## 这个项目解决什么问题

多数造语工具停留在随机音节拼接或平面语法模板。Telysta Diachron Engine 重点建模：

- 跨时代音变（磨损、同化、弱化等）
- 语法化路径（实词降级为语法标记）
- 分域形态漂移（按语法域独立状态迁移）
- 分支语言独立演化（Branch profiles）
- 基于 CSG 的生成管线（语义图作为稳定外部 API）

## 核心架构

- **符号层**：可测试、可复现的语言学规则算子（音系/形态/句法）
- **神经层**：可选 LLM 侧车用于受控叙事/注释（不直接覆写规则）
- **Hot State + Delta 事件**：内存态演化与事件式历史记录
- **Epoch 编排**：多纪元历史演化与偏置控制

## 仓库结构

- `app/` — 领域模型与引擎实现
- `data/` — 语言数据、语法化路径、预设
- `docs/` — 架构与开发文档
- `tests/` — 单元与集成测试
- `main.py` — CLI 入口
- `streamlit_app.py` — Web UI 入口

## 快速开始

### 环境要求

- Python 3.10+
- Poetry

### 安装依赖

```bash
poetry install
```

### 运行 CLI

```bash
poetry run python main.py
```

### 运行测试

```bash
poetry run pytest tests/ -q
```

### 运行 Streamlit 界面

```bash
poetry run streamlit run streamlit_app.py
```

## 当前状态

项目处于持续开发中。完整架构与路线图见：

- [开发文档](./docs/development.md)

## 许可证

MIT（见 `pyproject.toml` 元数据）。
