# ADR-004：Tauri 桌面客户端与 Python Sidecar

- 状态：`Superseded`
- 日期：2026-07-12
- 决策范围：桌面客户端、引擎进程边界、项目文件访问

> 替代说明：本文关于 Tauri、Svelte/TypeScript、本地优先和最小权限的原则继续有效；“Python sidecar 作为长期生产核心”的决策已由 [ADR-006：Rust 原生生产核心与 Python 研究桥接](./ADR-006-rust-native-core-python-research-bridge.md) 取代。本文仅保留为历史决策记录，不再作为执行依据。

## 背景

当前 Streamlit UI 适合展示研究原型，但不适合长期管理本地语言项目：运行状态依赖进程内 session，事件和 lore 又从全局目录读取，难以支持多个项目、并行运行、任务取消、安装分发和细粒度文件权限。

引擎主体已经以 Python 实现，并拥有较多领域测试。立即全量迁移 Rust 会扩大风险，且当前尚无性能数据证明全量迁移必要。

## 决策

采用以下桌面架构：

- Tauri 2 作为桌面应用容器；
- Svelte + TypeScript 作为前端；
- Python 引擎打包为独立 sidecar；
- Tauri/Rust 管理 sidecar 启动、终止、取消和异常恢复；
- 前端通过受控命令调用引擎，不直接获得任意 shell 权限；
- sidecar 与宿主默认使用 stdin/stdout 上的 NDJSON 消息通信；
- 项目文件由宿主选择和授权，引擎只访问明确传入的项目目录；
- Streamlit 在功能等价前保留为对照实现，随后弃用。

## 为什么不使用本地 HTTP

第一阶段不使用 localhost HTTP 服务，原因是：

- 需要端口发现和生命周期管理；
- 可能受到防火墙、代理和端口冲突影响；
- 需要额外鉴权，防止本机其他进程调用；
- 当前产品是单机、单宿主、单引擎进程，标准输入输出已经足够。

通信层必须抽象为 `EngineTransport`。未来如果引入远程计算，可以增加 HTTP/WebSocket transport，而不改变前端业务接口。

## 协议草案

请求：

```json
{"id":"req-1","method":"run_evolution","params":{"project_id":"p1","seed":888}}
```

进度事件：

```json
{"event":"progress","request_id":"req-1","era":12,"total_eras":100}
```

成功响应：

```json
{"id":"req-1","ok":true,"result":{"run_id":"run-...","final_era":100}}
```

失败响应：

```json
{"id":"req-1","ok":false,"error":{"code":"INVALID_RULE","message":"..."}}
```

协议要求：

- 每条消息单行 JSON；
- stdout 只能输出协议消息，普通日志进入 stderr；
- 所有请求有 ID；
- 长任务支持取消；
- 未知字段向前兼容，未知方法明确报错；
- 协议和项目格式独立版本化；
- 不向前端返回 API key、绝对内部路径或未经处理的异常堆栈。

## 权限原则

- capability 只允许启动已打包的固定 sidecar；
- 不允许前端传入任意可执行文件路径；
- 文件访问限制在用户选中的项目与导出位置；
- LLM API key 存储使用操作系统安全凭据能力，不写入项目文件或日志；
- 前端不直接访问数据库文件；
- 所有外部链接和更新来源使用显式 allowlist。

## 打包策略

第一阶段使用 PyInstaller 或等价方案生成平台相关 sidecar。构建产物必须：

- 固定 Python 和依赖版本；
- 在无 Python 环境中运行；
- 包含所需 data 规则和预设；
- 输出引擎版本、协议版本和数据格式版本；
- 分别为目标平台构建，不复用跨平台二进制。

## 后果

正面影响：

- 保留现有 Python 领域实现和测试投资；
- 获得原生安装、项目文件、任务取消和桌面权限控制；
- 前端与引擎可以独立测试和演化；
- 为未来局部 Rust 优化保留边界。

代价：

- 需要维护 TypeScript、Rust 和 Python 三个构建层；
- sidecar 打包会增加安装体积；
- IPC 协议和项目格式必须严格版本化；
- 跨平台构建需要独立 CI runner。

## Rust 迁移触发条件

只有同时满足以下条件才迁移计算模块：

1. 已有稳定的正确性基准；
2. profiling 证明模块是主要瓶颈；
3. Python/NumPy 优化无法达到产品目标；
4. Rust 实现可以通过同一黄金场景和后端一致性测试。
