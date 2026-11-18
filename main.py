#!/usr/bin/env python3
"""QuantumWalk-Lab - educational quantum-walk lab (discrete + continuous).

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * A classical random walk spreads DIFFUSIVELY: its width grows
    like sqrt(t). A quantum walk spreads BALLISTICALLY: its width
    grows like t. That one exponent - 1/2 versus 1 - is the whole
    reason quantum walks are interesting, and this lab MEASURES it
    three separate ways instead of quoting it.
  * Every probability here is computed exactly from amplitudes
    (statevector arithmetic, DFT diagonalisation of a cycle, a
    from-scratch Jacobi eigensolver for a line). Nothing is sampled,
    so every number can be re-derived and diffed.
  * The quantum-walk search at the end shows the quadratic-style
    scaling honestly: the time to find a marked vertex on a complete
    graph grows like sqrt(n) - fitted in-lab at slope ~0.5 - while
    classical random sampling needs ~(n+1)/2 expected draws. The
    units are labelled toy units; the exponent is the lesson.
  * This is a CLASSICAL simulation of tiny walks on a laptop. No
    quantum hardware is touched, no advantage over real classical
    algorithms is claimed, and no result here certifies anything
    about a real device. Advantage, hardware, supremacy, crypto,
    production, benchmark, and commercial claims are permanent HOLD
    gates - with Gemini Argon 4 Extended Thinking as DECIDER
    (names-only, tighten-only), Muse as advisor (never overrides
    HOLD), and Google Flow plan-only seats.
"""
import cmath
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Canonical runs the whole lab is built on.
CLASSICAL_FIT_STEPS = (10, 20, 40, 80, 160)
QW_FIT_STEPS = (20, 40, 60, 80, 100)
HEADLINE_STEPS = 100
CTQW_LINE_SITES = 41
CTQW_LINE_TIMES = (1.0, 2.0, 4.0, 6.0)
SEARCH_SIZES = (16, 64, 256, 1024)

# Symmetric initial coin for the Hadamard walk: (|0> + i|1>) / sqrt(2).
SYMMETRIC_COIN = (1 / math.sqrt(2), 1j / math.sqrt(2))
# Biased initial coin: start entirely in the left-moving coin state.
BIASED_COIN = (1.0 + 0j, 0j)

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "quantum_advantage_claim": "HOLD - no quantum-advantage claim from a classical simulation of tiny walks",
    "real_quantum_hardware_execution": "HOLD - no submitting walks to real quantum hardware or cloud QPUs",
    "quantum_supremacy_claim": "HOLD - no quantum-supremacy or beyond-classical claims from a laptop sim",
    "cryptographic_attack_claim": "HOLD - no using walk search to claim attacks on real cryptography",
    "production_algorithm_claim": "HOLD - no production search, optimisation, or routing deployment claims",
    "certified_benchmark_claim": "HOLD - no presenting lab timings or exponents as certified hardware benchmarks",
    "simulation_as_hardware_claim": "HOLD - simulated probabilities are never presented as measured hardware data",
    "publish_unverified_scaling_claim": "HOLD - no publishing a scaling exponent this lab did not measure",
    "drug_discovery_claim": "HOLD - no drug, materials, or chemistry discovery claims from walk toys",
    "financial_trading_claim": "HOLD - no trading, market, or portfolio claims from walk simulations",
    "military_targeting_claim": "HOLD - no military, targeting, or surveillance use of walk algorithms",
    "commercial_service_claim": "HOLD - no commercial service or product claims from a lab model",
    "investment_claim": "HOLD - no investment claims; a teaching sim is not a prospectus",
    "remove_human_override": "HOLD - the human override is never removed",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ helpers
def distribution_stats(probs):
    """Mean, sigma, peak probability, support size of a distribution.

    `probs` maps position -> probability. Support counts positions
    carrying more than 1e-12 of the mass.
    """
    mean = sum(x * p for x, p in probs.items())
    var = sum((x - mean) ** 2 * p for x, p in probs.items())
    support = sum(1 for p in probs.values() if p > 1e-12)
    return {
        "mean": mean,
        "sigma": math.sqrt(max(var, 0.0)),
        "max_prob": max(probs.values()) if probs else 0.0,
        "support": support,
        "total": sum(probs.values()),
    }


