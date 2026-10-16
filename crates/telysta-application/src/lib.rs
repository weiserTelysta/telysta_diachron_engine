//! Client-facing use cases over the existing, validated v1 project runtime.
//!
//! This first slice exposes sessions and Blueprint inspection. It neither
//! creates language states nor exposes the storage runtime's mutation methods.
//! Opening/refreshing can still recover a file or rebuild its derived index.

use std::path::Path;

use telysta_core::{
    blueprint::{BlueprintError, BlueprintValidationReport, FeatureRegistry, LanguageBlueprint},
    identity::EntityId,
    CommandResponse,
};
use telysta_storage::ProjectRuntime;

// Reuse the existing versioned read model and errors; no second client schema.
pub use telysta_storage::{ProjectRuntimeError, ProjectSession};

/// Owns session coordination without giving clients access to storage writers.
///
/// ```compile_fail
/// use telysta_application::ProjectApplication;
/// let _runtime = ProjectApplication::default().runtime;
/// ```
///
/// ```compile_fail
/// use telysta_application::ProjectApplication;
/// let _commit = ProjectApplication::commit_history;
/// ```
#[derive(Default)]
pub struct ProjectApplication {
    runtime: ProjectRuntime,
}

impl ProjectApplication {
    pub fn open_project(
        &mut self,
        root: impl AsRef<Path>,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.runtime.open_existing(root)
    }

    pub fn get_project_session(
        &self,
        project_id: &EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.runtime.session(project_id)
    }

    pub fn refresh_project(
        &mut self,
        project_id: &EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.runtime.refresh(project_id)
    }

    pub fn close_project(
        &mut self,
        project_id: &EntityId,
    ) -> Result<ProjectSession, ProjectRuntimeError> {
        self.runtime.close(project_id)
    }
}

/// Inspect existing v2 input; this does not compile or create a language.
/// Raw JSON retains numeric tokens and duplicate fields until Rust parses it.
pub fn inspect_blueprint(
    blueprint: Option<LanguageBlueprint>,
    blueprint_json: Option<String>,
) -> Result<CommandResponse<BlueprintValidationReport>, BlueprintError> {
    parse_blueprint_input(blueprint, blueprint_json)?
        .validation_report(&FeatureRegistry::builtin_phonology_v1())
        .map(|report| CommandResponse::new("validate_blueprint", report))
}

fn parse_blueprint_input(
    blueprint: Option<LanguageBlueprint>,
    blueprint_json: Option<String>,
) -> Result<LanguageBlueprint, BlueprintError> {
    match (blueprint, blueprint_json) {
        (Some(blueprint), None) => Ok(blueprint),
        (None, Some(raw)) => serde_json::from_str(&raw).map_err(|error| BlueprintError {
            code: "invalid_blueprint_json".to_owned(),
            path: Some("blueprintJson".to_owned()),
            message: error.to_string(),
        }),
        _ => Err(BlueprintError {
            code: "invalid_blueprint_input".to_owned(),
            path: None,
            message: "provide exactly one of blueprint or blueprintJson".to_owned(),
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn command_blueprint() -> LanguageBlueprint {
        serde_json::from_value(serde_json::json!({
            "schemaVersion": "telysta-language-blueprint.v2",
            "blueprintId": "telysta:blueprint:desktop-command-test",
            "displayName": "Desktop command test",
            "historyScope": {
                "originYear": 0,
                "horizonYears": 1200,
                "branching": "allowed",
                "contact": "allowed"
            },
            "generationPolicy": {
                "candidateCount": 4,
                "selection": "pareto_frontier"
            },
            "evidence": {
                "telysta:evidence:desktop-preference": {
                    "id": "telysta:evidence:desktop-preference",
                    "class": "creativePreference",
                    "note": "Desktop integration test preference.",
                    "citation": null,
                    "dataReferences": []
                }
            },
            "intents": {
                "telysta:intent:desktop-inventory": {
                    "id": "telysta:intent:desktop-inventory",
                    "featureId": "telysta:feature:consonant-inventory-size",
                    "desiredValue": {
                        "kind": "integer_range",
                        "minimum": 18,
                        "maximum": 28
                    },
                    "control": {
                        "kind": "preferred",
                        "strengthBasisPoints": 6500
                    },
                    "priorityBasisPoints": 6500,
                    "evidenceIds": ["telysta:evidence:desktop-preference"],
                    "explanation": "Prefer a medium consonant inventory."
                }
            }
        }))
        .expect("valid v2 blueprint")
    }

    #[test]
    fn blueprint_command_uses_the_built_in_registry_and_reports_capability() {
        let response =
            inspect_blueprint(Some(command_blueprint()), None).expect("validation response");
        assert_eq!(response.command, "validate_blueprint");
        assert_eq!(
            response.data.feature_registry_version,
            telysta_core::blueprint::BUILTIN_PHONOLOGY_REGISTRY_VERSION
        );
        assert!(!response.data.ready_for_compilation);
        assert!(response.data.diagnostics.iter().any(|diagnostic| {
            diagnostic.code == telysta_core::blueprint::BlueprintDiagnosticCode::CompilerUnavailable
        }));
    }

    #[test]
    fn raw_blueprint_preserves_i64_values_and_legacy_reports() {
        let blueprint = command_blueprint();
        let raw = String::from_utf8(blueprint.canonical_json().unwrap()).unwrap();
        let old = inspect_blueprint(Some(blueprint), None).unwrap();
        let current = inspect_blueprint(None, Some(raw.clone())).unwrap();
        assert_eq!(old.data, current.data);

        let large = raw
            .replace("\"minimum\":18", "\"minimum\":9007199254740993")
            .replace("\"maximum\":28", "\"maximum\":9007199254740994");
        let parsed = parse_blueprint_input(None, Some(large.clone())).unwrap();
        assert_eq!(
            parsed.intents().values().next().unwrap().desired_value,
            telysta_core::blueprint::BlueprintValue::IntegerRange {
                minimum: 9007199254740993,
                maximum: 9007199254740994,
            }
        );
        let report = inspect_blueprint(None, Some(large)).unwrap();
        assert_eq!(
            report.data.blueprint_document_sha256,
            parsed.document_sha256().unwrap()
        );
        assert!(!report.data.ready_for_compilation);
    }

    #[test]
    fn raw_blueprint_rejects_fractional_tokens_and_ambiguous_inputs() {
        let raw = String::from_utf8(command_blueprint().canonical_json().unwrap()).unwrap();
        let fractional = raw.replace(
            "\"candidateCount\":4",
            "\"candidateCount\":4.0000000000000001",
        );
        for invalid in [fractional, "{".to_owned()] {
            let error = inspect_blueprint(None, Some(invalid)).unwrap_err();
            assert_eq!(error.code, "invalid_blueprint_json");
            assert_eq!(error.path.as_deref(), Some("blueprintJson"));
        }
        for (typed, raw) in [(None, None), (Some(command_blueprint()), Some(raw))] {
            assert_eq!(
                inspect_blueprint(typed, raw).unwrap_err().code,
                "invalid_blueprint_input"
            );
        }
    }
}
