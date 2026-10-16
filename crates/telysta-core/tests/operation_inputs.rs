use serde_json::{json, Value};
use telysta_core::{
    execution_identity::{OperationId, RunId},
    hash::sha256_hex,
    operation::{
        validate_run_set, BaseHistory, OperationKind, OperationRequest, OperationSpec, RngLock,
        RootSeed, RunRole, RunSpec, MAX_SAFE_DRAW_BUDGET, OPERATION_INPUT_HASH_SCHEMA,
    },
};

fn cases() -> Vec<Value> {
    let fixture: Value = serde_json::from_str(include_str!(
        "../../../tests/fixtures/operation_input_known_answers_v1.json"
    ))
    .unwrap();
    fixture["cases"].as_array().unwrap().clone()
}

fn operation(case: &Value) -> OperationSpec {
    serde_json::from_str(&case["operation"].to_string()).unwrap()
}

fn run(parent: &OperationSpec, case: &Value) -> RunSpec {
    RunSpec::from_json(parent, &case["run"].to_string()).unwrap()
}

fn build(parent: &OperationSpec, id: &str, role: RunRole, key: &str) -> RunSpec {
    RunSpec::new(
        parent,
        RunId::new(id).unwrap(),
        role,
        key.to_owned(),
        "a".repeat(64),
        "telysta-fixture-result.v1".to_owned(),
    )
    .unwrap()
}

// Model an attacker able to recompute a checksum, so parent tests cannot pass
// merely by detecting a stale self hash. This is not an approval capability.
fn rehash(value: &mut Value, kind: &str, field: &str) {
    value.as_object_mut().unwrap().remove(field);
    value.sort_all_objects();
    let body = serde_json::to_vec(value).unwrap();
    let mut preimage = format!("{OPERATION_INPUT_HASH_SCHEMA}\0{kind}\0").into_bytes();
    preimage.extend_from_slice(&body);
    value[field] = json!(sha256_hex(&preimage));
}

#[test]
fn independent_known_bytes_and_hashes_round_trip() {
    for case in cases() {
        let parent = operation(&case);
        let restored = run(&parent, &case);
        let mut request = serde_json::to_value(parent.request()).unwrap();
        request.sort_all_objects();
        assert_eq!(
            serde_json::to_string(&request).unwrap(),
            case["canonicalRequest"]
        );
        let mut op = serde_json::to_value(&parent).unwrap();
        op.as_object_mut().unwrap().remove("operationSpecSha256");
        op.sort_all_objects();
        assert_eq!(
            serde_json::to_string(&op).unwrap(),
            case["canonicalOperationBody"]
        );
        let mut child = serde_json::to_value(&restored).unwrap();
        child.as_object_mut().unwrap().remove("runSpecSha256");
        child.sort_all_objects();
        assert_eq!(
            serde_json::to_string(&child).unwrap(),
            case["canonicalRunBody"]
        );
        assert_eq!(parent.sha256(), case["operation"]["operationSpecSha256"]);
        assert_eq!(restored.sha256(), case["run"]["runSpecSha256"]);
        assert_eq!(
            serde_json::from_slice::<OperationSpec>(&parent.canonical_json().unwrap()).unwrap(),
            parent
        );
        assert_eq!(
            RunSpec::from_json(
                &parent,
                std::str::from_utf8(&restored.canonical_json().unwrap()).unwrap()
            )
            .unwrap(),
            restored
        );
        let reference = parent.request().time.time_reference().unwrap();
        parent
            .request()
            .time
            .time_model()
            .unwrap()
            .validate_time_reference(&reference)
            .unwrap();
    }
}

#[test]
fn operation_identity_and_key_do_not_change_request_hash() {
    let case = &cases()[0];
    let parent = operation(case);
    let changed_id = OperationSpec::new(
        OperationId::new("other-operation").unwrap(),
        parent.idempotency_key().to_owned(),
        parent.request().clone(),
    )
    .unwrap();
    let changed_key = OperationSpec::new(
        parent.id().clone(),
        "other-key".to_owned(),
        parent.request().clone(),
    )
    .unwrap();
    for changed in [&changed_id, &changed_key] {
        assert_eq!(changed.request_sha256(), parent.request_sha256());
        assert_ne!(changed.sha256(), parent.sha256());
        assert!(run(&parent, case).validate_against(changed).is_err());
    }
}

