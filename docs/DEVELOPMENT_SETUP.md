---
document_type: runbook
decision_status: not-applicable
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-19
---

# 开发环境与质量检查

> 本文记录本地质量入口。Python 命令维护旧引擎基线、黄金场景和跨仓库文档检查；
> Rust workspace 与 Tauri 使用独立的 Rust 质量门。正式产品方向见
> [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)，完整强制命令以
> 仓库根目录 [AGENTS.md](../AGENTS.md) 和 CI 为准。

- 状态：`Current local quality runbook`
- 基线日期：2026-07-12；最后核验：2026-07-19
- 默认开发版本：Python 3.13
- 支持范围：Python 3.10–3.14

## 1. Windows 环境

安装 Python 3.13 后，在 PowerShell 中执行：

```powershell
py -3.13 -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

Poetry 必须运行在与项目 `.venv` 分离的工具环境中；也可以使用固定到 2.4.1 的
`pipx` 安装。不要把 Poetry 自身安装进项目 `.venv`，否则环境不再与 `poetry.lock`
描述的运行/开发依赖集合相等。

进入虚拟环境不是必需的，可以始终通过 `.venv` 中的 Python 执行命令。若希望激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. macOS 与 Linux 环境

```bash
python3.13 -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

## 3. Rust 与 Tauri 工具链

当前 workspace 的 MSRV 与精确验证工具链均为 Rust `1.88.0`：

```text
Cargo.toml [workspace.package].rust-version = 1.88.0
rust-toolchain.toml channel = 1.88.0
```

当前 `Cargo.lock` 中经 Tauri 进入 workspace 的 `time`、`plist`、`darling` 和
`serde_with` 等依赖声明的最高 `rust-version` 为 1.88.0。metadata 只确定候选下限；
必须使用精确 1.88.0 完成 locked build/test/clippy 才构成 MSRV 实现检查。依赖图改变时
必须重新计算并验证，不能把这一版本当成永久不变的产品规律。
`.cargo/config.toml` 的 `incompatible-rust-versions = "fallback"` 约束以后重新解析依赖时
优先选择兼容版本，但它不替代已提交 lock graph 的精确工具链验证。

所有平台先安装精确工具链：

```text
rustup toolchain install 1.88.0 --profile minimal --component rustfmt,clippy
```

