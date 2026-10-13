"""Research data membership and reproducibility, independent of network access."""

from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path
import zipfile

import pytest

from scripts import concepticon_slice as subject


def descriptor(raw: bytes, **extra: object) -> dict:
    return {"sizeBytes": len(raw), "sha256": subject.sha256(raw), **extra}


def fixture_archive(tmp_path: Path, mutation: str = "") -> tuple[Path, dict]:
    tables = {
        "conceptlists.csv": [{"ID": "list-a", "Source": "source-a"}],
        "concepts.csv": [{"ID": "entry-a", "Name": "see,\nperceive e\u0301", "Conceptlist_ID": "list-a", "Concepticon_ID": "1"}],
        "concepticon.csv": [{"ID": "1", "Name": "SEE", "Description": "visual perception", "Replacement_ID": ""}],
    }
    if mutation == "lineage":
        tables["concepts.csv"][0]["Conceptlist_ID"] = "other-list"
    elif mutation == "mapping":
        tables["concepts.csv"][0]["Concepticon_ID"] = "missing"
    elif mutation == "duplicate-id":
        tables["concepts.csv"].append(dict(tables["concepts.csv"][0]))
    elif mutation == "superseded":
        tables["concepticon.csv"][0]["Replacement_ID"] = "2"
    elif mutation == "unmapped-placeholder":
        tables["concepts.csv"][0]["Concepticon_ID"] = "0"
        tables["concepticon.csv"][0].update(ID="0", Name="<NA>")
    metadata = {
        "dc:conformsTo": "http://cldf.clld.org/v1.0/terms.rdf#Wordlist",
        "dc:license": {"url": "https://creativecommons.org/licenses/by/4.0/"},
        "tables": [{"url": name, "tableSchema": {"columns": [{"name": key} for key in rows[0]]}}
                   for name, rows in tables.items()],
    }
    members = {"cldf/Wordlist-metadata.json": subject.json_bytes(metadata), "LICENSE": b"CC-BY-4.0",
               "cldf/sources.bib": b"@article{source-a, title={Fixture}}"}
    locked_tables = {}
    for name, rows in tables.items():
        columns = list(rows[0])
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        members["cldf/" + name] = text.getvalue().encode()
        locked_tables[name] = descriptor(members["cldf/" + name], member="cldf/" + name, columns=columns)
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
        if mutation == "duplicate-member":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("cldf/concepts.csv", members["cldf/concepts.csv"])
    lock = {
        "schemaVersion": subject.LOCK_SCHEMA, "status": "research_only",
        "source": {
            "datasetId": "fixture:dataset", "version": "fixture-v1", "archive": descriptor(path.read_bytes()),
            "metadata": descriptor(members["cldf/Wordlist-metadata.json"], member="cldf/Wordlist-metadata.json"),
            "licenseFile": descriptor(members["LICENSE"], member="LICENSE"),
            "bibliography": descriptor(members["cldf/sources.bib"], member="cldf/sources.bib"),
            "licenseUrl": metadata["dc:license"]["url"], "tables": locked_tables,
        },
        "selection": {"conceptlistId": "list-a", "conceptIds": ["entry-a"]},
        "transform": {"schemaVersion": subject.TRANSFORM, "scriptSha256": subject.sha256(Path(subject.__file__).read_bytes())},
    }
    return path, lock


def test_offline_reproduction_preserves_raw_unicode_and_mapping(tmp_path: Path) -> None:
    archive, lock = fixture_archive(tmp_path)
    raw = subject.build_slice(archive, lock)
    assert subject.build_slice(archive, lock) == raw
    lock["output"] = descriptor(raw)
    output = tmp_path / "slice.json"
    output.write_bytes(raw)
    payload = subject.verify_slice(output, lock)
    row = subject.resolve_reference(payload, "fixture:dataset", "concepts.csv", "entry-a")
    assert row["Name"] == "see,\nperceive e\u0301"
    assert row["Concepticon_ID"] == "1"
    row["Name"] = "changed copy"
    assert payload["tables"]["concepts.csv"][0]["Name"].endswith("e\u0301")


@pytest.mark.parametrize("mutation", ["lineage", "mapping", "duplicate-id", "superseded", "duplicate-member", "unmapped-placeholder"])
def test_even_rehashed_source_rejects_bad_selection(tmp_path: Path, mutation: str) -> None:
    archive, lock = fixture_archive(tmp_path, mutation)
    with pytest.raises(ValueError):
        subject.build_slice(archive, lock)


@pytest.mark.parametrize("part", ["archive", "metadata", "licenseFile", "bibliography", "table", "transform"])
def test_source_and_transform_locks_are_enforced(tmp_path: Path, part: str) -> None:
    archive, lock = fixture_archive(tmp_path)
    if part == "transform":
        lock[part]["scriptSha256"] = "0" * 64
    elif part == "table":
        lock["source"]["tables"]["concepts.csv"]["sha256"] = "0" * 64
    else:
        lock["source"][part]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        subject.build_slice(archive, lock)


def test_output_integrity_does_not_replace_membership_validation(tmp_path: Path) -> None:
    archive, lock = fixture_archive(tmp_path)
    raw = subject.build_slice(archive, lock)
    payload = json.loads(raw)
    payload["tables"]["concepts.csv"][0]["Concepticon_ID"] = "absent"
    raw = subject.json_bytes(payload)
    lock["output"] = descriptor(raw)
    output = tmp_path / "slice.json"
    output.write_bytes(raw)
    with pytest.raises(ValueError, match="mapping closure"):
        subject.verify_slice(output, lock)


def test_checked_in_real_selection_and_out_of_slice_references() -> None:
    lock = json.loads((subject.DEFAULT_DIRECTORY / "lock.json").read_bytes())
    payload = subject.verify_slice(subject.DEFAULT_DIRECTORY / "slice.json", lock)
    assert len(payload["tables"]["concepts.csv"]) == 12
    assert payload["tables"]["conceptlists.csv"][0]["Source"] == "Swadesh1955"
    first = payload["tables"]["concepts.csv"][0]
    assert subject.resolve_reference(payload, payload["datasetId"], "concepts.csv", first["ID"]) == first
    for dataset, table, record in [
        ("foreign", "concepts.csv", first["ID"]),
        (payload["datasetId"], "glosses.csv", first["ID"]),
        (payload["datasetId"], "concepts.csv", "not-selected"),
    ]:
        with pytest.raises(ValueError):
            subject.resolve_reference(payload, dataset, table, record)
    altered = copy.deepcopy(lock)
    altered["selection"]["conceptIds"].append("absent")
    with pytest.raises(ValueError):
        subject.validate_selection(payload, altered)
