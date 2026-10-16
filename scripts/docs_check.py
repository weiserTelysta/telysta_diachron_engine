"""Validate documentation links, metadata, generated state, and code contracts."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

from scripts.generate_gate_evidence import (  # noqa: E402
    render_status,
    validate_passed_decision,
)

RUST_STRING_CONSTANT = re.compile(
    r'(?:pub\s+)?const\s+(?P<name>[A-Z0-9_]+)\s*:\s*&str\s*=\s*"(?P<value>[^"]+)"'
)

LEGACY_METADATA_EXEMPTIONS = frozenset(
    {
        "docs/adr/ADR-004-tauri-python-sidecar.md",
        "docs/adr/ADR-005-community-driven-language-simulation.md",
        "docs/adr/ADR-006-rust-native-core-python-research-bridge.md",
        "docs/adr/ADR-007-language-state-v3-change-event-ir.md",
        "docs/adr/ADR-008-registry-bundle-domain-registries.md",
        "docs/adr/ADR-009-atomic-change-set-and-usage-observations.md",
        "docs/adr/ADR-010-genesis-artifact-trust-boundary.md",
        "docs/AGENT_OPERATING_MODEL.md",
        "docs/BASELINE_REPORT_2026-07-14.md",
        "docs/CANONICAL_STATE_V1.md",
        "docs/CLEANUP_PLAN.md",
        "docs/development.md",
        "docs/FOUNDATION_MODEL_V1.md",
        "docs/LANGUAGE_BLUEPRINT_V1.md",
        "docs/LEGACY_EVENT_COVERAGE.md",
        "docs/MODULE_MIGRATION_MATRIX.md",
        "docs/PROJECT_OPERATION_JOB_CONTRACT_DRAFT.md",
        "docs/README.md",
        "docs/RULE_QUALITY_PLAN.md",
        "docs/RUST_DESKTOP_SPIKE.md",
        "docs/SKILL_ALLOWLIST.md",
    }
)

DOCUMENT_TYPES = frozenset(
    {
        "adr",
        "architecture-description",
        "architecture-target",
        "capability-plan",
        "contract",
        "evidence",
        "governance-policy",
        "index",
        "legacy",
        "migration-contract",
        "migration-plan",
        "operational-status",
        "plan",
        "product-plan",
        "research",
        "roadmap",
        "runbook",
    }
)

REQUIRED_SCHEMA_CONSTANTS = frozenset(
    {
        ("crates/telysta-core/src/state.rs", "LANGUAGE_STATE_SCHEMA"),
        ("crates/telysta-core/src/blueprint.rs", "LANGUAGE_BLUEPRINT_SCHEMA"),
        ("crates/telysta-core/src/data.rs", "DATA_MANIFEST_SCHEMA"),
        ("crates/telysta-core/src/rng.rs", "RNG_TREE_SCHEMA"),
        ("crates/telysta-core/src/time.rs", "TIME_MODEL_SCHEMA"),
        ("crates/telysta-core/src/project.rs", "PROJECT_HISTORY_SCHEMA"),
        ("crates/telysta-storage/src/lib.rs", "PROJECT_FILE_SCHEMA"),
        ("crates/telysta-storage/src/session.rs", "PROJECT_SESSION_SCHEMA"),
    }
)

REQUIRED_METADATA = frozenset(
    {
        "document_type",
        "decision_status",
        "implementation_status",
        "normative_scope",
        "last_verified",
    }
)

ALLOWED_METADATA: dict[str, frozenset[str]] = {
    "document_type": DOCUMENT_TYPES,
    "decision_status": frozenset(
        {"proposed", "accepted", "superseded", "not-applicable"}
    ),
    "implementation_status": frozenset(
        {
            "not-started",
            "in-progress",
            "partial",
            "implemented",
            "verified",
            "generated",
            "historical",
        }
    ),
    "normative_scope": frozenset({"current", "migration", "target", "historical"}),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_front_matter(text: str) -> dict[str, Any] | None:
    """Parse YAML front matter without accepting a second ambiguous block."""

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    document = yaml.safe_load("\n".join(lines[1:end]))
    return document if isinstance(document, dict) else None


def inline_link_targets(text: str) -> list[str]:
    """Extract inline Markdown targets while respecting balanced parentheses."""

    targets: list[str] = []
    cursor = 0
    while True:
        start = text.find("](", cursor)
        if start < 0:
            return targets
        index = start + 2
        depth = 1
        escaped = False
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    targets.append(text[start + 2 : index])
                    cursor = index + 1
                    break
            index += 1
        else:
            cursor = start + 2


def _target_href(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return target.split(maxsplit=1)[0] if target else ""


def _github_heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        heading = re.sub(r"[`*_~]", "", match.group(1)).strip().lower()
        heading = re.sub(r"[^\w\u3400-\u9fff -]", "", heading)
        slug = re.sub(r"\s", "-", heading)
        duplicate = counts.get(slug, 0)
        counts[slug] = duplicate + 1
        anchors.add(slug if duplicate == 0 else f"{slug}-{duplicate}")
    return anchors


def _rust_constants(path: Path) -> dict[str, str]:
    return {
        match.group("name"): match.group("value")
        for match in RUST_STRING_CONSTANT.finditer(_read(path))
    }


def _valid_verification_date(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = value.strip()
    if candidate == "not-verified":
        return True
    try:
        if "T" in candidate:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        else:
            date.fromisoformat(candidate)
    except ValueError:
        return False
    return True


class DocumentationRepository:
    """A repository-root-injectable documentation validator."""

    def __init__(
        self,
        root: Path,
        *,
        metadata_exemptions: Iterable[str] = LEGACY_METADATA_EXEMPTIONS,
        required_schema_constants: Iterable[tuple[str, str]] = REQUIRED_SCHEMA_CONSTANTS,
    ) -> None:
        self.root = root.resolve()
        self.docs = self.root / "docs"
        self.docs_index = self.docs / "README.md"
        self.metadata_exemptions = frozenset(metadata_exemptions)
        self.required_schema_constants = frozenset(required_schema_constants)

    def repository_markdown(self) -> list[Path]:
        files = [
            self.root / "AGENTS.md",
            self.root / "README.md",
            self.root / "README_zh.md",
        ]
        files.extend(self.docs.rglob("*.md"))
        files.append(self.root / "apps" / "desktop" / "README.md")
        return sorted({path for path in files if path.is_file()})

    def check_local_links(
        self,
        errors: list[str],
        *,
        files: Iterable[Path] | None = None,
    ) -> None:
        for path in files or self.repository_markdown():
            for raw_target in inline_link_targets(_read(path)):
                href = _target_href(raw_target)
                if href.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part, separator, fragment = href.partition("#")
                decoded_path = unquote(path_part)
                target_path = path if not decoded_path else (path.parent / decoded_path).resolve()
                if not target_path.exists():
                    errors.append(
                        f"{path.relative_to(self.root).as_posix()}: "
                        f"missing local link target {raw_target}"
                    )
                    continue
                if separator and fragment and target_path.suffix.lower() == ".md":
                    anchor = unquote(fragment).lower()
                    if anchor not in _github_heading_anchors(_read(target_path)):
                        errors.append(
                            f"{path.relative_to(self.root).as_posix()}: "
                            f"missing Markdown anchor {fragment} in "
                            f"{target_path.relative_to(self.root).as_posix()}"
                        )

    def check_docs_index(self, errors: list[str]) -> None:
        index_targets: set[str] = set()
        for raw_target in inline_link_targets(_read(self.docs_index)):
            href = _target_href(raw_target)
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = unquote(href.split("#", 1)[0])
            if not path_part:
                continue
            resolved = (self.docs_index.parent / path_part).resolve()
            try:
                index_targets.add(resolved.relative_to(self.docs).as_posix())
            except ValueError:
                continue

        basename_owners: dict[str, list[str]] = {}
        for path in sorted(self.docs.rglob("*")):
            if (
                not path.is_file()
                or path == self.docs_index
                or path.suffix not in {".md", ".json"}
            ):
                continue
            relative = path.relative_to(self.docs).as_posix()
            basename_owners.setdefault(path.name, []).append(relative)
            if relative not in index_targets:
                errors.append(f"docs/README.md: missing exact index entry for docs/{relative}")

        for basename, owners in sorted(basename_owners.items()):
            if len(owners) > 1:
                errors.append(
                    f"docs: duplicate basename {basename} requires unambiguous paths: "
                    f"{', '.join(owners)}"
                )

    def check_metadata(self, errors: list[str]) -> None:
        for path in sorted(self.docs.rglob("*.md")):
            relative = path.relative_to(self.root).as_posix()
            metadata = parse_front_matter(_read(path))
            if metadata is None and relative in self.metadata_exemptions:
                head = "\n".join(_read(path).splitlines()[:14])
                if "状态" not in head and "Status" not in head:
                    errors.append(
                        f"{relative}: legacy metadata has no status in first 14 lines"
                    )
                continue
            if metadata is None:
                errors.append(f"{relative}: required YAML front matter is missing")
                continue

            missing = sorted(REQUIRED_METADATA - metadata.keys())
            if missing:
                errors.append(
                    f"{relative}: missing metadata fields {', '.join(missing)}"
                )
            for field, allowed in ALLOWED_METADATA.items():
                value = metadata.get(field)
                if value is not None and str(value) not in allowed:
                    errors.append(f"{relative}: invalid {field} value {value!r}")

            last_verified = metadata.get("last_verified")
            if not _valid_verification_date(last_verified):
                errors.append(
                    f"{relative}: last_verified must be an ISO date/date-time "
                    "or not-verified"
                )
            if (
                metadata.get("document_type") == "architecture-target"
                and metadata.get("implementation_status") in {"implemented", "verified"}
            ):
                errors.append(f"{relative}: target architecture cannot claim implemented")
            if metadata.get("decision_status") == "proposed":
                if "owner" not in metadata or "reviewers" not in metadata:
                    errors.append(
                        f"{relative}: proposed decision requires owner and reviewers fields"
                    )

    def check_authority_read_order(self, errors: list[str]) -> None:
        agents = _read(self.root / "AGENTS.md")
        required_order = (
            "docs/STATUS.md",
            "docs/PRODUCT_DEVELOPMENT_PLAN.md",
            "docs/ROADMAP.md",
            "docs/LANGUAGE_SIMULATOR_PLAN.md",
            "docs/governance/AUTHORITY_ORDER.md",
            "docs/architecture/CURRENT.md",
            "docs/architecture/TARGET.md",
            "docs/architecture/MIGRATION.md",
        )
        positions = [agents.find(item) for item in required_order]
        missing = [
            item
            for item, position in zip(required_order, positions, strict=True)
            if position < 0
        ]
        if missing:
            errors.append(
                f"AGENTS.md: mandatory read order is missing {', '.join(missing)}"
            )
        elif positions != sorted(positions):
            errors.append(
                "AGENTS.md: mandatory read order conflicts with documented reading order"
            )

    def check_gate_status(self, errors: list[str]) -> None:
        evidence_path = self.docs / "G0A_GATE_EVIDENCE_2026-07-17.json"
        evidence = json.loads(_read(evidence_path))
        decision = evidence.get("decision")
        if decision not in {"blocked", "passed"}:
            errors.append(
                f"{evidence_path.relative_to(self.root).as_posix()}: "
                f"unsupported decision {decision!r}"
            )
            return

        try:
            validate_passed_decision(evidence, root=self.root)
        except (KeyError, OSError, TypeError, ValueError) as error:
            errors.append(
                f"{evidence_path.relative_to(self.root).as_posix()}: "
                f"invalid GateEvidence decision: {error}"
            )

        expected_fragments = (
            (self.docs / "README.md", f"当前决策为 `{decision}`"),
            (self.docs / "ROADMAP.md", f"当前决策为 `{decision}`"),
        )
        for path, fragment in expected_fragments:
            if fragment not in _read(path):
                errors.append(
                    f"{path.relative_to(self.root).as_posix()}: "
                    f"G0A status does not match GateEvidence {decision}"
                )

        status_path = self.docs / "STATUS.md"
        expected_status = render_status(evidence)
        if _read(status_path) != expected_status:
            errors.append("docs/STATUS.md: generated status differs from GateEvidence")

        current_metadata = parse_front_matter(
            _read(self.docs / "architecture" / "CURRENT.md")
        )
        if current_metadata is not None:
            expected_source = evidence_path.relative_to(self.root).as_posix()
            if current_metadata.get("verification_source") != expected_source:
                errors.append(
                    "docs/architecture/CURRENT.md: verification_source must point "
                    "to the authoritative GateEvidence"
                )
            if "base_commit" in current_metadata:
                errors.append(
                    "docs/architecture/CURRENT.md: base_commit must not duplicate "
                    "the dynamic GateEvidence subject"
                )

    def check_schema_contracts(self, errors: list[str]) -> None:
        covered: dict[tuple[str, str], str] = {}
        for path in sorted(self.docs.rglob("*.md")):
            relative = path.relative_to(self.root).as_posix()
            metadata = parse_front_matter(_read(path))
            if metadata is None or "implementation_schema" not in metadata:
                continue
            source_name = metadata.get("implementation_path")
            constant_name = metadata.get("implementation_constant")
            schema = metadata.get("implementation_schema")
            if not all(isinstance(value, str) and value for value in (source_name, constant_name, schema)):
                errors.append(
                    f"{relative}: implementation schema metadata must contain path, constant and schema"
                )
                continue
            key = (source_name, constant_name)
            if key in covered:
                errors.append(
                    f"{relative}: duplicates schema contract {source_name}:{constant_name} "
                    f"already declared by {covered[key]}"
                )
                continue
            covered[key] = relative
            source = self.root / source_name
            if not source.is_file():
                errors.append(f"{relative}: implementation path does not exist: {source_name}")
                continue
            actual = _rust_constants(source).get(constant_name)
            if actual is None:
                errors.append(
                    f"{relative}: Rust constant {constant_name} is missing from {source_name}"
                )
            elif actual != schema:
                errors.append(
                    f"{relative}: implementation_schema {schema} does not match "
                    f"{source_name}:{constant_name} value {actual}"
                )

        missing = sorted(self.required_schema_constants - covered.keys())
        for source_name, constant_name in missing:
            errors.append(
                f"docs: no structured contract declares {source_name}:{constant_name}"
            )

    def check_desktop_command_docs(self, errors: list[str]) -> None:
        source_path = (
            self.root / "apps" / "desktop" / "src-tauri" / "src" / "main.rs"
        )
        source = _read(source_path)
        match = re.search(
            r"invoke_handler\s*\(\s*tauri::generate_handler!\[(?P<body>.*?)]\s*\)",
            source,
            re.DOTALL,
        )
        if match is None:
            errors.append(
                "apps/desktop/src-tauri/src/main.rs: cannot locate Tauri command handler list"
            )
            return
        commands = [
            command.strip()
            for command in match.group("body").split(",")
            if command.strip()
        ]
        readme = _read(self.root / "apps" / "desktop" / "README.md")
        for command in commands:
            if f"`{command}" not in readme:
                errors.append(f"apps/desktop/README.md: missing Tauri command {command}")

    def check_json_documents(self, errors: list[str]) -> None:
        paths = list(self.docs.rglob("*.json"))
        paths.extend((self.root / "data" / "manifests").glob("*.json"))
        for path in sorted(paths):
            try:
                json.loads(_read(path))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                errors.append(
                    f"{path.relative_to(self.root).as_posix()}: invalid UTF-8 JSON: {error}"
                )

    def collect_errors(self) -> list[str]:
        errors: list[str] = []
        self.check_local_links(errors)
        self.check_docs_index(errors)
        self.check_metadata(errors)
        self.check_authority_read_order(errors)
        self.check_gate_status(errors)
        self.check_schema_contracts(errors)
        self.check_desktop_command_docs(errors)
        self.check_json_documents(errors)
        return sorted(set(errors))


def collect_errors(root: Path = ROOT) -> list[str]:
    """Return all documentation consistency errors in stable order."""

    return DocumentationRepository(root).collect_errors()


def main() -> int:
    errors = collect_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Documentation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