Windows 还需要 Microsoft C++ Build Tools 与 WebView2 开发/运行环境。Debian/Ubuntu
开发机与 CI 使用 [Tauri v2 官方前置要求](https://v2.tauri.app/start/prerequisites/)
列出的原生依赖：

```bash
sudo apt update
sudo apt install -y \
  libwebkit2gtk-4.1-dev \
  build-essential \
  curl \
  wget \
  file \
  libxdo-dev \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev
```

这些包只说明 Debian/Ubuntu 的构建前置；`ubuntu-24.04` 通过不能推导所有 Linux
发行版、macOS、安装包或运行时兼容性已经得到证明。

## 4. 一键质量检查

Windows：

```powershell
.\.venv\Scripts\python.exe -I scripts/check.py
```

macOS/Linux：

```bash
.venv/bin/python -I scripts/check.py
```

该脚本依次执行：

1. Python 语法编译；
2. Ruff 正确性级静态检查；
3. 文档链接、索引、Gate、schema 和 desktop command 一致性检查；
4. 完整 pytest 测试套件。

pytest 使用系统为当前进程分配的独立临时目录；不得在共享工作树中固定一个 basetemp，
以免连续运行或并发 agent 互相删除目录。测试缓存插件在该总门禁中关闭。任一步失败都会
返回非零退出码。CI 与开发者使用同一个脚本，避免本地和远程检查漂移。

需要刷新 G0A 证据时，不手工编辑测试数量或工作区计数。执行：

```powershell
.\.venv\Scripts\python.exe -I scripts/generate_gate_evidence.py --verify
```

当前应审查的 G0A 合同指针是 Proposed
[G0A policy v2](./G0A_POLICY_V2.json) 及其
[schema](./G0A_POLICY_V2.schema.json)，以及 Proposed
[GateEvidence v3 model](./governance/GATE_EVIDENCE_MODEL_V3.md) 和
[manifest schema](./GATE_EVIDENCE_MANIFEST_V3.schema.json)。生成器与测试已有本地
迁移实现候选，不等于这些治理合同已被独立接受；现有 GateEvidence/STATUS 尚未形成
有效 v3 attestation，G0A 必须保持 `blocked`。

准备独立评审与 clean subject 前，先运行：

```powershell
.\.venv\Scripts\python.exe -I scripts/g0a_handoff.py --check --json
```

它会列出全部 subject candidate、两份 attestation-only 生成文件、待审合同哈希以及被拒绝的
缓存/构建产物。提交 subject 后追加 `--require-clean-subject`；该检查成功只证明 worktree
边界满足交接条件，不表示 ADR 已接受或 G0A 已通过。完整职责与提交顺序见
[G0A 独立评审与 Clean Baseline 交接](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)。

该命令必须由仓库 `.venv` 的解释器启动。它先生成排除自身输出的 worktree fingerprint，
将**全部**旧 `SoftwareVerificationEvidence` 标记为未运行，再依次执行 Python/docs、
Rustfmt、Rust test、Clippy、desktop locked build 和 JavaScript 检查。所有登记协议，包括定向测试，
都必须直接执行才能恢复 `pass`，不得依赖手工声明的父门禁覆盖关系。

全部通过后才创建带 UTC 开始/结束时间的 `verificationRuns`，记录真实 Python 可执行路径、
已安装分发集合摘要、Python/Rust/Cargo/Node 版本、锁文件摘要和实际命令。验证前会拒绝与
`poetry.lock` 不一致的 `.venv`，并要求本次正式验证使用 workspace 锁定的精确
Rust 1.88.0 工具链。CI 的 Windows/Linux MSRV job 也必须使用同一版本；本地较新
工具链不伪装成 MSRV 证明。任一命令
失败会清除当前成功标记，尚未执行的后续协议继续保持 `not_run_for_fingerprint`。

GateEvidence v3 的 `subjectCommit`/`subjectTree` 仍指向被验证提交；证据和
`STATUS.md` 只能在后续 attestation 范围内发布。v3 还要求 policy hash、完整
delivery readiness，以及绑定同一 subject 的 Windows/Linux provider、workflow、run/job
identity 和 artifact digest。当前 workflow 或本地实现候选存在不等于这些远端证据已经
产生；现有 v1/v2 evidence 只能作为强制降为 `blocked` 的迁移输入。普通开发循环仍可只运行
相关子门，但不能据此签发 GateEvidence pass。

## 5. 单独运行

```powershell
.\.venv\Scripts\python.exe -I scripts/docs_check.py
.\.venv\Scripts\python.exe -I scripts\pytest_runner.py tests -q
.\.venv\Scripts\python.exe -m ruff check app ui tests main.py streamlit_app.py
.\.venv\Scripts\python.exe -m compileall -q app ui tests main.py streamlit_app.py
cargo +1.88.0 fmt --all --check
cargo +1.88.0 test --workspace --locked
cargo +1.88.0 clippy --workspace --all-targets --locked -- -D warnings
cargo +1.88.0 build -p telysta-desktop --locked
node --check apps/desktop/web/app.js
```

2026-07-19 的 Windows 本地实现检查点中，精确 1.88.0 workspace tests 为
`62 passed`，fmt、Clippy `-D warnings`、desktop locked build 与 `node --check`
均通过。Linux/fresh-checkout 远程 CI、run identity、artifact digest 和跨平台聚合
尚未完成；该记录不是 GateEvidence，也不关闭 R0A-08 或 G0A。

CI 的 `ubuntu-24.04`/`windows-2025` MSRV lanes 才验证最低版本；附加 stable lanes
用于发现向前兼容漂移，不能替代 1.88.0 证明。workflow 文件存在也不是远端通过证据。

## 6. 依赖管理

- `pyproject.toml` 是直接依赖和工具配置来源；
- `poetry.lock` 必须提交，用于锁定完整依赖图；
- 添加或升级依赖后必须重新运行一键检查；
- CI 使用固定 Poetry 2.4.1，升级 Poetry 需要独立提交；
- 不在 `pyproject.toml` 中固定个人镜像源。需要镜像时使用本机 Poetry/pip 配置；
- 当前项目使用 Poetry application mode，不构建或安装根 Python 包。

更新锁文件：

```powershell
uvx --from poetry==2.4.1 poetry lock
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

## 7. Python 支持策略

- 3.13 是旧引擎基线、研究桥接和迁移期对照的默认版本；
- CI 在 Linux 验证最低版本 3.10、中间版本 3.12 和最高版本 3.14；
- CI 额外在 Windows + Python 3.13 验证主要桌面开发平台；
- 新 Python 次版本先加入 CI，验证通过后再扩大 `requires-python` 范围。

## 8. 静态检查策略

当前 Ruff 只启用影响正确性的规则：语法错误、无效控制流和未定义名称。更广泛的导入排序、风格和格式统一将在清理阶段独立进行，避免一次产生大量与行为修改混杂的差异。

任何新增代码仍应保持一致格式；该限制不表示项目接受长期风格漂移。