#[test]
fn every_semantic_parent_lock_invalidates_an_old_run() {
    let case = &cases()[0];
    let parent = operation(case);
    let child = run(&parent, case);
    let changes = [
        ("/projectId", json!("telysta:project:other-project")),
        ("/kind", json!("import")),
        ("/targetHistory", json!("other-branch")),
        ("/baseHistory/historySha256", json!("1".repeat(64))),
        ("/commandSchema", json!("telysta-other-command.v1")),
        ("/commandPayloadSha256", json!("2".repeat(64))),
        ("/parameterSha256", json!("3".repeat(64))),
        ("/engineVersion", json!("other-engine")),
        ("/compilerVersion", json!("other-compiler")),
        ("/reducerVersion", json!("other-reducer")),
        (
            "/dependencyBundle/schemaVersion",
            json!("telysta-other-bundle.v1"),
        ),
        ("/dependencyBundle/contentSha256", json!("4".repeat(64))),
        ("/time/originYear", json!(-101)),
        ("/time/generationYears", json!(26)),
        ("/time/stepYears", json!(6)),
        ("/time/atYear", json!(43)),
        ("/rngLock/rootSeed", json!("9007199254740993")),
        ("/rngLock/pathRoot", json!("other.root")),
        (
            "/rngLock/distributionVersion",
            json!("telysta-rng-next-u64.v1"),
        ),
        ("/rngLock/streamBudgets/0/maxRawDraws", json!(1025)),
        ("/actorProvenance/kind", json!("system")),
        ("/actorProvenance/actorId", json!("another-actor")),
        ("/actorProvenance/source", json!("different declaration")),
    ];
    for (pointer, value) in changes {
        let mut request = serde_json::to_value(parent.request()).unwrap();
        *request.pointer_mut(pointer).unwrap() = value;
        let request: OperationRequest = serde_json::from_value(request).unwrap();
        let changed = OperationSpec::new(
            parent.id().clone(),
            parent.idempotency_key().to_owned(),
            request,
        )
        .unwrap();
        assert_ne!(
            changed.request_sha256(),
            parent.request_sha256(),
            "{pointer}"
        );
        assert!(child.validate_against(&changed).is_err(), "{pointer}");
    }
    let case = &cases()[1];
    let parent = operation(case);
    let child = run(&parent, case);
    let mut request = parent.request().clone();
    if let telysta_core::operation::AuthorIntervention::Recorded { report } =
        &mut request.author_intervention
    {
        report.content_sha256 = "b".repeat(64);
    }
    let changed = OperationSpec::new(
        parent.id().clone(),
        parent.idempotency_key().to_owned(),
        request,
    )
    .unwrap();
    assert!(child.validate_against(&changed).is_err());
}

#[test]
fn recomputed_child_checksums_cannot_override_parent_locks() {
    let case = &cases()[0];
    let parent = operation(case);
    for (pointer, value) in [
        ("/operationId", json!("telysta:operation:foreign-parent")),
        ("/operationSpecSha256", json!("0".repeat(64))),
        ("/parameterSha256", json!("0".repeat(64))),
        ("/rngLock/rootSeed", json!("0")),
        ("/rngLock/pathRoot", json!("unrelated.stream")),
        (
            "/rngLock/distributionVersion",
            json!("telysta-rng-next-u64.v1"),
        ),
        ("/rngLock/streamBudgets/0/maxRawDraws", json!(1025)),
    ] {
        let mut candidate = case["run"].clone();
        *candidate.pointer_mut(pointer).unwrap() = value;
        rehash(&mut candidate, "run", "runSpecSha256");
        assert!(
            RunSpec::from_json(&parent, &candidate.to_string()).is_err(),
            "{pointer}"
        );
    }
}

#[test]
fn roots_and_authoring_reports_have_explicit_boundaries() {
    let parent = operation(&cases()[0]);
    for kind in [
        OperationKind::Genesis,
        OperationKind::Authoring,
        OperationKind::Simulation,
        OperationKind::Migration,
        OperationKind::Retcon,
        OperationKind::Import,
    ] {
        for empty in [true, false] {
            let mut request = parent.request().clone();
            request.kind = kind;
            request.author_intervention =
                operation(&cases()[1]).request().author_intervention.clone();
            request.base_history = if empty {
                BaseHistory::Empty {}
            } else {
                BaseHistory::Existing {
                    history_sha256: "0".repeat(64),
                }
            };
            let expected = match kind {
                OperationKind::Genesis => empty,
                OperationKind::Import => true,
                _ => !empty,
            };
            assert_eq!(
                OperationSpec::new(parent.id().clone(), "key".to_owned(), request).is_ok(),
                expected
            );
        }
    }
    for kind in [OperationKind::Authoring, OperationKind::Retcon] {
        let mut request = parent.request().clone();
        request.kind = kind;
        assert_eq!(
            OperationSpec::new(parent.id().clone(), "key".to_owned(), request)
                .unwrap_err()
                .code,
            "missing_author_intervention"
        );
    }
}

