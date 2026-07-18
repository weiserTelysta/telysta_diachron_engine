use serde::Deserialize;
use telysta_core::rng::{RngPath, RngTree, RNG_TREE_SCHEMA};

const FIXTURE: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../tests/fixtures/rng_known_answers_v1.json"
));

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct KnownAnswers {
    schema_version: String,
    rng_tree_schema: String,
    next_u64_distribution: String,
    uniform_u64_distribution: String,
    next_vectors: Vec<NextVector>,
    uniform_vectors: Vec<UniformVector>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NextVector {
    root_seed: u64,
    path: String,
    outputs: Vec<u64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UniformVector {
    root_seed: u64,
    path: String,
    upper_exclusive: u64,
    outputs: Vec<u64>,
}

fn fixture() -> KnownAnswers {
    serde_json::from_str(FIXTURE).expect("RNG known-answer fixture must remain valid")
}

#[test]
fn next_u64_matches_frozen_known_answers() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, "telysta-rng-known-answers.v1");
    assert_eq!(fixture.rng_tree_schema, RNG_TREE_SCHEMA);
    assert_eq!(fixture.next_u64_distribution, "telysta-rng-next-u64.v1");

    for vector in fixture.next_vectors {
        let path = RngPath::parse(&vector.path).expect("known-answer path");
        let mut stream = RngTree::new(vector.root_seed).stream(&path);
        let actual = (0..vector.outputs.len())
            .map(|_| stream.next_u64())
            .collect::<Vec<_>>();
        assert_eq!(actual, vector.outputs, "seed/path vector changed");
    }
}

#[test]
fn uniform_matches_frozen_rejection_sampling_answers() {
    let fixture = fixture();
    assert_eq!(
        fixture.uniform_u64_distribution,
        "telysta-rng-uniform-u64.v1"
    );

    for vector in fixture.uniform_vectors {
        let path = RngPath::parse(&vector.path).expect("known-answer path");
        let mut stream = RngTree::new(vector.root_seed).stream(&path);
        let actual = (0..vector.outputs.len())
            .map(|_| {
                stream
                    .uniform(vector.upper_exclusive)
                    .expect("known-answer upper bound")
            })
            .collect::<Vec<_>>();
        assert_eq!(actual, vector.outputs, "bounded distribution changed");
    }
}
