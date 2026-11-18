"""Tests for QuantumWalk-Lab: walks, exponents, search, gates."""
import math

import pytest

import main as m


# ---- classical walk
def test_classical_probs_normalised():
    assert abs(sum(m.classical_probs(37).values()) - 1) < 1e-12


def test_classical_sigma_exact():
    stats = m.distribution_stats(m.classical_probs(100))
    assert abs(stats["sigma"] - 10.0) < 1e-9
    assert abs(stats["mean"]) < 1e-12


def test_classical_binomial_formula():
    assert abs(m.classical_probs(100)[0]
               - math.comb(100, 50) / 2 ** 100) < 1e-15


def test_classical_parity():
    probs = m.classical_probs(50)
    assert all(probs.get(x, 0.0) == 0.0 for x in range(-49, 50, 2))


def test_classical_scaling_diffusive():
    sigmas = [m.distribution_stats(m.classical_probs(t))["sigma"]
              for t in m.CLASSICAL_FIT_STEPS]
    assert abs(m.fit_exponent(m.CLASSICAL_FIT_STEPS, sigmas) - 0.5) < 0.01


# ---- discrete-time Hadamard walk
def test_qw_probs_normalised():
    stats = m.distribution_stats(m.hadamard_walk(100))
    assert abs(stats["total"] - 1) < 1e-12


def test_qw_parity():
    probs = m.hadamard_walk(100)
    assert all(probs.get(x, 0.0) < 1e-15 for x in range(-99, 100, 2))


def test_qw_symmetric_mean_zero():
    stats = m.distribution_stats(m.hadamard_walk(100))
    assert abs(stats["mean"]) < 1e-9


def test_qw_sigma_ballistic():
    stats = m.distribution_stats(m.hadamard_walk(100))
    assert 50.0 < stats["sigma"] < 58.0
    assert abs(stats["sigma"] / 100
               - math.sqrt(1 - 1 / math.sqrt(2))) < 0.01


def test_qw_scaling_ballistic():
    sigmas = [m.distribution_stats(m.hadamard_walk(t))["sigma"]
              for t in m.QW_FIT_STEPS]
    assert abs(m.fit_exponent(m.QW_FIT_STEPS, sigmas) - 1.0) < 0.02


def test_qw_beats_classical_width():
    qw = m.distribution_stats(m.hadamard_walk(100))["sigma"]
    cl = m.distribution_stats(m.classical_probs(100))["sigma"]
    assert qw > 4 * cl


def test_qw_deterministic_repeat():
    assert m.hadamard_walk(60) == m.hadamard_walk(60)


def test_qw_biased_coin_drifts_left():
    probs = m.hadamard_walk(100, m.BIASED_COIN)
    stats = m.distribution_stats(probs)
    left = sum(p for x, p in probs.items() if x < 0)
    right = sum(p for x, p in probs.items() if x > 0)
    assert stats["mean"] < -20.0
    assert left > 0.70 and left > 2 * right


def test_qw_trapped_never_moves():
    probs = m.hadamard_walk(100, m.SYMMETRIC_COIN, shift=False)
    assert m.distribution_stats(probs)["sigma"] == 0.0
    assert abs(probs[0] - 1.0) < 1e-12


# ---- Jacobi eigensolver
def test_jacobi_reconstruction():
    a = m.path_adjacency(8)
    evals, vecs = m.jacobi_eigh(a)
    assert m.reconstruct_error(a, evals, vecs) < 1e-9


def test_jacobi_matches_dft_on_cycle():
    evals, _ = m.jacobi_eigh(m.cycle_adjacency(7))
    assert max(abs(a - b) for a, b in zip(
        sorted(evals), sorted(m.cycle_eigenvalues(7)))) < 1e-9


# ---- continuous-time walks
def test_ctqw_cycle_norm_conserved():
    assert abs(sum(m.ctqw_cycle_probs(8, 0, 1.234)) - 1) < 1e-12


def test_ctqw_c4_perfect_transfer():
    assert m.ctqw_cycle_probs(4, 0, math.pi / 2)[2] > 1 - 1e-9


def test_ctqw_c4_revival():
    assert m.ctqw_cycle_probs(4, 0, math.pi)[0] > 1 - 1e-9


def test_ctqw_c6_revival():
    assert m.ctqw_cycle_probs(6, 0, 2 * math.pi)[0] > 1 - 1e-9


def test_ctqw_c4_return_closed_form():
    t = 0.7
    assert abs(m.ctqw_cycle_probs(4, 0, t)[0]
               - ((1 + math.cos(2 * t)) / 2) ** 2) < 1e-9


def test_ctqw_line_ballistic():
    probs = {i: p for i, p in enumerate(m.ctqw_line_probs(41, 20, 6.0))}
    stats = m.distribution_stats(probs)
    assert abs(stats["total"] - 1) < 1e-9
    assert abs(stats["sigma"] / 6.0 - math.sqrt(2)) < 0.01


def test_ctqw_line_symmetric():
    probs = m.ctqw_line_probs(41, 20, 3.0)
    assert max(abs(probs[i] - probs[40 - i]) for i in range(41)) < 1e-9


# ---- quantum-walk search
def test_search_reduced_matches_full():
    for t in (0.5, 1.0, 2.0):
        assert abs(m.search_success(8, t)
                   - m.search_success_full(8, t)) < 1e-9


def test_search_starts_uniform():
    assert abs(m.search_success(64, 0.0) - 1 / 64) < 1e-12


def test_search_peak_probability():
    assert m.search_peak(1024)["p_max"] > 0.98


def test_search_time_constant():
    peak = m.search_peak(1024)
    assert abs(peak["t_star_over_sqrt_n"] - math.pi / 2) / (math.pi / 2) < 0.02


def test_search_time_scaling_quadratic():
    peaks = [m.search_peak(n) for n in m.SEARCH_SIZES]
    slope = m.fit_exponent([p["n"] for p in peaks],
                           [p["t_star"] for p in peaks])
    assert abs(slope - 0.5) < 0.02


def test_search_beats_classical_count():
    peak = m.search_peak(1024)
    assert peak["t_star"] < peak["classical_expected_draws"] / 5


# ---- classifier
def test_classifier_scenarios():
    rep = m.classifier_report()
    assert rep["classical_line"] == "diffusive"
    assert rep["hadamard_symmetric"] == "ballistic"
    assert rep["hadamard_biased_coin"] == "ballistic"
    assert rep["trapped_coin_only"] == "localized"
    assert rep["ctqw_line"] == "ballistic"


def test_classifier_matches_model():
    for features in m.measured_features().values():
        assert m.classify_walk(*features) == m.model_label(*features)


# ---- gates + seats
def test_hold_gates_count_and_style():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())


@pytest.mark.parametrize("action", [
    "quantum_advantage_claim", "real_quantum_hardware_execution",
    "quantum_supremacy_claim", "cryptographic_attack_claim",
    "certified_benchmark_claim",
])
def test_gated_actions_hold(action):
    assert m.gate(action) == "HOLD"


def test_sandbox_proceeds():
    assert m.gate("run_simulation") == "PROCEED"


def test_argon4_seat():
    decider = m.brains_report()["decider"]
    assert decider["seat"] == "Gemini Argon 4 Extended Thinking"
    assert decider["can_override_hold"] is False
    assert decider["live_calls"] == 0


def test_claude_and_flow_seats():
    brains = m.brains_report()
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_hold_demo_exit_code(capsys):
    assert m.main(["hold-demo"]) == 2
    assert "quantum_advantage_claim" in capsys.readouterr().out


def test_checks_all_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks)
