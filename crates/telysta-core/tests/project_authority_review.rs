//! Independent byte cross-check for ADR-012 mutable review vectors only.
//!
//! No production module imports this code. It does not parse hostile input,
//! validate a project schema/object graph, or implement a package writer.

use serde_json::Value;
use sha2::{Digest, Sha256};

const VECTORS: &str = include_str!("../../../tests/fixtures/project_authority_hash_review_v1.json");
const DOMAIN: &[u8] = b"telysta-project-authority-hash-draft.v1\0";

fn restricted_canonical(value: &Value, output: &mut String) {
    match value {
        Value::Object(object) => {
            let mut keys: Vec<&String> = object.keys().collect();
            keys.sort_by(|left, right| left.encode_utf16().cmp(right.encode_utf16()));
            output.push('{');
            for (index, key) in keys.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                output.push_str(&serde_json::to_string(key).expect("scalar string"));
                output.push(':');
                restricted_canonical(&object[*key], output);
            }
            output.push('}');
        }
        Value::String(_) | Value::Null => {
            output.push_str(&serde_json::to_string(value).expect("scalar string/null"));
        }
        _ => panic!("review profile permits only objects, strings and null"),
    }
}

#[test]
fn mutable_authority_review_vectors_match_independent_rust_bytes_and_sha256() {
    let bundle: Value = serde_json::from_str(VECTORS).expect("review fixture JSON");
    assert_eq!(bundle["status"], "mutable_review_not_production_evidence");
    let vectors = bundle["vectors"].as_array().expect("vector array");
    assert_eq!(vectors.len(), 2);
    for vector in vectors {
        let raw = vector["rawManifestJson"].as_str().expect("raw JSON");
        let mut manifest: Value = serde_json::from_str(raw).expect("review manifest JSON");
        let object = manifest.as_object_mut().expect("manifest object");
        let recorded = object.remove("projectAuthorityHash").expect("self field");
        assert_eq!(recorded, vector["sha256"]);
        let mut canonical = String::new();
        restricted_canonical(&manifest, &mut canonical);
        assert_eq!(canonical, vector["canonicalJson"].as_str().unwrap());
        let mut digest = Sha256::new();
        digest.update(DOMAIN);
        digest.update(canonical.as_bytes());
        assert_eq!(
            format!("{:x}", digest.finalize()),
            recorded.as_str().unwrap()
        );
        for input in vector["hashInputs"].as_array().expect("fake inputs") {
            let raw_input = input["rawUtf8"].as_str().expect("fake preimage");
            assert_eq!(
                format!("{:x}", Sha256::digest(raw_input.as_bytes())),
                input["sha256"].as_str().unwrap()
            );
        }
    }
}
