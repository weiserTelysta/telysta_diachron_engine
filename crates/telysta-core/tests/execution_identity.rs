//! Production wrapper checks, not validation of the planning record schema.

use std::{collections::BTreeMap, fmt::Debug, str::FromStr};

use serde::{de::DeserializeOwned, Serialize};
use serde_json::Value;
use telysta_core::{
    execution_identity::{AttemptId, ExecutionIdError, JobId, OperationId, ProjectId, RunId},
    identity::{EntityId, EntityKind},
};

fn assert_contract<T>(kind: &str, new: impl Fn(&str) -> Result<T, ExecutionIdError>)
where
    T: Debug + Eq + Serialize + DeserializeOwned + FromStr<Err = ExecutionIdError>,
{
    for length in 1..=96 {
        let local = "a".repeat(length);
        let value = new(&local).unwrap();
        let raw = format!("telysta:{kind}:{local}");
        assert_eq!(raw.parse::<T>().unwrap(), value);
        assert_eq!(serde_json::to_string(&value).unwrap(), format!("\"{raw}\""));
        assert_eq!(
            serde_json::from_str::<T>(&format!("\"{raw}\"")).unwrap(),
            value
        );
    }

    for byte in 0..=u8::MAX {
        let local = char::from(byte).to_string();
        assert_eq!(
            new(&local).is_ok(),
            byte.is_ascii_lowercase() || byte.is_ascii_digit(),
            "single-byte local value {local:?}"
        );
    }

    for local in [
        "", "-a", "a-", "A", "a_b", "a.b", "a:b", "a/b", "a\\b", "a b", "a\n", "é", "水",
    ] {
        assert!(new(local).is_err(), "{local:?}");
        let raw = serde_json::to_string(&format!("telysta:{kind}:{local}")).unwrap();
        assert!(serde_json::from_str::<T>(&raw).is_err(), "{raw}");
    }
    assert!(new(&"a".repeat(97)).is_err());
    assert!(new("a--0").is_ok()); // Same accepted grammar as EntityId v1.

    for other in [
        "project",
        "operation",
        "run",
        "job",
        "attempt",
        "language",
        "unknown",
    ] {
        let raw = format!("telysta:{other}:same-local");
        assert_eq!(raw.parse::<T>().is_ok(), other == kind);
        assert_eq!(
            serde_json::from_str::<T>(&format!("\"{raw}\"")).is_ok(),
            other == kind
        );
    }
    for malformed in ["same-local", "Telysta:project:a", "telysta:project:a:extra"] {
        assert!(malformed.parse::<T>().is_err());
    }
    for raw in [
        "null",
        "0",
        "true",
        "[]",
        "{}",
        "{\"id\":\"telysta:project:a\"}",
    ] {
        assert!(serde_json::from_str::<T>(raw).is_err());
    }
}

#[test]
fn project_id_contract() {
    assert_contract("project", |value| ProjectId::new(value));
}

#[test]
fn operation_id_contract() {
    assert_contract("operation", |value| OperationId::new(value));
}

#[test]
fn run_id_contract() {
    assert_contract("run", |value| RunId::new(value));
}

#[test]
fn job_id_contract() {
    assert_contract("job", |value| JobId::new(value));
}

#[test]
fn attempt_id_contract() {
    assert_contract("attempt", |value| AttemptId::new(value));
}

#[test]
fn legacy_conversion_preserves_bytes_and_checks_the_kind() {
    let project = EntityId::new(EntityKind::Project, "legacy-project").unwrap();
    let run = EntityId::new(EntityKind::Run, "legacy-run").unwrap();
    assert_eq!(
        ProjectId::try_from(&project).unwrap().as_str(),
        project.as_str()
    );
    assert_eq!(RunId::try_from(&run).unwrap().as_str(), run.as_str());
    assert!(ProjectId::try_from(&run).is_err());
    assert!(RunId::try_from(&project).is_err());
    let language = EntityId::new(EntityKind::Language, "legacy-language").unwrap();
    assert!(ProjectId::try_from(&language).is_err());
    assert!(RunId::try_from(&language).is_err());

    for raw in [
        OperationId::new("request").unwrap().to_string(),
        JobId::new("scheduled").unwrap().to_string(),
        AttemptId::new("initial").unwrap().to_string(),
    ] {
        assert!(EntityId::parse(&raw).is_err());
        assert!(serde_json::from_str::<EntityId>(&format!("\"{raw}\"")).is_err());
    }
}

#[test]
fn wrappers_accept_existing_planning_id_bytes_without_accepting_the_records() {
    let bundle: Value = serde_json::from_str(include_str!(
        "../../../tests/fixtures/adr_011_schema_records_v1.json"
    ))
    .unwrap();
    for operation in bundle["operationSpecs"].as_array().unwrap() {
        assert!(serde_json::from_value::<ProjectId>(operation["projectId"].clone()).is_ok());
        assert!(serde_json::from_value::<OperationId>(operation["operationId"].clone()).is_ok());
    }
    for run in bundle["runSpecs"].as_array().unwrap() {
        assert!(serde_json::from_value::<RunId>(run["runId"].clone()).is_ok());
        assert!(serde_json::from_value::<OperationId>(run["operationId"].clone()).is_ok());
    }
    for job in bundle["jobRecords"].as_array().unwrap() {
        assert!(serde_json::from_value::<ProjectId>(job["projectId"].clone()).is_ok());
        assert!(serde_json::from_value::<JobId>(job["jobId"].clone()).is_ok());
        assert!(serde_json::from_value::<RunId>(job["runId"].clone()).is_ok());
    }
    for attempt in bundle["attemptRecords"].as_array().unwrap() {
        assert!(serde_json::from_value::<AttemptId>(attempt["attemptId"].clone()).is_ok());
        assert!(serde_json::from_value::<JobId>(attempt["jobId"].clone()).is_ok());
    }
}

#[test]
fn typed_map_keys_have_stable_order_and_round_trip() {
    let ids = BTreeMap::from([
        (OperationId::new("b").unwrap(), 2),
        (OperationId::new("a").unwrap(), 1),
    ]);
    let raw = serde_json::to_string(&ids).unwrap();
    assert_eq!(raw, r#"{"telysta:operation:a":1,"telysta:operation:b":2}"#);
    assert_eq!(
        serde_json::from_str::<BTreeMap<OperationId, i32>>(&raw).unwrap(),
        ids
    );
    assert!(serde_json::from_str::<BTreeMap<OperationId, i32>>(r#"{"telysta:job:a":1}"#).is_err());
}
