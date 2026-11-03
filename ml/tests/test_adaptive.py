import json

import numpy as np

from src.adaptive import RESULTS, VALUES, entropy, next_question


def test_frequencies_are_probabilities():
    freq = json.loads((RESULTS / "question_frequencies.json").read_text(encoding="utf-8"))
    assert len(freq["questions"]) == 35
    for per_condition in freq["questions"].values():
        for dist in per_condition.values():
            assert abs(sum(dist.values()) - 1) < 1e-4
            assert min(dist.values()) > 0  # smoothed: no answer is ever impossible


def test_next_question_never_repeats_and_prefers_the_informative_one():
    # Question 0 separates the two conditions perfectly; question 1 says nothing.
    P = np.array([
        [[0.01, 0.01, 0.98], [0.01, 0.98, 0.01]],
        [[0.01, 0.495, 0.495], [0.01, 0.495, 0.495]],
    ])
    post = np.array([[0.5, 0.5]])
    assert next_question(post, P, np.array([[False, False]]))[0] == 0
    assert next_question(post, P, np.array([[True, False]]))[0] == 1


def test_entropy_is_highest_when_unsure():
    assert entropy(np.array([0.5, 0.5])) > entropy(np.array([0.9, 0.1])) > entropy(np.array([1.0, 0.0]))
    assert len(VALUES) == 3