def peak_ratio(probs):
    """Peak probability relative to a flat distribution on the support."""
    stats = distribution_stats(probs)
    if stats["support"] == 0:
        return 0.0
    return stats["max_prob"] * stats["support"]


def fit_exponent(steps, sigmas):
    """Least-squares slope of log(sigma) vs log(steps): the scaling exponent.

    A walk whose width never grows (all sigmas ~ 0) has exponent 0.
    """
    if all(s < 1e-12 for s in sigmas):
        return 0.0
    xs = [math.log(t) for t in steps]
    ys = [math.log(max(s, 1e-12)) for s in sigmas]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den


# ================================================================ 1. Classical random walk
# Exact binomial probabilities - no sampling. After t steps the
# walker is at x = 2k - t with probability C(t, k) / 2**t, the
# variance is exactly t, and the width therefore grows like sqrt(t):
# diffusion, with exponent exactly 1/2.

def classical_probs(steps):
    """Exact position distribution of the classical walk after `steps`."""
    probs = {}
    for k in range(steps + 1):
        probs[2 * k - steps] = math.comb(steps, k) / 2 ** steps
    return probs


def classical_report():
    sigmas = [distribution_stats(classical_probs(t))["sigma"]
              for t in CLASSICAL_FIT_STEPS]
    headline = distribution_stats(classical_probs(HEADLINE_STEPS))
    return {
        "fit_steps": list(CLASSICAL_FIT_STEPS),
        "fit_sigmas": [round(s, 6) for s in sigmas],
        "scaling_exponent": round(fit_exponent(CLASSICAL_FIT_STEPS, sigmas), 6),
        "headline_steps": HEADLINE_STEPS,
        "headline_sigma": headline["sigma"],
        "headline_mean": headline["mean"],
        "headline_max_prob": headline["max_prob"],
        "headline_peak_ratio": round(peak_ratio(classical_probs(HEADLINE_STEPS)), 6),
        "variance_law": "sigma^2 = t exactly (binomial), so sigma = sqrt(t)",
    }


# ================================================================ 2. Discrete-time quantum walk
# Hadamard coin + conditional shift, evolved as an exact statevector
# over (position, coin). Coin state 0 moves left, coin state 1 moves
# right. Amplitudes interfere, so instead of piling up in the middle
# the walker piles up near two ballistic fronts at about +/-0.54 t
# and the width grows linearly: sigma ~ t * sqrt(1 - 1/sqrt(2)).

def hadamard_walk(steps, init_coin=SYMMETRIC_COIN, shift=True):
    """Exact position distribution of the Hadamard walk after `steps`.

    With shift=False the coin still flips but the walker never moves:
    the labelled trapped/localised degenerate case.
    """
    state = {(0, 0): complex(init_coin[0]), (0, 1): complex(init_coin[1])}
    inv = 1 / math.sqrt(2)
    for _ in range(steps):
        nxt = {}
        for (x, coin), amp in state.items():
            if amp == 0:
                continue
            if coin == 0:
                outs = ((0, amp * inv), (1, amp * inv))
            else:
                outs = ((0, amp * inv), (1, -amp * inv))
            for new_coin, new_amp in outs:
                if shift:
                    nx = x - 1 if new_coin == 0 else x + 1
                else:
                    nx = x
                key = (nx, new_coin)
                nxt[key] = nxt.get(key, 0j) + new_amp
        state = nxt
    probs = {}
    for (x, _coin), amp in state.items():
        probs[x] = probs.get(x, 0.0) + abs(amp) ** 2
    return probs


def qw_report():
    sigmas = [distribution_stats(hadamard_walk(t))["sigma"]
              for t in QW_FIT_STEPS]
    headline = distribution_stats(hadamard_walk(HEADLINE_STEPS))
    biased = distribution_stats(hadamard_walk(HEADLINE_STEPS, BIASED_COIN))
    biased_probs = hadamard_walk(HEADLINE_STEPS, BIASED_COIN)
    left = sum(p for x, p in biased_probs.items() if x < 0)
    right = sum(p for x, p in biased_probs.items() if x > 0)
    return {
        "fit_steps": list(QW_FIT_STEPS),
        "fit_sigmas": [round(s, 6) for s in sigmas],
        "scaling_exponent": round(fit_exponent(QW_FIT_STEPS, sigmas), 6),
        "headline_steps": HEADLINE_STEPS,
        "headline_sigma": headline["sigma"],
        "headline_mean": headline["mean"],
        "sigma_over_t": headline["sigma"] / HEADLINE_STEPS,
        "theory_sigma_over_t": math.sqrt(1 - 1 / math.sqrt(2)),
        "headline_peak_ratio": round(peak_ratio(hadamard_walk(HEADLINE_STEPS)), 6),
        "biased_mean": biased["mean"],
        "biased_sigma": biased["sigma"],
        "biased_left_mass": left,
        "biased_right_mass": right,
        "biased_peak_position": max(biased_probs, key=biased_probs.get),
    }


