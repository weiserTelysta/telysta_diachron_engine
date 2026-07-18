# Rust Desktop Shell Spike

- 状态：`Completed`
- 完成日期：2026-07-13
- 对应工作：`PLT-001`、`PLT-002`、`APP-001`
- 边界：这是 Rust/Tauri 的技术纵切，不是正式 `LanguageState`、规则执行器或产品 UI。

## 已验证的边界

`crates/telysta-core` 是纯 Rust 的最小核心；`apps/desktop/src-tauri` 只依赖该 crate，不启动 Python、不调用 Python 子进程，也不把 Python 状态写入产品路径。

```text
Tauri command
  -> DesktopState (checkpoint adapter)
  -> telysta-core::DemoEngine
  -> versioned response / event envelope
```

当前 command 和 event 的 `apiVersion` 都是 `telysta-engine-api.v1`：

| 接口 | 行为 |
|---|---|
| `engine_info` | 返回 Rust-native 运行时声明，明确 `pythonRuntimeRequired: false`。 |
| `run_demo(runId, seed)` | 以用户提供的幂等 `runId` 创建可取消 demo run；同 ID、同 seed 的重试返回同一 run，不同 seed 被拒绝。 |
| `cancel_run(runId)` | 停止仍在运行的 demo，并推送 `engine://cancelled`。 |
| `recover_pending_runs` | 从已恢复的 checkpoint 找出未完成 run，重新启动其 worker。 |

## 最小崩溃恢复合同

核心以版本化 `telysta-demo-checkpoint.v1` 保存 run、进度和 revision。桌面壳将 payload 包入 `telysta-desktop-demo-checkpoint.v1`，附带 SHA-256 校验和，并将连续 revision 交替写入应用数据目录中的两个槽位。单槽替换经临时文件完成；写入或替换中断时，另一个最后成功槽位仍可恢复。两个槽位都无法通过 schema 与 checksum 验证时，桌面程序显式报错，不静默丢弃或臆造状态。

这只证明 demo 任务的恢复边界。该 Spike 验收时，正式项目恢复仍须在 `FND-005` 至 `FND-008` 中重新实现；相关基线现已由 [Project Runtime v1](./PROJECT_RUNTIME_V1.md) 与 [Project Storage v1](./PROJECT_STORAGE_V1.md) 建立。该进展仍不允许把 demo 格式升级为产品格式。

## 本地验证

需要 Rust 1.77.2 或更高版本、Node.js（仅在后续正式前端构建时需要）和 Windows Tauri/WebView2 构建前置条件。当前静态壳不依赖 Python，也不需要 Node 包安装。

```powershell
cargo fmt --all --check
cargo test -p telysta-core
cargo check -p telysta-desktop
```

本工作包的证据：核心 crate 中 A-005 的 6 项测试覆盖 Rust runtime 声明、确定性 run ID、进度顺序、取消、checkpoint 恢复与版本化 envelope；Windows 上的 `cargo check -p telysta-desktop` 已通过。CI 以 Linux 验证核心和格式，以 Windows 编译 Tauri 壳。

## 非目标与验收时的下一步（历史）

- 不复刻 Python 的 `EngineHotState`、`EpochManager` 或历史回放缺陷；
- 不把 demo checkpoint 当成正式项目存储；
- 不在此阶段迁移 Streamlit 页面或建立完整 UI。

本 Spike 验收时的下一工作包是 `B-001`；该工作及其后续基础合同现已完成。本句保留历史交接信息，当前 Next 以文档索引中的三份主计划为准。
