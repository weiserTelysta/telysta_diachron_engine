//! Cross-check the planning-only ADR-011 records against Rust's accepted
//! EntityId local-value grammar and RngPath parser.
//!
//! This does not add Operation/Job/Attempt to the production EntityKind enum
//! and does not authorize an ADR-011 writer.

use serde_json::Value;
use telysta_core::{
    identity::{EntityId, EntityKind},
    rng::RngPath,
};

const RECORDS: &str = include_str!("../../../tests/fixtures/adr_011_schema_records_v1.json");

fn array<'a>(bundle: &'a Value, key: &str) -> &'a [Value] {
    bundle[key]
        .as_array()
        .unwrap_or_else(|| panic!("{key} array"))
}

fn field<'a>(record: &'a Value, key: &str) -> &'a str {
    record[key]
        .as_str()
        .unwrap_or_else(|| panic!("{key} string"))
}

fn assert_planning_seed(rng_lock: &Value) {
    let text = field(rng_lock, "rootSeed");
    let seed = text.parse::<u64>().expect("planning seed fits u64");
    assert_eq!(seed.to_string(), text, "canonical unsigned decimal");
}

fn assert_proposed_id_uses_entity_local_grammar(value: &str, kind: &str) {
    let prefix = format!("telysta:{kind}:");
    let local = value
        .strip_prefix(&prefix)
        .unwrap_or_else(|| panic!("{value:?} must use the {kind} prefix"));
    EntityId::new(EntityKind::Event, local)
        .unwrap_or_else(|error| panic!("{value:?} violates EntityId local grammar: {error}"));
}

#[test]
fn planning_records_reuse_accepted_entity_and_rng_value_grammars() {
    let bundle: Value = serde_json::from_str(RECORDS).expect("ADR-011 record fixture is JSON");

    for manifest in array(&bundle, "projectManifests") {
        let id = EntityId::parse(field(manifest, "projectId")).expect("accepted ProjectId");
        assert_eq!(id.kind(), EntityKind::Project);
    }

    for operation in array(&bundle, "operationSpecs") {
        let project = EntityId::parse(field(operation, "projectId")).expect("accepted ProjectId");
        assert_eq!(project.kind(), EntityKind::Project);
        assert_proposed_id_uses_entity_local_grammar(field(operation, "operationId"), "operation");

        let rng_lock = &operation["rngLock"];
        if rng_lock["kind"] == "rng_tree" {
            RngPath::parse(field(rng_lock, "pathRoot")).expect("accepted RngPath");
            assert_planning_seed(rng_lock);
        }
    }

    for run in array(&bundle, "runSpecs") {
        let id = EntityId::parse(field(run, "runId")).expect("accepted RunId");
        assert_eq!(id.kind(), EntityKind::Run);
        assert_proposed_id_uses_entity_local_grammar(field(run, "operationId"), "operation");
        let rng_lock = &run["rngLock"];
        RngPath::parse(field(rng_lock, "pathRoot")).expect("accepted RngPath");
        assert_planning_seed(rng_lock);
    }

    for job in array(&bundle, "jobRecords") {
        assert_proposed_id_uses_entity_local_grammar(field(job, "jobId"), "job");
        let project = EntityId::parse(field(job, "projectId")).expect("accepted ProjectId");
        assert_eq!(project.kind(), EntityKind::Project);
        let run = EntityId::parse(field(job, "runId")).expect("accepted RunId");
        assert_eq!(run.kind(), EntityKind::Run);
    }

    for attempt in array(&bundle, "attemptRecords") {
        assert_proposed_id_uses_entity_local_grammar(field(attempt, "attemptId"), "attempt");
        assert_proposed_id_uses_entity_local_grammar(field(attempt, "jobId"), "job");
    }
}
