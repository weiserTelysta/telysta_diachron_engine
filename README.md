# Telysta Diachron Engine

[中文说明 (Chinese)](./README_zh.md)

Telysta Diachron Engine is a neuro-symbolic conlang engine for **diachronic language evolution**.

It is designed for serious worldbuilding workflows where language is not a static wordlist but a historical system evolving through eras, branches, and structural drift.

## Why this project

Most language generators stop at random phoneme assembly or flat grammar templates. Telysta Diachron Engine models:

- Sound change over time (erosion, assimilation, lenition, etc.)
- Grammaticalization pathways from lexical items to function markers
- Morphological drift with per-domain state transitions
- Branch language divergence with independent evolution profiles
- CSG-based generation (semantic graph as stable external API)

## Core architecture

- **Symbolic layer**: deterministic linguistic operators (phonology, morphology, syntax)
- **Neural layer**: optional LLM sidecar for controlled narrative/annotation (never direct rule override)
- **Hot State + Delta events**: in-memory evolution state with event-style history
- **Epoch orchestration**: multi-era historical simulation with optional bias profiles

## Repository layout

- `app/` — core domain and engine implementation
- `data/` — linguistic datasets, pathways, and presets
- `docs/` — development architecture and design documentation
- `tests/` — unit and integration tests
- `main.py` — CLI entry point
- `streamlit_app.py` — web UI entry point

## Quickstart

### Requirements

- Python 3.10+
- Poetry

### Install

```bash
poetry install
```

### Run CLI

```bash
poetry run python main.py
```

### Run tests

```bash
poetry run pytest tests/ -q
```

### Run Streamlit UI

```bash
poetry run streamlit run streamlit_app.py
```

## Current status

This project is under active development. For the complete architecture and roadmap, see:

- [Development Document](./docs/development.md)

## License

MIT (see `pyproject.toml` metadata).