#[test]
fn strict_seed_wire_and_budget_edges() {
    for seed in [0, 1, 9007199254740993, u64::MAX] {
        let value = RootSeed::new(seed);
        let raw = serde_json::to_string(&value).unwrap();
        assert_eq!(raw, format!("\"{seed}\""));
        assert_eq!(serde_json::from_str::<RootSeed>(&raw).unwrap().get(), seed);
    }
    for raw in [
        "0",
        "18446744073709551615",
        "null",
        "true",
        "\"+1\"",
        "\"01\"",
        "\"-0\"",
        "\" 1\"",
        "\"1e2\"",
        "\"1.0\"",
        "\"１\"",
        "\"18446744073709551616\"",
    ] {
        assert!(serde_json::from_str::<RootSeed>(raw).is_err(), "{raw}");
    }
    let parent = operation(&cases()[0]);
    for budget in [0, MAX_SAFE_DRAW_BUDGET, MAX_SAFE_DRAW_BUDGET + 1] {
        let mut request = parent.request().clone();
        if let RngLock::RngTree { stream_budgets, .. } = &mut request.rng_lock {
            stream_budgets[0].max_raw_draws = budget;
        }
        assert_eq!(
            OperationSpec::new(parent.id().clone(), "key".to_owned(), request).is_ok(),
            budget <= MAX_SAFE_DRAW_BUDGET
        );
    }
    for token in ["1024.0", "1024.0000000000000001", "true", "-1"] {
        let raw = cases()[0]["operation"]
            .to_string()
            .replace("\"maxRawDraws\":1024", &format!("\"maxRawDraws\":{token}"));
        assert!(
            serde_json::from_str::<OperationSpec>(&raw).is_err(),
            "{token}"
        );
    }
}

#[test]
fn closed_objects_reject_unknown_missing_and_duplicate_fields() {
    for case in cases() {
        for pointer in [
            "",
            "/request",
            "/request/baseHistory",
            "/request/dependencyBundle",
            "/request/time",
            "/request/rngLock",
            "/request/actorProvenance",
            "/request/authorIntervention",
        ] {
            let mut value = case["operation"].clone();
            value
                .pointer_mut(pointer)
                .unwrap()
                .as_object_mut()
                .unwrap()
                .insert("unexpected".to_owned(), json!(true));
            assert!(
                serde_json::from_str::<OperationSpec>(&value.to_string()).is_err(),
                "unknown {pointer}"
            );
        }
        for pointer in ["", "/request", "/request/time", "/request/actorProvenance"] {
            let object = case["operation"]
                .pointer(pointer)
                .unwrap()
                .as_object()
                .unwrap();
            for key in object.keys() {
                let mut value = case["operation"].clone();
                value
                    .pointer_mut(pointer)
                    .unwrap()
                    .as_object_mut()
                    .unwrap()
                    .remove(key);
                assert!(
                    serde_json::from_str::<OperationSpec>(&value.to_string()).is_err(),
                    "missing {pointer}/{key}"
                );
            }
        }
        let raw = case["operation"].to_string();
        for token in [
            "\"schemaVersion\":\"telysta-operation-spec.v2\"",
            "\"targetHistory\":\"main\"",
            "\"kind\":\"user\"",
        ] {
            let changed = raw.replacen(token, &format!("{token},{token}"), 1);
            assert_ne!(raw, changed);
            assert!(
                serde_json::from_str::<OperationSpec>(&changed).is_err(),
                "duplicate {token}"
            );
        }
        let token = if case["name"] == "no-rng" {
            "\"kind\":\"no_rng\""
        } else {
            "\"kind\":\"rng_tree\""
        };
        assert!(serde_json::from_str::<OperationSpec>(&raw.replacen(
            token,
            &format!("{token},{token}"),
            1
        ))
        .is_err());
        let parent = operation(&case);
        let mut child = case["run"].clone();
        child["unexpected"] = json!(true);
        assert!(RunSpec::from_json(&parent, &child.to_string()).is_err());
        for key in case["run"].as_object().unwrap().keys() {
            let mut child = case["run"].clone();
            child.as_object_mut().unwrap().remove(key);
            assert!(
                RunSpec::from_json(&parent, &child.to_string()).is_err(),
                "missing Run/{key}"
            );
        }
    }
}

