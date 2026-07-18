---
document_type: runbook
decision_status: not-applicable
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-18
---

# 开发环境与质量检查

> 本文记录本地质量入口。Python 命令维护旧引擎基线、黄金场景和跨仓库文档检查；
> Rust workspace 与 Tauri 使用独立的 Rust 质量门。正式产品方向见
> [ADR-006](./adr/ADR-006-rust-native-core-python-research-bridge.md)，完整强制命令以
> 仓库根目录 [AGENTS.md](../AGENTS.md) 和 CI 为准。

- 状态：`Current local quality runbook`
- 基线日期：2026-07-12；最后核验：2026-07-17
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

## 3. 一键质量检查

Windows：

```powershell
.\.venv\Scripts\python.exe scripts/check.py
```

macOS/Linux：

```bash
.venv/bin/python scripts/check.py
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
.\.venv\Scripts\python.exe scripts/generate_gate_evidence.py --verify
```

准备独立评审与 clean subject 前，先运行：

```powershell
.\.venv\Scripts\python.exe scripts/g0a_handoff.py --check --json
```

它会列出全部 subject candidate、两份 attestation-only 生成文件、待审合同哈希以及被拒绝的
缓存/构建产物。提交 subject 后追加 `--require-clean-subject`；该检查成功只证明 worktree
边界满足交接条件，不表示 ADR 已接受或 G0A 已通过。完整职责与提交顺序见
[G0A 独立评审与 Clean Baseline 交接](./governance/G0A_REVIEW_AND_BASELINE_HANDOFF.md)。

该命令必须由仓库 `.venv` 的解释器启动。它先生成排除自身输出的 worktree fingerprint，
将**全部**旧 `SoftwareVerificationEvidence` 标记为未运行，再依次执行 Python/docs、
Rustfmt、Rust test、Clippy 和 desktop JavaScript 检查。所有登记协议，包括定向测试，
都必须直接执行才能恢复 `pass`，不得依赖手工声明的父门禁覆盖关系。

全部通过后才创建带 UTC 开始/结束时间的 `verificationRuns`，记录真实 Python 可执行路径、
已安装分发集合摘要、Python/Rust/Cargo/Node 版本、锁文件摘要和实际命令。验证前会拒绝与
`poetry.lock` 不一致的 `.venv`，并要求本机 Rust 不低于 workspace 的 1.77.2 MSRV。
CI 另有固定 1.77.2 的最低版本兼容 job；本地较新工具链不伪装成 MSRV 证明。任一命令
失败会清除当前成功标记，尚未执行的后续协议继续保持 `not_run_for_fingerprint`。

GateEvidence v2 的 `subjectCommit`/`subjectTree` 指向被验证提交；证据和 `STATUS.md` 可以在
后续只包含这两个生成文件的 attestation commit 中提交。CI 验证 subject 与 attestation 的
祖先和 diff 关系，但不会要求 Linux、Windows 或不同 Python 矩阵复制证据生产机器的绝对
路径。普通开发循环仍可只运行相关子门，但不能据此刷新 GateEvidence。

## 4. 单独运行

```powershell
.\.venv\Scripts\python.exe scripts/docs_check.py
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check app ui tests main.py streamlit_app.py
.\.venv\Scripts\python.exe -m compileall -q app ui tests main.py streamlit_app.py
cargo fmt --all --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
node --check apps/desktop/web/app.js
```

## 5. 依赖管理

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

## 6. Python 支持策略

- 3.13 是旧引擎基线、研究桥接和迁移期对照的默认版本；
- CI 在 Linux 验证最低版本 3.10、中间版本 3.12 和最高版本 3.14；
- CI 额外在 Windows + Python 3.13 验证主要桌面开发平台；
- 新 Python 次版本先加入 CI，验证通过后再扩大 `requires-python` 范围。

## 7. 静态检查策略

当前 Ruff 只启用影响正确性的规则：语法错误、无效控制流和未定义名称。更广泛的导入排序、风格和格式统一将在清理阶段独立进行，避免一次产生大量与行为修改混杂的差异。

任何新增代码仍应保持一致格式；该限制不表示项目接受长期风格漂移。
