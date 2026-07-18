# Telysta Diachron Engine

[中文说明 (Chinese)](./README_zh.md)

Telysta Diachron Engine is an early-stage, local-first and auditable simulator for
**constructed languages and diachronic language evolution**. The repository is currently
building its product foundation; it does not yet generate a complete usable language.

It is designed for serious worldbuilding workflows where language is not a static wordlist but a historical system evolving through eras, branches, and structural drift.

## Why this project

Most language generators stop at random phoneme assembly or flat grammar templates. Telysta is being built to model:

- Sound change over time (erosion, assimilation, lenition, etc.)
- Grammaticalization pathways from lexical items to function markers
- Morphological drift with per-domain state transitions
- Branch language divergence with independent evolution profiles
- CSG-based generation (semantic graph as stable external API)

## Core architecture

Rust is the only production authority, Tauri is the desktop client, and Python is a
legacy/research baseline. The current Rust foundation provides versioned state, deterministic
RNG, project transactions and storage, but the production Genesis compiler and LanguageState
v3 are not implemented. See [Current Architecture](./docs/architecture/CURRENT.md) and
[ADR-006](./docs/adr/ADR-006-rust-native-core-python-research-bridge.md).

The bullets below describe capabilities in the Python research prototype, not shipped Rust
product capabilities:

- **Symbolic layer**: deterministic linguistic operators (phonology, morphology, syntax)
- **Neural layer**: optional LLM sidecar for controlled narrative/annotation (never direct rule override)
- **Hot State + Delta events**: in-memory evolution state with event-style history
- **Epoch orchestration**: multi-era historical simulation with optional bias profiles

## Repository layout

- `crates/` — Rust production core and project storage
- `apps/desktop/` — Tauri desktop shell and static webview
- `app/` — Python legacy baseline and research implementation
- `data/` — linguistic datasets, pathways, and presets
- `docs/` — development architecture and design documentation
- `tests/` — unit and integration tests
- `main.py` — CLI entry point
- `streamlit_app.py` — web UI entry point

## Quickstart

### Requirements

- Rust 1.77.2 for the production core and desktop checks
- Python 3.10–3.14 (Python 3.13 recommended) for legacy/research checks

### Install

```bash
python -m venv .venv
uvx --from poetry==2.4.1 poetry sync --no-interaction
```

See [Development Setup and Quality Checks](./docs/DEVELOPMENT_SETUP.md) for Windows and Unix activation commands.
Poetry runs in an isolated tool environment so that the project `.venv` remains an exact
`poetry.lock` environment.

Install the pinned Rust toolchain:

```bash
rustup toolchain install 1.77.2 --component rustfmt --component clippy
```

### Run CLI

```bash
python main.py
```

### Run tests

```bash
python scripts/check.py
cargo +1.77.2 fmt --all --check
cargo +1.77.2 test --workspace --locked
cargo +1.77.2 clippy --workspace --all-targets --locked -- -D warnings
node --check apps/desktop/web/app.js
```

The Python command covers the legacy/research baseline and documentation governance. It is
not a replacement for the Rust and desktop gates.

### Run Streamlit UI

```bash
python -m streamlit run streamlit_app.py
```

### Run the Tauri foundation shell

```bash
cargo run -p telysta-desktop
```

This launches the current project/Blueprint inspector, not the future Genesis product flow.

## Current status

This project is in its product-foundation phase. R0A is closing the repository/platform/Project–Operation–Run–Job contracts for G0A while R0B freezes the WS-1 Meaning/Grammar/Task/Canon evidence for G0B. R1 may start only after G0A; production LanguageState v3 and Genesis work require both G1 and G0B. The first product wedge is a canon-safe, auditable Story Language Kit, followed by mechanistic change and language-family capabilities.

Planning and architecture documents:

- [Current Status](./docs/STATUS.md)
- [Documentation Index](./docs/README.md)
- [Product Development Execution Plan](./docs/PRODUCT_DEVELOPMENT_PLAN.md)
- [Professional Language Simulator Implementation Plan](./docs/LANGUAGE_SIMULATOR_PLAN.md)
- [Development Setup and Quality Checks](./docs/DEVELOPMENT_SETUP.md)
- [Current Roadmap](./docs/ROADMAP.md)
- [Rust-native Core + Python Research Bridge ADR](./docs/adr/ADR-006-rust-native-core-python-research-bridge.md)
- [Community-driven Simulation Architecture](./docs/adr/ADR-005-community-driven-language-simulation.md)
- [Cleanup Plan](./docs/CLEANUP_PLAN.md)
- [Rule and Language Quality Plan](./docs/RULE_QUALITY_PLAN.md)
- [Development Document](./docs/development.md)

## License

MIT (see `pyproject.toml` metadata).