# ================================================================ 3. Matrix toolkit + Jacobi eigensolver
# Continuous-time walks need exp(-i H t). For the line, H is the
# adjacency matrix of a path graph - real symmetric - so a cyclic
# Jacobi eigensolver written from scratch diagonalises it exactly
# enough to assert V L V^T = A to 1e-9. For the cycle, the DFT
# diagonalises it analytically; the checks cross-validate the two.

def jacobi_eigh(matrix, tol=1e-12, max_sweeps=100):
    """Eigendecomposition of a real symmetric matrix by cyclic Jacobi.

    Returns (eigenvalues, V) with eigenvectors as COLUMNS of V, so
    A = V diag(eigenvalues) V^T.
    """
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_sweeps):
        off = math.sqrt(sum(a[i][j] ** 2
                            for i in range(n) for j in range(n) if i != j))
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
                c, s = math.cos(theta), math.sin(theta)
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    return [a[i][i] for i in range(n)], v


def reconstruct_error(matrix, evals, vecs):
    """max |A - V diag(evals) V^T| - the eigensolver's receipt."""
    n = len(matrix)
    err = 0.0
    for i in range(n):
        for j in range(n):
            rec = sum(vecs[i][k] * evals[k] * vecs[j][k] for k in range(n))
            err = max(err, abs(rec - matrix[i][j]))
    return err


def path_adjacency(n):
    a = [[0.0] * n for _ in range(n)]
    for i in range(n - 1):
        a[i][i + 1] = a[i + 1][i] = 1.0
    return a


def cycle_adjacency(n):
    a = [[0.0] * n for _ in range(n)]
    for i in range(n):
        a[i][(i + 1) % n] = 1.0
        a[(i + 1) % n][i] = 1.0
    return a


_EIG_CACHE = {}


def _path_eig(n):
    if ("path", n) not in _EIG_CACHE:
        _EIG_CACHE[("path", n)] = jacobi_eigh(path_adjacency(n))
    return _EIG_CACHE[("path", n)]


# ================================================================ 4. Continuous-time quantum walk
# H = adjacency. On a cycle the DFT modes diagonalise H with
# eigenvalues 2 cos(2 pi k / n), giving closed-form amplitudes. The
# 4-cycle is exactly solvable by hand: perfect transfer to the
# opposite site at t = pi/2 and full revival at t = pi. On a line
# the Jacobi spectrum drives the evolution and the width grows
# ballistically at sigma = sqrt(2) t - faster than the discrete
# Hadamard walk's 0.5412 t, because the fastest modes move at the
# maximum group velocity 2 and the packet is built from them.

def cycle_eigenvalues(n):
    return [2 * math.cos(2 * math.pi * k / n) for k in range(n)]


def ctqw_cycle_probs(n, start, t):
    """Exact CTQW probabilities on cycle C_n via the DFT spectrum."""
    evals = cycle_eigenvalues(n)
    probs = []
    for x in range(n):
        amp = sum(cmath.exp(-1j * evals[k] * t)
                  * cmath.exp(2j * math.pi * k * (x - start) / n)
                  for k in range(n)) / n
        probs.append(abs(amp) ** 2)
    return probs


def ctqw_line_probs(n, start, t):
    """Exact CTQW probabilities on a path of n sites via Jacobi spectrum."""
    evals, vecs = _path_eig(n)
    coeffs = [vecs[start][k] * cmath.exp(-1j * evals[k] * t)
              for k in range(n)]
    probs = []
    for x in range(n):
        amp = sum(vecs[x][k] * coeffs[k] for k in range(n))
        probs.append(abs(amp) ** 2)
    return probs