#[test]
fn schema_time_path_hash_and_untrusted_shape_failures_are_rejected() {
    let case = &cases()[0];
    let parent = operation(case);
    for (pointer, value) in [
        ("/schemaVersion", json!("telysta-operation-request.v999")),
        ("/identitySchema", json!("telysta-entity-id.v1")),
        ("/projectId", json!("telysta:run:wrong-kind")),
        ("/targetHistory", json!(" \n")),
        ("/commandSchema", json!("latest")),
        ("/commandPayloadSha256", json!("G".repeat(64))),
        ("/parameterSha256", json!("0".repeat(63))),
        ("/engineVersion", json!("")),
        ("/dependencyBundle/contentSha256", json!("unavailable")),
        ("/time/schemaVersion", json!("telysta-time-model.v1")),
        ("/time/generationYears", json!(0)),
        ("/time/stepYears", json!(0)),
        ("/rngLock/schemaVersion", json!("telysta-rng-tree.v999")),
        ("/rngLock/distributionVersion", json!("unknown")),
        ("/rngLock/pathRoot", json!("invalid..path")),
        ("/rngLock/streamBudgets", json!([])),
        ("/actorProvenance/source", json!("")),
    ] {
        let mut request = case["operation"]["request"].clone();
        *request.pointer_mut(pointer).unwrap() = value;
        let result = serde_json::from_value::<OperationRequest>(request)
            .ok()
            .and_then(|request| {
                OperationSpec::new(parent.id().clone(), "key".to_owned(), request).ok()
            });
        assert!(result.is_none(), "{pointer}");
    }
    let mut duplicate = parent.request().clone();
    if let RngLock::RngTree { stream_budgets, .. } = &mut duplicate.rng_lock {
        stream_budgets.push(stream_budgets[0].clone());
    }
    assert!(OperationSpec::new(parent.id().clone(), "key".to_owned(), duplicate).is_err());
    for key in ["", " ", "two.parts", "Upper", &"a".repeat(65)] {
        assert!(
            RunSpec::new(
                &parent,
                RunId::new("run").unwrap(),
                RunRole::Single,
                key.to_owned(),
                "a".repeat(64),
                "telysta-result.v1".to_owned()
            )
            .is_err(),
            "{key:?}"
        );
    }
    for field in ["schemaVersion", "requestSha256", "operationSpecSha256"] {
        let mut value = case["operation"].clone();
        value[field] = json!("0".repeat(64));
        assert!(serde_json::from_str::<OperationSpec>(&value.to_string()).is_err());
    }
    let mut stale_request = case["operation"].clone();
    stale_request["request"]["targetHistory"] = json!("changed");
    rehash(&mut stale_request, "operation", "operationSpecSha256");
    assert!(serde_json::from_str::<OperationSpec>(&stale_request.to_string()).is_err());
}

#[test]
fn no_rng_and_run_batch_uniqueness_are_explicit() {
    let parent = operation(&cases()[1]);
    let first = build(&parent, "first", RunRole::Candidate, "a");
    assert_eq!(first.rng_lock(), &RngLock::NoRng {});
    assert!(validate_run_set(&parent, &[]).is_ok());
    assert!(validate_run_set(
        &parent,
        &[
            first.clone(),
            build(&parent, "second", RunRole::Candidate, "b")
        ]
    )
    .is_ok());
    assert!(validate_run_set(
        &parent,
        &[
            first.clone(),
            build(&parent, "first", RunRole::Candidate, "b")
        ]
    )
    .is_err());
    assert!(validate_run_set(
        &parent,
        &[
            first.clone(),
            build(&parent, "second", RunRole::Candidate, "a")
        ]
    )
    .is_err());
    assert!(validate_run_set(
        &parent,
        &[first, build(&parent, "third", RunRole::Replicate, "a")]
    )
    .is_ok());
    let foreign = operation(&cases()[0]);
    assert!(
        validate_run_set(&parent, &[build(&foreign, "foreign", RunRole::Single, "a")]).is_err()
    );
}

#[test]
fn no_implicit_planning_or_legacy_spec_migration() {
    let planning: Value = serde_json::from_str(include_str!(
        "../../../tests/fixtures/adr_011_schema_records_v1.json"
    ))
    .unwrap();
    for old in planning["operationSpecs"].as_array().unwrap() {
        assert!(serde_json::from_str::<OperationSpec>(&old.to_string()).is_err());
    }
    let parent = operation(&cases()[0]);
    for old in planning["runSpecs"].as_array().unwrap() {
        assert!(RunSpec::from_json(&parent, &old.to_string()).is_err());
    }
}
