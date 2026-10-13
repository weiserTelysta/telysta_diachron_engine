"""Reproduce a small, locked Concepticon selection for research, offline.

This module never imports a language project or writes production state. Its
JSON is a research artifact, not DataManifest, Meaning IR or a CLDF validator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / "experiments" / "concepticon-slice"
LOCK_SCHEMA = "telysta-concepticon-research-lock.v1"
SLICE_SCHEMA = "telysta-concepticon-research-slice.v1"
TRANSFORM = "telysta-concepticon-selection.v1"
TABLES = ("conceptlists.csv", "concepts.csv", "concepticon.csv")
MAX_ARCHIVE_BYTES = 25_000_000
MAX_MEMBER_BYTES = 80_000_000


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _validate_lock(lock: dict[str, Any]) -> None:
    if lock["schemaVersion"] != LOCK_SCHEMA or lock["status"] != "research_only":
        raise ValueError("unsupported research lock")
    transform = lock["transform"]
    if transform["schemaVersion"] != TRANSFORM or transform["scriptSha256"] != sha256(Path(__file__).read_bytes()):
        raise ValueError("transform implementation differs from lock")


def _locked_bytes(raw: bytes, descriptor: dict[str, Any], label: str) -> None:
    if len(raw) != descriptor["sizeBytes"] or sha256(raw) != descriptor["sha256"]:
        raise ValueError(f"{label}: locked bytes differ")


def _bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"{path.name}: payload exceeds research limit")
    return raw


def _member(archive: zipfile.ZipFile, descriptor: dict[str, Any]) -> bytes:
    # Never extract paths. Still reject duplicate names so a member lock cannot
    # ambiguously select the first or last of two entries.
    name = descriptor["member"]
    matches = [entry for entry in archive.infolist() if entry.filename == name]
    if len(matches) != 1 or matches[0].file_size > MAX_MEMBER_BYTES:
        raise ValueError(f"{name}: missing, duplicate or oversized member")
    with archive.open(matches[0]) as stream:
        raw = stream.read(MAX_MEMBER_BYTES + 1)
    _locked_bytes(raw, descriptor, name)
    return raw


def _rows(raw: bytes, columns: list[str]) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if reader.fieldnames != columns or "ID" not in columns or len(set(columns)) != len(columns):
        raise ValueError("CSV columns differ from lock")
    result = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("ragged CSV row")
        identifier = row["ID"]
        if not identifier or identifier in result:
            raise ValueError("blank or duplicate CSV record ID")
        result[identifier] = row
    return result


def validate_selection(payload: dict[str, Any], lock: dict[str, Any]) -> None:
    """Check this selection's exact membership and mapping closure only."""
    source, selection = lock["source"], lock["selection"]
    if payload["schemaVersion"] != SLICE_SCHEMA or payload["status"] != "research_only":
        raise ValueError("unsupported research slice")
    if (payload["datasetId"], payload["sourceVersion"], payload["sourceArchiveSha256"]) != (
        source["datasetId"], source["version"], source["archive"]["sha256"],
    ) or payload["selection"] != selection:
        raise ValueError("source or selection differs from lock")
    if set(payload["tables"]) != set(TABLES):
        raise ValueError("unexpected research table")
    tables = {}
    for table in TABLES:
        rows = payload["tables"][table]
        columns = source["tables"][table]["columns"]
        by_id = {}
        for row in rows:
            if set(row) != set(columns) or any(not isinstance(v, str) for v in row.values()):
                raise ValueError("research row columns/types differ from source")
            if not row["ID"] or row["ID"] in by_id:
                raise ValueError("blank or duplicate research record ID")
            by_id[row["ID"]] = row
        tables[table] = by_id
    if set(tables["conceptlists.csv"]) != {selection["conceptlistId"]}:
        raise ValueError("selected source list differs")
    concepts = tables["concepts.csv"]
    identifiers = selection["conceptIds"]
    if not identifiers or len(set(identifiers)) != len(identifiers) or set(concepts) != set(identifiers):
        raise ValueError("selected source-list entries differ")
    if any(row["Conceptlist_ID"] != selection["conceptlistId"] for row in concepts.values()):
        raise ValueError("source-list entry has foreign lineage")
    mapped = {row["Concepticon_ID"] for row in concepts.values()}
    # This release contains ID 0 / <NA> as a placeholder, not a mapped meaning.
    if mapped & {"", "0"} or mapped != set(tables["concepticon.csv"]):
        raise ValueError("concept-set mapping closure differs")
    if any(row["Replacement_ID"] for row in tables["concepticon.csv"].values()):
        raise ValueError("superseded concept set requires a separate explicit selection")


