"""Repository-level documentation governance checks and negative fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.docs_check import DocumentationRepository, collect_errors
from scripts.generate_gate_evidence import render_status


def _write(root: Path, relative: str, contents: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def test_documentation_contracts_are_consistent() -> None:
    assert collect_errors() == []


def test_link_parser_supports_parentheses_and_rejects_missing_anchor(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path, "docs/target(v1).md", "# Existing Heading\n")
    source = _write(
        tmp_path,
        "docs/source.md",
        "[file](./target(v1).md)\n[bad](./target(v1).md#missing)\n",
    )
    repository = DocumentationRepository(
        tmp_path, metadata_exemptions=(), required_schema_constants=()
    )
    errors: list[str] = []
    repository.check_local_links(errors, files=[source, target])
    assert errors == [
        "docs/source.md: missing Markdown anchor missing in docs/target(v1).md"
    ]


def test_index_requires_exact_paths_and_reports_duplicate_basenames(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "docs/README.md", "[one](./a/shared.md)\n")
    _write(tmp_path, "docs/a/shared.md", "# A\n")
    _write(tmp_path, "docs/b/shared.md", "# B\n")
    repository = DocumentationRepository(
        tmp_path, metadata_exemptions=(), required_schema_constants=()
    )
    errors: list[str] = []
    repository.check_docs_index(errors)
    assert "docs/README.md: missing exact index entry for docs/b/shared.md" in errors
    assert any("duplicate basename shared.md" in error for error in errors)


def test_structured_metadata_rejects_missing_and_invalid_values(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "docs/sample.md",
        """---
document_type: architecture-target
decision_status: maybe
implementation_status: implemented
normative_scope: future
last_verified: 2026-07-17
---
# Target
""",
    )
    repository = DocumentationRepository(
        tmp_path,
        metadata_exemptions=(),
        required_schema_constants=(),
    )
    errors: list[str] = []
    repository.check_metadata(errors)
    assert "docs/sample.md: invalid decision_status value 'maybe'" in errors
    assert "docs/sample.md: invalid normative_scope value 'future'" in errors
    assert "docs/sample.md: target architecture cannot claim implemented" in errors


def test_schema_contract_compares_structured_value_to_rust_constant(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "crates/core/src/state.rs",
        'pub const LANGUAGE_STATE_SCHEMA: &str = "state.v2";\n',
    )
    _write(
        tmp_path,
        "docs/state.md",
        """---
document_type: contract
decision_status: accepted
implementation_status: implemented
normative_scope: current
last_verified: 2026-07-17
implementation_schema: state.v1
implementation_path: crates/core/src/state.rs
implementation_constant: LANGUAGE_STATE_SCHEMA
---
# State
""",
    )
    required = (("crates/core/src/state.rs", "LANGUAGE_STATE_SCHEMA"),)
    repository = DocumentationRepository(
        tmp_path,
        metadata_exemptions=(),
        required_schema_constants=required,
    )
    errors: list[str] = []
    repository.check_schema_contracts(errors)
    assert errors == [
        "docs/state.md: implementation_schema state.v1 does not match "
        "crates/core/src/state.rs:LANGUAGE_STATE_SCHEMA value state.v2"
    ]


def test_desktop_command_must_be_documented(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "apps/desktop/src-tauri/src/main.rs",
        ".invoke_handler(tauri::generate_handler![engine_info, new_command])\n",
    )
    _write(tmp_path, "apps/desktop/README.md", "- `engine_info`\n")
    repository = DocumentationRepository(
        tmp_path, metadata_exemptions=(), required_schema_constants=()
    )
    errors: list[str] = []
    repository.check_desktop_command_docs(errors)
    assert errors == ["apps/desktop/README.md: missing Tauri command new_command"]


def test_new_normative_document_cannot_use_legacy_status_bypass(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "docs/NEW_AUTHORITATIVE_CONTRACT.md",
        "# New contract\n\nStatus: accepted\n",
    )
    repository = DocumentationRepository(
        tmp_path,
        metadata_exemptions=(),
        required_schema_constants=(),
    )
    errors: list[str] = []
    repository.check_metadata(errors)
    assert errors == [
        "docs/NEW_AUTHORITATIVE_CONTRACT.md: "
        "required YAML front matter is missing"
    ]


def test_metadata_rejects_unknown_document_type_and_bad_date(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "docs/sample.md",
        """---
document_type: invented-authority
decision_status: accepted
implementation_status: verified
normative_scope: current
last_verified: eventually
---
# Sample
""",
    )
    repository = DocumentationRepository(
        tmp_path,
        metadata_exemptions=(),
        required_schema_constants=(),
    )
    errors: list[str] = []
    repository.check_metadata(errors)
    assert "docs/sample.md: invalid document_type value 'invented-authority'" in errors
    assert (
        "docs/sample.md: last_verified must be an ISO date/date-time or not-verified"
        in errors
    )


def test_docs_gate_rejects_manually_forged_passed_decision(
    tmp_path: Path,
) -> None:
    evidence = {
        "$schema": "GATE_EVIDENCE_MANIFEST_V2.schema.json",
        "schemaVersion": "telysta-gate-evidence-manifest.v2",
        "gateId": "G0A",
        "gateName": "test",
        "decision": "passed",
        "decisionDate": "2026-07-18",
        "source": {
            "subjectCommit": "a" * 40,
            "subjectTree": "b" * 40,
            "worktreeDirty": True,
            "worktreeStatusEntryCount": 1,
            "worktreeFingerprintSchema": "telysta-git-worktree-fingerprint.v2",
            "worktreeInventorySha256": "0" * 64,
            "excludedGeneratedPaths": [
                "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
                "docs/STATUS.md",
            ],
            "environment": "test",
            "verificationRuns": [],
        },
        "claims": {"allowed": [], "forbidden": ["G0A has passed"]},
        "evidence": [],
        "requirements": [
            {
                "id": "R0A-05",
                "name": "baseline",
                "status": "failed",
                "evidencePaths": [],
            }
        ],
        "blockers": [
            {"severity": "blocking", "id": "G0A-B01", "summary": "still blocked"}
        ],
        "owner": None,
        "reviewers": [],
        "waivers": [],
        "nextDecision": "stop",
    }
    _write(
        tmp_path,
        "docs/G0A_GATE_EVIDENCE_2026-07-17.json",
        json.dumps(evidence),
    )
    decision_fragment = "\u5f53\u524d\u51b3\u7b56\u4e3a `passed`"
    _write(tmp_path, "docs/README.md", decision_fragment)
    _write(tmp_path, "docs/ROADMAP.md", decision_fragment)
    _write(tmp_path, "docs/STATUS.md", render_status(evidence))
    _write(
        tmp_path,
        "docs/architecture/CURRENT.md",
        "---\n"
        "verification_source: docs/G0A_GATE_EVIDENCE_2026-07-17.json\n"
        "---\n",
    )
    repository = DocumentationRepository(
        tmp_path,
        metadata_exemptions=(),
        required_schema_constants=(),
    )
    errors: list[str] = []
    repository.check_gate_status(errors)
    assert len(errors) == 1
    assert "invalid GateEvidence decision" in errors[0]
