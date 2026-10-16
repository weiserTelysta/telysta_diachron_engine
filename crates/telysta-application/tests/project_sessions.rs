//! Integration checks against real v1 storage, not a mocked runtime.
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
use telysta_application::{ProjectApplication, ProjectRuntimeError};
use telysta_core::{
    identity::{EntityId, EntityKind},
    project::{ProjectDataLock, ProjectHistory, RunContext, RunContextParts, StateTransaction},
    state::{
        ConceptReference, ConstructionInventory, EvidenceClass, EvidenceRecord, FamilyPosition,
        LanguageState, LanguageStateParts, Lexeme, LexiconSenseGraph, MorphologyState,
        OrthographyState, Phoneme, PhonologyState, PragmaticsAndRegisters, ProsodyState,
        ProvenanceEntry, ProvenanceKind, ProvenanceLedger, RegisterDefinition, SegmentClass, Sense,
    },
    time::{SimYear, TimeModel},
};
use telysta_storage::{ProjectStore, PROJECT_FILE_NAME};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        loop {
            let path = std::env::temp_dir().join(format!(
                "telysta-application-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            match fs::create_dir(&path) {
                Ok(()) => return Self(path),
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => panic!("create test directory: {error}"),
            }
        }
    }
    fn store(&self) {
        ProjectStore::open(&self.0)
            .expect("open fixture store")
            .save(history())
            .expect("fixture history");
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn id(kind: EntityKind, value: &str) -> EntityId {
    EntityId::new(kind, value).expect("fixture ID")
}

fn minimal_state() -> LanguageState {
    let time_model = TimeModel::new(SimYear(0), 25, 1).expect("valid time model");
    let timestamp = time_model.time_reference(SimYear(0));
    let evidence_id = id(EntityKind::Evidence, "fixture-preference");
    let event_id = id(EntityKind::Event, "genesis");
    let language_id = id(EntityKind::Language, "proto-fixture");
    let family_node_id = id(EntityKind::FamilyNode, "fixture-root");
    let community_id = id(EntityKind::SpeechCommunity, "fixture-community");
    let consonant_id = id(EntityKind::Phoneme, "p");
    let vowel_id = id(EntityKind::Phoneme, "a");
    let lexeme_id = id(EntityKind::Lexeme, "water");
    let sense_id = id(EntityKind::Sense, "water-liquid");
    let evidence_ids = BTreeSet::from([evidence_id.clone()]);

    let mut provenance_entries = BTreeMap::new();
    for entity_id in [
        language_id.clone(),
        family_node_id.clone(),
        consonant_id.clone(),
        vowel_id.clone(),
        lexeme_id.clone(),
        sense_id.clone(),
    ] {
        provenance_entries.insert(
            entity_id.clone(),
            ProvenanceEntry {
                entity_id,
                event_id: event_id.clone(),
                kind: ProvenanceKind::Genesis,
                created_at: timestamp.clone(),
                evidence_ids: evidence_ids.clone(),
            },
        );
    }

    LanguageState::new(LanguageStateParts {
        language_id,
        as_of: timestamp,
        evidence: BTreeMap::from([(
            evidence_id.clone(),
            EvidenceRecord {
                id: evidence_id,
                class: EvidenceClass::CreativePreference,
                note: "fixture only".to_owned(),
                citation: None,
                data_references: BTreeSet::new(),
            },
        )]),
        phonology: PhonologyState {
            phonemes: BTreeMap::from([
                (
                    consonant_id.clone(),
                    Phoneme {
                        id: consonant_id.clone(),
                        ipa: "p".to_owned(),
                        class: SegmentClass::Consonant,
                        evidence_ids: evidence_ids.clone(),
                    },
                ),
                (
                    vowel_id.clone(),
                    Phoneme {
                        id: vowel_id.clone(),
                        ipa: "a".to_owned(),
                        class: SegmentClass::Vowel,
                        evidence_ids: evidence_ids.clone(),
                    },
                ),
            ]),
        },
        prosody: ProsodyState {
            syllable_nuclei: BTreeSet::from([vowel_id.clone()]),
            max_syllable_moras: 2,
        },
        morphology: MorphologyState {
            morphemes: BTreeMap::new(),
        },
        constructions: ConstructionInventory {
            constructions: BTreeMap::new(),
        },
        lexicon: LexiconSenseGraph {
            lexemes: BTreeMap::from([(
                lexeme_id.clone(),
                Lexeme {
                    id: lexeme_id,
                    phoneme_sequence: vec![consonant_id, vowel_id],
                    morpheme_ids: BTreeSet::new(),
                    sense_ids: BTreeSet::from([sense_id.clone()]),
                    register: "neutral".to_owned(),
                },
            )]),
            senses: BTreeMap::from([(
                sense_id.clone(),
                Sense {
                    id: sense_id,
                    concept: ConceptReference {
                        catalog: "fixture".to_owned(),
                        concept_id: "water".to_owned(),
                    },
                    related_sense_ids: BTreeSet::new(),
                    evidence_ids: evidence_ids.clone(),
                },
            )]),
        },
        pragmatics: PragmaticsAndRegisters {
            default_register: "neutral".to_owned(),
            registers: BTreeMap::from([(
                "neutral".to_owned(),
                RegisterDefinition {
                    description: "default register".to_owned(),
                    formality_basis_points: 5_000,
                },
            )]),
        },
        orthography: OrthographyState::Disabled,
        typology: BTreeMap::new(),
        family_position: FamilyPosition {
            node_id: family_node_id,
            parent_language_id: None,
            community_ids: BTreeSet::from([community_id]),
        },
        provenance: ProvenanceLedger {
            entries: provenance_entries,
        },
    })
    .expect("minimal state is valid")
}

fn history() -> ProjectHistory {
    let context = RunContext::new(RunContextParts {
        project_id: id(EntityKind::Project, "storage-fixture-project"),
        run_id: id(EntityKind::Run, "storage-fixture-run"),
        time_model: TimeModel::new(SimYear(0), 25, 1).expect("valid time model"),
        root_seed: 88,
        engine_version: "0.1.0-test".to_owned(),
        data_lock: ProjectDataLock::new(Vec::new()).expect("empty data lock"),
        rule_packs: BTreeMap::new(),
    })
    .expect("valid run context");
    StateTransaction::begin(context, id(EntityKind::Event, "genesis"), minimal_state())
        .expect("valid transaction")
        .history()
}

#[test]
fn session_lifecycle_preserves_authoritative_bytes_and_duplicate_guards() {
    let fixture = Fixture::new();
    fixture.store();
    let original = fs::read(fixture.0.join(PROJECT_FILE_NAME)).unwrap();
    let mut app = ProjectApplication::default();
    let opened = app.open_project(&fixture.0).unwrap();
    assert_eq!(app.get_project_session(&opened.project_id).unwrap(), opened);
    assert!(matches!(
        app.open_project(&fixture.0),
        Err(ProjectRuntimeError::ProjectAlreadyOpen { .. })
    ));
    let refreshed = app.refresh_project(&opened.project_id).unwrap();
    assert_eq!(refreshed.history_sha256, opened.history_sha256);
    assert_eq!(refreshed.state_hashes, opened.state_hashes);
    assert_eq!(app.close_project(&opened.project_id).unwrap(), refreshed);
    assert!(matches!(
        app.get_project_session(&opened.project_id),
        Err(ProjectRuntimeError::UnknownProject { .. })
    ));
    assert_eq!(
        fs::read(fixture.0.join(PROJECT_FILE_NAME)).unwrap(),
        original
    );
    assert_eq!(
        app.open_project(&fixture.0).unwrap().history_sha256,
        opened.history_sha256
    );
}

#[test]
fn opening_a_missing_project_does_not_create_one() {
    let fixture = Fixture::new();
    let absent = fixture.0.join("absent");
    let mut app = ProjectApplication::default();
    assert!(app.open_project(&absent).is_err());
    assert!(!absent.exists());
    assert!(app.open_project(&fixture.0).is_err());
    assert!(!fixture.0.join(PROJECT_FILE_NAME).exists());
}

#[test]
fn failed_refresh_retains_session_and_does_not_rewrite_invalid_history() {
    let fixture = Fixture::new();
    fixture.store();
    let mut app = ProjectApplication::default();
    let opened = app.open_project(&fixture.0).unwrap();
    let primary = fixture.0.join(PROJECT_FILE_NAME);
    fs::write(&primary, b"invalid history").unwrap();
    assert!(app.refresh_project(&opened.project_id).is_err());
    assert_eq!(app.get_project_session(&opened.project_id).unwrap(), opened);
    assert_eq!(fs::read(primary).unwrap(), b"invalid history");
    assert!(app.close_project(&opened.project_id).is_ok());
}