def build_slice(archive_path: Path, lock: dict[str, Any]) -> bytes:
    """Validate exact source bytes and reproduce the deterministic selection."""
    _validate_lock(lock)
    source = lock["source"]
    raw = _bounded_read(archive_path, MAX_ARCHIVE_BYTES)
    _locked_bytes(raw, source["archive"], "archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        metadata = json.loads(_member(archive, source["metadata"]))
        _member(archive, source["licenseFile"])
        _member(archive, source["bibliography"])
        if metadata["dc:conformsTo"] != "http://cldf.clld.org/v1.0/terms.rdf#Wordlist":
            raise ValueError("source is not the locked CLDF Wordlist")
        if metadata["dc:license"]["url"] != source["licenseUrl"]:
            raise ValueError("metadata license differs from lock")
        declared = {table["url"]: table for table in metadata["tables"]}
        if set(source["tables"]) != set(TABLES):
            raise ValueError("unexpected locked table")
        tables = {}
        for name in TABLES:
            descriptor = source["tables"][name]
            columns = [column["name"] for column in declared[name]["tableSchema"]["columns"]]
            if columns != descriptor["columns"]:
                raise ValueError("metadata columns differ from lock")
            tables[name] = _rows(_member(archive, descriptor), columns)
    selection = lock["selection"]
    try:
        concepts = [tables["concepts.csv"][identifier] for identifier in selection["conceptIds"]]
        selected = {
            "conceptlists.csv": [tables["conceptlists.csv"][selection["conceptlistId"]]],
            "concepts.csv": concepts,
            "concepticon.csv": [tables["concepticon.csv"][identifier]
                               for identifier in sorted({row["Concepticon_ID"] for row in concepts})],
        }
    except KeyError as error:
        raise ValueError(f"selected record is absent: {error}") from error
    payload = {
        "schemaVersion": SLICE_SCHEMA,
        "status": "research_only",
        "datasetId": source["datasetId"],
        "sourceVersion": source["version"],
        "sourceArchiveSha256": source["archive"]["sha256"],
        "selection": selection,
        "tables": selected,
    }
    validate_selection(payload, lock)
    return json_bytes(payload)


def verify_slice(slice_path: Path, lock: dict[str, Any]) -> dict[str, Any]:
    _validate_lock(lock)
    raw = _bounded_read(slice_path, MAX_MEMBER_BYTES)
    _locked_bytes(raw, lock["output"], "research output")
    payload = json.loads(raw)
    validate_selection(payload, lock)
    return payload


def resolve_reference(payload: dict[str, Any], dataset_id: str, table: str, record_id: str) -> dict[str, str]:
    """Resolve only included records; this confers no production capability."""
    if dataset_id != payload["datasetId"]:
        raise ValueError("dataset is outside this research slice")
    for row in payload["tables"].get(table, []):
        if row["ID"] == record_id:
            return dict(row)
    raise ValueError("table or record is outside this research slice")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_DIRECTORY / "lock.json")
    parser.add_argument("--slice", type=Path, default=DEFAULT_DIRECTORY / "slice.json")
    parser.add_argument("--archive", type=Path, help="also reproduce from the original local ZIP, offline")
    args = parser.parse_args()
    lock = json.loads(args.lock.read_bytes())
    payload = verify_slice(args.slice, lock)
    if args.archive and build_slice(args.archive, lock) != args.slice.read_bytes():
        raise ValueError("regenerated selection differs from checked-in output")
    print(f"Verified research selection: {len(payload['tables']['concepts.csv'])} source-list entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
