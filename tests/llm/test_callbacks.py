"""Tests for the semantic proposal callback pipeline."""

from app.llm.backends.mock_backend import MockBackend
from app.llm.callbacks import generate_and_validate_proposal
from app.llm.contracts import SemanticProposalRequest


class TestCallbackPipeline:
    def test_mock_proposal_accepted(self) -> None:
        backend = MockBackend(seed=42)
        req = SemanticProposalRequest(
            era=1, word_id="era_0_1", concept="I",
            current_primes=["SELF"], context_chain=[],
        )
        verdict = generate_and_validate_proposal(
            backend, req, known_primes={"SUN", "SOUL", "LIGHT", "SPIRIT"},
        )
        assert verdict.status == "accepted"
        assert verdict.proposal is not None
        assert verdict.proposal.from_prime == "SUN"
        assert verdict.proposal.to_prime == "SOUL"

    def test_unknown_prime_becomes_lore_only(self) -> None:
        backend = MockBackend(seed=42)
        req = SemanticProposalRequest(
            era=1, word_id="era_0_1", concept="I",
            current_primes=[], context_chain=[],
        )
        # Mock always proposes SUN->SOUL; if SUN not in known_primes, lore_only
        verdict = generate_and_validate_proposal(
            backend, req, known_primes={"WATER", "FIRE"},
        )
        assert verdict.status == "lore_only"

    def test_rate_limit_enforced(self) -> None:
        backend = MockBackend(seed=42)
        counter: dict[int, int] = {}
        statuses: list[str] = []
        for i in range(7):
            req = SemanticProposalRequest(
                era=1, word_id=f"era_0_{i}", concept="test",
                current_primes=[], context_chain=[],
            )
            v = generate_and_validate_proposal(
                backend, req, known_primes=set(),
                max_proposals_per_era=5, proposal_counter=counter,
            )
            statuses.append(v.status)

        # First 5 should not be "rejected" due to rate; 6th and 7th should be
        rejected_count = sum(1 for s in statuses[5:] if s == "rejected")
        assert rejected_count >= 1
