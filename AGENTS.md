# Telysta Agent Operating Contract

This repository builds a local-first, auditable language-history simulator. It is not a random word-list generator. Every agent working here must preserve the distinction between software correctness, linguistic plausibility, and user preference.

## Authority and scope

- Rust is the only production authority for language state, rules, simulation, project history, and storage.
- Python is a legacy baseline and research laboratory. It must not become a second production state writer.
- Tauri and the webview are clients of versioned Rust commands. They must not invent a second Blueprint or LanguageState schema.
- LLMs may parse, explain, or propose. They never commit authoritative state without deterministic schema and domain validation.

### User-authorized AI development review (2026-10-16)

Independent AI reviews replace human/expert availability and human staffing gates
for local development, as explicitly requested by the user. Record actual agent
identities, reviewed bytes, findings and scope; the author cannot self-approve.
Do not wait for human owner names, expert recruitment or human capacity estimates.
The AI coordinator uses WIP 1 and advances one tested slice at a time.
This changes development acceptance, not domain validation, migration safety or
the truth of scientific, usability and platform claims. Unobtained human evidence
remains unobtained. The effective policy and relation to historical GateEvidence
are in `docs/AGENT_OPERATING_MODEL.md` section 3.1; older human/remote readiness
predicates must not silently override this user-authorized local development mode.

Read these documents before changing a core domain:

1. `docs/STATUS.md`
2. `docs/PRODUCT_DEVELOPMENT_PLAN.md`
3. `docs/ROADMAP.md`
4. `docs/LANGUAGE_SIMULATOR_PLAN.md`
5. `docs/governance/AUTHORITY_ORDER.md`
6. `docs/architecture/CURRENT.md`
7. `docs/architecture/TARGET.md`
8. `docs/architecture/MIGRATION.md`
9. `docs/AGENT_OPERATING_MODEL.md`
10. `docs/adr/ADR-006-rust-native-core-python-research-bridge.md`
11. `docs/adr/ADR-007-language-state-v3-change-event-ir.md`
12. The domain-specific contract and ADR index entries referenced by the files being changed.

## Non-negotiable invariants

- Do not use IPA or grapheme string matching when a typed phonological feature match is available.
- Do not add an uncontrolled random source. Derive every stream from the versioned `RngTree` path contract.
- Do not persist an unversioned schema, rule pack, data payload, or external model result.
- Do not describe empirical priors, research hypotheses, environmental labels, or aesthetic preferences as hard linguistic laws.
- Do not add a sound or grammar change without a typed environment, effect, provenance, and replay story.
- Do not bypass `StateTransaction`, storage leases, expected-history hashes, migrations, or validation boundaries.
- Do not copy a known Python defect into Rust merely to preserve legacy output.
- Do not expose a UI control whose compiler capability is still `planned` as if it were supported.
- Do not report a single opaque "naturalness" score. Quality metrics must be traceable to entities, rules, constructions, events, or task failures.
- Do not delete legacy modules based only on static unreachability. Follow `docs/CLEANUP_PLAN.md` and the migration matrix.

## Required change workflow

1. State the user-visible or research question the change answers.
2. Identify the authoritative schema, ADR, data source, and migration impact.
3. Classify every relevant assumption as a hard constraint, empirical prior, research hypothesis, or creative preference.
4. Make the smallest complete domain slice; keep unrelated moves and formatting separate.
5. Add unit, property, replay, migration, and scientific validation in proportion to risk.
6. Run the required gates and record any semantic-hash or baseline change.
7. Update the roadmap and contracts when capability or architecture changes.

## Local verification

Run builds, tests, simulations, and application processes locally. Git remotes
are for code backup and stage commits; do not add or enable remote workflows,
CI runners, hosted application services, or remote computation without a new
explicit user instruction. Archived workflow examples are not executable plans.

Python baseline:

```powershell
.\.venv\Scripts\python.exe -I scripts\check.py
```

Rust core and desktop:

```powershell
cargo +1.88.0 fmt --all --check
cargo +1.88.0 test --workspace --locked
cargo +1.88.0 clippy --workspace --all-targets --locked -- -D warnings
cargo +1.88.0 build -p telysta-desktop --locked
```

Targeted work may run a smaller command while iterating, but the relevant full gate must pass before handoff. Expected failures must use strict `xfail` with a documented migration target; do not add broad skips.

## External skills and dependencies

- Follow `docs/SKILL_ALLOWLIST.md` before installing or invoking a network-fetched skill.
- Pin external data payloads and record hashes, versions, licenses, citations, sampling units, and limitations.
- Review new Rust dependencies with advisory, source, duplicate-version, and license checks before release.
- GPL or share-alike research tools require an explicit distribution decision before entering the shipped product.

## Stop conditions

Stop implementation and write or amend an ADR when a change would:

- alter the meaning or identity of a persisted entity;
- add a new authoritative writer;
- change event replay semantics;
- introduce a new plugin execution boundary;
- turn a statistical association into a causal product rule;
- make the current migration path ambiguous.

Large-scale refactoring is allowed when bounded by domain contracts, migrations, golden scenarios, and stop/go gates. Existing code volume is not a reason to preserve a faulty abstraction.
