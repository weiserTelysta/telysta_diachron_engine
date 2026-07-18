# Telysta Desktop Foundation Shell

This is the current Tauri foundation shell. It calls the Rust core and storage directly; it
does not launch a Python sidecar. The direct desktop-to-storage dependency is transitional
until `telysta-application` is introduced after G0A.

The current commands are:

- `engine_info`
- `run_demo(seed)` with `engine://progress` events
- `cancel_run(run_id)`
- `recover_pending_runs`
- `open_project(project_root)`
- `get_project_session(project_id)`
- `refresh_project(project_id)`
- `close_project(project_id)`
- `validate_blueprint(blueprint)`

The static HTML is a project/Blueprint inspector and packaging proof. It does not provide
Genesis or project creation because every built-in Blueprint compiler capability is currently
`planned`. Product UI work remains gated by the application boundary and the WS-1 executable
language slice. See [`docs/architecture/CURRENT.md`](../../docs/architecture/CURRENT.md).
