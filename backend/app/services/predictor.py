"""Load the trained model bundle and turn checklist answers into ranked conditions.

The bundle is exported by the ML repo (src/compare.py) and carries the model together
with the exact feature order, the danger-sign codes and the config hash it was trained
on, so the backend never has to guess how to build an input.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings

ANSWER_CODES = {"yes": 1, "no": 0}


class InvalidAnswers(ValueError):
    """The submitted answers do not match the model's question set."""


@dataclass
class Prediction:
    ranked: list[tuple[str, float]]          # (condition code, probability), best first
    explanation: list[tuple[str, str, float]]  # (question code, answer, weight)


class Predictor:
    def __init__(self, bundle: dict):
        self.model = bundle["model"]
        self.feature_order: list[str] = bundle["feature_order"]
        self.danger_signs: list[str] = bundle["danger_signs"]
        self.conditions: list[str] = bundle["conditions"]
        self.unanswered = int(bundle["unanswered_code"])
        self.config_hash: str = bundle["config_hash"]
        self.covariates = [f for f in self.feature_order if f in ("age_band", "sex")]
        self.symptoms = [f for f in self.feature_order if f not in self.covariates]

    # ------------------------------------------------------------------ #
    def validate(self, answers: dict[str, str]) -> None:
        given, expected = set(answers), set(self.symptoms)
        missing, extra = sorted(expected - given), sorted(given - expected)
        if missing or extra:
            parts = []
            if missing:
                parts.append(f"missing {len(missing)} question(s): {', '.join(missing)}")
            if extra:
                parts.append(f"unknown question code(s): {', '.join(extra)}")
            raise InvalidAnswers("; ".join(parts))

    def danger_signs_present(self, answers: dict[str, str]) -> list[str]:
        return [code for code in self.danger_signs if answers.get(code) == "yes"]

    def _frame(self, answers: dict[str, str], age_band: str, sex: str) -> pd.DataFrame:
        row = {code: ANSWER_CODES.get(answers[code], self.unanswered) for code in self.symptoms}
        row["age_band"], row["sex"] = age_band, sex
        return pd.DataFrame([row], columns=self.feature_order)

    # ------------------------------------------------------------------ #
    def predict(self, answers: dict[str, str], age_band: str, sex: str, top_k: int = 3) -> Prediction:
        self.validate(answers)
        frame = self._frame(answers, age_band, sex)
        probs = self.model.predict_proba(frame)[0]
        labels = list(self.model.classes_)
        order = np.argsort(probs)[::-1][:top_k]
        ranked = [(str(labels[i]), float(probs[i])) for i in order]
        explanation = self._explain(frame, answers, ranked[0][0])
        return Prediction(ranked=ranked, explanation=explanation)

    def _explain(self, frame: pd.DataFrame, answers: dict[str, str], top: str, n: int = 3):
        """The answers that pushed the top condition most, relative to the others.

        Linear models only: each active input contributes its coefficient for the top
        condition minus that input's mean coefficient across all conditions. Returns an
        empty list for models without coefficients rather than inventing a reason.
        """
        classifier = self.model.named_steps.get("classifier")
        encoder = self.model.named_steps.get("encode")
        if classifier is None or encoder is None or not hasattr(classifier, "coef_"):
            return []

        onehot = encoder.named_transformers_["answers"]
        columns = [(feature, value)
                   for feature, values in zip(onehot.feature_names_in_, onehot.categories_)
                   for value in values]
        encoded = encoder.transform(frame)
        if hasattr(encoded, "toarray"):  # the encoder may return a sparse matrix
            encoded = encoded.toarray()
        active = np.asarray(encoded)[0]

        coef = classifier.coef_
        k = list(classifier.classes_).index(top)
        relative = coef[k] - coef.mean(axis=0)

        scored = [
            (feature, answers[feature], float(relative[i]))
            for i, (feature, _value) in enumerate(columns)
            if active[i] and feature in self.symptoms
        ]
        scored.sort(key=lambda item: item[2], reverse=True)
        return [item for item in scored if item[2] > 0][:n]


@lru_cache
def get_predictor() -> Predictor:
    """Load once, on first use."""
    return Predictor(joblib.load(get_settings().model_path))