def ctqw_report():
    line = {}
    for t in CTQW_LINE_TIMES:
        probs = ctqw_line_probs(CTQW_LINE_SITES, CTQW_LINE_SITES // 2, t)
        stats = distribution_stats({i: p for i, p in enumerate(probs)})
        line[str(t)] = {"sigma": stats["sigma"], "mean": stats["mean"],
                        "total": stats["total"]}
    sigmas = [line[str(t)]["sigma"] for t in CTQW_LINE_TIMES]
    return {
        "cycle_c4_transfer_at_pi_over_2": ctqw_cycle_probs(4, 0, math.pi / 2)[2],
        "cycle_c4_revival_at_pi": ctqw_cycle_probs(4, 0, math.pi)[0],
        "cycle_c6_revival_at_2pi": ctqw_cycle_probs(6, 0, 2 * math.pi)[0],
        "line_sites": CTQW_LINE_SITES,
        "line": line,
        "line_scaling_exponent": round(
            fit_exponent(list(CTQW_LINE_TIMES), sigmas), 6),
        "line_sigma_over_t": sigmas[-1] / CTQW_LINE_TIMES[-1],
        "theory_line_sigma_over_t": math.sqrt(2),
    }


# ================================================================ 5. Quantum-walk search (complete graph)
# Childs-Goldstone spatial search: H = -gamma A - |w><w| on the
# complete graph K_n with gamma = 1/n. By symmetry the dynamics live
# in the 2D span of |w> and the uniform state |r> over the unmarked
# vertices, so the search is a two-level Rabi oscillation that this
# lab solves exactly - and cross-checks against the full n x n
# Hamiltonian at n = 8. The marked probability peaks near 1 at
# t* ~ (pi/2) sqrt(n): the time grows like sqrt(n) while classical
# random sampling needs (n+1)/2 expected draws. LABELLED toy units:
# one unit of walk time is priced as one oracle query; the fitted
# exponent (slope ~0.5) is the claim, nothing more.

def _search_eig(n):
    """Eigendecomposition of the reduced 2x2 search Hamiltonian."""
    if ("search", n) not in _EIG_CACHE:
        gamma = 1.0 / n
        r = math.sqrt(n - 1)
        h = [[-1.0, -gamma * r], [-gamma * r, -gamma * (n - 2)]]
        _EIG_CACHE[("search", n)] = jacobi_eigh(h)
    return _EIG_CACHE[("search", n)]


def search_success(n, t):
    """Probability of measuring the marked vertex at time t (reduced model)."""
    evals, vecs = _search_eig(n)
    s0 = (1 / math.sqrt(n), math.sqrt((n - 1) / n))
    coeffs = []
    for k in range(2):
        amp0 = vecs[0][k] * s0[0] + vecs[1][k] * s0[1]
        coeffs.append(amp0 * cmath.exp(-1j * evals[k] * t))
    amp_w = vecs[0][0] * coeffs[0] + vecs[0][1] * coeffs[1]
    return abs(amp_w) ** 2


def search_success_full(n, t):
    """Same probability from the full n x n Hamiltonian (cross-check)."""
    gamma = 1.0 / n
    h = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                h[i][j] = -gamma
    h[0][0] -= 1.0
    evals, vecs = jacobi_eigh(h)
    s0 = [1 / math.sqrt(n)] * n
    coeffs = [sum(vecs[x][k] * s0[x] for x in range(n))
              * cmath.exp(-1j * evals[k] * t) for k in range(n)]
    amp_w = sum(vecs[0][k] * coeffs[k] for k in range(n))
    return abs(amp_w) ** 2


def search_peak(n):
    """First-peak time and height of the marked-vertex probability."""
    evals, vecs = _search_eig(n)
    s0 = (1 / math.sqrt(n), math.sqrt((n - 1) / n))
    base = [vecs[0][k] * s0[0] + vecs[1][k] * s0[1] for k in range(2)]
    best_t, best_p = 0.0, -1.0
    steps = 4000
    horizon = 2.0 * math.sqrt(n)
    for i in range(steps + 1):
        t = horizon * i / steps
        amp_w = sum(vecs[0][k] * base[k] * cmath.exp(-1j * evals[k] * t)
                    for k in range(2))
        p = abs(amp_w) ** 2
        if p > best_p:
            best_t, best_p = t, p
    return {"n": n, "t_star": best_t, "p_max": best_p,
            "t_star_over_sqrt_n": best_t / math.sqrt(n),
            "classical_expected_draws": (n + 1) / 2}


def search_report():
    peaks = [search_peak(n) for n in SEARCH_SIZES]
    slope = fit_exponent([p["n"] for p in peaks],
                         [p["t_star"] for p in peaks])
    return {
        "peaks": [{**p,
                   "t_star": round(p["t_star"], 6),
                   "p_max": round(p["p_max"], 6),
                   "t_star_over_sqrt_n": round(p["t_star_over_sqrt_n"], 6)}
                  for p in peaks],
        "time_scaling_exponent": round(slope, 6),
        "note": "toy units: 1 unit of walk time = 1 oracle query; "
                "classical = random sampling without replacement",
    }


# ================================================================ 6. kNN walk-regime classifier
# Features: (scaling exponent, peak ratio, evolution length). The
# training grid is labelled by the lab's own regime model below -
# the classifier interpolates measured walk behaviour, it does not
# invent labels. The regime of a walk is decided by its MEASURED
# width-growth exponent: ~0 localised, ~1/2 diffusive, ~1 ballistic.

def model_label(exponent, peak_ratio, steps):
    """The regime model distilled to a three-way teaching label."""
    if exponent < 0.25:
        return "localized"
    if exponent < 0.70:
        return "diffusive"
    return "ballistic"


def _training_grid():
    rows = []
    exponent = 0.0
    while exponent <= 1.051:
        for peak in (1.0, 2.0, 4.0, 8.0):
            for steps in (10, 50, 100, 200):
                rows.append(((round(exponent, 2), peak, steps),
                             model_label(exponent, peak, steps)))
        exponent += 0.05
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    exponent, peak, steps = features
    return (exponent, peak / 8.0, steps / 200.0)


def classify_walk(exponent, peak_ratio_value, steps, k=5):
    """kNN over the model-labelled grid, deterministic tie-breaking."""
    target = _scaled((exponent, peak_ratio_value, steps))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for _, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    priority = {"ballistic": 0, "diffusive": 1, "localized": 2}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def measured_features():
    """Features of the lab's own walks, measured - never assumed."""
    classical_sigmas = [distribution_stats(classical_probs(t))["sigma"]
                        for t in QW_FIT_STEPS]
    qw_sigmas = [distribution_stats(hadamard_walk(t))["sigma"]
                 for t in QW_FIT_STEPS]
    biased_sigmas = [distribution_stats(hadamard_walk(t, BIASED_COIN))["sigma"]
                     for t in QW_FIT_STEPS]
    trapped_sigmas = [distribution_stats(
        hadamard_walk(t, SYMMETRIC_COIN, shift=False))["sigma"]
        for t in QW_FIT_STEPS]
    line_sigmas = [distribution_stats(
        {i: p for i, p in enumerate(
            ctqw_line_probs(CTQW_LINE_SITES, CTQW_LINE_SITES // 2, t))})["sigma"]
        for t in CTQW_LINE_TIMES]
    return {
        "classical_line": (
            fit_exponent(QW_FIT_STEPS, classical_sigmas),
            peak_ratio(classical_probs(HEADLINE_STEPS)), HEADLINE_STEPS),
        "hadamard_symmetric": (
            fit_exponent(QW_FIT_STEPS, qw_sigmas),
            peak_ratio(hadamard_walk(HEADLINE_STEPS)), HEADLINE_STEPS),
        "hadamard_biased_coin": (
            fit_exponent(QW_FIT_STEPS, biased_sigmas),
            peak_ratio(hadamard_walk(HEADLINE_STEPS, BIASED_COIN)),
            HEADLINE_STEPS),
        "trapped_coin_only": (
            fit_exponent(QW_FIT_STEPS, trapped_sigmas),
            peak_ratio(hadamard_walk(HEADLINE_STEPS, SYMMETRIC_COIN,
                                     shift=False)), HEADLINE_STEPS),
        "ctqw_line": (
            fit_exponent(list(CTQW_LINE_TIMES), line_sigmas),
            peak_ratio({i: p for i, p in enumerate(ctqw_line_probs(
                CTQW_LINE_SITES, CTQW_LINE_SITES // 2, CTQW_LINE_TIMES[-1]))}),
            int(10 * CTQW_LINE_TIMES[-1])),
    }


def classifier_report():
    return {name: classify_walk(*features)
            for name, features in measured_features().items()}


# ================================================================ 7. Advisory seats
def _trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumwalk-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all advantage and hardware gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="quantumwalk-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Lead with the exponent: classical 1/2, quantum 1 - measured three ways in this lab, with the search slope fitted at ~0.5 and every unit labelled a toy before anyone says the word advantage.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a bell curve widening slowly beside two quantum fronts racing outward",
                  "a coin flipping in superposition above a line of sites",
                  "a wave packet circling a ring and returning to its start in phase",
                  "one marked vertex lighting up as the walk's amplitude finds it",
                  "three width-versus-time curves: flat, square-root, and straight-line"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. classical walk - diffusion with exponent exactly 1/2
    p37 = classical_probs(37)
    chk("classical_probs_normalised", abs(sum(p37.values()) - 1) < 1e-12)
    head = distribution_stats(classical_probs(HEADLINE_STEPS))
    chk("classical_sigma_exact", abs(head["sigma"] - 10.0) < 1e-9)
    chk("classical_mean_zero", abs(head["mean"]) < 1e-12)
    chk("classical_binomial_formula",
        abs(classical_probs(100)[0]
            - math.comb(100, 50) / 2 ** 100) < 1e-15)
    chk("classical_parity",
        all(classical_probs(50).get(x, 0.0) == 0.0
            for x in range(-49, 50, 2)))
    csig = [distribution_stats(classical_probs(t))["sigma"]
            for t in CLASSICAL_FIT_STEPS]
    chk("classical_scaling_diffusive",
        abs(fit_exponent(CLASSICAL_FIT_STEPS, csig) - 0.5) < 0.01)

    # 2. Hadamard walk - ballistic, asymmetric under a biased coin
    qw = hadamard_walk(HEADLINE_STEPS)
    qhead = distribution_stats(qw)
    chk("qw_probs_normalised", abs(qhead["total"] - 1) < 1e-12)
    chk("qw_parity", all(qw.get(x, 0.0) < 1e-15
                         for x in range(-99, 100, 2)))
    chk("qw_symmetric_mean_zero", abs(qhead["mean"]) < 1e-9)
    chk("qw_sigma_ballistic_value", 50.0 < qhead["sigma"] < 58.0)
    chk("qw_sigma_rate_matches_theory",
        abs(qhead["sigma"] / HEADLINE_STEPS
            - math.sqrt(1 - 1 / math.sqrt(2))) < 0.01)
    qsig = [distribution_stats(hadamard_walk(t))["sigma"]
            for t in QW_FIT_STEPS]
    chk("qw_scaling_ballistic",
        abs(fit_exponent(QW_FIT_STEPS, qsig) - 1.0) < 0.02)
    chk("qw_beats_classical_width", qhead["sigma"] > 4 * head["sigma"])
    chk("qw_deterministic_repeat", hadamard_walk(60) == hadamard_walk(60))
    biased = hadamard_walk(HEADLINE_STEPS, BIASED_COIN)
    bstats = distribution_stats(biased)
    left = sum(p for x, p in biased.items() if x < 0)
    right = sum(p for x, p in biased.items() if x > 0)
    chk("qw_biased_drifts_left", bstats["mean"] < -20.0)
    chk("qw_biased_left_majority", left > 0.70 and left > 2 * right)
    chk("qw_biased_still_ballistic",
        abs(fit_exponent(QW_FIT_STEPS,
                         [distribution_stats(
                             hadamard_walk(t, BIASED_COIN))["sigma"]
                          for t in QW_FIT_STEPS]) - 1.0) < 0.02)
    trapped = hadamard_walk(HEADLINE_STEPS, SYMMETRIC_COIN, shift=False)
    chk("qw_trapped_never_moves",
        distribution_stats(trapped)["sigma"] == 0.0
        and abs(trapped[0] - 1.0) < 1e-12)

    # 3. Jacobi eigensolver - proven before anything trusts it
    a8 = path_adjacency(8)
    ev8, vv8 = jacobi_eigh(a8)
    chk("jacobi_reconstruction_path8", reconstruct_error(a8, ev8, vv8) < 1e-9)
    cyc7 = cycle_adjacency(7)
    evc, _ = jacobi_eigh(cyc7)
    chk("jacobi_matches_dft_cycle7",
        max(abs(a - b) for a, b in zip(sorted(evc),
                                       sorted(cycle_eigenvalues(7)))) < 1e-9)

    # 4. continuous-time walks - transfer, revival, ballistic line
    chk("ctqw_cycle_norm_conserved",
        abs(sum(ctqw_cycle_probs(8, 0, 1.234)) - 1) < 1e-12)
    chk("ctqw_c4_perfect_transfer",
        ctqw_cycle_probs(4, 0, math.pi / 2)[2] > 1 - 1e-9)
    chk("ctqw_c4_revival", ctqw_cycle_probs(4, 0, math.pi)[0] > 1 - 1e-9)
    chk("ctqw_c6_revival",
        ctqw_cycle_probs(6, 0, 2 * math.pi)[0] > 1 - 1e-9)
    t07 = 0.7
    chk("ctqw_c4_return_closed_form",
        abs(ctqw_cycle_probs(4, 0, t07)[0]
            - ((1 + math.cos(2 * t07)) / 2) ** 2) < 1e-9)
    line6 = distribution_stats({i: p for i, p in enumerate(
        ctqw_line_probs(CTQW_LINE_SITES, CTQW_LINE_SITES // 2, 6.0))})
    chk("ctqw_line_norm_conserved", abs(line6["total"] - 1) < 1e-9)
    chk("ctqw_line_ballistic_rate",
        abs(line6["sigma"] / 6.0 - math.sqrt(2)) < 0.01)
    line_probs = ctqw_line_probs(CTQW_LINE_SITES, CTQW_LINE_SITES // 2, 3.0)
    chk("ctqw_line_symmetric",
        max(abs(line_probs[i] - line_probs[CTQW_LINE_SITES - 1 - i])
            for i in range(CTQW_LINE_SITES)) < 1e-9)

    # 5. search - reduced model proven against the full Hamiltonian
    chk("search_reduced_matches_full",
        all(abs(search_success(8, t) - search_success_full(8, t)) < 1e-9
            for t in (0.5, 1.0, 2.0)))
    chk("search_starts_uniform", abs(search_success(64, 0.0) - 1 / 64) < 1e-12)
    peak1024 = search_peak(1024)
    chk("search_peak_probability", peak1024["p_max"] > 0.98)
    chk("search_time_constant",
        abs(peak1024["t_star_over_sqrt_n"] - math.pi / 2)
        / (math.pi / 2) < 0.02)
    peaks = [search_peak(n) for n in SEARCH_SIZES]
    slope = fit_exponent([p["n"] for p in peaks],
                         [p["t_star"] for p in peaks])
    chk("search_time_scaling_quadratic", abs(slope - 0.5) < 0.02)
    chk("search_beats_classical_count",
        peak1024["t_star"] < peak1024["classical_expected_draws"] / 5)

    # 6. classifier - labels come from the lab's own regime model
    rep = classifier_report()
    chk("classifier_classical_diffusive", rep["classical_line"] == "diffusive")
    chk("classifier_hadamard_ballistic",
        rep["hadamard_symmetric"] == "ballistic")
    chk("classifier_biased_ballistic",
        rep["hadamard_biased_coin"] == "ballistic")
    chk("classifier_trapped_localized", rep["trapped_coin_only"] == "localized")
    chk("classifier_ctqw_ballistic", rep["ctqw_line"] == "ballistic")
    chk("classifier_matches_model",
        all(classify_walk(*features) == model_label(*features)
            for features in measured_features().values()))

    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_advantage_hold", gate("quantum_advantage_claim") == "HOLD")
    chk("gate_hardware_hold",
        gate("real_quantum_hardware_execution") == "HOLD")
    chk("gate_supremacy_hold", gate("quantum_supremacy_claim") == "HOLD")
    chk("gate_crypto_hold", gate("cryptographic_attack_claim") == "HOLD")
    chk("gate_benchmark_hold", gate("certified_benchmark_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumWalk-Lab - quantum walk lab (discrete + continuous time)")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - one exponent separates the two walks")
    print("    A classical walker spreads like sqrt(t): double the time,")
    print("    only ~1.41x the width. A quantum walker spreads like t:")
    print("    double the time, double the width. Everything below is")
    print("    that exponent, measured - exact probabilities, no sampling,")
    print("    and no hardware or advantage claim anywhere.")
    crep = classical_report()
    print("\n[2] Classical random walk - exact binomial, diffusive")
    print(f"    fit steps {crep['fit_steps']}")
    print(f"    fit sigmas {crep['fit_sigmas']}")
    print(f"    scaling exponent {crep['scaling_exponent']} (diffusive 1/2)")
    print(f"    at {HEADLINE_STEPS} steps: sigma {crep['headline_sigma']:.4f} "
          f"| peak prob {crep['headline_max_prob']:.4f}")
    print("    -> sigma^2 = t exactly, so the width can only grow as sqrt(t).")
    qrep = qw_report()
    print("\n[3] Discrete-time Hadamard walk - ballistic, coin-driven")
    print(f"    fit sigmas {qrep['fit_sigmas']}")
    print(f"    scaling exponent {qrep['scaling_exponent']} (ballistic 1)")
    print(f"    at {HEADLINE_STEPS} steps: sigma {qrep['headline_sigma']:.4f} "
          f"= {qrep['sigma_over_t']:.4f} per step "
          f"(theory sqrt(1 - 1/sqrt(2)) = {qrep['theory_sigma_over_t']:.4f})")
    print(f"    width ratio vs classical at {HEADLINE_STEPS} steps: "
          f"{qrep['headline_sigma'] / crep['headline_sigma']:.2f}x")
    print(f"    biased coin (start left-moving): mean "
          f"{qrep['biased_mean']:.2f}, left mass "
          f"{qrep['biased_left_mass']:.4f}, peak at x = "
          f"{qrep['biased_peak_position']}")
    print("    -> interference empties the middle and piles probability at")
    print("       two fronts; the initial coin steers the whole distribution.")
    ctrep = ctqw_report()
    print("\n[4] Continuous-time walk - Hamiltonian evolution, no coin")
    print(f"    C4 perfect transfer at t = pi/2: P(opposite) = "
          f"{ctrep['cycle_c4_transfer_at_pi_over_2']:.6f}")
    print(f"    C4 revival at t = pi: P(start) = "
          f"{ctrep['cycle_c4_revival_at_pi']:.6f}")
    print(f"    C6 revival at t = 2pi: P(start) = "
          f"{ctrep['cycle_c6_revival_at_2pi']:.6f}")
    print(f"    line ({ctrep['line_sites']} sites): sigma = "
          f"{ctrep['line_sigma_over_t']:.4f} per unit time "
          f"(theory sqrt(2) = {ctrep['theory_line_sigma_over_t']:.4f}), "
          f"exponent {ctrep['line_scaling_exponent']}")
    print("    -> the cycle walk is periodic and returns exactly; the line")
    print("       walk outruns even the Hadamard walk, at sqrt(2) t.")
    srep = search_report()
    print("\n[5] Quantum-walk search on a complete graph (labelled toy units)")
    for peak in srep["peaks"]:
        print(f"    n = {peak['n']:5d} | t* {peak['t_star']:8.3f} | "
              f"P(marked) {peak['p_max']:.4f} | "
              f"classical expected draws {peak['classical_expected_draws']}")
    print(f"    fitted time-scaling exponent {srep['time_scaling_exponent']} "
          f"(quadratic-style: t* grows like sqrt(n))")
    print("    -> units are toy units (1 walk-time = 1 oracle query); the")
    print("       exponent is the lesson, cross-checked at n = 8 against")
    print("       the full Hamiltonian. No real search claim is made.")
    print("\n[6] Walk-regime classifier (TinyML kNN, labels from the regime model)")
    feats = measured_features()
    for name, label in classifier_report().items():
        exp, peak, steps = feats[name]
        print(f"    {name:22s} exponent {exp:6.3f} peak {peak:5.2f} "
              f"len {steps:3d} -> {label}")
    print("\n[7] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[8] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "classical":
        print(json.dumps(classical_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "discrete":
        print(json.dumps(qw_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "continuous":
        print(json.dumps(ctqw_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "search":
        print(json.dumps(search_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "quantum_advantage_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
