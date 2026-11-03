"""Adaptive questioning: which question to ask next, and when to stop.

After the three danger signs, the next question is the unasked one that most reduces the
expected uncertainty (entropy) about the condition. The uncertainty is computed from
per-condition answer frequencies in the training data (question_frequencies.json, exported
by the ML repo's src/adaptive.py). Questioning stops when the deployed model is confident
enough, when a danger sign is Yes, or when every question has been asked. The stop
threshold was chosen on validation in the ML repo and travels in the same file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.services.predictor import InvalidAnswers, Predictor

ANSWERS = ("unknown", "no", "yes")


@dataclass
class NextStep:
    done: bool
    reason: str | None          # "danger_sign", "confident" or "complete" when done
    next_question: str | None   # question code when not done
    asked: int
    top_probability: float


def _entropy(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1.0)
    return -(p * np.log(p)).sum(-1)


class Questioner:
    def __init__(self, freq: dict, predictor: Predictor):
        self.predictor = predictor
        self.stop_threshold = float(freq["stop_threshold"])
        self.conditions: list[str] = freq["conditions"]
        self.codes: list[str] = list(freq["questions"])
        if set(self.codes) != set(predictor.symptoms):
            raise ValueError("question_frequencies.json does not match the model's questions")
        # P[q, k, v]: probability of answer v to question q for condition k
        self.P = np.array([[[freq["questions"][q][k][a] for a in ANSWERS] for k in self.conditions]
                           for q in self.codes])

    def validate(self, answers: dict[str, str]) -> None:
        extra = sorted(set(answers) - set(self.codes))
        if extra:
            raise InvalidAnswers(f"unknown question code(s): {', '.join(extra)}")
        unchecked = [c for c in self.predictor.danger_signs if answers.get(c) not in ("yes", "no")]
        if unchecked:
            raise InvalidAnswers(f"answer the danger sign question(s) first, yes or no: {', '.join(unchecked)}")

    def next(self, answers: dict[str, str], age_band: str, sex: str) -> NextStep:
        self.validate(answers)
        asked = len(answers)
        full = {c: answers.get(c, "unknown") for c in self.codes}
        probs = self.predictor.probabilities(full, age_band, sex)
        top = float(max(probs.values()))
        if self.predictor.danger_signs_present(answers):
            return NextStep(True, "danger_sign", None, asked, top)
        if top >= self.stop_threshold:
            return NextStep(True, "confident", None, asked, top)
        remaining = [i for i, c in enumerate(self.codes) if c not in answers]
        if not remaining:
            return NextStep(True, "complete", None, asked, top)

        # Naive Bayes posterior over the conditions from the answers given so far
        logp = np.zeros(len(self.conditions))
        for c, a in answers.items():
            logp += np.log(self.P[self.codes.index(c), :, ANSWERS.index(a)])
        post = np.exp(logp - logp.max())
        post /= post.sum()
        # expected entropy after each remaining question
        Pr = self.P[remaining]                                  # q, k, v
        pv = np.einsum("k,qkv->qv", post, Pr)                   # P(answer v)
        after = post[None, :, None] * Pr
        after = after / after.sum(1, keepdims=True)             # posterior per answer
        expected = (pv * _entropy(np.swapaxes(after, 1, 2))).sum(-1)
        best = remaining[int(expected.argmin())]
        return NextStep(False, None, self.codes[best], asked, top)


@lru_cache
def get_questioner() -> Questioner:
    from app.services.predictor import get_predictor
    with open(get_settings().questions_path, encoding="utf-8") as f:
        return Questioner(json.load(f), get_predictor())
