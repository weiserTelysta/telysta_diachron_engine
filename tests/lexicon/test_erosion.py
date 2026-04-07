import pytest

from app.domain.phonology.erosion import ErosionModel


@pytest.fixture
def model() -> ErosionModel:
    return ErosionModel()


# ------------------------------------------------------------------
# Base rate tiers
# ------------------------------------------------------------------

def test_function_word_base_rate(model: ErosionModel) -> None:
    assert model.rate(0.05, "") == pytest.approx(1.0)


def test_high_freq_base_rate(model: ErosionModel) -> None:
    r = model.rate(0.02, "")
    assert 0.5 <= r <= 1.0


def test_mid_freq_base_rate(model: ErosionModel) -> None:
    r = model.rate(0.005, "")
    assert 0.3 <= r <= 0.7


def test_low_freq_base_rate(model: ErosionModel) -> None:
    r = model.rate(0.0005, "")
    assert r <= 0.25


# ------------------------------------------------------------------
# Stress multiplier on high-frequency words
# ------------------------------------------------------------------

def test_prominent_stress_reduces_rate(model: ErosionModel) -> None:
    unstressed = model.rate(0.02, "")
    stressed   = model.rate(0.02, "initial")
    assert stressed < unstressed


def test_prominent_stress_penultimate(model: ErosionModel) -> None:
    unstressed = model.rate(0.02, "")
    stressed   = model.rate(0.02, "penultimate")
    assert stressed < unstressed


def test_final_stress_increases_rate(model: ErosionModel) -> None:
    no_stress = model.rate(0.02, "")
    final     = model.rate(0.02, "final")
    assert final >= no_stress


# ------------------------------------------------------------------
# Low-frequency words are stress-insensitive
# ------------------------------------------------------------------

def test_low_freq_stress_insensitive(model: ErosionModel) -> None:
    r_no_stress = model.rate(0.0005, "")
    r_stressed  = model.rate(0.0005, "initial")
    assert r_no_stress == pytest.approx(r_stressed)


# ------------------------------------------------------------------
# Rate is always in [0, 1]
# ------------------------------------------------------------------

@pytest.mark.parametrize("freq,stress", [
    (1.0, "initial"),
    (0.0, "final"),
    (0.04, "penultimate"),
])
def test_rate_bounded(model: ErosionModel, freq: float, stress: str) -> None:
    r = model.rate(freq, stress)
    assert 0.0 <= r <= 1.0
